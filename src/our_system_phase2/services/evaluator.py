from __future__ import annotations

from statistics import mean
from typing import Any

from our_system_phase2.domain.models import CandidateRecord, make_candidate_id
from our_system_phase2.services.fingerprint import (
    behavioral_cell,
    min_distance_to_archive,
    validate_fingerprint_contract,
)
from our_system_phase2.services.variation import extract_structural_skeleton
from our_system_phase2.services.surrogates import (
    SurrogateFingerprintHead,
    SurrogateICHead,
)


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _ic_by_regime(fingerprint: dict[str, float]) -> dict[str, float]:
    return {
        "trending": _clip(fingerprint["ic_regime_trending"]),
        "mean_reverting": _clip(fingerprint["ic_regime_mean_reverting"]),
        "volatile": _clip(fingerprint["ic_regime_volatile"]),
        "low_vol": _clip(fingerprint["ic_regime_low_vol"]),
    }


def _ic_positive_coverage(ic_by_regime: dict[str, float]) -> float:
    return round(sum(1 for value in ic_by_regime.values() if value >= 0.5) / max(1, len(ic_by_regime)), 6)


def _label(ic_max: float, ic_positive_coverage: float, oos_stability: float) -> str:
    if ic_max >= 0.72 and ic_positive_coverage >= 0.5 and oos_stability >= 0.68:
        return "robust"
    if ic_max >= 0.58 and ic_positive_coverage >= 0.25:
        return "regime_conditional"
    return "weak"


def _oos_ic(*, short_ic: float, oos_stability: float, ic_positive_coverage: float) -> float:
    retention_factor = _clip(
        0.45
        + (oos_stability * 0.35)
        + (ic_positive_coverage * 0.2)
    )
    return _clip(short_ic * retention_factor)


