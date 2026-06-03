"""Panelization preflight for Phase3AD new-data factor candidates.

This gate verifies that every formula alias referenced by the Phase3AD factor
pack can be materialized from a valid source table with the required PIT/event
keys. It intentionally does not build the full replay panel and does not run
backtests.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_phase3ad_new_data_factor_candidate_pack_v1_20260603.json")
DEFAULT_ALIAS_MAP = Path("reports/cn_phase3ad_new_data_factor_pack_v1_20260603/field_alias_map.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/cn_phase3ad_panelization_preflight_v1_20260603")

FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
FORBIDDEN_FIELD_RE = re.compile(r"^(next_|label_|future_|return_|forward_return|R3_liquidity_low)", re.IGNORECASE)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _fields(expression: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in FIELD_RE.findall(expression or ""):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _parquet_schema(path: Path) -> dict[str, Any]:
    info = {
        "path": str(path),
        "exists": path.exists(),
        "valid_parquet": False,
        "row_count": None,
        "column_count": None,
        "columns": [],
        "field_types": {},
        "error": "",
    }
    if not path.exists():
        info["error"] = "missing_file"
        return info
    try:
        parquet_file = pq.ParquetFile(path)
        schema = parquet_file.schema_arrow
        info.update(
            {
                "valid_parquet": True,
                "row_count": int(parquet_file.metadata.num_rows),
                "column_count": len(schema.names),
                "columns": list(schema.names),
                "field_types": {field.name: str(field.type) for field in schema},
            }
        )
    except Exception as exc:  # noqa: BLE001 - preflight should preserve exact error.
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def _required_keys(route: str, dataset: str) -> list[str]:
    if route == "announcement_pit_feature":
        return ["source_code6", "NOTICE_DATE", "REPORT_DATE"]
    if route == "timestamped_stock_event_feature":
        return ["date", "code", "up_limit_event_time"]
    if route == "lagged_stock_heat_context":
        return ["date", "code"]
    if route == "lagged_market_regime_context":
        return ["date"]
    return []


def _materialization_mode(route: str) -> str:
    if route == "announcement_pit_feature":
        return "latest_notice_or_update_lagged_daily_context"
    if route == "timestamped_stock_event_feature":
        return "event_cutoff_intraday_or_lag1_daily_context"
    if route == "lagged_stock_heat_context":
        return "stock_level_tplus1_heat_context"
    if route == "lagged_market_regime_context":
        return "market_level_tplus1_context_broadcast_to_stock"
    return "manual"


def build_preflight(factor_pack: Path, alias_map: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    pack = _read_json(factor_pack)
    candidates = [dict(row) for row in pack.get("candidate_rows") or []]
    aliases = _read_csv(alias_map)
    alias_by_panel = {str(row["panel_field"]): row for row in aliases}
    source_paths = sorted({str(row.get("materialized_path") or "") for row in aliases if row.get("materialized_path")})
    schema_by_path = {path: _parquet_schema(Path(path)) for path in source_paths}

    source_rows: list[dict[str, Any]] = []
    for path, info in schema_by_path.items():
        source_rows.append(
            {
                "path": path,
                "exists": info["exists"],
                "valid_parquet": info["valid_parquet"],
                "row_count": info["row_count"],
                "column_count": info["column_count"],
                "error": info["error"],
            }
        )

    alias_rows: list[dict[str, Any]] = []
    blocked_alias_rows: list[dict[str, Any]] = []
    duplicate_aliases = [alias for alias, count in Counter(str(row["panel_field"]) for row in aliases).items() if count > 1]
    for row in aliases:
        path = str(row.get("materialized_path") or "")
        info = schema_by_path.get(path, {})
        columns = set(info.get("columns") or [])
        raw_field = str(row.get("raw_field") or "")
        route = str(row.get("route") or "")
        required_keys = _required_keys(route, str(row.get("dataset") or ""))
        missing_keys = [key for key in required_keys if key not in columns]
        raw_field_exists = raw_field in columns
        forbidden = bool(FORBIDDEN_FIELD_RE.match(raw_field)) or bool(FORBIDDEN_FIELD_RE.match(str(row.get("panel_field") or "")))
        materializable = bool(info.get("valid_parquet")) and raw_field_exists and not missing_keys and not forbidden
        status = "materializable" if materializable else "blocked"
        reason = "ok"
        if not info.get("valid_parquet"):
            reason = "invalid_or_missing_source_parquet"
        elif not raw_field_exists:
            reason = "raw_field_missing_from_source_schema"
        elif missing_keys:
            reason = "missing_required_keys"
        elif forbidden:
            reason = "forbidden_future_or_label_field"
        out = {
            "panel_field": row.get("panel_field"),
            "source_group": row.get("source_group"),
            "dataset": row.get("dataset"),
            "raw_field": raw_field,
            "route": route,
            "field_family": row.get("field_family"),
            "data_type": row.get("data_type"),
            "materialized_path": path,
            "materialization_mode": _materialization_mode(route),
            "required_keys": "|".join(required_keys),
            "missing_keys": "|".join(missing_keys),
            "raw_field_exists": raw_field_exists,
            "materialization_status": status,
            "block_reason": reason,
            "pit_rule": row.get("pit_rule"),
        }
        alias_rows.append(out)
        if status != "materializable":
            blocked_alias_rows.append(out)

    materializable_aliases = {str(row["panel_field"]) for row in alias_rows if row["materialization_status"] == "materializable"}
    candidate_rows: list[dict[str, Any]] = []
    missing_input_rows: list[dict[str, Any]] = []
    forbidden_candidate_rows: list[dict[str, Any]] = []
    for row in candidates:
        expression = str(row.get("expression") or "")
        fields = _fields(expression)
        missing = [field for field in fields if field not in alias_by_panel]
        blocked = [field for field in fields if field in alias_by_panel and field not in materializable_aliases]
        forbidden = [field for field in fields if FORBIDDEN_FIELD_RE.match(field)]
        status = "materializable" if not missing and not blocked and not forbidden else "blocked"
        out = {
            "candidate_id": row.get("candidate_id"),
            "factor_lane": row.get("factor_lane"),
            "diagnostic_role": row.get("diagnostic_role"),
            "input_field_count": len(fields),
            "missing_input_fields": "|".join(missing),
            "blocked_input_fields": "|".join(blocked),
            "forbidden_input_fields": "|".join(forbidden),
            "materialization_status": status,
            "expression": expression,
        }
        candidate_rows.append(out)
        for field in missing:
            missing_input_rows.append({"candidate_id": row.get("candidate_id"), "missing_input_field": field, "expression": expression})
        if forbidden:
            forbidden_candidate_rows.append(out)

    alias_status_counts = Counter(row["materialization_status"] for row in alias_rows)
    candidate_status_counts = Counter(row["materialization_status"] for row in candidate_rows)
    candidate_lane_counts = Counter(row["factor_lane"] for row in candidate_rows if row["materialization_status"] == "materializable")
    alias_route_counts = Counter(row["route"] for row in alias_rows if row["materialization_status"] == "materializable")

    decision = (
        "PASS_PHASE3AD_PANELIZATION_PREFLIGHT"
        if not blocked_alias_rows and not missing_input_rows and not forbidden_candidate_rows and not duplicate_aliases
        else "HOLD_PHASE3AD_PANELIZATION_PREFLIGHT"
    )
    report = {
        "version": "cn-phase3ad-panelization-preflight-v1-2026-06-03",
        "decision": decision,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "schema_key_alias_preflight_no_panel_write_no_replay",
        "factor_pack": str(factor_pack),
        "alias_map": str(alias_map),
        "output_root": str(output_root),
        "candidate_count": len(candidates),
        "alias_count": len(aliases),
        "source_count": len(source_paths),
        "materializable_alias_count": int(alias_status_counts.get("materializable", 0)),
        "blocked_alias_count": int(alias_status_counts.get("blocked", 0)),
        "materializable_candidate_count": int(candidate_status_counts.get("materializable", 0)),
        "blocked_candidate_count": int(candidate_status_counts.get("blocked", 0)),
        "duplicate_alias_count": len(duplicate_aliases),
        "missing_input_field_count": len(missing_input_rows),
        "forbidden_candidate_count": len(forbidden_candidate_rows),
        "alias_status_counts": dict(sorted(alias_status_counts.items())),
        "candidate_status_counts": dict(sorted(candidate_status_counts.items())),
        "materializable_alias_by_route": dict(sorted(alias_route_counts.items())),
        "materializable_candidate_by_lane": dict(sorted(candidate_lane_counts.items())),
        "policy": {
            "fundamental": "materialization requires source_code6, REPORT_DATE, NOTICE_DATE and conservative availability lag",
            "timestamped_event": "same-day use requires up_limit_event_time cutoff; otherwise lag1 context",
            "daily_sentiment": "T+1 by default",
            "blocked": "no replay until all selected candidate inputs are materializable",
        },
        "next": (
            "build_phase3ad_selected_sidecars_then_selector_only_smoke"
            if decision.startswith("PASS_")
            else "fix_blocked_aliases_or_reduce_candidate_pack_before_selector"
        ),
        "schema_version": "cn-phase3ad-panelization-preflight-v1",
    }

    write_json_artifact(output_root / "phase3ad_panelization_preflight.json", report)
    _write_csv(output_root / "source_schema_audit.csv", source_rows)
    _write_csv(output_root / "alias_materialization_status.csv", alias_rows)
    _write_csv(output_root / "blocked_aliases.csv", blocked_alias_rows)
    _write_csv(output_root / "candidate_materialization_status.csv", candidate_rows)
    _write_csv(output_root / "missing_input_fields.csv", missing_input_rows)
    _write_csv(output_root / "forbidden_candidate_fields.csv", forbidden_candidate_rows)
    _write_markdown(output_root / "CN_PHASE3AD_PANELIZATION_PREFLIGHT_V1_2026-06-03.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Phase3AD Panelization Preflight v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- candidate_count: `{report['candidate_count']}`",
        f"- alias_count: `{report['alias_count']}`",
        f"- source_count: `{report['source_count']}`",
        f"- materializable_alias_count: `{report['materializable_alias_count']}`",
        f"- blocked_alias_count: `{report['blocked_alias_count']}`",
        f"- materializable_candidate_count: `{report['materializable_candidate_count']}`",
        f"- blocked_candidate_count: `{report['blocked_candidate_count']}`",
        f"- duplicate_alias_count: `{report['duplicate_alias_count']}`",
        f"- missing_input_field_count: `{report['missing_input_field_count']}`",
        f"- forbidden_candidate_count: `{report['forbidden_candidate_count']}`",
        "",
        "## Materializable Alias Routes",
        "",
    ]
    for route, count in report["materializable_alias_by_route"].items():
        lines.append(f"- `{route}`: `{count}`")
    lines.extend(["", "## Materializable Candidate Lanes", ""])
    for lane, count in report["materializable_candidate_by_lane"].items():
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This preflight only checks schemas, aliases, required keys, and forbidden fields. It does not write a replay panel and does not validate alpha performance.",
            "",
            "## Next",
            "",
            f"`{report['next']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--alias-map", type=Path, default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    report = build_preflight(args.factor_pack, args.alias_map, args.output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
