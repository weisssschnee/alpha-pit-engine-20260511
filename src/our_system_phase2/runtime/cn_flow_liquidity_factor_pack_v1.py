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
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json")
DEFAULT_OUTPUT_DIR = Path("reports/cn_flow_liquidity_factor_pack_v1_20260601")

PACK_ID = "cn_flow_liquidity_factor_candidate_pack_v1_20260601"
PACK_VERSION = "cn-flow-liquidity-factor-pack-v1-2026-06-01"


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


def _columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


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


def _metadata(expression: str, lane: str, role: str) -> dict[str, Any]:
    fields = _expr_fields(expression)
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    return {
        "event_fields": "|".join([field for field in fields if field.startswith("limit_") or field in {"open_board_record", "plate_score"}]),
        "flow_liquidity_fields": "|".join([field for field in fields if field in {"amount", "volume", "turnover_ratio", "turnover_ratio_real", "seal_money", "seal_rate", "seal_circulation_rate"}]),
        "capacity_fields": "|".join([field for field in fields if "market_cap" in field or field in {"float_share", "total_share", "actual_circulation_value"}]),
        "fundamental_fields": "|".join([field for field in fields if field.startswith("fund_")]),
        "lag_rule": "all_daily_fields_lagged_by_signal_clock; event_vendor_fields_after_close_lagged_one_session",
        "tradability_rule": "daily_after_open_conservative; limit/susp masks remain execution filters",
        "leakage_flag": "requires_signal_clock_lags; same_day_event_fields_not_usable_without lag",
        "search_memory_key": f"cn_flow_liquidity_factor_v1:{digest}",
    }


def _row(expression: str, *, lane: str, role: str, index: int) -> dict[str, Any]:
    item = {
        "candidate_id": f"cn_flow_liq_v1_{lane}_{index:04d}",
        "expression": expression,
        "source_lane": "cn_flow_liquidity_feature_layer",
        "source_generator": "cn_flow_liquidity_factor_pack_v1",
        "diagnostic_role": role,
        "factor_lane": lane,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|flow_capacity_role_check|frozen_selection_replay|global_cluster|OOS_regime_marginal",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "contains_new_event_adapter_field": any(field.startswith("limit_") or field in {"open_board_record", "plate_score"} for field in _expr_fields(expression)),
        "contains_fundamental_field": any(field.startswith("fund_") for field in _expr_fields(expression)),
        "contains_flow_liquidity_field": any(field in {"amount", "volume", "turnover_ratio", "turnover_ratio_real", "seal_money", "seal_rate", "seal_circulation_rate"} for field in _expr_fields(expression)),
        "contains_capacity_field": any("market_cap" in field or field in {"float_share", "total_share", "actual_circulation_value"} for field in _expr_fields(expression)),
        **_metadata(expression, lane, role),
    }
    return enrich_candidate_pool_priority(item)


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, role: str) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(_row(expression, lane=lane, role=role, index=len(rows) + 1))


