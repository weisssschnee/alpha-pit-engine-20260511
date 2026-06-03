"""Build focused HFQ valuation/liquidity candidate pack for Phase3AD."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_OUTPUT_PACK = Path("runtime/factor_packs/cn_phase3ad_hfq_valuation_factor_pack_v1_20260603.json")
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_hfq_valuation_factor_pack_v1_20260603")


def _key(expression: str) -> str:
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()[:12]


def _row(index: int, lane: str, expression: str, fields: list[str], role: str, *, contains_flow: bool = False) -> dict[str, Any]:
    return {
        "candidate_id": f"phase3ad_hfqval_{lane}_{index:04d}",
        "expression": expression,
        "expression_key": f"hfqval-{_key(expression)}",
        "factor_lane": lane,
        "diagnostic_role": role,
        "input_fields": "|".join(fields),
        "input_sources": "hfq_daily_lag1",
        "input_datasets": "hfq_daily",
        "input_families": "valuation_liquidity",
        "source_lane": "cn_phase3ad_hfq_valuation_feature_layer",
        "source_generator": "cn_phase3ad_hfq_valuation_factor_pack_v1",
        "source_quota_group": "hfq_valuation_lag1",
        "source_credit_policy": "cluster_capped",
        "source_credit_cap_basis": "hfq_valuation_family",
        "pool_priority_score": 1.22,
        "pool_priority_version": "phase3ad-hfq-valuation-v1",
        "contains_fundamental_field": True,
        "contains_flow_liquidity_field": bool(contains_flow),
        "contains_event_cutoff_field": False,
        "contains_limit_event_field": False,
        "contains_sentiment_field": False,
        "contains_capacity_field": "market_cap" in "|".join(fields),
        "official_book_eligible": False,
        "required_lag_days": 1,
        "required_audits": "valuation_lag1_pit;style_exposure;coverage;replay_smoke",
        "leakage_flag": "hfq_daily_lag1_only",
        "search_memory_key": _key(expression),
        "skeleton_key": lane,
    }


def candidate_rows() -> list[dict[str, Any]]:
    specs = [
        ("valuation_low_pe", "CSRank($ctx_hfq_inv_pe_ttm_lag1)", ["ctx_hfq_inv_pe_ttm_lag1"], "low_pe_inverse"),
        ("valuation_low_pb", "CSRank($ctx_hfq_inv_pb_lag1)", ["ctx_hfq_inv_pb_lag1"], "low_pb_inverse"),
        ("valuation_low_ps", "CSRank($ctx_hfq_inv_ps_ttm_lag1)", ["ctx_hfq_inv_ps_ttm_lag1"], "low_ps_inverse"),
        ("valuation_low_pe_raw", "CSRank(Neg($ctx_hfq_pe_ttm_lag1))", ["ctx_hfq_pe_ttm_lag1"], "low_pe_raw"),
        ("valuation_low_pb_raw", "CSRank(Neg($ctx_hfq_pb_lag1))", ["ctx_hfq_pb_lag1"], "low_pb_raw"),
        ("valuation_low_ps_raw", "CSRank(Neg($ctx_hfq_ps_ttm_lag1))", ["ctx_hfq_ps_ttm_lag1"], "low_ps_raw"),
        ("liquidity_volume_ratio", "CSRank($ctx_hfq_volume_ratio_lag1)", ["ctx_hfq_volume_ratio_lag1"], "volume_ratio", True),
        ("liquidity_turnover_ratio", "CSRank($ctx_hfq_turnover_ratio_lag1)", ["ctx_hfq_turnover_ratio_lag1"], "turnover_ratio", True),
        ("valuation_low_pe_x_liquidity", "CSRank(Mul($ctx_hfq_inv_pe_ttm_lag1,CSRank($ctx_hfq_volume_ratio_lag1)))", ["ctx_hfq_inv_pe_ttm_lag1", "ctx_hfq_volume_ratio_lag1"], "low_pe_with_volume_ratio", True),
        ("valuation_low_pb_x_liquidity", "CSRank(Mul($ctx_hfq_inv_pb_lag1,CSRank($ctx_hfq_turnover_ratio_lag1)))", ["ctx_hfq_inv_pb_lag1", "ctx_hfq_turnover_ratio_lag1"], "low_pb_with_turnover_ratio", True),
        ("valuation_low_ps_x_float_size", "CSRank(Div($ctx_hfq_inv_ps_ttm_lag1,Add(Abs(Log(Add($ctx_hfq_float_market_cap_yuan_lag1,1))),0.000001)))", ["ctx_hfq_inv_ps_ttm_lag1", "ctx_hfq_float_market_cap_yuan_lag1"], "low_ps_size_adjusted"),
        ("valuation_pb_size_adjusted", "CSRank(Div($ctx_hfq_inv_pb_lag1,Add(Abs(Log(Add($ctx_hfq_float_market_cap_yuan_lag1,1))),0.000001)))", ["ctx_hfq_inv_pb_lag1", "ctx_hfq_float_market_cap_yuan_lag1"], "low_pb_size_adjusted"),
    ]
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(specs, 1):
        lane, expr, fields, role, *rest = item
        rows.append(
            _row(
                index,
                lane,
                expr,
                fields,
                role,
                contains_flow=bool(rest and rest[0]),
            )
        )
    return rows


def build_pack(output_pack: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    rows = candidate_rows()
    pack = {
        "factor_pack_id": "cn_phase3ad_hfq_valuation_factor_pack_v1_20260603",
        "factor_pack_version": "cn-phase3ad-hfq-valuation-factor-pack-v1-2026-06-03",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(rows),
        "candidate_rows": rows,
        "policy": {
            "lag": "all fields are previous selected trading day only",
            "scope": "focused valuation/liquidity diagnostic pack; no promotion without replay and style audit",
        },
    }
    write_json_artifact(output_pack, pack)
    report = {
        "decision": "PASS_HFQ_VALUATION_FACTOR_PACK_READY",
        "output_pack": str(output_pack),
        "candidate_count": len(rows),
        "lanes": sorted({row["factor_lane"] for row in rows}),
        "not_confirmed": ["alpha_quality", "replay_pass", "style_neutrality"],
    }
    write_json_artifact(report_root / "hfq_valuation_factor_pack_report.json", report)
    (report_root / "CN_PHASE3AD_HFQ_VALUATION_FACTOR_PACK_V1_2026-06-03.md").write_text(
        "# CN Phase3AD HFQ Valuation Factor Pack v1\n\n"
        f"decision: `{report['decision']}`\n\n"
        f"- candidate_count: `{report['candidate_count']}`\n"
        "- fields: lagged PE/PB/PS, inverse valuation, volume_ratio, turnover_ratio, float market cap\n\n"
        "This pack is diagnostic until replay and style exposure audits pass.\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-pack", type=Path, default=DEFAULT_OUTPUT_PACK)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_pack(args.output_pack, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
