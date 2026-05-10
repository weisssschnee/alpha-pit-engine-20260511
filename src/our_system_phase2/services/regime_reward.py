from __future__ import annotations

from statistics import mean
from typing import Any

from our_system_phase2.domain.models import CandidateRecord


def _combination_ic(records: list[CandidateRecord]) -> float:
    if not records:
        return 0.0
    retained = [record for record in records if record.retained]
    pool = retained or records
    mean_ic = mean(record.ic_max for record in pool)
    coverage_bonus = mean(record.ic_positive_coverage for record in pool) * 0.2
    redundancy_penalty = max(0, len(pool) - len({record.archive_cell for record in pool})) * 0.015
    return round(mean_ic + coverage_bonus - redundancy_penalty, 6)


def _decay_resistance(record: CandidateRecord) -> float:
    return round((record.fingerprint["decay_halflife"] * 0.7) + (record.oos_stability * 0.3), 6)


def compute_phase2_reward(candidate: CandidateRecord, archive: list[CandidateRecord]) -> dict[str, Any]:
    """Training signal only; it does not replace IC/OOS retention or archive dominance."""

    archive_score = _combination_ic(archive)
    combined_score = _combination_ic([*archive, candidate])
    marginal_ic = round(combined_score - archive_score, 6)
    if marginal_ic < 0:
        return {
            "reward": -1.0,
            "rejected_for_policy_training": True,
            "reject_reason": "negative_marginal_combination_ic",
            "marginal_ic": marginal_ic,
            "max_regime_ic": candidate.ic_max,
            "decay_resistance": _decay_resistance(candidate),
            "oos_hard_veto_used": False,
        }

    max_regime_ic = candidate.ic_max
    decay_resistance = _decay_resistance(candidate)
    reward = round((0.4 * marginal_ic) + (0.4 * max_regime_ic) + (0.2 * decay_resistance), 6)
    return {
        "reward": reward,
        "rejected_for_policy_training": False,
        "reject_reason": None,
        "marginal_ic": marginal_ic,
        "max_regime_ic": max_regime_ic,
        "decay_resistance": decay_resistance,
        "components": {
            "marginal_ic_weight": 0.4,
            "max_regime_ic_weight": 0.4,
            "decay_resistance_weight": 0.2,
        },
        "ic_by_regime": dict(candidate.ic_by_regime),
        "oos_degradation_ratio": candidate.oos_degradation_ratio,
        "oos_stability": candidate.oos_stability,
        "oos_hard_veto_used": False,
        "retention_rule_replaced": False,
    }


def build_regime_reward_report(records: list[CandidateRecord]) -> dict[str, Any]:
    archive: list[CandidateRecord] = []
    evaluations: list[dict[str, Any]] = []
    for record in records:
        reward = compute_phase2_reward(record, archive)
        evaluations.append(
            {
                "candidate_id": record.candidate_id,
                "frontier_lane": record.frontier_lane,
                "label": record.label,
                **reward,
            }
        )
        if record.retained:
            archive.append(record)

    accepted = [item for item in evaluations if not item["rejected_for_policy_training"]]
    return {
        "reward_contract": "0.4*marginal_combination_ic + 0.4*max_regime_ic + 0.2*decay_resistance",
        "scope": "future_policy_training_signal_only",
        "does_not_replace_archive_dominance": True,
        "oos_hard_veto_used": False,
        "candidate_count": len(evaluations),
        "accepted_for_policy_training": len(accepted),
        "mean_reward": round(mean(item["reward"] for item in accepted), 6) if accepted else 0.0,
        "evaluations": evaluations[:32],
    }
