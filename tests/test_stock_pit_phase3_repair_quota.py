from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from our_system_phase2.services.stock_pit_phase3_repair import (
    _ablation_budgets,
    _cluster_quota_select,
    _repair_aware_soft_quota_select,
)


def _row(candidate_id: str, expression: str, cluster: str = "cluster_a") -> dict:
    return {
        "candidate_id": candidate_id,
        "expression": expression,
        "pre_audit_return_corr_cluster": cluster,
        "mean_window_rank_ic": 0.02,
        "mean_window_long_sortino": 1.0,
        "mean_window_sortino": 1.0,
        "proof_variant": "cem_adaptive_grammar",
    }


def test_phase3b_budgets_are_explicit_and_sum_to_audit_budget() -> None:
    b2 = _ablation_budgets(64, "Phase3B_B2_direct_R0_quota_only")
    b3 = _ablation_budgets(64, "Phase3B_B3_repair_aware_soft_quota")
    assert b2 == {"r0_cem_led": 32, "ast_failure_aware_repair": 26, "replay_aware_residual": 3, "novelty_diagnostic": 3}
    assert b3 == b2
    assert sum(b2.values()) == 64


def test_direct_quota_rejections_are_logged_and_kept_as_repair_sources() -> None:
    events: list[dict] = []
    repair_sources: list[dict] = []
    rows = [
        _row("a", "CSRank(Mean($close,5))"),
        _row("b", "CSRank(Mean($open,5))"),
        _row("c", "CSRank(Mean($high,5))"),
    ]
    selected = _cluster_quota_select(
        rows,
        budget=3,
        policy="phase3_r0_cem_led",
        role_prefix="phase3_r0",
        bucket="r0_cem_led",
        max_per_return_corr_cluster=1,
        max_per_ast_cluster=10,
        seed="unit",
        quota_type="direct_r0_quota",
        quota_stage="direct_replay_pre_audit",
        quota_events=events,
        rejected_rows_for_repair=repair_sources,
        allow_rejected_as_repair_source=True,
    )
    assert len(selected) == 1
    assert selected[0]["quota_type"] == "direct_r0_quota"
    assert any(event["quota_reject_reason"] == "return_corr_cluster_cap" for event in events)
    assert len(repair_sources) == 2


def test_repair_aware_soft_quota_uses_child_stage_metadata() -> None:
    events: list[dict] = []
    rows = [
        {
            **_row("r1", "CSRank(Mean($close,5))", cluster="child_a"),
            "parent_signal_cluster_id": "parent_hot",
            "source_failure_reasons": "corr_duplicate|operator_pathology",
            "repair_policy": "operator_sanitize",
        },
        {
            **_row("r2", "CSRank(Mean($open,8))", cluster="child_b"),
            "parent_signal_cluster_id": "parent_hot",
            "source_failure_reasons": "corr_duplicate|operator_pathology",
            "repair_policy": "duplicate_escape",
        },
    ]
    selected = _repair_aware_soft_quota_select(
        rows,
        budget=2,
        policy="ast_failure_aware_repair",
        role_prefix="phase3_ast_repair",
        bucket="ast_failure_aware_repair",
        max_share_per_parent_cluster=0.35,
        max_per_child_cluster=1,
        seed="unit",
        quota_events=events,
    )
    assert len(selected) == 2
    assert all(row["quota_stage"] == "post_mutation_child_filter" for row in selected)
    assert all(row["provisional_child_cluster"] in {"child_a", "child_b"} for row in selected)
    assert any(event["quota_type"] == "repair_aware_soft_quota" for event in events)
