from __future__ import annotations

from typing import Any


def gate_result(*, name: str, passed: bool, metric_definition: dict[str, str], measured: dict[str, Any], thresholds: dict[str, Any], fail_consequence: str, stop_on_failure: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "metric_definition": metric_definition,
        "measured": measured,
        "thresholds": thresholds,
        "fail_consequence": fail_consequence,
        "stop_on_failure": stop_on_failure,
    }


def evaluate_m1(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "semantic_pair_margin": report["semantic_pair_margin"],
        "misordered_pair_rate": report["misordered_pair_rate"],
    }
    thresholds = {"semantic_pair_margin_min": 0.2, "misordered_pair_rate_max": 0.1}
    passed = measured["semantic_pair_margin"] >= 0.2 and measured["misordered_pair_rate"] <= 0.1
    return gate_result(
        name="M1",
        passed=passed,
        metric_definition=report.get("metric_definition", {}),
        measured=measured,
        thresholds=thresholds,
        fail_consequence="behavioral_navigation_claim_blocked",
    )


def evaluate_m2(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "novel_structure_ratio": report["novel_structure_ratio"],
        "from_scratch_trigger_observed": report["from_scratch_trigger_observed"],
    }
    thresholds = {"novel_structure_ratio_min": 0.25, "from_scratch_trigger_observed_min": 1}
    passed = measured["novel_structure_ratio"] >= 0.25 and measured["from_scratch_trigger_observed"] >= 1
    return gate_result(
        name="M2",
        passed=passed,
        metric_definition=report.get("metric_definition", {}),
        measured=measured,
        thresholds=thresholds,
        fail_consequence="open_search_claim_blocked",
    )


def evaluate_m3(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "level0_rejection_rate": report["levels"]["level_0_surrogate_ic"]["rejection_rate"],
        "false_negative_rate": report["false_negative_rate"],
        "full_evaluation_ratio": report["full_evaluation_ratio"],
        "fallback_status": report["fallback_status"],
    }
    thresholds = {
        "level0_rejection_rate_min": 0.15,
        "level0_rejection_rate_max": 0.8,
        "false_negative_rate_max": 0.1,
        "full_evaluation_ratio_max": 0.35,
    }
    passed = (
        thresholds["level0_rejection_rate_min"] <= measured["level0_rejection_rate"] <= thresholds["level0_rejection_rate_max"]
        and measured["false_negative_rate"] <= thresholds["false_negative_rate_max"]
        and measured["full_evaluation_ratio"] <= thresholds["full_evaluation_ratio_max"]
        and measured["fallback_status"] == "active"
    )
    return gate_result(
        name="M3",
        passed=passed,
        metric_definition={
            "level0_rejection_rate": "surrogate_rejected / total_candidates",
            "false_negative_rate": "good_candidates_rejected_early / audited_good_candidates",
            "full_evaluation_ratio": "full_eval_count / total_candidates",
        },
        measured=measured,
        thresholds=thresholds,
        fail_consequence="funnel_efficiency_claim_blocked",
    )


def evaluate_m4(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "coverage_gain": report["coverage_gain"],
        "quality_noninferiority": report["quality_noninferiority"],
    }
    thresholds = {"coverage_gain_min": 0.15, "quality_noninferiority_min": 0.0}
    passed = measured["coverage_gain"] >= 0.15 and measured["quality_noninferiority"] >= 0.0
    return gate_result(
        name="M4",
        passed=passed,
        metric_definition=report.get("metric_definition", {}),
        measured=measured,
        thresholds=thresholds,
        fail_consequence="superiority_over_random_search_claim_blocked",
    )


def evaluate_m5(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "oos_only_hard_veto_count": report["oos_only_hard_veto_count"],
        "regime_conditional_retention_rate": report["regime_conditional_retention_rate"],
        "channel_merge_leakage": report["channel_merge_leakage"],
    }
    thresholds = {
        "oos_only_hard_veto_count_max": 0,
        "regime_conditional_retention_rate_min": 0.01,
        "channel_merge_leakage_max": 0.0,
    }
    passed = (
        measured["oos_only_hard_veto_count"] == 0
        and measured["regime_conditional_retention_rate"] >= 0.01
        and measured["channel_merge_leakage"] == 0.0
    )
    return gate_result(
        name="M5",
        passed=passed,
        metric_definition=report.get("metric_definition", {}),
        measured=measured,
        thresholds=thresholds,
        fail_consequence="dual_channel_correctness_claim_blocked",
    )


def evaluate_m6(report: dict[str, Any]) -> dict[str, Any]:
    measured = {
        "transition_alignment_gain": report["transition_alignment_gain"],
        "transition_signal_stability": report["transition_signal_stability"],
    }
    thresholds = {"transition_alignment_gain_min": 0.1, "transition_signal_stability_min": 0.6}
    passed = (
        measured["transition_alignment_gain"] >= 0.1
        and measured["transition_signal_stability"] >= 0.6
    )
    return gate_result(
        name="M6",
        passed=passed,
        metric_definition=report.get("metric_definition", {}),
        measured=measured,
        thresholds=thresholds,
        fail_consequence="regime_transition_search_claim_blocked",
    )
