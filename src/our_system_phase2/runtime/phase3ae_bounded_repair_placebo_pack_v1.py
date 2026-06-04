from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_SELECTION_INPUTS = Path(
    "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3_strict_selection_inputs.json"
)
DEFAULT_JOINED_PANEL = Path(
    "runtime/phase3ae_bounded_repair_selector_only_v1_20260604/phase3ae_bounded_repair_joined_panel_v1.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3ae_bounded_repair_placebo_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ae_bounded_repair_placebo_v1_20260604")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/phase3ae_bounded_repair_placebo_factor_pack_v1_20260604.json")

PACK_ID = "phase3ae_bounded_repair_placebo_factor_pack_v1_20260604"
PACK_VERSION = "phase3ae-bounded-repair-placebo-pack-v1-2026-06-04"
DECISION = "PASS_AE2_PLACEBO_PACK_READY_FOR_REPLAY_CANARY_COMPARISON"
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for field in FIELD_RE.findall(expression or ""):
        if field not in seen:
            seen.add(field)
            out.append(field)
    return out


def _selected_ae2_rows(selection_inputs: Path) -> list[dict[str, Any]]:
    selected = [dict(row) for row in (_read_json(selection_inputs).get("selected") or [])]
    return [
        row
        for row in selected
        if str(row.get("factor_pack_id") or "").startswith("phase3ae_bounded_repair_factor_pack_v1_20260604")
    ]


def _safe_name(field: str, prefix: str) -> str:
    digest = hashlib.sha1(field.encode("utf-8")).hexdigest()[:8]
    clean = re.sub(r"[^A-Za-z0-9_]", "_", field)
    return f"{prefix}_{clean}_{digest}"