def build_pack(*, panel: Path, output_pack: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cols = _columns(panel)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Pure flow shock and relative-activity effects. These are intentionally
    # separate from event interactions so the selector can assign explicit credit.
    for field in ("volume", "amount", "turnover_ratio", "turnover_ratio_real"):
        if field not in cols:
            continue
        for fast, slow in ((2, 10), (3, 20), (5, 20), (10, 60)):
            _add(rows, seen, f"CSRank({_safe_div(f'Mean(${field},{fast})', f'Mean(${field},{slow})')})", lane="flow_relative_activity", role="flow_liquidity_alpha_candidate")
            _add(rows, seen, f"CSRank(Sub(ZScore(Mean(${field},{fast})),ZScore(Mean(${field},{slow}))))", lane="flow_relative_activity", role="flow_liquidity_alpha_candidate")
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank(Delta(${field},{window}))", lane="flow_impulse", role="flow_liquidity_alpha_candidate")
            _add(rows, seen, f"CSRank(Std(${field},{window}))", lane="flow_volatility", role="flow_liquidity_alpha_candidate")

    # Price-volume divergence: high trading pressure with weak price response,
    # and exhaustion / confirmation alternatives.
    if {"amount", "close"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank(Mul(ZScore(Delta($amount,{window})),Neg(ZScore(Delta($close,{window})))))", lane="price_flow_divergence", role="flow_price_interaction")
            _add(rows, seen, f"CSRank(Corr(Delta($amount,1),Delta($close,1),{window}))", lane="price_flow_confirmation", role="flow_price_interaction")
    if {"volume", "close"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank(Mul(ZScore(Delta($volume,{window})),Neg(ZScore(Delta($close,{window})))))", lane="price_flow_divergence", role="flow_price_interaction")
            _add(rows, seen, f"CSRank(Corr(Delta($volume,1),Delta($close,1),{window}))", lane="price_flow_confirmation", role="flow_price_interaction")

    # Capacity normalized liquidity. These candidates test whether apparent
    # flow alpha is just size/capacity exposure.
    if {"amount", "final_float_market_cap"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank({_safe_div(f'Mean($amount,{window})', f'Mean($final_float_market_cap,{window})')})", lane="capacity_normalized_flow", role="capacity_adjusted_flow")
            _add(rows, seen, f"CSRank(CSResidual(ZScore(Mean($amount,{window})),ZScore(Mean($final_float_market_cap,{window}))))", lane="capacity_residual_flow", role="capacity_adjusted_flow")
    if {"volume", "float_share"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank({_safe_div(f'Mean($volume,{window})', f'Mean($float_share,{window})')})", lane="capacity_normalized_flow", role="capacity_adjusted_flow")
    if {"daily_ret", "amount"}.issubset(cols):
        for window in (3, 5, 10, 20):
            _add(rows, seen, f"CSRank({_safe_div(f'Mean(Abs($daily_ret),{window})', f'Mean($amount,{window})')})", lane="amihud_illiquidity", role="liquidity_cost_proxy")

    # Limit seal / event flow. Keep it in a separate lane: prior selector did
    # not select these, so this is explicit coverage rather than promotion.
    event_fields = [
        field for field in (
            "limit_up_close_event",
            "limit_up_touch_not_close",
            "limit_up_open_not_close",
            "limit_up_close_not_open",
            "limit_up_close_count_t3",
            "limit_up_close_count_t5",
            "break_board_after_streak_ge_2",
            "break_board_after_streak_ge_3",
            "open_board_record",
            "plate_score",
        )
        if field in cols
    ]
    flow_fields = [field for field in ("amount", "turnover_ratio", "turnover_ratio_real", "seal_money", "seal_rate", "seal_circulation_rate") if field in cols]
    for event in event_fields:
        for flow in flow_fields:
            for window in (3, 5, 10):
                _add(rows, seen, f"CSRank(Mul(ZScore(Mean(${event},{window})),ZScore(Mean(${flow},{window}))))", lane="event_x_flow_liquidity", role="event_flow_interaction")

    # Fundamental quality interacted with flow pressure. This is intentionally
    # small and conservative because the fundamental panel is sparse/top200 smoke.
    fundamental_fields = [field for field in ("fund_ocf_to_assets", "fund_cash_to_assets", "fund_debt_to_assets", "fund_current_ratio", "fund_netprofit_margin") if field in cols]
    for fund in fundamental_fields:
        for flow in ("amount", "turnover_ratio"):
            if flow not in cols:
                continue
            for window in (10, 20, 60):
                flow_curve = _safe_div("Mean($" + flow + ",5)", f"Mean(${flow},{window})")
                if "debt" in fund:
                    expr = f"Neg(CSRank(Mul(ZScore(${fund}),ZScore({flow_curve}))))"
                else:
                    expr = f"CSRank(Mul(ZScore(${fund}),ZScore({flow_curve})))"
                _add(rows, seen, expr, lane="fundamental_x_flow", role="fundamental_flow_interaction")

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "flow_liquidity_factor_pack_ready_for_shared_pool_preflight_no_promotion",
        "source_panel": str(panel),
        "candidate_count": len(rows),
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "not_allowed_from_pack_generation",
            "flow_fields": "must be lagged by evaluator signal clock",
            "capacity_fields": "role_separated_as_alpha_candidate_or_filter_proxy",
            "limit_seal_fields": "diagnostic until tradability and lag checks pass",
        },
        "candidate_rows": rows,
    }
    _write_json(output_pack, payload)
    _write_json(output_dir / "cn_flow_liquidity_factor_pack_v1.json", payload)
    _write_csv(output_dir / "cn_flow_liquidity_factor_pack_v1_candidates.csv", rows)
    _write_markdown(output_dir / "CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Flow Liquidity Factor Pack V1",
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