class MultiFidelityEvaluator:
    def __init__(self) -> None:
        self.surrogate_fingerprint = SurrogateFingerprintHead()
        self.surrogate_ic = SurrogateICHead()
        self.funnel_stats = {
            "levels": {
                "level_0_surrogate_ic": {"evaluated_count": 0, "rejected_count": 0, "false_negative_count": 0},
                "level_1_short_window_ic": {"evaluated_count": 0, "rejected_count": 0},
                "level_2_regime_conditional_ic": {"evaluated_count": 0, "rejected_count": 0},
                "level_3_full_dual_channel": {"evaluated_count": 0, "rejected_count": 0},
            },
            "audit_overrides": {"real_replay_feedback_level0_review_count": 0},
            "surrogate_disable_protocol": {"disabled": False, "reason": None},
        }

    def _maybe_disable_surrogate(self) -> None:
        stats = self.funnel_stats["levels"]["level_0_surrogate_ic"]
        evaluated = stats["evaluated_count"]
        if evaluated < 6:
            return
        false_negative_rate = stats["false_negative_count"] / max(1, evaluated)
        if false_negative_rate > 0.3:
            self.funnel_stats["surrogate_disable_protocol"] = {
                "disabled": True,
                "reason": "false_negative_rate_above_threshold",
            }
            self.surrogate_ic.disabled = True

    def evaluate(
        self,
        *,
        expression: str,
        parent_candidate_id: str | None,
        source_mode: str,
        frontier_lane: str,
        round_index: int,
        archive: list[CandidateRecord],
        screening_context: dict[str, Any] | None = None,
    ) -> tuple[CandidateRecord, dict[str, Any]]:
        fingerprint_output = self.surrogate_fingerprint.predict(expression)
        validate_fingerprint_contract(fingerprint_output.fingerprint)
        ic_output = self.surrogate_ic.predict(expression=expression, fingerprint=fingerprint_output.fingerprint)

        level0 = self.funnel_stats["levels"]["level_0_surrogate_ic"]
        level0["evaluated_count"] += 1
        transition_asymmetry = abs(
            fingerprint_output.fingerprint["ic_at_bull_to_bear"] - fingerprint_output.fingerprint["ic_at_bear_to_bull"]
        )
        surrogate_gate_score = _clip(
            ic_output.quality_estimate
            - (ic_output.uncertainty * 0.45)
            - (transition_asymmetry * 0.1)
        )
        level0_raw_rejected = (not self.surrogate_ic.disabled) and surrogate_gate_score < 0.32
        real_replay_feedback_score = float((screening_context or {}).get("real_replay_feedback_score", 0.0) or 0.0)
        real_replay_feedback_reasons = list((screening_context or {}).get("real_replay_feedback_reasons", []) or [])
        level0_real_replay_feedback_review = (
            level0_raw_rejected
            and real_replay_feedback_score >= 0.04
            and (surrogate_gate_score + min(0.18, real_replay_feedback_score * 2.0)) >= 0.32
        )
        level0_rejected = level0_raw_rejected and not level0_real_replay_feedback_review
        if level0_real_replay_feedback_review:
            self.funnel_stats["audit_overrides"]["real_replay_feedback_level0_review_count"] += 1

        short_ic = _clip(
            (ic_output.quality_estimate * 0.58)
            + (fingerprint_output.fingerprint["momentum_tilt"] * 0.12)
            + (fingerprint_output.fingerprint["ic_regime_mean_reverting"] * 0.1)
            - (transition_asymmetry * 0.08)
        )
        level1 = self.funnel_stats["levels"]["level_1_short_window_ic"]
        if not level0_rejected:
            level1["evaluated_count"] += 1
        level1_rejected = not level0_rejected and short_ic < 0.56

        ic_by_regime = _ic_by_regime(fingerprint_output.fingerprint)
        ic_max = round(max(ic_by_regime.values()), 6)
        coverage = _ic_positive_coverage(ic_by_regime)
        level2 = self.funnel_stats["levels"]["level_2_regime_conditional_ic"]
        if not level0_rejected and not level1_rejected:
            level2["evaluated_count"] += 1
        level2_rejected = not level0_rejected and not level1_rejected and (ic_max < 0.58 or coverage < 0.25)

        oos_stability = _clip(
            (1.0 - abs(fingerprint_output.fingerprint["ic_at_bull_to_bear"] - fingerprint_output.fingerprint["ic_at_bear_to_bull"])) * 0.6
            + fingerprint_output.fingerprint["decay_halflife"] * 0.4
        )
        oos_ic = _oos_ic(
            short_ic=short_ic,
            oos_stability=oos_stability,
            ic_positive_coverage=coverage,
        )
        oos_degradation_ratio = _clip(oos_ic / max(short_ic, 1e-6))
        label = _label(ic_max, coverage, oos_stability)

        level3 = self.funnel_stats["levels"]["level_3_full_dual_channel"]
        full_evaluation_reached = not level0_rejected and not level1_rejected and not level2_rejected
        if full_evaluation_reached:
            level3["evaluated_count"] += 1

        if level0_rejected:
            level0["rejected_count"] += 1
            if ic_max >= 0.7 and coverage >= 0.5:
                level0["false_negative_count"] += 1
        if level1_rejected:
            level1["rejected_count"] += 1
        if level2_rejected:
            level2["rejected_count"] += 1

        self._maybe_disable_surrogate()
        archive_skeletons = {extract_structural_skeleton(item.expression) for item in archive}
        candidate_skeleton = extract_structural_skeleton(expression)
        novel_structure = candidate_skeleton not in archive_skeletons

        record = CandidateRecord(
            candidate_id=make_candidate_id(expression),
            expression=expression,
            parent_candidate_id=parent_candidate_id,
            source_mode=source_mode,
            frontier_lane=frontier_lane,
            fingerprint=fingerprint_output.fingerprint,
            surrogate_quality=ic_output.quality_estimate,
            surrogate_uncertainty=ic_output.uncertainty,
            short_ic=short_ic,
            ic_by_regime=ic_by_regime,
            ic_max=ic_max,
            ic_positive_coverage=coverage,
            oos_ic=oos_ic,
            oos_degradation_ratio=oos_degradation_ratio,
            oos_stability=oos_stability,
            label=label,
            min_behavior_distance=min_distance_to_archive(fingerprint_output.fingerprint, archive),
            novel_structure=novel_structure,
            retained=False,
            archive_cell=behavioral_cell(fingerprint_output.fingerprint),
            round_index=round_index,
            metadata={
                "full_evaluation_reached": full_evaluation_reached,
                "level0_rejected": level0_rejected,
                "level0_raw_rejected": level0_raw_rejected,
                "level0_real_replay_feedback_review": level0_real_replay_feedback_review,
                "real_replay_feedback_score": round(real_replay_feedback_score, 6),
                "real_replay_feedback_reasons": real_replay_feedback_reasons[:8],
                "level1_rejected": level1_rejected,
                "level2_rejected": level2_rejected,
                "fingerprint_uncertainty": fingerprint_output.uncertainty,
                "surrogate_disabled": self.surrogate_ic.disabled,
                "candidate_skeleton": candidate_skeleton,
                "skeleton_previously_seen": not novel_structure,
            },
        )
        details = {
            "surrogate_fingerprint": {
                "calibration_error": fingerprint_output.calibration_error,
                "uncertainty": fingerprint_output.uncertainty,
                "disabled": fingerprint_output.disabled,
                "monitored_dimensions": sorted(fingerprint_output.fingerprint.keys()),
            },
            "surrogate_ic": {
                "quality_estimate": ic_output.quality_estimate,
                "uncertainty": ic_output.uncertainty,
                "disabled": ic_output.disabled,
                "calibration_error": ic_output.calibration_error,
                "output_head": "surrogate_ic_head",
                "surrogate_gate_score": surrogate_gate_score,
                "level0_raw_rejected": level0_raw_rejected,
                "level0_real_replay_feedback_review": level0_real_replay_feedback_review,
                "real_replay_feedback_score": round(real_replay_feedback_score, 6),
                "real_replay_feedback_reasons": real_replay_feedback_reasons[:8],
            },
            "dual_channel": {
                "ic_by_regime": ic_by_regime,
                "ic_max": ic_max,
                "ic_positive_coverage": coverage,
                "oos_ic": oos_ic,
                "oos_degradation_ratio": oos_degradation_ratio,
                "oos_stability": oos_stability,
                "label": label,
                "transition_asymmetry": round(transition_asymmetry, 6),
            },
        }
        return record, details

    def build_funnel_statistics(self) -> dict[str, Any]:
        levels = {}
        for name, payload in self.funnel_stats["levels"].items():
            evaluated = payload["evaluated_count"]
            rejected = payload["rejected_count"]
            levels[name] = {
                **payload,
                "rejection_rate": round(rejected / max(1, evaluated), 6),
            }
        false_negative_rate = round(
            levels["level_0_surrogate_ic"]["false_negative_count"]
            / max(1, levels["level_0_surrogate_ic"]["evaluated_count"]),
            6,
        )
        fallback_status = "disabled" if self.funnel_stats["surrogate_disable_protocol"]["disabled"] else "active"
        if (
            0.15 <= levels["level_0_surrogate_ic"]["rejection_rate"] <= 0.8
            and false_negative_rate <= 0.1
            and fallback_status == "active"
        ):
            calibration = "PASS"
        else:
            calibration = "FAIL"
        return {
            "levels": levels,
            "full_evaluation_ratio": round(
                levels["level_3_full_dual_channel"]["evaluated_count"]
                / max(1, levels["level_0_surrogate_ic"]["evaluated_count"]),
                6,
            ),
            "false_negative_rate": false_negative_rate,
            "audit_overrides": dict(self.funnel_stats["audit_overrides"]),
            "fallback_status": fallback_status,
            "calibration_verdict": calibration,
            "surrogate_disable_protocol": dict(self.funnel_stats["surrogate_disable_protocol"]),
            "funnel_contract": {
                "level_0": "surrogate_ic",
                "level_1": "short_window_ic_60d",
                "level_2": "regime_conditional_ic",
                "level_3": "full_dual_channel_evaluation",
            },
        }
