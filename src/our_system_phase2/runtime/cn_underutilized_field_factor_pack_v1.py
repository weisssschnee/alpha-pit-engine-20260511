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

import pyarrow.parquet as pq

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_PANEL = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json")
DEFAULT_OUTPUT_DIR = Path("reports/cn_underutilized_field_factor_pack_v1_20260601")

PACK_ID = "cn_underutilized_field_factor_candidate_pack_v1_20260601"
PACK_VERSION = "cn-underutilized-field-factor-pack-v1-2026-06-01"

FLOW_FIELDS = {"amount", "volume", "turnover_ratio", "turnover_ratio_real", "seal_money", "seal_rate", "seal_circulation_rate"}
CAPACITY_FIELDS = {"float_share", "total_share", "final_float_market_cap", "final_total_market_cap", "actual_circulation_value"}
EVENT_FIELDS = {
    "limit_up_close_event",
    "limit_up_touch_not_close",
    "limit_up_open_not_close",
    "limit_up_close_not_open",
    "limit_up_close_count_t2",
    "limit_up_close_count_t3",
    "limit_up_close_count_t5",
    "limit_up_touch_not_close_count_t3",
    "limit_up_touch_not_close_count_t5",
    "limit_up_any_open_not_close_in_t3",
    "limit_up_any_close_not_open_in_t3",
    "open_board_record",
    "plate_score",
}


def _read_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


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


def _expr_fields(expression: str) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for token in re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or ""):
        field = token.lower()
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _rank(expr: str) -> str:
    return f"CSRank({expr})"


def _z(expr: str) -> str:
    return f"ZScore({expr})"


def _metadata(expression: str, lane: str, role: str) -> dict[str, Any]:
    fields = _expr_fields(expression)
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    return {
        "event_fields": "|".join([field for field in fields if field in EVENT_FIELDS or field.startswith("limit_")]),
        "flow_liquidity_fields": "|".join([field for field in fields if field in FLOW_FIELDS]),
        "capacity_fields": "|".join([field for field in fields if field in CAPACITY_FIELDS or "market_cap" in field]),
        "fundamental_fields": "|".join([field for field in fields if field.startswith("fund_")]),
        "price_return_fields": "|".join([field for field in fields if field in {"close", "daily_ret", "ret", "return_1d", "return_5d", "return_20d", "rps_rank", "rps_score"}]),
        "lag_rule": "all_daily_fields_lagged_by_signal_clock; PIT fundamentals notice-date-asof only",
        "tradability_rule": "susp/limit execution fields stay controls, not alpha signals",
        "leakage_flag": "requires_signal_clock_lags_no_same_day_execution_or_replay_labels",
        "search_memory_key": f"cn_underutilized_field_v1:{digest}",
    }


def _row(expression: str, *, lane: str, role: str, index: int) -> dict[str, Any]:
    fields = _expr_fields(expression)
    item = {
        "candidate_id": f"cn_underutil_v1_{lane}_{index:04d}",
        "expression": expression,
        "source_lane": "cn_underutilized_field_feature_layer",
        "source_generator": "cn_underutilized_field_factor_pack_v1",
        "diagnostic_role": role,
        "factor_lane": lane,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|frozen_selection_replay|global_cluster|source_attribution|OOS_regime_marginal",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "contains_new_event_adapter_field": any(field in EVENT_FIELDS or field.startswith("limit_") for field in fields),
        "contains_fundamental_field": any(field.startswith("fund_") for field in fields),
        "contains_flow_liquidity_field": any(field in FLOW_FIELDS for field in fields),
        "contains_capacity_field": any(field in CAPACITY_FIELDS or "market_cap" in field for field in fields),
        **_metadata(expression, lane, role),
    }
    return enrich_candidate_pool_priority(item)


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, role: str) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(_row(expression, lane=lane, role=role, index=len(rows) + 1))


