"""Build Phase3AD candidate formulas from newly integrated CN data assets.

This is a candidate-pack generator. It consumes the vetted field registry from
``cn-new-data-asset-integration-v1`` and emits bounded, auditable formula
templates for later panelization, selector preflight, and locked replay.

It does not run replay and does not promote any candidate.
"""

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

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_SEED_AXES = Path("runtime/field_registry/cn_new_data_asset_integration_v1_20260603/next_factor_pack_seed_axes.csv")
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_phase3ad_new_data_factor_candidate_pack_v1_20260603.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_new_data_factor_pack_v1_20260603")

PACK_ID = "cn_phase3ad_new_data_factor_candidate_pack_v1_20260603"
PACK_VERSION = "cn-phase3ad-new-data-factor-pack-v1-2026-06-03"


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_name(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()
    text = re.sub(r"_+", "_", text)
    return text or "field"


def _panel_prefix(row: dict[str, Any]) -> str:
    dataset = str(row.get("dataset") or "")
    source_group = str(row.get("source_group") or "")
    if source_group == "fundamental_pit_silver":
        if "balance" in dataset:
            return "ctx_fulla_bs"
        if "profit" in dataset:
            return "ctx_fulla_ps"
        if "cashflow" in dataset:
            return "ctx_fulla_cf"
        return "ctx_fulla"
    if dataset == "uplimit_stock_event_day":
        return "evt_uplimit"
    if dataset == "open_sentiment_daily":
        return "ctx_sent"
    if dataset == "sentiment_hot_daily":
        return "ctx_sent_hot"
    if dataset == "ths_hot_stock_day":
        return "ctx_ths_hot"
    return f"ctx_{_clean_name(dataset)}"


def _panel_field(row: dict[str, Any]) -> str:
    return f"{_panel_prefix(row)}_{_clean_name(str(row.get('field') or 'field'))}"


def _alias_rows(seed_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in seed_rows:
        key = (str(row.get("source_group")), str(row.get("dataset")), str(row.get("field")))
        if key in seen:
            continue
        seen.add(key)
        aliases.append(
            {
                "source_group": row.get("source_group"),
                "dataset": row.get("dataset"),
                "raw_field": row.get("field"),
                "panel_field": _panel_field(row),
                "data_type": row.get("data_type"),
                "field_family": row.get("field_family"),
                "route": row.get("route"),
                "selector_allowed": row.get("selector_allowed"),
                "pit_rule": row.get("pit_rule"),
                "allowed_transforms": row.get("allowed_transforms"),
                "materialized_path": row.get("materialized_path"),
            }
        )
    return aliases


def _f(field: str) -> str:
    return f"${field}"


def _rank(expr: str) -> str:
    return f"CSRank({expr})"


def _z(expr: str) -> str:
    return f"ZScore({expr})"


def _neg(expr: str) -> str:
    return f"Neg({expr})"


def _add(left: str, right: str) -> str:
    return f"Add({left},{right})"


def _sub(left: str, right: str) -> str:
    return f"Sub({left},{right})"


def _mul(left: str, right: str) -> str:
    return f"Mul({left},{right})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _field(alias: dict[str, dict[str, Any]], dataset: str, raw_field: str) -> str | None:
    row = alias.get(f"{dataset}:{raw_field}")
    return str(row["panel_field"]) if row else None


def _present(alias: dict[str, dict[str, Any]], dataset: str, raw_field: str) -> bool:
    return f"{dataset}:{raw_field}" in alias


def _row(
    expression: str,
    *,
    lane: str,
    role: str,
    fields: list[str],
    alias_by_panel_field: dict[str, dict[str, Any]],
    index: int,
    coverage_priority_delta: float = 0.0,
) -> dict[str, Any]:
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    families = sorted({str(alias_by_panel_field.get(field, {}).get("field_family") or "unknown") for field in fields})
    routes = sorted({str(alias_by_panel_field.get(field, {}).get("route") or "unknown") for field in fields})
    sources = sorted({str(alias_by_panel_field.get(field, {}).get("source_group") or "unknown") for field in fields})
    datasets = sorted({str(alias_by_panel_field.get(field, {}).get("dataset") or "unknown") for field in fields})
    item = {
        "candidate_id": f"phase3ad_newdata_{lane}_{index:05d}",
        "expression": expression,
        "source_lane": "cn_phase3ad_new_data_feature_layer",
        "source_generator": "cn_phase3ad_new_data_factor_pack_v1",
        "factor_lane": lane,
        "diagnostic_role": role,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "panelization_preflight|field_lag_check|selector_only_smoke|frozen_replay_smoke|x0_r3_marginal_audit",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "search_memory_key": f"phase3ad_new_data:{digest}",
        "input_fields": "|".join(fields),
        "input_families": "|".join(families),
        "input_routes": "|".join(routes),
        "input_sources": "|".join(sources),
        "input_datasets": "|".join(datasets),
        "contains_fundamental_field": any(source == "fundamental_pit_silver" for source in sources),
        "contains_limit_event_field": any("limit_event" in family for family in families),
        "contains_sentiment_field": any(route in {"lagged_market_regime_context", "lagged_stock_heat_context"} for route in routes),
        "contains_event_cutoff_field": any(route == "timestamped_stock_event_feature" for route in routes),
        "contains_capacity_field": any(family == "capacity_size" for family in families),
        "contains_flow_liquidity_field": any(family == "flow_liquidity" for family in families),
        "coverage_priority_delta": coverage_priority_delta,
        "leakage_flag": "no_next_fields;fundamental_notice_lag_required;timestamped_event_cutoff_or_lag1;daily_sentiment_tplus1",
    }
    if item["contains_event_cutoff_field"]:
        item["contains_new_event_adapter_field"] = True
    return enrich_candidate_pool_priority(item)


def _add_candidate(
    rows: list[dict[str, Any]],
    seen: set[str],
    expression: str,
    *,
    lane: str,
    role: str,
    fields: list[str],
    alias_by_panel_field: dict[str, dict[str, Any]],
    coverage_priority_delta: float = 0.0,
) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        _row(
            expression,
            lane=lane,
            role=role,
            fields=fields,
            alias_by_panel_field=alias_by_panel_field,
            index=len(rows) + 1,
            coverage_priority_delta=coverage_priority_delta,
        )
    )


def _ratio_candidate(
    rows: list[dict[str, Any]],
    seen: set[str],
    *,
    numerator: str | None,
    denominator: str | None,
    lane: str,
    role: str,
    direction: str,
    alias_by_panel_field: dict[str, dict[str, Any]],
) -> None:
    if not numerator or not denominator:
        return
    expr = _safe_div(_f(numerator), _f(denominator))
    if direction == "negative":
        expr = _neg(expr)
    _add_candidate(rows, seen, _rank(expr), lane=lane, role=role, fields=[numerator, denominator], alias_by_panel_field=alias_by_panel_field)


def build_pack(seed_axes: Path, output_pack: Path, report_root: Path) -> dict[str, Any]:
    seed_rows = _read_csv(seed_axes)
    aliases = _alias_rows(seed_rows)
    alias = {f"{row['dataset']}:{row['raw_field']}": row for row in aliases}
    alias_by_panel = {str(row["panel_field"]): row for row in aliases}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Fundamental PIT ratios: balance risk, liquidity, profitability, expense intensity.
    bs = "fundamental_balance_long"
    ps = "fundamental_profit_long"
    total_assets = _field(alias, bs, "TOTAL_ASSETS") or _field(alias, bs, "ASSET_BALANCE")
    total_liab = _field(alias, bs, "TOTAL_LIABILITIES") or _field(alias, bs, "LIAB_BALANCE")
    total_equity = _field(alias, bs, "TOTAL_EQUITY") or _field(alias, bs, "EQUITY_BALANCE")
    current_assets = _field(alias, bs, "TOTAL_CURRENT_ASSETS") or _field(alias, bs, "CURRENT_ASSET_BALANCE")
    current_liab = _field(alias, bs, "TOTAL_CURRENT_LIAB") or _field(alias, bs, "CURRENT_LIAB_BALANCE")
    cash = _field(alias, bs, "MONETARYFUNDS")
    goodwill = _field(alias, bs, "GOODWILL")
    inventory = _field(alias, bs, "INVENTORY")
    fixed_asset = _field(alias, bs, "FIXED_ASSET")
    intangible = _field(alias, bs, "INTANGIBLE_ASSET")
    operate_income = _field(alias, ps, "OPERATE_INCOME") or _field(alias, ps, "TOTAL_OPERATE_INCOME")
    total_operate_income = _field(alias, ps, "TOTAL_OPERATE_INCOME") or operate_income
    netprofit = _field(alias, ps, "NETPROFIT")
    parent_netprofit = _field(alias, ps, "PARENT_NETPROFIT")
    operate_profit = _field(alias, ps, "OPERATE_PROFIT")
    total_profit = _field(alias, ps, "TOTAL_PROFIT")
    operate_cost = _field(alias, ps, "OPERATE_COST")
    sale_expense = _field(alias, ps, "SALE_EXPENSE")
    manage_expense = _field(alias, ps, "MANAGE_EXPENSE")
    research_expense = _field(alias, ps, "RESEARCH_EXPENSE") or _field(alias, ps, "ME_RESEARCH_EXPENSE")
    finance_expense = _field(alias, ps, "FINANCE_EXPENSE")

    for numerator, denominator, lane, role, direction in [
        (total_liab, total_assets, "fundamental_debt_asset_inverse", "balance_risk_inverse", "negative"),
        (cash, total_assets, "fundamental_cash_asset_quality", "balance_quality", "positive"),
        (goodwill, total_assets, "fundamental_goodwill_asset_inverse", "balance_risk_inverse", "negative"),
        (inventory, total_assets, "fundamental_inventory_asset_inverse", "balance_risk_inverse", "negative"),
        (current_assets, current_liab, "fundamental_current_ratio", "balance_liquidity_quality", "positive"),
        (total_equity, total_assets, "fundamental_equity_asset_quality", "balance_quality", "positive"),
        (fixed_asset, total_assets, "fundamental_fixed_asset_intensity", "asset_structure", "positive"),
        (intangible, total_assets, "fundamental_intangible_asset_inverse", "balance_risk_inverse", "negative"),
        (netprofit, total_operate_income, "fundamental_netprofit_margin", "profit_quality", "positive"),
        (parent_netprofit, total_operate_income, "fundamental_parent_netprofit_margin", "profit_quality", "positive"),
        (operate_profit, total_operate_income, "fundamental_operate_profit_margin", "profit_quality", "positive"),
        (total_profit, total_operate_income, "fundamental_total_profit_margin", "profit_quality", "positive"),
        (operate_cost, total_operate_income, "fundamental_cost_intensity_inverse", "expense_control", "negative"),
        (sale_expense, total_operate_income, "fundamental_sales_expense_intensity_inverse", "expense_control", "negative"),
        (manage_expense, total_operate_income, "fundamental_manage_expense_intensity_inverse", "expense_control", "negative"),
        (research_expense, total_operate_income, "fundamental_research_intensity", "quality_growth", "positive"),
        (finance_expense, total_operate_income, "fundamental_finance_expense_inverse", "expense_control", "negative"),
    ]:
        _ratio_candidate(rows, seen, numerator=numerator, denominator=denominator, lane=lane, role=role, direction=direction, alias_by_panel_field=alias_by_panel)

    # YOY direct ranks where available.
    for dataset, raw_field, direction, role in [
        (ps, "TOTAL_OPERATE_INCOME_YOY", "positive", "growth_quality"),
        (ps, "OPERATE_PROFIT_YOY", "positive", "growth_quality"),
        (ps, "NETPROFIT_YOY", "positive", "growth_quality"),
        (ps, "PARENT_NETPROFIT_YOY", "positive", "growth_quality"),
        (bs, "TOTAL_ASSETS_YOY", "negative", "balance_expansion_risk"),
        (bs, "TOTAL_LIABILITIES_YOY", "negative", "leverage_growth_risk"),
        (bs, "GOODWILL_YOY", "negative", "goodwill_growth_risk"),
        (bs, "INVENTORY_YOY", "negative", "inventory_growth_risk"),
    ]:
        field = _field(alias, dataset, raw_field)
        if not field:
            continue
        expr = _f(field)
        if direction == "negative":
            expr = _neg(expr)
        _add_candidate(rows, seen, _rank(expr), lane=f"fundamental_yoy_{_clean_name(raw_field)}", role=role, fields=[field], alias_by_panel_field=alias_by_panel)

    # Stock-level timestamped limit event features.
    event_dataset = "uplimit_stock_event_day"
    evt_amount = _field(alias, event_dataset, "amount")
    auction_buy = _field(alias, event_dataset, "auction_buy")
    auction_offer = _field(alias, event_dataset, "auction_offer")
    auction_money = _field(alias, event_dataset, "auction_money")
    auction_turnover = _field(alias, event_dataset, "auction_turnover")
    premax = _field(alias, event_dataset, "auction_pre1max_ratio")
    fd_close = _field(alias, event_dataset, "fd_close")
    fd_max = _field(alias, event_dataset, "fd_max")
    if auction_buy and auction_offer:
        _add_candidate(
            rows,
            seen,
            _rank(_safe_div(_sub(_f(auction_buy), _f(auction_offer)), _add(_f(auction_buy), _f(auction_offer)))),
            lane="event_auction_buy_offer_imbalance",
            role="event_module",
            fields=[auction_buy, auction_offer],
            alias_by_panel_field=alias_by_panel,
        )
    for numerator, denominator, lane in [
        (auction_money, evt_amount, "event_auction_money_share"),
        (auction_turnover, evt_amount, "event_auction_turnover_share"),
        (fd_close, evt_amount, "event_seal_close_strength"),
        (fd_max, evt_amount, "event_seal_max_strength"),
    ]:
        _ratio_candidate(rows, seen, numerator=numerator, denominator=denominator, lane=lane, role="event_module", direction="positive", alias_by_panel_field=alias_by_panel)
    if premax:
        _add_candidate(rows, seen, _rank(_f(premax)), lane="event_auction_premax_strength", role="event_module", fields=[premax], alias_by_panel_field=alias_by_panel)

    # Daily sentiment/regime features. These are interactions/gates, not standalone promotion claims.
    sent = "open_sentiment_daily"
    uplimit_num = _field(alias, sent, "uplimit_num")
    downlimit_num = _field(alias, sent, "downlimit_num")
    up_num = _field(alias, sent, "up_num")
    down_num = _field(alias, sent, "down_num")
    lb2 = _field(alias, sent, "lb_2_num")
    lb3 = _field(alias, sent, "lb_3_num")
    max_lb = _field(alias, sent, "max_lb_num")
    zb_num = _field(alias, sent, "zb_num")
    damian = _field(alias, sent, "damian_num")
    tiandi = _field(alias, sent, "tiandi_num")
    ditian = _field(alias, sent, "ditian_num")
    breadth_den = _add(_add(_f(up_num), _f(down_num)), "0.000001") if up_num and down_num else None
    if uplimit_num and breadth_den:
        _add_candidate(rows, seen, _rank(_safe_div(_f(uplimit_num), breadth_den)), lane="sentiment_limit_density", role="regime_interaction", fields=[uplimit_num, up_num, down_num], alias_by_panel_field=alias_by_panel)
    if downlimit_num and breadth_den:
        _add_candidate(rows, seen, _rank(_neg(_safe_div(_f(downlimit_num), breadth_den))), lane="sentiment_downlimit_pressure_inverse", role="regime_interaction", fields=[downlimit_num, up_num, down_num], alias_by_panel_field=alias_by_panel)
    if lb2 and lb3 and uplimit_num:
        _add_candidate(rows, seen, _rank(_safe_div(_add(_f(lb2), _mul("2.0", _f(lb3))), _f(uplimit_num))), lane="sentiment_board_continuation_ratio", role="regime_interaction", fields=[lb2, lb3, uplimit_num], alias_by_panel_field=alias_by_panel)
    for field, lane, direction in [
        (max_lb, "sentiment_market_high_board", "positive"),
        (zb_num, "sentiment_open_board_pressure_inverse", "negative"),
        (damian, "sentiment_big_fail_pressure_inverse", "negative"),
        (tiandi, "sentiment_heaven_earth_inverse", "negative"),
        (ditian, "sentiment_floor_to_ceiling_strength", "positive"),
    ]:
        if not field:
            continue
        expr = _f(field)
        if direction == "negative":
            expr = _neg(expr)
        _add_candidate(rows, seen, _rank(expr), lane=lane, role="regime_interaction", fields=[field], alias_by_panel_field=alias_by_panel)

    # Stock heat features.
    heat = "ths_hot_stock_day"
    rank = _field(alias, heat, "rank")
    rank_diff = _field(alias, heat, "rank_diff")
    last_pct = _field(alias, heat, "last_pct")
    circ = _field(alias, heat, "circulation_value")
    if rank:
        _add_candidate(rows, seen, _rank(_neg(_f(rank))), lane="stock_heat_rank_strength", role="lagged_heat_context", fields=[rank], alias_by_panel_field=alias_by_panel)
    if rank_diff:
        _add_candidate(rows, seen, _rank(_neg(_f(rank_diff))), lane="stock_heat_rank_improvement", role="lagged_heat_context", fields=[rank_diff], alias_by_panel_field=alias_by_panel)
    if last_pct and circ:
        _add_candidate(rows, seen, _rank(_safe_div(_f(last_pct), _f(circ))), lane="stock_heat_small_liquid_momentum", role="lagged_heat_context", fields=[last_pct, circ], alias_by_panel_field=alias_by_panel)

    # Interactions between event fields and market sentiment.
    interaction_left = [field for field in [premax, fd_close, fd_max, rank, rank_diff] if field]
    interaction_right = [field for field in [uplimit_num, downlimit_num, max_lb, zb_num, damian] if field]
    for left in interaction_left[:5]:
        for right in interaction_right[:5]:
            _add_candidate(
                rows,
                seen,
                _rank(_mul(_z(_f(left)), _z(_f(right)))),
                lane="event_x_market_sentiment",
                role="event_regime_interaction",
                fields=[left, right],
                alias_by_panel_field=alias_by_panel,
            )

    # Broad atomic tier: every accepted numeric seed gets both polarities.
    # These rows are deliberately lower-priority than semantic formulas, but
    # they prevent the new field universe from being bottlenecked by hand-picked
    # motifs in the first selector pass. Generated after semantic formulas so
    # direct expression duplicates retain their more informative semantic lane.
    for alias_row in aliases:
        panel_field = str(alias_row["panel_field"])
        route = str(alias_row.get("route") or "")
        if route in {"event_cutoff_key", "availability_key"}:
            continue
        _add_candidate(
            rows,
            seen,
            _rank(_f(panel_field)),
            lane="atomic_direct_rank",
            role="broad_field_direction_probe",
            fields=[panel_field],
            alias_by_panel_field=alias_by_panel,
            coverage_priority_delta=-0.12,
        )
        _add_candidate(
            rows,
            seen,
            _rank(_neg(_f(panel_field))),
            lane="atomic_inverse_rank",
            role="broad_field_direction_probe",
            fields=[panel_field],
            alias_by_panel_field=alias_by_panel,
            coverage_priority_delta=-0.12,
        )

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    dataset_counts = Counter()
    family_counts = Counter()
    for row in rows:
        for dataset in str(row.get("input_datasets") or "").split("|"):
            if dataset:
                dataset_counts[dataset] += 1
        for family in str(row.get("input_families") or "").split("|"):
            if family:
                family_counts[family] += 1

    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_panelization_preflight_no_replay_no_promotion",
        "source_seed_axes": str(seed_axes),
        "candidate_count": len(rows),
        "alias_count": len(aliases),
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_input_dataset": dict(sorted(dataset_counts.items())),
        "by_input_family": dict(sorted(family_counts.items())),
        "policy": {
            "scope": "candidate_generation_only",
            "official_x0_r3": "read_only",
            "promotion": "blocked until panelized fields pass selector-only and frozen replay",
            "future_labels": "next_* fields excluded by upstream registry",
            "fundamental": "NOTICE_DATE/UPDATE_DATE lag required",
            "limit_event": "event cutoff or lag1 context required",
        },
        "candidate_rows": rows,
    }
    output_pack.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_pack, payload)
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "field_alias_map.csv", aliases)
    _write_csv(report_root / "candidate_rows.csv", rows)
    _write_csv(report_root / "factor_lane_summary.csv", [{"factor_lane": k, "candidate_count": v} for k, v in sorted(lane_counts.items())])
    _write_csv(report_root / "input_dataset_summary.csv", [{"input_dataset": k, "candidate_count": v} for k, v in sorted(dataset_counts.items())])

    lines = [
        "# CN Phase3AD New Data Factor Pack v1",
        "",
        "decision: `PASS_PHASE3AD_FACTOR_PACK_READY_FOR_PANELIZATION_PREFLIGHT`",
        "",
        f"- candidate_count: `{len(rows)}`",
        f"- alias_count: `{len(aliases)}`",
        f"- source_seed_axes: `{seed_axes}`",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in sorted(lane_counts.items()):
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This pack is not a replay result and does not promote any alpha.",
            "- Formula fields use panel aliases from `field_alias_map.csv`; panelization must materialize those aliases before replay.",
            "- Fundamental formulas require `NOTICE_DATE`/`UPDATE_DATE` lag.",
            "- Limit event formulas require event cutoff or lag1 daily materialization.",
            "- X0/R3 remains read-only.",
            "",
            "## Next",
            "",
            "- Run panelization preflight for all `input_fields`.",
            "- Build selected sidecars for panel aliases.",
            "- Run selector-only smoke before any replay.",
        ]
    )
    (report_root / "CN_PHASE3AD_NEW_DATA_FACTOR_PACK_V1_2026-06-03.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-axes", type=Path, default=DEFAULT_SEED_AXES)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = build_pack(args.seed_axes, args.output_pack, args.report_root)
    print(json.dumps({k: v for k, v in payload.items() if k != "candidate_rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
