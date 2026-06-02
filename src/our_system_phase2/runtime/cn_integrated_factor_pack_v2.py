"""Build CN integrated factor candidate pack v2.

v1 proved executable access to integrated fields, but direct ranks mostly
selected RZRQ/minute fields and produced weak replay.  v2 keeps X0/R3 read-only
and shifts the candidate space toward quality residuals and interactions:

- fundamental quality minus size/capacity proxies,
- fundamental quality gated by minute early-flow/price pressure,
- fundamental quality gated by RZRQ and market-breadth context.
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
DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_integrated_feature_factor_candidate_pack_v2_20260602.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_integrated_factor_pack_v2_20260602")

PACK_ID = "cn_integrated_feature_factor_candidate_pack_v2_20260602"
PACK_VERSION = "cn-integrated-feature-factor-pack-v2-2026-06-02"

BASE_SIZE_FIELDS = ["final_float_market_cap", "final_total_market_cap", "amount", "volume", "vwap"]


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


def _f(field: str) -> str:
    return f"${field}"


def _sub(left: str, right: str) -> str:
    return f"Sub({left},{right})"


def _mul(left: str, right: str) -> str:
    return f"Mul({left},{right})"


def _eligible(plan: list[dict[str, Any]], families: set[str]) -> list[str]:
    out = []
    for row in plan:
        if str(row.get("materialized")).lower() != "true":
            continue
        if row.get("selector_status") not in {"selector_candidate", "regime_context_not_standalone_alpha"}:
            continue
        if str(row.get("family") or "") in families:
            out.append(str(row["field"]))
    return sorted(set(out))


def _families(fields: list[str], plan_rows: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for field in fields:
        out.append(str(plan_rows.get(field, {}).get("family") or ("base_replay" if field in BASE_SIZE_FIELDS else "unknown")))
    return sorted(set(out))


def _sources(fields: list[str], plan_rows: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for field in fields:
        out.append(str(plan_rows.get(field, {}).get("source") or ("base_replay_panel" if field in BASE_SIZE_FIELDS else "unknown")))
    return sorted(set(out))


def _row(expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]], index: int) -> dict[str, Any]:
    digest = hashlib.sha256("|".join([expression, lane, role, *fields]).encode("utf-8")).hexdigest()[:16]
    item = {
        "candidate_id": f"cn_integrated_v2_{lane}_{index:05d}",
        "expression": expression,
        "source_lane": "cn_integrated_feature_layer",
        "source_generator": "cn_integrated_factor_pack_v2",
        "factor_lane": lane,
        "diagnostic_role": role,
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "field_lag_check|shared_pool_frozen_selection|signal_vector_cluster|replay_smoke|source_attribution",
        "expression_key": expression_memory_key(expression),
        "skeleton_key": skeleton_memory_key(expression),
        "search_memory_key": f"cn_integrated_feature_v2:{digest}",
        "input_fields": "|".join(fields),
        "input_families": "|".join(_families(fields, plan_rows)),
        "input_sources": "|".join(_sources(fields, plan_rows)),
        "contains_minute_field": any(field.startswith("m1_") for field in fields),
        "contains_rzrq_field": any(field.startswith("ctx_rzrq_") for field in fields),
        "contains_fundamental_field": any(field.startswith("ctx_fund_") for field in fields),
        "contains_holder_field": any(field.startswith("ctx_holder_") for field in fields),
        "contains_market_regime_field": any(field.startswith("ctx_mkt_updown_") for field in fields),
        "contains_flow_liquidity_field": any("amount" in field or "vol" in field or "rzrq" in field or field in {"amount", "volume", "vwap"} for field in fields),
        "contains_capacity_field": any("market_cap" in field or "mcap" in field or "float" in field for field in fields),
        "leakage_flag": "no_label_fields;minute_fields_after_observed_window;nonminute_context_lagged_or_pit;base_replay_fields_only",
    }
    return enrich_candidate_pool_priority(item)


def _add(rows: list[dict[str, Any]], seen: set[str], expression: str, *, lane: str, role: str, fields: list[str], plan_rows: dict[str, dict[str, Any]]) -> None:
    key = expression_memory_key(expression)
    if key in seen:
        return
    seen.add(key)
    rows.append(_row(expression, lane=lane, role=role, fields=fields, plan_rows=plan_rows, index=len(rows) + 1))


def _choose_fields(plan: list[dict[str, Any]]) -> dict[str, list[str]]:
    quality = _eligible(plan, {"fundamental_income_quality", "fundamental_cashflow_quality"})
    risk = _eligible(plan, {"fundamental_balance_risk"})
    rzrq = _eligible(plan, {"rzrq_flow_leverage"})
    minute = _eligible(plan, {"minute_flow_liquidity", "minute_vwap_pressure", "minute_return_pressure", "minute_range_volatility"})
    regime = _eligible(plan, {"market_breadth_regime"})
    holder = _eligible(plan, {"holder_structure"})
    preferred_quality = [
        field
        for field in [
            "ctx_fund_ps_operate_profit_margin",
            "ctx_fund_ps_netprofit_margin",
            "ctx_fund_cf_operate_cash_to_netprofit",
            "ctx_fund_ps_research_to_income",
            "ctx_fund_bs_cash_to_assets",
        ]
        if field in quality or field in risk
    ]
    if not preferred_quality:
        preferred_quality = quality[:8]
    return {
        "quality": preferred_quality,
        "risk": [field for field in ["ctx_fund_bs_debt_to_assets", "ctx_fund_bs_goodwill_to_assets", "ctx_fund_bs_inventory_to_assets"] if field in risk],
        "rzrq": [field for field in rzrq if any(token in field for token in ("rzjme", "rzmre", "rzche", "rqjmg", "rqmcl", "rqye", "rzye"))][:18],
        "minute": [field for field in minute if any(token in field for token in ("first5", "first15", "first30", "amount", "vwap", "return", "range"))][:18],
        "regime": [field for field in regime if any(token in field for token in ("zt", "dt", "szjs", "xdjs", "zrcs", "zrtj", "ratio"))][:12],
        "holder": [field for field in holder if any(token in field for token in ("holder_num", "avg_market_cap", "interval_chrate"))][:8],
    }


def build_pack(*, transform_plan: Path, output_pack: Path, report_root: Path) -> dict[str, Any]:
    plan = _read_plan(transform_plan)
    plan_rows = {str(row["field"]): row for row in plan}
    selected = _choose_fields(plan)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    quality = selected["quality"]
    risk = selected["risk"]
    rzrq = selected["rzrq"]
    minute = selected["minute"]
    regime = selected["regime"]
    holder = selected["holder"]

    for q in quality:
        qz = _z(_f(q))
        _add(rows, seen, _rank(_f(q)), lane="quality_direct_control", role="quality_control", fields=[q], plan_rows=plan_rows)
        for size in ("final_float_market_cap", "final_total_market_cap", "amount"):
            _add(rows, seen, _rank(_sub(qz, _z(_f(size)))), lane="quality_size_residual", role="quality_residual", fields=[q, size], plan_rows=plan_rows)
        for r in risk:
            _add(rows, seen, _rank(_sub(qz, _z(_f(r)))), lane="quality_minus_balance_risk", role="quality_risk_residual", fields=[q, r], plan_rows=plan_rows)
        for h in holder:
            _add(rows, seen, _rank(_sub(qz, _z(_f(h)))), lane="quality_holder_residual", role="quality_holder_residual", fields=[q, h], plan_rows=plan_rows)
        for m in minute:
            _add(rows, seen, _rank(_mul(qz, _z(_f(m)))), lane="quality_x_minute_pressure", role="context_interaction", fields=[q, m], plan_rows=plan_rows)
        for lev in rzrq:
            _add(rows, seen, _rank(_mul(qz, _z(_f(lev)))), lane="quality_x_rzrq_flow", role="context_interaction", fields=[q, lev], plan_rows=plan_rows)
        for reg in regime:
            _add(rows, seen, _rank(_mul(qz, _z(_f(reg)))), lane="quality_x_market_breadth", role="regime_interaction", fields=[q, reg], plan_rows=plan_rows)

    for lev in rzrq:
        for size in ("final_float_market_cap", "amount"):
            _add(rows, seen, _rank(_safe_div(_f(lev), _f(size))), lane="rzrq_size_normalized", role="leverage_flow_normalized", fields=[lev, size], plan_rows=plan_rows)
    for m in minute:
        if "amount" in m or "vol" in m:
            _add(rows, seen, _rank(_safe_div(_f(m), "$amount")), lane="minute_amount_share_daily", role="minute_flow_normalized", fields=[m, "amount"], plan_rows=plan_rows)
        if "vwap" in m or "return" in m or "range" in m:
            _add(rows, seen, _rank(_sub(_z(_f(m)), _z("$vwap"))), lane="minute_vs_daily_vwap_residual", role="minute_price_residual", fields=[m, "vwap"], plan_rows=plan_rows)

    lane_counts = Counter(str(row.get("factor_lane") or "unknown") for row in rows)
    family_counts = Counter()
    for row in rows:
        for family in str(row.get("input_families") or "").split("|"):
            if family:
                family_counts[family] += 1
    payload = {
        "factor_pack_id": PACK_ID,
        "factor_pack_version": PACK_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "integrated_feature_factor_pack_v2_ready_for_selector_preflight_no_promotion",
        "v2_reason": "v1 direct ranks produced weak replay except one concentrated fundamental quality cluster; v2 emphasizes quality residuals and context interactions.",
        "transform_plan": str(transform_plan),
        "candidate_count": len(rows),
        "selected_field_counts": {key: len(value) for key, value in selected.items()},
        "by_factor_lane": dict(sorted(lane_counts.items())),
        "by_input_family": dict(sorted(family_counts.items())),
        "policy": {
            "official_x0_r3": "read_only",
            "promotion": "requires selector-only smoke, frozen replay smoke, global clustering, source attribution, OOS/regime/marginal audit",
            "labels": "label_* and meta_* fields are excluded",
            "minute_fields": "only observed-window features; future bars forbidden",
            "nonminute_context": "lagged/PIT only",
        },
        "candidate_rows": rows,
    }
    _write_json(output_pack, payload)
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "factor_lane_summary.csv", [{"factor_lane": key, "candidate_count": value} for key, value in sorted(lane_counts.items())])
    lines = [
        "# CN Integrated Factor Pack v2",
        "",
        "decision: `PASS_INTEGRATED_FACTOR_PACK_V2_READY_FOR_SELECTOR_PREFLIGHT`",
        f"candidate_count: `{payload['candidate_count']}`",
        "",
        "## Factor Lanes",
        "",
    ]
    for lane, count in payload["by_factor_lane"].items():
        lines.append(f"- `{lane}`: `{count}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is candidate generation only, not alpha proof.",
            "- It does not modify X0/R3 or any official shadow object.",
            "- It is designed to test interactions/residuals after v1 direct-rank weakness.",
        ]
    )
    (report_root / "CN_INTEGRATED_FACTOR_PACK_V2_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_INTEGRATED_FACTOR_PACK_V2_DECISION_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


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
                "selected_field_counts": payload["selected_field_counts"],
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