def _flow_ratio_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    for field in ("volume", "amount", "turnover_ratio", "turnover_ratio_real"):
        if field not in cols:
            continue
        for fast, slow in ((2, 5), (2, 10), (3, 20), (5, 20), (10, 60)):
            fast_mean = f"Mean(${field},{fast})"
            slow_mean = f"Mean(${field},{slow})"
            _add(rows, seen, _rank(_safe_div(fast_mean, slow_mean)), lane="flow_ratio_curve", role="standalone_flow_activity")
            _add(rows, seen, _rank(f"Sub({_z(fast_mean)},{_z(slow_mean)})"), lane="flow_ratio_curve", role="standalone_flow_activity")
        for window in (3, 5, 10, 20):
            _add(rows, seen, _rank(f"Delta(${field},{window})"), lane="flow_impulse_curve", role="standalone_flow_activity")
            _add(rows, seen, _rank(f"Std(${field},{window})"), lane="flow_volatility_curve", role="standalone_flow_activity")


def _price_flow_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    price_fields = [field for field in ("daily_ret", "ret", "return_1d", "return_5d", "rps_rank", "rps_score") if field in cols]
    flow_fields = [field for field in ("amount", "volume", "turnover_ratio") if field in cols]
    for price in price_fields:
        for flow in flow_fields:
            for window in (3, 5, 10, 20):
                flow_z = _z(f"Mean(${flow},{window})")
                price_z = _z(f"Mean(${price},{window})")
                _add(rows, seen, _rank(f"Mul({flow_z},{price_z})"), lane="price_flow_confirmation", role="price_flow_interaction")
                _add(rows, seen, _rank(f"Mul({flow_z},Neg({price_z}))"), lane="price_flow_divergence", role="price_flow_interaction")
                _add(rows, seen, _rank(f"Corr(Delta(${flow},1),Delta(${price},1),{window})"), lane="price_flow_correlation", role="price_flow_interaction")


def _capacity_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    pairs = [
        ("amount", "final_float_market_cap"),
        ("amount", "final_total_market_cap"),
        ("volume", "float_share"),
        ("turnover_ratio", "final_float_market_cap"),
    ]
    for left, right in pairs:
        if {left, right}.issubset(cols):
            for window in (3, 5, 10, 20):
                left_mean = f"Mean(${left},{window})"
                right_mean = f"Mean(${right},{window})"
                _add(rows, seen, _rank(_safe_div(left_mean, right_mean)), lane="capacity_normalized_activity", role="capacity_adjusted_activity")
                _add(rows, seen, _rank(f"CSResidual({_z(left_mean)},{_z(right_mean)})"), lane="capacity_residual_activity", role="capacity_adjusted_activity")
    if {"daily_ret", "amount"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, _rank(_safe_div(f"Mean(Abs($daily_ret),{window})", f"Mean($amount,{window})")), lane="amihud_capacity_cost", role="liquidity_cost_proxy")


def _seal_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    seal_fields = [field for field in ("seal_money", "seal_rate", "seal_circulation_rate") if field in cols]
    event_fields = [field for field in sorted(EVENT_FIELDS) if field in cols]
    for seal in seal_fields:
        for window in (2, 3, 5, 10):
            _add(rows, seen, _rank(f"Mean(${seal},{window})"), lane="limit_seal_flow", role="limit_seal_flow_probe")
            _add(rows, seen, _rank(f"Delta(${seal},{window})"), lane="limit_seal_flow", role="limit_seal_flow_probe")
        if "amount" in cols:
            for window in (3, 5, 10):
                _add(rows, seen, _rank(_safe_div(f"Mean(${seal},{window})", f"Mean($amount,{window})")), lane="seal_to_amount", role="limit_seal_flow_probe")
    for event in event_fields:
        for seal in seal_fields:
            for window in (3, 5):
                _add(rows, seen, _rank(f"Mul({_z(f'Mean(${event},{window})')},{_z(f'Mean(${seal},{window})')})"), lane="event_x_seal_flow", role="event_flow_interaction")


