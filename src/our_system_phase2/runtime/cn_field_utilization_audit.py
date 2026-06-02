from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

from our_system_phase2.services.event_derived_features import BASE_EVENT_DERIVED_FEATURE_SPECS
from our_system_phase2.services.field_encoder import FIELD_TYPE_MAP, canonical_field_name


DEFAULT_PANEL = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet")
DEFAULT_FACTOR_PACK = Path("runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json")
DEFAULT_SHARED_POOL = Path("runtime/cn_research_factor_pack_v2_phase3aa_preflight_20260531/shared_candidate_pool_event_fund_enriched.json")
DEFAULT_SELECTION_INPUTS = Path("runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector/aa/phase3_strict_selection_inputs.json")
DEFAULT_STRICT_ROWS = Path("runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa/phase3_strict_rows.json")
DEFAULT_OUTPUT_DIR = Path("reports/cn_field_utilization_audit_20260531")


FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fields(expression: str | None) -> list[str]:
    if not expression:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for token in FIELD_RE.findall(expression):
        field = token.lower()
        if field in seen:
            continue
        seen.add(field)
        out.append(field)
    return out


def _expr(row: dict[str, Any]) -> str:
    return str(row.get("expression") or row.get("canonical_rank_validation_expression") or row.get("parent_expression") or "")


def _iter_factor_pack_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("candidate_rows") or [] if _expr(row)]


def _iter_shared_pool_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("candidate_pool") or [] if _expr(row)]


def _iter_selected_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("selected") or [] if _expr(row)]


def _iter_strict_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return [dict(row) for row in payload.get("strict_rows") or [] if _expr(row)]


def _family(field: str) -> str:
    name = field.lower()
    if name in {"open", "high", "low", "close", "vwap", "daily_ret", "overnight", "rt_change_pct", "ret", "return_1d", "return_5d", "return_20d"}:
        return "price_return"
    if name in {"volume", "amount", "turnover_rate", "turnover_ratio", "turnover_ratio_real", "money_flow"}:
        return "flow_liquidity"
    if name in {"seal_money", "seal_rate", "seal_circulation_rate"}:
        return "limit_seal_flow"
    if name in {"susp", "is_limit_up", "is_limit_down"}:
        return "tradability_raw"
    if name.startswith("limit_") or name in {
        "open_board_record",
        "high_board_rank",
        "market_high_board",
        "is_market_high_board",
        "break_board_after_streak_ge_1",
        "actual_circulation_value",
    } or name.startswith("break_board_after_streak_ge_"):
        return "limit_event_morphology"
    if name in {"plate_score", "sector", "sector_code", "sector_source", "sector_confidence"}:
        return "theme_sector"
    if name.startswith("fund_"):
        if any(token in name for token in ("debt", "goodwill", "inventory")):
            return "fundamental_risk"
        if any(token in name for token in ("holder", "float_share", "shares")):
            return "fundamental_holder_share"
        if any(token in name for token in ("assets", "income", "netprofit", "netcash")):
            return "fundamental_scale_income_cash"
        return "fundamental_quality"
    if any(token in name for token in ("market_cap", "float_share", "total_share", "circulation_value")):
        return "capacity_size"
    if name in {"code", "symbol", "market", "date", "instrument_type"}:
        return "metadata_id"
    return "other_unclassified"


def _source_lane(row: dict[str, Any]) -> str:
    return str(
        row.get("source_lane")
        or row.get("phase3_source_lane")
        or row.get("source_generator")
        or row.get("factor_lane")
        or "unknown"
    )


def _factor_lane(row: dict[str, Any]) -> str:
    return str(row.get("factor_lane") or row.get("source_generator") or row.get("phase3_source_lane") or "unknown")


def _count_field_usage(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "lanes": Counter(), "examples": []})
    for row in rows:
        expression = _expr(row)
        for field in _fields(expression):
            item = usage[field]
            item["count"] += 1
            item["lanes"][_factor_lane(row)] += 1
            if len(item["examples"]) < 3:
                item["examples"].append(expression)
    return usage


