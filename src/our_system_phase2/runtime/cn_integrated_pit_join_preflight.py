"""Preflight the PIT join required for the CN integrated factor pack.

This module is read-only. It does not build a replay panel. It verifies whether
the frozen selected expressions can become replay-executable after joining the
minute and non-minute PIT panels to the mature replay panel.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq


DEFAULT_SELECTION_INPUTS = Path(
    "runtime/cn_integrated_factor_pack_company_selector_20260602/phase3_strict_selection_inputs.json"
)
DEFAULT_BASE_SCHEMA = Path(
    "runtime/field_registry/cn_integrated_replay_base_schema_20260602/company_phase2_stock_tdx_schema.json"
)
DEFAULT_MINUTE_PANEL = Path(
    "runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1"
)
DEFAULT_NONMINUTE_PANEL = Path(
    "runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_integrated_pit_join_preflight_20260602")
DEFAULT_REPORT_PATH = Path("reports/CN_INTEGRATED_PIT_JOIN_PREFLIGHT_2026-06-02.md")

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
BLOCKED_PREFIXES = ("label_", "meta_")
DERIVABLE_FIELDS = {
    "vwap": {
        "source": "derived_from_base",
        "requires": ["amount", "volume"],
        "formula": "amount / volume",
        "pit_policy": "same-row daily replay fields only; guard volume > 0",
    }
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fields(expression: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _parquet_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.parquet") if path.is_file())


def _schema_union(root: Path) -> tuple[set[str], list[dict[str, Any]]]:
    fields: set[str] = set()
    rows: list[dict[str, Any]] = []
    for path in _parquet_files(root):
        pf = pq.ParquetFile(path)
        names = list(pf.schema.names)
        fields.update(names)
        rows.append(
            {
                "relative_path": str(path.relative_to(root)),
                "row_count": pf.metadata.num_rows,
                "field_count": len(names),
                "has_ctx_aug": any(name.startswith("ctx_aug_") for name in names),
                "has_ctx_hfq": any(name.startswith("ctx_hfq_") for name in names),
            }
        )
    return fields, rows


def _date_stats(root: Path, date_col: str) -> dict[str, Any]:
    mins: list[Any] = []
    maxs: list[Any] = []
    rows = 0
    samples: list[str] = []
    file_stats: list[dict[str, Any]] = []
    for path in _parquet_files(root):
        pf = pq.ParquetFile(path)
        table = pf.read(columns=[date_col, "code"])
        min_value = pc.min(table[date_col]).as_py()
        max_value = pc.max(table[date_col]).as_py()
        rows += table.num_rows
        mins.append(min_value)
        maxs.append(max_value)
        if len(samples) < 10:
            samples.extend(str(value) for value in table["code"].to_pylist()[: 10 - len(samples)])
        file_stats.append(
            {
                "relative_path": str(path.relative_to(root)),
                "row_count": table.num_rows,
                "date_min": str(min_value)[:10],
                "date_max": str(max_value)[:10],
            }
        )
    return {
        "row_count": rows,
        "date_min": str(min(mins))[:10] if mins else "",
        "date_max": str(max(maxs))[:10] if maxs else "",
        "sample_codes": samples,
        "files": file_stats,
    }


def _base_schema(path: Path, dataset_path: Path | None) -> dict[str, Any]:
    if dataset_path and dataset_path.exists():
        pf = pq.ParquetFile(dataset_path)
        return {
            "dataset_path": str(dataset_path),
            "row_count": pf.metadata.num_rows,
            "field_count": len(pf.schema.names),
            "fields": list(pf.schema.names),
            "date_min": "",
            "date_max": "",
            "code_format": "unknown",
            "source": "dataset_schema",
        }
    payload = _read_json(path)
    payload["source"] = str(path)
    return payload


def _field_source(field: str, *, base: set[str], minute: set[str], nonminute: set[str]) -> tuple[str, list[str]]:
    sources: list[str] = []
    if field in base:
        sources.append("base_replay")
    if field in minute:
        sources.append("minute_panel")
    if field in nonminute:
        sources.append("nonminute_panel")
    if field in DERIVABLE_FIELDS and all(required in base for required in DERIVABLE_FIELDS[field]["requires"]):
        sources.append("derivable")
    if field.startswith(BLOCKED_PREFIXES):
        return "blocked_forbidden_field", sources
    if sources:
        return "available_after_join", sources
    return "missing_after_join", sources


def _join_policy() -> dict[str, Any]:
    return {
        "base_code_format": "tdx_market_prefix_lowercase, e.g. sh600000/sz000001/bj430017",
        "integrated_panel_code_format": "six_digit.exchange_suffix, e.g. 600000.SH/000001.SZ/430017.BJ",
        "required_normalizer": {
            "shXXXXXX": "XXXXXX.SH",
            "szXXXXXX": "XXXXXX.SZ",
            "bjXXXXXX": "XXXXXX.BJ",
        },
        "join_keys": {
            "minute": ["normalized_code", "date = exec_date"],
            "nonminute": ["normalized_code", "date"],
        },
    }


def run_preflight(
    *,
    selection_inputs: Path,
    base_schema_path: Path,
    base_dataset_path: Path | None,
    minute_panel: Path,
    nonminute_panel: Path,
    output_root: Path,
    report_path: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    selected = list((_read_json(selection_inputs).get("selected") or []))
    base_payload = _base_schema(base_schema_path, base_dataset_path)
    base_fields = set(base_payload.get("fields") or [])
    minute_fields, minute_schema_rows = _schema_union(minute_panel)
    nonminute_fields, nonminute_schema_rows = _schema_union(nonminute_panel)
    minute_dates = _date_stats(minute_panel, "exec_date")
    nonminute_dates = _date_stats(nonminute_panel, "date")

    field_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    missing_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()
    lane_status: Counter[tuple[str, str]] = Counter()
    field_examples: defaultdict[str, list[str]] = defaultdict(list)

    for index, row in enumerate(selected):
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        missing: list[str] = []
        blocked: list[str] = []
        sources_per_field: list[str] = []
        for field in fields:
            status, sources = _field_source(field, base=base_fields, minute=minute_fields, nonminute=nonminute_fields)
            source_label = "+".join(sources) if sources else status
            source_counter[source_label] += 1
            sources_per_field.append(f"{field}:{source_label}")
            if status == "missing_after_join":
                missing.append(field)
                missing_counter[field] += 1
            if status == "blocked_forbidden_field":
                blocked.append(field)
            if len(field_examples[field]) < 5:
                field_examples[field].append(str(row.get("candidate_id") or ""))
            field_rows.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "source_lane": row.get("source_lane") or "legacy_unknown",
                    "field": field,
                    "status": status,
                    "sources": "|".join(sources),
                    "derivation": DERIVABLE_FIELDS.get(field, {}).get("formula", ""),
                }
            )
        status = "join_executable" if not missing and not blocked else "blocked"
        lane = str(row.get("source_lane") or "legacy_unknown")
        lane_status[(lane, status)] += 1
        selected_rows.append(
            {
                "selection_index": index,
                "candidate_id": row.get("candidate_id"),
                "source_lane": lane,
                "source_generator": row.get("source_generator") or row.get("generator"),
                "status": status,
                "field_count": len(fields),
                "fields": "|".join(fields),
                "field_sources": "|".join(sources_per_field),
                "missing_after_join": "|".join(missing),
                "blocked_fields": "|".join(blocked),
                "expression": expression,
            }
        )

    blocked_rows = [row for row in selected_rows if row["status"] == "blocked"]
    integrated_rows = [row for row in selected_rows if row["source_lane"] == "cn_integrated_feature_layer"]
    integrated_blocked = [row for row in integrated_rows if row["status"] == "blocked"]
    coverage_warning = (
        bool(base_payload.get("date_max"))
        and (minute_dates["date_max"] < str(base_payload.get("date_max")) or nonminute_dates["date_max"] < str(base_payload.get("date_max")))
    )
    decision = "PASS_JOIN_PREFLIGHT_READY_TO_BUILD_PANEL" if not blocked_rows else "HOLD_JOIN_PREFLIGHT_MISSING_FIELDS"
    if coverage_warning and decision.startswith("PASS"):
        decision = "PASS_JOIN_PREFLIGHT_WITH_DATE_COVERAGE_WARNING"

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "selection_inputs": str(selection_inputs),
        "selected_count": len(selected_rows),
        "selected_join_executable_count": len(selected_rows) - len(blocked_rows),
        "selected_blocked_count": len(blocked_rows),
        "integrated_selected_count": len(integrated_rows),
        "integrated_join_executable_count": len(integrated_rows) - len(integrated_blocked),
        "integrated_blocked_count": len(integrated_blocked),
        "base_schema": {
            "path": str(base_schema_path),
            "dataset_path": base_payload.get("dataset_path"),
            "row_count": base_payload.get("row_count"),
            "field_count": len(base_fields),
            "date_min": base_payload.get("date_min", ""),
            "date_max": base_payload.get("date_max", ""),
        },
        "minute_panel": {
            "path": str(minute_panel),
            "field_union_count": len(minute_fields),
            **minute_dates,
        },
        "nonminute_panel": {
            "path": str(nonminute_panel),
            "field_union_count": len(nonminute_fields),
            **nonminute_dates,
        },
        "schema_file_counts": {
            "minute_files": len(minute_schema_rows),
            "nonminute_files": len(nonminute_schema_rows),
        },
        "join_policy": _join_policy(),
        "date_coverage_warning": coverage_warning,
        "by_lane_status": [
            {"source_lane": lane, "status": status, "count": count}
            for (lane, status), count in sorted(lane_status.items())
        ],
        "field_source_counts": [
            {"source": source, "count": count}
            for source, count in sorted(source_counter.items(), key=lambda item: (-item[1], item[0]))
        ],
        "missing_field_counts": [
            {"field": field, "count": count, "candidate_examples": field_examples[field]}
            for field, count in missing_counter.most_common()
        ],
        "derivable_fields": DERIVABLE_FIELDS,
        "blocking_items": _blocking_items(coverage_warning=coverage_warning, blocked_rows=blocked_rows),
        "schema_version": "cn-integrated-pit-join-preflight-v1",
    }

    _write_json(output_root / "pit_join_preflight.json", report)
    _write_csv(output_root / "selected_join_field_sources.csv", selected_rows)
    _write_csv(output_root / "field_source_matrix.csv", field_rows)
    _write_csv(output_root / "minute_schema_files.csv", minute_schema_rows)
    _write_csv(output_root / "nonminute_schema_files.csv", nonminute_schema_rows)
    _write_markdown(report_path, report)
    return report


def _blocking_items(*, coverage_warning: bool, blocked_rows: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    if blocked_rows:
        items.append("At least one selected expression still references fields unavailable from base/minute/nonminute/derivable sources.")
    if coverage_warning:
        items.append("Minute/nonminute panel date coverage ends before the base replay panel; replay after panel max date will have missing integrated features.")
    items.append("Build step must normalize code format before joining: sh/sz/bj prefix to .SH/.SZ/.BJ suffix.")
    items.append("Build step must derive vwap from base amount/volume with a zero-volume guard.")
    return items


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CN Integrated PIT Join Preflight",
        "",
        f"- decision: `{report['decision']}`",
        f"- selected_count: `{report['selected_count']}`",
        f"- selected_join_executable_count: `{report['selected_join_executable_count']}`",
        f"- selected_blocked_count: `{report['selected_blocked_count']}`",
        f"- integrated_selected_count: `{report['integrated_selected_count']}`",
        f"- integrated_join_executable_count: `{report['integrated_join_executable_count']}`",
        f"- integrated_blocked_count: `{report['integrated_blocked_count']}`",
        "",
        "## Panel Coverage",
        "",
        f"- base date range: `{report['base_schema']['date_min']}` to `{report['base_schema']['date_max']}`",
        f"- minute date range: `{report['minute_panel']['date_min']}` to `{report['minute_panel']['date_max']}`",
        f"- nonminute date range: `{report['nonminute_panel']['date_min']}` to `{report['nonminute_panel']['date_max']}`",
        f"- date_coverage_warning: `{report['date_coverage_warning']}`",
        "",
        "## By Lane",
    ]
    for row in report["by_lane_status"]:
        lines.append(f"- {row['source_lane']} / {row['status']}: `{row['count']}`")
    lines.extend(["", "## Field Sources"])
    for row in report["field_source_counts"][:40]:
        lines.append(f"- {row['source']}: `{row['count']}`")
    lines.extend(["", "## Missing Fields"])
    if report["missing_field_counts"]:
        for row in report["missing_field_counts"][:40]:
            lines.append(f"- {row['field']}: `{row['count']}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Required Join Policy", ""])
    lines.append("- normalize base code from `sh/sz/bj` prefix format to `.SH/.SZ/.BJ` suffix format before joining.")
    lines.append("- join minute panel on `normalized_code` and `date = exec_date`.")
    lines.append("- join nonminute context panel on `normalized_code` and `date`.")
    lines.append("- derive `vwap = amount / volume` in the joined replay panel with a zero-volume guard.")
    lines.extend(["", "## Blocking Items"])
    for item in report["blocking_items"]:
        lines.append(f"- {item}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-inputs", type=Path, default=DEFAULT_SELECTION_INPUTS)
    parser.add_argument("--base-schema", type=Path, default=DEFAULT_BASE_SCHEMA)
    parser.add_argument("--base-dataset-path", type=Path, default=None)
    parser.add_argument("--minute-panel", type=Path, default=DEFAULT_MINUTE_PANEL)
    parser.add_argument("--nonminute-panel", type=Path, default=DEFAULT_NONMINUTE_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    report = run_preflight(
        selection_inputs=args.selection_inputs,
        base_schema_path=args.base_schema,
        base_dataset_path=args.base_dataset_path,
        minute_panel=args.minute_panel,
        nonminute_panel=args.nonminute_panel,
        output_root=args.output_root,
        report_path=args.report_path,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
