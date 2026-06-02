"""Build CN integrated factor candidate pack v1 from the transform plan.

The pack is intentionally selector-ready but not promotion-ready. It converts
materialized 1-minute and non-minute PIT context fields into candidate formula
templates while carrying search-memory and source-priority metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.candidate_pool_priority import enrich_candidate_pool_priority
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


DEFAULT_TRANSFORM_PLAN = Path(
    "runtime/field_registry/cn_integrated_feature_transform_plan_v1_20260602/integrated_feature_transform_plan.csv"
)
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_integrated_feature_factor_candidate_pack_v1_20260602.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_integrated_factor_pack_v1_20260602")

PACK_ID = "cn_integrated_feature_factor_candidate_pack_v1_20260602"
PACK_VERSION = "cn-integrated-feature-factor-pack-v1-2026-06-02"


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


def _read_plan(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _rank(expr: str) -> str:
    return f"CSRank({expr})"


def _z(expr: str) -> str:
    return f"ZScore({expr})"


def _neg(expr: str) -> str:
    return f"Neg({expr})"


def _safe_div(left: str, right: str) -> str:
    return f"Div({left},Add(Abs({right}),0.000001))"


def _field_expr(field: str) -> str:
    return f"${field}"


def _contains(field: str, tokens: tuple[str, ...]) -> bool:
    text = field.lower()
    return any(token in text for token in tokens)


def _row(expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]], index: int) -> dict[str, Any]:
    families = sorted({str(plan_rows.get(field, {}).get("family") or "unknown") for field in fields})
    sources = sorted({str(plan_rows.get(field, {}).get("source") or "unknown") for field in fields})
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    item = {
        "candidate_id": f"cn_integrated_v1_{lane}_{index:05d}",
        "expression": expression,
        "source_lane": "cn_integrated_feature_layer",
        "source_generator": "cn_integrated_factor_pack_v1",
        "factor_lane": lane,
        "diagnostic_role": role,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|shared_pool_frozen_selection|signal_vector_cluster|replay_smoke|source_attribution",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "search_memory_key": f"cn_integrated_feature_v1:{digest}",
        "input_fields": "|".join(fields),
        "input_families": "|".join(families),
        "input_sources": "|".join(sources),
        "contains_minute_field": any(field.startswith("m1_") for field in fields),
        "contains_rzrq_field": any(field.startswith("ctx_rzrq_") for field in fields),
        "contains_fundamental_field": any(field.startswith("ctx_fund_") for field in fields),
        "contains_holder_field": any(field.startswith("ctx_holder_") for field in fields),
        "contains_market_regime_field": any(field.startswith("ctx_mkt_updown_") for field in fields),
        "contains_flow_liquidity_field": any("amount" in field or "vol" in field or "rzrq" in field for field in fields),
        "contains_capacity_field": any("market_cap" in field or "mcap" in field or "float" in field for field in fields),
        "leakage_flag": "no_label_fields;minute_fields_after_observed_window;nonminute_context_lagged_or_pit",
    }
    return enrich_candidate_pool_priority(item)


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(_row(expression, lane=lane, role=role, fields=fields, plan_rows=plan_rows, index=len(rows) + 1))


def _eligible(plan: list[dict[str, Any]], *, families: set[str] | None = None, source: str | None = None) -> list[str]:
    out: list[str] = []
    for row in plan:
        if str(row.get("materialized")).lower() != "true":
            continue
        if row.get("selector_status") != "selector_candidate" and row.get("selector_status") != "regime_context_not_standalone_alpha":
            continue
        if families and row.get("family") not in families:
            continue
        if source and row.get("source") != source:
            continue
        out.append(str(row["field"]))
    return sorted(set(out))


def _direct_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], fields: list[str], *, lane: str, role: str) -> None:
    for field in fields:
        expr = _field_expr(field)
        _add(rows, seen, _rank(expr), lane=lane, role=role, fields=[field], plan_rows=plan_rows)
        _add(rows, seen, _rank(_z(expr)), lane=f"{lane}_zrank", role=role, fields=[field], plan_rows=plan_rows)


def _minute_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], minute_fields: list[str]) -> None:
    fields = set(minute_fields)
    for window in ("first5", "first15", "first30"):
        amount = f"m1_{window}_amount"
        vol = f"m1_{window}_vol"
        vwap_ret = f"m1_{window}_vwap_return_vs_open"
        last_ret = f"m1_{window}_last_return_vs_open"
        rng = f"m1_{window}_range"
        if amount in fields and "m1_amount_day" in fields:
            _add(rows, seen, _rank(_safe_div(_field_expr(amount), "$m1_amount_day")), lane="minute_early_amount_share", role="minute_flow_pressure", fields=[amount, "m1_amount_day"], plan_rows=plan_rows)
        if vol in fields and "m1_vol_day" in fields:
            _add(rows, seen, _rank(_safe_div(_field_expr(vol), "$m1_vol_day")), lane="minute_early_volume_share", role="minute_flow_pressure", fields=[vol, "m1_vol_day"], plan_rows=plan_rows)
        if vwap_ret in fields:
            _add(rows, seen, _rank(_field_expr(vwap_ret)), lane="minute_vwap_pressure", role="minute_price_pressure", fields=[vwap_ret], plan_rows=plan_rows)
        if last_ret in fields and vwap_ret in fields:
            _add(rows, seen, _rank(f"Sub(${last_ret},${vwap_ret})"), lane="minute_last_vs_vwap_pressure", role="minute_price_pressure", fields=[last_ret, vwap_ret], plan_rows=plan_rows)
        if rng in fields:
            _add(rows, seen, _rank(_field_expr(rng)), lane="minute_early_range", role="minute_volatility_pressure", fields=[rng], plan_rows=plan_rows)
    if {"m1_first5_amount", "m1_first30_amount"}.issubset(fields):
        _add(rows, seen, _rank(_safe_div("$m1_first5_amount", "$m1_first30_amount")), lane="minute_frontloaded_amount", role="minute_flow_pressure", fields=["m1_first5_amount", "m1_first30_amount"], plan_rows=plan_rows)
    if {"m1_first5_vwap_return_vs_open", "m1_first30_vwap_return_vs_open"}.issubset(fields):
        _add(rows, seen, _rank(f"Sub($m1_first5_vwap_return_vs_open,$m1_first30_vwap_return_vs_open)"), lane="minute_early_reversal_pressure", role="minute_price_pressure", fields=["m1_first5_vwap_return_vs_open", "m1_first30_vwap_return_vs_open"], plan_rows=plan_rows)


def _rzrq_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], fields: list[str]) -> None:
    available = set(fields)
    pairs = [
        ("ctx_rzrq_rzmre", "ctx_rzrq_rzye"),
        ("ctx_rzrq_rzche", "ctx_rzrq_rzye"),
        ("ctx_rzrq_rzjme", "ctx_rzrq_rzrqye"),
        ("ctx_rzrq_rqmcl", "ctx_rzrq_rqye"),
        ("ctx_rzrq_rqchl", "ctx_rzrq_rqye"),
        ("ctx_rzrq_rqjmg", "ctx_rzrq_rqye"),
        ("ctx_rzrq_rzmre3d", "ctx_rzrq_rzye"),
        ("ctx_rzrq_rzmre5d", "ctx_rzrq_rzye"),
        ("ctx_rzrq_rzjme3d", "ctx_rzrq_rzrqye"),
        ("ctx_rzrq_rqjmg3d", "ctx_rzrq_rqye"),
    ]
    for left, right in pairs:
        if {left, right}.issubset(available):
            _add(rows, seen, _rank(_safe_div(_field_expr(left), _field_expr(right))), lane="rzrq_balance_normalized_flow", role="leverage_flow", fields=[left, right], plan_rows=plan_rows)
    if {"ctx_rzrq_rzmre", "ctx_rzrq_rzche"}.issubset(available):
        _add(rows, seen, _rank(f"Sub($ctx_rzrq_rzmre,$ctx_rzrq_rzche)"), lane="rzrq_financing_net_flow", role="leverage_flow", fields=["ctx_rzrq_rzmre", "ctx_rzrq_rzche"], plan_rows=plan_rows)
    if {"ctx_rzrq_rqmcl", "ctx_rzrq_rqchl"}.issubset(available):
        _add(rows, seen, _rank(f"Sub($ctx_rzrq_rqmcl,$ctx_rzrq_rqchl)"), lane="rzrq_short_net_flow", role="leverage_flow", fields=["ctx_rzrq_rqmcl", "ctx_rzrq_rqchl"], plan_rows=plan_rows)


def _fund_holder_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], fields: list[str]) -> None:
    available = set(fields)
    quality = [
        "ctx_fund_bs_cash_to_assets",
        "ctx_fund_ps_netprofit_margin",
        "ctx_fund_ps_operate_profit_margin",
        "ctx_fund_cf_operate_cash_to_netprofit",
        "ctx_fund_ps_research_to_income",
    ]
    risk = [
        "ctx_fund_bs_debt_to_assets",
        "ctx_fund_bs_goodwill_to_assets",
        "ctx_fund_bs_inventory_to_assets",
    ]
    holder = [
        "ctx_holder_holder_num_change",
        "ctx_holder_holder_num_ratio",
        "ctx_holder_interval_chrate",
        "ctx_holder_avg_market_cap",
        "ctx_holder_avg_hold_num",
    ]
    _direct_rows(rows, seen, plan_rows, [field for field in quality if field in available], lane="fundamental_quality_direct", role="fundamental_quality")
    for field in risk:
        if field in available:
            _add(rows, seen, _rank(_neg(_field_expr(field))), lane="fundamental_risk_inverse", role="fundamental_risk_control", fields=[field], plan_rows=plan_rows)
    for field in holder:
        if field in available:
            _add(rows, seen, _rank(_field_expr(field)), lane="holder_structure_direct", role="holder_structure", fields=[field], plan_rows=plan_rows)
            if _contains(field, ("change", "ratio", "chrate")):
                _add(rows, seen, _rank(_neg(_field_expr(field))), lane="holder_dispersion_inverse", role="holder_structure", fields=[field], plan_rows=plan_rows)
    for fund in [field for field in quality if field in available]:
        for minute in ("m1_first5_amount", "m1_first15_amount", "m1_first30_amount"):
            if minute in available:
                _add(rows, seen, _rank(f"Mul({_z(_field_expr(fund))},{_z(_field_expr(minute))})"), lane="fundamental_x_minute_flow", role="context_interaction", fields=[fund, minute], plan_rows=plan_rows)


def _regime_interaction_rows(rows: list[dict[str, Any]], seen: set[str], plan_rows: dict[str, dict[str, Any]], fields: list[str]) -> None:
    available = set(fields)
    regimes = [field for field in fields if field.startswith("ctx_mkt_updown_")]
    minute = [field for field in fields if field in {"m1_first5_amount", "m1_first15_amount", "m1_first5_vwap_return_vs_open", "m1_open_gap_vs_preclose"}]
    rzrq = [field for field in fields if field in {"ctx_rzrq_rzmre3d", "ctx_rzrq_rzjme3d", "ctx_rzrq_rqjmg3d"}]
    for regime in regimes[:10]:
        for other in [*minute, *rzrq]:
            if other in available:
                _add(rows, seen, _rank(f"Mul({_z(_field_expr(regime))},{_z(_field_expr(other))})"), lane="market_regime_x_signal", role="regime_interaction", fields=[regime, other], plan_rows=plan_rows)


def build_pack(*, transform_plan: Path, output_pack: Path, report_root: Path) -> dict[str, Any]:
    plan = _read_plan(transform_plan)
    plan_rows = {str(row["field"]): row for row in plan}
    materialized_fields = _eligible(plan)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    minute_fields = _eligible(
        plan,
        source="minute_panel_v2",
        families={"minute_flow_liquidity", "minute_vwap_pressure", "minute_return_pressure", "minute_range_volatility"},
    )
    rzrq_fields = _eligible(plan, families={"rzrq_flow_leverage"})
    fund_holder_fields = _eligible(
        plan,
        families={"fundamental_balance_risk", "fundamental_income_quality", "fundamental_cashflow_quality", "holder_structure"},
    )
    regime_fields = _eligible(plan, families={"market_breadth_regime"})

    _minute_rows(rows, seen, plan_rows, minute_fields)
    _rzrq_rows(rows, seen, plan_rows, rzrq_fields)
    _fund_holder_rows(rows, seen, plan_rows, fund_holder_fields)
    _regime_interaction_rows(rows, seen, plan_rows, [*minute_fields, *rzrq_fields, *regime_fields])
    _direct_rows(rows, seen, plan_rows, [field for field in minute_fields[:24]], lane="minute_direct_rank", role="minute_context")
    _direct_rows(rows, seen, plan_rows, [field for field in rzrq_fields[:24]], lane="rzrq_direct_rank", role="leverage_flow")

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    family_counts = Counter()
    source_counts = Counter()
    for row in rows:
        for family in str(row.get("input_families") or "").split("|"):
            if family:
                family_counts[family] += 1
        for source in str(row.get("input_sources") or "").split("|"):
            if source:
                source_counts[source] += 1

    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "integrated_feature_factor_pack_ready_for_shared_pool_preflight_no_promotion",
        "transform_plan": str(transform_plan),
        "candidate_count": len(rows),
        "materialized_selector_field_count": len(materialized_fields),
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_input_family": dict(sorted(family_counts.items())),
        "by_input_source": dict(sorted(source_counts.items())),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "requires selector-only smoke, frozen replay smoke, global clustering, field attribution, OOS/regime/marginal audit",
            "labels": "label_* and meta_* fields are excluded",
            "minute_fields": "only after observed minute window closes; future bars forbidden",
            "nonminute_context": "lagged/PIT only",
        },
        "candidate_rows": rows,
    }
    _write_json(output_pack, payload)
    report_root.mkdir(parents=True, exist_ok=True)
    summary_rows = [{"factor_lane": key, "candidate_count": value} for key, value in sorted(lane_counts.items())]
    _write_csv(report_root / "factor_lane_summary.csv", summary_rows)
    _write_markdown(report_root / "CN_INTEGRATED_FACTOR_PACK_V1_2026-06-02.md", payload)
    Path("reports/CN_INTEGRATED_FACTOR_PACK_V1_DECISION_2026-06-02.md").write_text(
        _decision_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Integrated Factor Pack v1",
        "",
        f"status: `{payload['status']}`",
        f"candidate_count: `{payload['candidate_count']}`",
        f"materialized_selector_field_count: `{payload['materialized_selector_field_count']}`",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in payload["by_factor_lane"].items():
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- official X0/R3 remains read-only.",
            "- This pack is not alpha proof and cannot promote without selector/replay audits.",
            "- `label_*` and `meta_*` fields are excluded.",
            "- 1min features must respect observed-window timing.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# CN Integrated Factor Pack v1 Decision",
            "",
            "decision: `PASS_INTEGRATED_FACTOR_PACK_V1_READY_FOR_SELECTOR_PREFLIGHT`",
            "",
            f"candidate_count: `{payload['candidate_count']}`",
            "",
            "confirmed:",
            "- integrated materialized fields now have candidate expressions with search-memory keys",
            "- source-priority metadata is attached",
            "- official X0/R3 remains read-only",
            "",
            "not_confirmed:",
            "- replay pass",
            "- deployable alpha",
            "- production readiness",
            "",
            "next: `run selector-only shared-pool preflight for this pack`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transform-plan", type=Path, default=DEFAULT_TRANSFORM_PLAN)
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = build_pack(transform_plan=args.transform_plan, output_pack=args.output_pack, report_root=args.report_root)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "candidate_count": payload["candidate_count"],
                "materialized_selector_field_count": payload["materialized_selector_field_count"],
                "by_factor_lane": payload["by_factor_lane"],
                "output_pack": str(args.output_pack),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