def _fundamental_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    quality = [field for field in ("fund_cash_to_assets", "fund_current_ratio", "fund_netprofit_margin", "fund_ocf_to_assets", "fund_ocf_to_netprofit", "fund_research_to_income") if field in cols]
    holders = [field for field in ("fund_top1_holder_pct", "fund_top10_holder_pct", "fund_circulate_top10_holder_pct", "fund_float_share_ratio_cninfo") if field in cols]
    risk = [field for field in ("fund_debt_to_assets", "fund_goodwill_to_assets", "fund_inventory_to_assets") if field in cols]
    activity = [field for field in ("amount", "turnover_ratio", "volume") if field in cols]
    for fund in [*quality, *holders, *risk]:
        for flow in activity:
            for window in (5, 20):
                curve = _safe_div(f"Mean(${flow},5)", f"Mean(${flow},{window})")
                body = f"Mul({_z(f'${fund}')},{_z(curve)})"
                if fund in risk:
                    _add(rows, seen, f"Neg({_rank(body)})", lane="fundamental_x_activity", role="fundamental_activity_interaction")
                else:
                    _add(rows, seen, _rank(body), lane="fundamental_x_activity", role="fundamental_activity_interaction")
    if {"fund_total_operate_income", "final_float_market_cap"}.issubset(cols):
        _add(rows, seen, _rank(_safe_div("$fund_total_operate_income", "$final_float_market_cap")), lane="fundamental_capacity_value", role="fundamental_capacity_interaction")
    if {"fund_parent_netprofit", "final_float_market_cap"}.issubset(cols):
        _add(rows, seen, _rank(_safe_div("$fund_parent_netprofit", "$final_float_market_cap")), lane="fundamental_capacity_value", role="fundamental_capacity_interaction")


def _theme_rows(rows: list[dict[str, Any]], seen: set[str], cols: set[str]) -> None:
    if "plate_score" in cols:
        for flow in ("amount", "turnover_ratio", "volume"):
            if flow not in cols:
                continue
            for window in (3, 5, 10):
                _add(rows, seen, _rank(f"Mul({_z(f'Mean($plate_score,{window})')},{_z(f'Mean(${flow},{window})')})"), lane="theme_activity_proxy", role="theme_flow_interaction")
    for style in ("rps_rank", "rps_score"):
        if style in cols and "amount" in cols:
            for window in (5, 20):
                _add(rows, seen, _rank(f"Mul({_z(f'Mean(${style},{window})')},{_z(f'Mean($amount,{window})')})"), lane="style_activity_proxy", role="style_flow_interaction")


def build_pack(*, panel: Path, output_pack: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cols = _read_columns(panel)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    _flow_ratio_rows(rows, seen, cols)
    _price_flow_rows(rows, seen, cols)
    _capacity_rows(rows, seen, cols)
    _seal_rows(rows, seen, cols)
    _fundamental_rows(rows, seen, cols)
    _theme_rows(rows, seen, cols)

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    field_counts = Counter()
    for row in rows:
        for field in _expr_fields(str(row.get("expression") or "")):
            field_counts[field] += 1
    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "underutilized_field_factor_pack_ready_for_shared_pool_preflight_no_promotion",
        "source_panel": str(panel),
        "candidate_count": len(rows),
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "top_fields": dict(field_counts.most_common(30)),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_pack_generation",
            "tradability_raw_fields": "not promoted as alpha; remain execution controls",
            "sector_fields": "sector_code/sector are metadata; plate_score is numeric theme proxy",
            "field_lag": "all fields must pass evaluator signal-clock lag policy",
        },
        "candidate_rows": rows,
    }
    _write_json(output_pack, payload)
    _write_json(output_dir / "cn_underutilized_field_factor_pack_v1.json", payload)
    _write_csv(output_dir / "cn_underutilized_field_factor_pack_v1_candidates.csv", rows)
    _write_markdown(output_dir / "CN_UNDERUTILIZED_FIELD_FACTOR_PACK_V1_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Factor Pack V1",
        "",
        f"status: `{payload['status']}`",
        "",
        f"- candidate_count: {payload['candidate_count']}",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in payload["by_factor_lane"].items():
        lines.append(f"- {lane}: {count}")
    lines.extend(["", "## Top Fields", ""])
    for field, count in payload["top_fields"].items():
        lines.append(f"- {field}: {count}")
    lines.extend(["", "## Policy", ""])
    for key, value in payload["policy"].items():
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_pack(panel=args.panel, output_pack=args.output_pack, output_dir=args.output_dir)
    print(json.dumps({"status": payload["status"], "candidate_count": payload["candidate_count"], "by_factor_lane": payload["by_factor_lane"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
