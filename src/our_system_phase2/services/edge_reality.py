from __future__ import annotations

from statistics import mean
from typing import Any

from our_system_phase2.domain.models import CandidateRecord, utc_now_iso
from our_system_phase2.services.real_market_data import build_real_market_data_contract


REALITY_NET_EDGE_FLOOR = 0.30
REALITY_ACTIVITY_FLOOR = 0.25
REALITY_LIQUIDITY_FLOOR = 0.30
REAL_EDGE_EVIDENCE_TIER = "synthetic_proxy_only"
REAL_EDGE_CANNOT_CLAIM = [
    "tradable_net_edge",
    "production_alpha_quality",
    "real_market_superiority",
    "capital_allocation_readiness",
]
REAL_EDGE_REQUIRED_VALIDATION = [
    "leakage_checked_real_market_dataset",
    "transaction_cost_slippage_capacity_backtest",
    "quarterly_3_month_purged_embargoed_walk_forward_oos",
    "factor_exposure_and_crowding_audit",
    "forward_paper_trading_or_live_shadow_validation",
]


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def evaluate_edge_reality(record: CandidateRecord) -> dict[str, Any]:
    """Deterministic tradeability proxy inspired by AlphaGPT's friction-aware backtest.

    This is intentionally report-only. It approximates liquidity, turnover cost,
    activity, and drawdown pressure from the behavioral fingerprint because Phase2
    does not yet own a real market-data backtest loop.
    """
    fp = record.fingerprint
    liquidity_proxy = _clip(
        (fp["size_tilt"] * 0.45)
        + ((1.0 - fp["sector_concentration"]) * 0.25)
        + (fp["decay_halflife"] * 0.20)
        + ((1.0 - fp["beta_to_market"]) * 0.10)
    )
    activity_proxy = _clip(
        (record.ic_positive_coverage * 0.35)
        + (max(fp["momentum_tilt"], fp["value_tilt"], fp["predictive_of_regime_change"]) * 0.30)
        + (record.oos_stability * 0.20)
        + (fp["autocorr_lag1"] * 0.15)
    )
    cost_penalty = _clip(
        0.015
        + (fp["turnover_proxy"] * 0.09)
        + ((1.0 - liquidity_proxy) * 0.05)
    )
    drawdown_penalty = _clip(fp["ic_regime_volatile"] * (1.0 - record.oos_stability) * 0.12)
    crowding_penalty = _clip((fp["beta_to_market"] * 0.05) + (fp["sector_concentration"] * 0.04))
    net_edge_score = round(record.oos_ic - cost_penalty - drawdown_penalty - crowding_penalty, 6)

    blockers: list[str] = []
    if net_edge_score < REALITY_NET_EDGE_FLOOR:
        blockers.append("net_edge_below_floor_after_cost_drawdown_crowding")
    if activity_proxy < REALITY_ACTIVITY_FLOOR:
        blockers.append("activity_proxy_below_floor")
    if liquidity_proxy < REALITY_LIQUIDITY_FLOOR:
        blockers.append("liquidity_proxy_below_floor")

    return {
        "candidate_id": record.candidate_id,
        "expression": record.expression,
        "frontier_lane": record.frontier_lane,
        "source_mode": record.source_mode,
        "archive_cell": record.archive_cell,
        "oos_ic": record.oos_ic,
        "oos_stability": record.oos_stability,
        "liquidity_proxy": liquidity_proxy,
        "activity_proxy": activity_proxy,
        "turnover_proxy": fp["turnover_proxy"],
        "cost_penalty": cost_penalty,
        "drawdown_penalty": drawdown_penalty,
        "crowding_penalty": crowding_penalty,
        "net_edge_score": net_edge_score,
        "passes_reality_proxy": not blockers,
        "blockers": blockers,
    }


def build_edge_reality_gate_report(
    *,
    run_id: str,
    records: list[CandidateRecord],
    real_market_data_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retained_generated = [record for record in records if record.round_index > 0 and record.retained]
    evaluations = [evaluate_edge_reality(record) for record in retained_generated]
    passing = [item for item in evaluations if item["passes_reality_proxy"]]

    if evaluations:
        pass_rate = round(len(passing) / len(evaluations), 6)
        mean_net_edge = round(mean(item["net_edge_score"] for item in evaluations), 6)
        max_net_edge = round(max(item["net_edge_score"] for item in evaluations), 6)
    else:
        pass_rate = 0.0
        mean_net_edge = None
        max_net_edge = None

    blocker_counts: dict[str, int] = {}
    for item in evaluations:
        for blocker in item["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    market_data_contract = real_market_data_contract or build_real_market_data_contract()

    return {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "source_reference": "imbue-bit/AlphaGPT model_core.backtest.MemeBacktest friction checks: liquidity, turnover cost, drawdown, activity",
        "scope": "report_only_reality_proxy_not_archive_retention",
        "evidence_tier": REAL_EDGE_EVIDENCE_TIER,
        "proxy_role": "candidate_triage_only_not_real_edge_evidence",
        "does_not_change_archive_retention": True,
        "not_claiming_tradable_alpha": True,
        "real_market_data_contract": market_data_contract,
        "real_market_data_consumed_by_runtime": False,
        "real_edge_promotion_blockers": [
            "candidate_expressions_not_backtested_on_real_market_dataset",
            "transaction_cost_slippage_capacity_model_not_applied_to_real_trades",
            "walk_forward_oos_not_run",
            "factor_exposure_audit_not_run",
        ],
        "can_support_claims": [
            "search_runtime_candidate_triage",
            "friction_proxy_diagnostics",
        ],
        "cannot_support_claims": REAL_EDGE_CANNOT_CLAIM,
        "required_validation_before_real_edge_claim": REAL_EDGE_REQUIRED_VALIDATION,
        "metric_definition": {
            "liquidity_proxy": "size_tilt + inverse sector concentration + decay + inverse beta proxy",
            "activity_proxy": "positive regime coverage + strongest style signal + oos stability + autocorr",
            "cost_penalty": "base friction + turnover pressure + low-liquidity penalty",
            "drawdown_penalty": "volatile-regime pressure scaled by oos instability",
            "crowding_penalty": "market beta and sector concentration penalty",
            "net_edge_score": "oos_ic - cost_penalty - drawdown_penalty - crowding_penalty",
        },
        "thresholds": {
            "net_edge_score_min": REALITY_NET_EDGE_FLOOR,
            "activity_proxy_min": REALITY_ACTIVITY_FLOOR,
            "liquidity_proxy_min": REALITY_LIQUIDITY_FLOOR,
        },
        "retained_candidate_count": len(evaluations),
        "reality_proxy_pass_count": len(passing),
        "reality_proxy_pass_rate": pass_rate,
        "mean_net_edge_score": mean_net_edge,
        "max_net_edge_score": max_net_edge,
        "blocker_counts": blocker_counts,
        "evaluations": evaluations,
    }