def _replace_fields(expression: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        field = match.group(1)
        return f"${mapping.get(field, field)}"

    return FIELD_RE.sub(repl, expression or "")


def _shuffle_within_date(series: pd.Series, dates: pd.Series, *, seed: int) -> pd.Series:
    frame = pd.DataFrame({"date": dates, "value": series})
    out = pd.Series(index=series.index, dtype="float64")
    for i, (_, idx) in enumerate(frame.groupby("date", sort=False).groups.items()):
        values = frame.loc[idx, "value"]
        shuffled = values.sample(frac=1.0, random_state=seed + i).to_numpy()
        out.loc[idx] = shuffled
    return out


def _field_stats(frame: pd.DataFrame, fields: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = max(1, len(frame))
    for field in fields:
        value = pd.to_numeric(frame[field], errors="coerce") if field in frame.columns else pd.Series(dtype="float64")
        nonnull = int(value.notna().sum())
        by_date = frame.assign(_nonnull=value.notna()).groupby("date")["_nonnull"].mean() if field in frame.columns else pd.Series(dtype="float64")
        rows.append(
            {
                "field": field,
                "coverage": round(nonnull / total, 6),
                "nonnull_rows": nonnull,
                "total_rows": total,
                "unique_nonnull": int(value.nunique(dropna=True)) if nonnull else 0,
                "mean": float(value.mean()) if nonnull else None,
                "std": float(value.std()) if nonnull else None,
                "date_coverage_min": float(by_date.min()) if not by_date.empty else None,
                "date_coverage_median": float(by_date.median()) if not by_date.empty else None,
                "date_coverage_max": float(by_date.max()) if not by_date.empty else None,
            }
        )
    return rows


def _candidate(row: dict[str, Any], *, expression: str, placebo_type: str, index: int, mapping: dict[str, str]) -> dict[str, Any]:
    item = dict(row)
    item["candidate_id"] = f"phase3ae_placebo_{placebo_type}_{index:05d}_{row.get('candidate_id')}"
    item["expression"] = expression
    item["expression_key"] = expression_memory_key(expression)
    item["skeleton_key"] = skeleton_memory_key(expression)
    item["factor_pack_id"] = PACK_ID
    item["factor_pack_version"] = PACK_VERSION
    item["source_lane"] = "phase3ae_bounded_repair_placebo_layer"
    item["source_generator"] = "phase3ae_bounded_repair_placebo_pack_v1"
    item["placebo_type"] = placebo_type
    item["true_candidate_id"] = row.get("candidate_id")
    item["true_expression"] = row.get("expression")
    item["field_mapping"] = "|".join(f"{k}->{v}" for k, v in sorted(mapping.items()))
    item["official_book_eligible"] = False
    item["promotion_gate"] = "placebo_comparison_only_no_promotion"
    item["required_audits"] = "paired_true_vs_placebo_replay_canary|source_attribution|new_vs_149_recluster"
    item["leakage_flag"] = "placebo_fields_derived_from_pre_replay_feature_panel_only"
    item["search_memory_key"] = expression_memory_key(expression)
    return enrich_candidate_pool_priority(item)


def build_placebo_pack(
    *,
    selection_inputs: Path,
    joined_panel: Path,
    output_root: Path,
    report_root: Path,
    output_pack: Path,
    seed: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    selected = _selected_ae2_rows(selection_inputs)
    fields = sorted({field for row in selected for field in _fields(str(row.get("expression") or ""))})
    if not selected:
        raise RuntimeError("No AE2 selected rows found.")
    if not fields:
        raise RuntimeError("No AE2 input fields found.")

    read_cols = ["date", "code", "join_code", *fields]
    frame = pd.read_parquet(joined_panel, columns=read_cols)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    coverage_map = {field: _safe_name(field, "plcov") for field in fields}
    shuffled_map = {field: _safe_name(field, "plshuf") for field in fields}

    sidecar = frame[["date", "code", "join_code"]].copy()
    for field in fields:
        value = pd.to_numeric(frame[field], errors="coerce")
        sidecar[coverage_map[field]] = value.notna().astype("float32")
        sidecar[shuffled_map[field]] = _shuffle_within_date(value, frame["date"], seed=seed).astype("float32")

    sidecar_path = output_root / "phase3ae_bounded_repair_placebo_sidecar_v1.parquet"
    sidecar.to_parquet(sidecar_path, index=False)

    candidate_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for row in selected:
        expression = str(row.get("expression") or "")
        input_fields = _fields(expression)
        cov_mapping = {field: coverage_map[field] for field in input_fields}
        shuf_mapping = {field: shuffled_map[field] for field in input_fields}
        cov_expr = _replace_fields(expression, cov_mapping)
        shuf_expr = _replace_fields(expression, shuf_mapping)
        cov_row = _candidate(row, expression=cov_expr, placebo_type="coverage_mask", index=len(candidate_rows) + 1, mapping=cov_mapping)
        shuf_row = _candidate(row, expression=shuf_expr, placebo_type="shuffled_value", index=len(candidate_rows) + 2, mapping=shuf_mapping)
        candidate_rows.extend([cov_row, shuf_row])
        pair_rows.append(
            {
                "true_candidate_id": row.get("candidate_id"),
                "true_expression": expression,
                "coverage_candidate_id": cov_row["candidate_id"],
                "coverage_expression": cov_expr,
                "shuffled_candidate_id": shuf_row["candidate_id"],
                "shuffled_expression": shuf_expr,
                "input_fields": "|".join(input_fields),
            }
        )

    field_stats = _field_stats(frame, fields)
    pack = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": DECISION,
        "status": "ready_for_paired_replay_canary_comparison",
        "selection_inputs": str(selection_inputs),
        "joined_panel": str(joined_panel),
        "placebo_sidecar": str(sidecar_path),
        "selected_ae2_count": len(selected),
        "input_field_count": len(fields),
        "candidate_count": len(candidate_rows),
        "by_placebo_type": dict(Counter(str(row.get("placebo_type")) for row in candidate_rows)),
        "policy": {
            "coverage_mask_interpretation": "tests whether field availability/event membership alone explains behavior; pass/fail is diagnostic, not automatic rejection",
            "shuffled_value_interpretation": "tests whether numeric field values add information beyond date-level coverage/distribution",
            "promotion": "placebo pack cannot promote alpha; only paired replay comparison can inform AE2 canary",
        },
        "candidate_rows": candidate_rows,
    }
    _write_json(output_pack, pack)
    _write_csv(report_root / "phase3ae_placebo_candidate_pairs.csv", pair_rows)
    _write_csv(report_root / "phase3ae_placebo_field_stats.csv", field_stats)
    _write_csv(report_root / "phase3ae_placebo_candidates.csv", candidate_rows)
    report = {key: value for key, value in pack.items() if key != "candidate_rows"}
    report["outputs"] = {
        "placebo_factor_pack": str(output_pack),
        "placebo_sidecar": str(sidecar_path),
        "candidate_pairs": str(report_root / "phase3ae_placebo_candidate_pairs.csv"),
        "field_stats": str(report_root / "phase3ae_placebo_field_stats.csv"),
        "candidates_csv": str(report_root / "phase3ae_placebo_candidates.csv"),
        "report_json": str(report_root / "phase3ae_bounded_repair_placebo_pack_report.json"),
        "markdown": str(report_root / "PHASE3AE_BOUNDED_REPAIR_PLACEBO_PACK_V1_2026-06-04.md"),
    }
    _write_json(report_root / "phase3ae_bounded_repair_placebo_pack_report.json", report)
    _write_markdown(report_root / "PHASE3AE_BOUNDED_REPAIR_PLACEBO_PACK_V1_2026-06-04.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3AE Bounded Repair Placebo Pack V1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- selected AE2 true candidates: `{report['selected_ae2_count']}`",
        f"- input fields: `{report['input_field_count']}`",
        f"- placebo candidates: `{report['candidate_count']}`",
        "",
        "## Interpretation",
        "",
        "Coverage-mask candidates test event/coverage membership. A strong coverage placebo is not automatically bad; it means the edge may come from field availability or event membership rather than numeric magnitude.",
        "",
        "Shuffled-value candidates preserve coverage and date-level distribution while breaking stock-field alignment. If shuffled candidates match true candidates, numeric field values are not adding much beyond coverage/distribution.",
        "",
        "This pack is for paired replay canary comparison only. It is not an alpha proof.",
        "",
        "## Outputs",
        "",
    ]
    for key, value in report["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-inputs", type=Path, default=DEFAULT_SELECTION_INPUTS)
    parser.add_argument("--joined-panel", type=Path, default=DEFAULT_JOINED_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--seed", type=int, default=4604)
    args = parser.parse_args()
    report = build_placebo_pack(
        selection_inputs=args.selection_inputs,
        joined_panel=args.joined_panel,
        output_root=args.output_root,
        report_root=args.report_root,
        output_pack=args.output_pack,
        seed=int(args.seed),
    )
    print(json.dumps({key: report[key] for key in ["decision", "selected_ae2_count", "input_field_count", "candidate_count", "by_placebo_type"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