def _source_counts_for_field(rows: Iterable[dict[str, Any]], field: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        if field in _fields(_expr(row)):
            counts[_source_lane(row)] += 1
    return counts


def _is_replay_pass(row: dict[str, Any]) -> bool:
    return bool(row.get("portfolio_replay_pass") or row.get("strict_pass_proxy") or row.get("cost_survives"))


def _panel_columns(panel: Path) -> list[str]:
    return list(pq.ParquetFile(panel).schema_arrow.names)


def build_audit(
    *,
    panel: Path,
    factor_pack: Path,
    shared_pool: Path,
    selection_inputs: Path,
    strict_rows: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    columns = _panel_columns(panel)
    pack_rows = _iter_factor_pack_rows(factor_pack)
    pool_rows = _iter_shared_pool_rows(shared_pool)
    selected_rows = _iter_selected_rows(selection_inputs)
    strict = _iter_strict_rows(strict_rows)

    pack_usage = _count_field_usage(pack_rows)
    pool_usage = _count_field_usage(pool_rows)
    selected_usage = _count_field_usage(selected_rows)
    strict_usage = _count_field_usage(strict)
    replay_pass_rows = [row for row in strict if _is_replay_pass(row)]
    replay_pass_usage = _count_field_usage(replay_pass_rows)

    rows: list[dict[str, Any]] = []
    for field in sorted(columns):
        family = _family(field)
        canonical = canonical_field_name(field)
        encoder_known = canonical is not None
        event_spec_known = field in BASE_EVENT_DERIVED_FEATURE_SPECS
        rows.append(
            {
                "field": field,
                "family": family,
                "in_panel": True,
                "encoder_known": encoder_known,
                "canonical_field": canonical or "",
                "field_encoder_type": FIELD_TYPE_MAP.get(canonical or field, ""),
                "event_spec_known": event_spec_known,
                "factor_pack_count": pack_usage.get(field, {}).get("count", 0),
                "shared_pool_count": pool_usage.get(field, {}).get("count", 0),
                "selected_count": selected_usage.get(field, {}).get("count", 0),
                "strict_count": strict_usage.get(field, {}).get("count", 0),
                "replay_pass_count": replay_pass_usage.get(field, {}).get("count", 0),
                "selected_source_lanes": dict(_source_counts_for_field(selected_rows, field)),
                "strict_source_lanes": dict(_source_counts_for_field(strict, field)),
                "factor_pack_lanes": dict(pack_usage.get(field, {}).get("lanes", Counter())),
                "example_expression": (pack_usage.get(field, {}).get("examples") or pool_usage.get(field, {}).get("examples") or [""])[0],
            }
        )

    by_family: list[dict[str, Any]] = []
    for family in sorted({row["family"] for row in rows}):
        members = [row for row in rows if row["family"] == family]
        by_family.append(
            {
                "family": family,
                "panel_fields": len(members),
                "encoder_known_fields": sum(1 for row in members if row["encoder_known"]),
                "factor_pack_fields_used": sum(1 for row in members if row["factor_pack_count"]),
                "shared_pool_fields_used": sum(1 for row in members if row["shared_pool_count"]),
                "selected_fields_used": sum(1 for row in members if row["selected_count"]),
                "strict_fields_used": sum(1 for row in members if row["strict_count"]),
                "replay_pass_fields_used": sum(1 for row in members if row["replay_pass_count"]),
                "factor_pack_expr_count": sum(int(row["factor_pack_count"]) for row in members),
                "shared_pool_expr_count": sum(int(row["shared_pool_count"]) for row in members),
                "selected_expr_count": sum(int(row["selected_count"]) for row in members),
                "strict_expr_count": sum(int(row["strict_count"]) for row in members),
                "replay_pass_expr_count": sum(int(row["replay_pass_count"]) for row in members),
            }
        )

    gaps = []
    for row in rows:
        if row["family"] in {"metadata_id", "tradability_raw"}:
            continue
        if not row["encoder_known"] and row["family"] not in {"other_unclassified", "theme_sector"}:
            gaps.append({"field": row["field"], "family": row["family"], "gap": "panel_field_not_encoded"})
        if row["shared_pool_count"] and not row["selected_count"] and row["family"] not in {"metadata_id"}:
            gaps.append({"field": row["field"], "family": row["family"], "gap": "in_pool_not_selected_current_gate"})
        if row["factor_pack_count"] == 0 and row["family"] in {"flow_liquidity", "capacity_size", "price_return", "theme_sector"}:
            gaps.append({"field": row["field"], "family": row["family"], "gap": "no_dedicated_factor_pack_usage"})

    explicit_missing = []
    expected_derived = [
        "volume_ratio_5_20",
        "amount_ratio_5_20",
        "turnover_ratio_z20",
        "amount_to_float_mcap",
        "volume_to_float_share",
        "amihud_absret_over_amount",
        "seal_money_to_amount",
        "seal_rate_z20",
        "price_volume_divergence_5",
        "sector_relative_amount_ratio",
        "fundamental_quality_x_amount_ratio",
    ]
    for name in expected_derived:
        if name not in columns:
            explicit_missing.append(name)

    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "FIELD_UTILIZATION_AUDIT_FINDS_MATERIAL_FLOW_AND_DERIVED_FIELD_GAPS",
        "panel_path": str(panel),
        "factor_pack_path": str(factor_pack),
        "shared_pool_path": str(shared_pool),
        "selection_inputs_path": str(selection_inputs),
        "strict_rows_path": str(strict_rows),
        "panel_column_count": len(columns),
        "factor_pack_candidate_count": len(pack_rows),
        "shared_pool_candidate_count": len(pool_rows),
        "selected_count": len(selected_rows),
        "strict_audited_count": len(strict),
        "replay_pass_row_count": len(replay_pass_rows),
        "by_family": by_family,
        "field_rows": rows,
        "material_gaps": gaps,
        "missing_expected_derived_fields": explicit_missing,
        "critical_findings": [
            "flow/liquidity fields exist in panel and mature generators, but v2 factor pack does not provide a dedicated standalone flow-liquidity lane",
            "turnover_ratio/seal flow fields appear in event_x_flow but were not selected in the current 64 queue",
            "raw volume appears through mature generators, not the v2 research factor pack",
            "volume/amount ratio and price-volume divergence fields are not materialized as named derived fields",
            "several raw panel columns are metadata or tradability controls and should not be promoted as alpha fields without role separation",
        ],
        "next_action": "build_cn_flow_liquidity_factor_pack_v1_before_claiming_field_coverage_complete",
    }
    _write_json(output_dir / "cn_field_utilization_audit.json", payload)
    _write_csv(output_dir / "cn_field_utilization_by_field.csv", rows)
    _write_csv(output_dir / "cn_field_utilization_by_family.csv", by_family)
    _write_csv(output_dir / "cn_field_utilization_gaps.csv", gaps)
    _write_markdown(output_dir / "CN_FIELD_UTILIZATION_AUDIT_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Field Utilization Audit",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
        f"- panel_column_count: {payload['panel_column_count']}",
        f"- factor_pack_candidate_count: {payload['factor_pack_candidate_count']}",
        f"- shared_pool_candidate_count: {payload['shared_pool_candidate_count']}",
        f"- selected_count: {payload['selected_count']}",
        f"- strict_audited_count: {payload['strict_audited_count']}",
        f"- replay_pass_row_count: {payload['replay_pass_row_count']}",
        "",
        "## Family Utilization",
        "",
        "| family | panel fields | factor-pack fields | pool fields | selected fields | strict fields | replay-pass fields | selected expr |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["by_family"]:
        lines.append(
            "| {family} | {panel_fields} | {factor_pack_fields_used} | {shared_pool_fields_used} | {selected_fields_used} | {strict_fields_used} | {replay_pass_fields_used} | {selected_expr_count} |".format(
                **row
            )
        )
    lines.extend(["", "## Critical Findings", ""])
    for item in payload["critical_findings"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Missing Expected Derived Fields", ""])
    for item in payload["missing_expected_derived_fields"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Next Action", "", f"`{payload['next_action']}`"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--factor-pack", type=Path, default=DEFAULT_FACTOR_PACK)
    parser.add_argument("--shared-pool", type=Path, default=DEFAULT_SHARED_POOL)
    parser.add_argument("--selection-inputs", type=Path, default=DEFAULT_SELECTION_INPUTS)
    parser.add_argument("--strict-rows", type=Path, default=DEFAULT_STRICT_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_audit(
        panel=args.panel,
        factor_pack=args.factor_pack,
        shared_pool=args.shared_pool,
        selection_inputs=args.selection_inputs,
        strict_rows=args.strict_rows,
        output_dir=args.output_dir,
    )
    print(json.dumps({
        "decision": payload["decision"],
        "panel_column_count": payload["panel_column_count"],
        "selected_count": payload["selected_count"],
        "critical_findings": payload["critical_findings"],
        "missing_expected_derived_fields": payload["missing_expected_derived_fields"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
