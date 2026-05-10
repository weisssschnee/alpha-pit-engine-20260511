from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from our_system_phase2.domain.models import CandidateRecord, make_candidate_id  # noqa: E402
from our_system_phase2.services.a5_parameterized_lane import (  # noqa: E402
    build_a5_real_parameterized_ledger,
    extract_a5_observed_windows,
    infer_real_data_windows,
)
from our_system_phase2.services.auto_long_only_replay import (  # noqa: E402
    _already_replayed_candidate_ids,
    _long_only_decision,
    _select_replay_records,
)
from our_system_phase2.services.ashare_search_adapter import (  # noqa: E402
    annotate_ledger_for_ashare,
    ashare_trading_contract,
    build_ashare_targeted_search_ledger,
)
from our_system_phase2.runtime.generation_run import (  # noqa: E402
    YIELD_FLOOR,
    _build_continuation_scale_decision,
    _distill_continuation_records,
    _select_best_budget,
    run_phase2_bootstrap_independence_precheck,
    run_phase2_budget_profile_comparison,
    run_phase2_discarded_space_probe,
    run_phase2_generation,
    run_phase2_generation_flow,
)
from our_system_phase2.runtime.prototype_run import (  # noqa: E402
    _apply_high_budget_quality_control,
    _apply_real_replay_feedback_allocation,
    _adaptive_behavior_cell,
    _archive_coverage_key,
    _coverage_refresh_candidate_pool,
    _coverage_refresh_target_for_lane,
    _ensure_adaptive_archive_cell,
    _new_cell_coverage,
    _refresh_score_lane_parents_for_unseen_variation,
    _target_aware_pre_screen,
    _target_behavior_from_cell,
    memory_duplicate_saturation,
    run_phase2_prototype,
)
from our_system_phase2.services.archive import PrototypeArchive, dominates  # noqa: E402
from our_system_phase2.services.bootstrap import Phase2BootstrapLayer  # noqa: E402
from our_system_phase2.services.discarded_shadow import build_discarded_space_shadow_report  # noqa: E402
from our_system_phase2.services.edge_reality import build_edge_reality_gate_report, evaluate_edge_reality  # noqa: E402
from our_system_phase2.services.evaluator import MultiFidelityEvaluator  # noqa: E402
from our_system_phase2.services.feature_algebra import (  # noqa: E402
    WINDOW_PRIOR,
    expand_derived_fields,
    operator_catalog_report,
    parse_derived_feature_name,
)
from our_system_phase2.services.field_encoder import (  # noqa: E402
    FIRST_BATCH_FIELDS,
    FieldEncoder,
    aggregate_field_profile,
    canonical_field_name,
    extract_field_names,
    field_redundancy_report,
)
from our_system_phase2.services.frontier import classify_frontiers, select_lane_parents  # noqa: E402
from our_system_phase2.services.fingerprint import (  # noqa: E402
    FINGERPRINT_DIMENSIONS,
    FORBIDDEN_FINGERPRINT_DIMENSIONS,
    behavioral_cell,
    build_behavioral_fingerprint,
    fingerprint_distance,
    semantic_pair_report,
    validate_fingerprint_contract,
)
from our_system_phase2.services.gates import evaluate_m1, evaluate_m2, evaluate_m3, evaluate_m4, evaluate_m5, evaluate_m6  # noqa: E402
from our_system_phase2.services.meta_policy import LaneOutcome, MetaSearchPolicy  # noqa: E402
from our_system_phase2.services.policy_network import (  # noqa: E402
    NewtonSchulzLowRankDecay,
    Phase2PolicyNetwork,
    StableRankMonitor,
    run_lord_smoke_step,
    run_lord_training_harness,
)
from our_system_phase2.services.regime_reward import compute_phase2_reward  # noqa: E402
from our_system_phase2.services.real_market_data import build_real_market_data_contract  # noqa: E402
from our_system_phase2.services.search_memory import (  # noqa: E402
    LocalSearchMemory,
    candidate_reward_proxy,
    enrich_search_memory_with_auto_long_only_replay,
    expression_memory_key,
    production_rule_key,
    replay_reward_proxy,
    skeleton_memory_key,
)
from our_system_phase2.services.search_core_v2 import (  # noqa: E402
    build_phase2_search_core_v2_plan,
    dedupe_scale_twins,
    scale_twin_key,
)
from our_system_phase2.services.search_core_v3 import (  # noqa: E402
    build_phase2_activation_gate_dataset,
    build_phase2_search_core_v3_plan,
    candidate_regime_profile,
)
from our_system_phase2.services.search_core_v4 import (  # noqa: E402
    activation_pattern_novelty,
    build_phase2_search_core_v4_plan,
    gate_separability_scores,
    pareto_front,
)
from our_system_phase2.services.search_core_v5 import (  # noqa: E402
    build_phase2_search_core_v5_plan,
    expected_hypervolume_improvement,
    hypervolume_improvement,
    monte_carlo_hypervolume,
)
from our_system_phase2.services.search_core_v6 import (  # noqa: E402
    build_phase2_search_core_v6_plan,
    correlated_posterior_samples,
    family_neighborhood_statistics,
    fast_screen_proxy_objective,
)
from our_system_phase2.services.search_core_v7 import (  # noqa: E402
    build_actual_neighborhood_objective_plan,
    build_local_formula_neighborhood_ledger,
)
from our_system_phase2.services.search_core_v8 import (  # noqa: E402
    build_natural_parameter_proposal_ledger,
    build_rank_quotient_proposal_ledger,
    extract_expression_window,
    infer_family_parameter_posterior,
    rank_validation_canonical_expression,
)
from our_system_phase2.services.search_core_v9 import (  # noqa: E402
    build_v9_continuous_proposal_ledger,
    infer_rank_quotient_posterior,
)
from our_system_phase2.services.search_core_v10 import (  # noqa: E402
    build_v10_local_continuous_ledger,
    infer_v10_local_surface,
)
from our_system_phase2.services.search_core_v11 import (  # noqa: E402
    build_v11_tplus1_momentum_heavy_ledger,
    infer_v11_tplus1_surface,
)
from our_system_phase2.services.search_core_v12 import (  # noqa: E402
    build_v12_tplus1_residual_ledger,
    infer_v12_tplus1_residual_surface,
)
from our_system_phase2.services.search_core_v13 import (  # noqa: E402
    build_v13_higher_order_momentum_ledger,
    infer_v13_higher_order_surface,
)
from our_system_phase2.services.search_core_v14 import (  # noqa: E402
    build_v14_curvature_volnorm_ledger,
    infer_v14_curvature_volnorm_surface,
)
from our_system_phase2.services.search_core_v15 import (  # noqa: E402
    build_v15_robust_denominator_ledger,
    infer_v15_robust_denominator_surface,
)
from our_system_phase2.services.search_core_v16 import (  # noqa: E402
    build_v16_quarter_floor_ledger,
    infer_v16_quarter_floor_surface,
    quarter_floor_stats,
)
from our_system_phase2.services.search_core_v17 import (  # noqa: E402
    build_v17_stable_denominator_ledger,
    infer_v17_stable_denominator_surface,
)
from our_system_phase2.services.search_core_v18 import (  # noqa: E402
    build_v18_compact_validation_ledger,
    build_v18_light_smoothing_ledger,
    infer_v18_light_smoothing_surface,
)
from our_system_phase2.services.search_core_v19 import (  # noqa: E402
    build_v19_compact_validation_ledger,
    build_v19_continuous_kernel_ledger,
    infer_v19_continuous_kernel_surface,
)
from our_system_phase2.services.search_core_v20 import (  # noqa: E402
    build_v20_activation_geometry_report,
    build_v20_activation_holdout_report,
    build_v21_rolling_activation_search_report,
)
from our_system_phase2.services.real_market_validation import (  # noqa: E402
    UnsupportedExpressionError,
    _load_market_panel,
    _limit_state_masks,
    _prepare_market_panel,
    _signal_evaluation_frame,
    audit_expression_panel_exposure_neutrality,
    batch_validate_candidate_ledger,
    build_real_replay_feedback_objective,
    build_validation_cost_report_from_ledger,
    evaluate_panel_expression,
    build_forward_shadow_watchlist,
    expression_validation_cost_report,
    strict_audit_expression_on_real_market_panel,
    validate_expression_on_loaded_panel,
    validate_expression_on_real_market_panel,
)
from our_system_phase2.services.stock_pit_compact_ensemble import (  # noqa: E402
    _select_sector_capped_codes,
    build_stock_pit_compact_top6_ensemble_report,
)
from our_system_phase2.services.stock_pit_forward_first_search import (  # noqa: E402
    QLIB_FORWARD_COMPATIBLE_FIELDS,
    build_stock_pit_forward_first_large_search_ledger,
    build_stock_pit_rx_typed_beam_search_ledger,
    build_stock_pit_forward_first_five_day_proof_gate,
    build_stock_pit_forward_first_replay_aware_shortlist,
)
from our_system_phase2.services.stock_pit_ledger_policy import (  # noqa: E402
    apply_stock_pit_ledger_selection_policy,
    apply_stock_pit_search_control_schedule,
    build_stock_pit_search_control_policy,
    diversified_top_candidates,
    stock_pit_terminal_reward_proxy,
)
from our_system_phase2.services.stock_pit_proof_suite import (  # noqa: E402
    run_stock_pit_fast_to_strict_calibration,
    run_stock_pit_search_ab_test,
    stock_pit_coverage_cluster_health,
    summarize_stock_pit_validation_report,
)
from our_system_phase2.services.stock_pit_chain_audit import build_stock_pit_chain_audit  # noqa: E402
from our_system_phase2.services.stock_pit_factor_library_optimizer import (  # noqa: E402
    build_stock_pit_factor_library_optimizer_report,
)
from our_system_phase2.services.stock_pit_successive_halving import run_stock_pit_successive_halving_validation  # noqa: E402
from our_system_phase2.services.stock_pit_ashare_state_search import (  # noqa: E402
    build_stock_pit_ashare_state_ledger,
)
from our_system_phase2.services.surrogates import SurrogateFingerprintHead, SurrogateICHead, extract_structural_features  # noqa: E402
from our_system_phase2.services.variation import (  # noqa: E402
    behavior_guided_crossover,
    canonicalize_expression_light,
    directed_variation,
    extract_structural_skeleton,
    enumerate_single_step_edits,
    expression_complexity,
    extract_structural_skeletons,
    generate_from_scratch,
    generate_from_scratch_from_archive,
    generate_distant_axis_recompositions,
    is_pathological_expression,
    novelty_saturation,
    phase2_native_ast_expansion,
)


def make_candidate(
    *,
    expression: str,
    ic_max: float,
    coverage: float,
    label: str,
    oos_stability: float,
    archive_cell: str = "cell-a",
) -> CandidateRecord:
    fingerprint = build_behavioral_fingerprint(expression)
    return CandidateRecord(
        candidate_id=f"cand-{abs(hash((expression, ic_max, coverage, label, oos_stability))) % 100000}",
        expression=expression,
        parent_candidate_id=None,
        source_mode="test",
        frontier_lane="score_frontier",
        fingerprint=fingerprint,
        surrogate_quality=ic_max,
        surrogate_uncertainty=0.1,
        short_ic=ic_max,
        ic_by_regime={"trending": ic_max, "mean_reverting": coverage, "volatile": coverage, "low_vol": coverage},
        ic_max=ic_max,
        ic_positive_coverage=coverage,
        oos_ic=min(ic_max, oos_stability),
        oos_degradation_ratio=max(0.0, ic_max - oos_stability),
        oos_stability=oos_stability,
        label=label,
        min_behavior_distance=0.5,
        novel_structure=False,
        retained=False,
        archive_cell=archive_cell,
        round_index=1,
        metadata={},
    )


class Phase2V21RuntimeTests(unittest.TestCase):
    def assertExpressionFieldsRegistered(self, expression: str) -> None:
        unknown_fields = [
            field
            for field in extract_field_names(expression)
            if canonical_field_name(field) is None
        ]
        self.assertEqual(unknown_fields, [], expression)

    def test_generation_continuation_seed_distillation_keeps_diverse_high_score_records(self) -> None:
        lanes = ["score_frontier", "novelty_frontier", "uncertainty_frontier", "bridge_frontier"]
        records: list[CandidateRecord] = []
        for index in range(12):
            record = make_candidate(
                expression=f"CSRank($close_{index})",
                ic_max=0.01 * index,
                coverage=0.5,
                label=f"record-{index}",
                oos_stability=0.02 * index,
                archive_cell=f"cell-{index % 4}",
            )
            record.candidate_id = f"cand-{index:02d}"
            record.frontier_lane = lanes[index % len(lanes)]
            record.min_behavior_distance = 0.01 * index
            records.append(record)

        distilled = _distill_continuation_records(records, max_records=5)

        self.assertEqual(len(distilled), 5)
        self.assertEqual(len({record.candidate_id for record in distilled}), 5)
        self.assertIn("cand-11", {record.candidate_id for record in distilled})
        self.assertGreaterEqual(len({record.frontier_lane for record in distilled}), 2)
        self.assertGreaterEqual(len({record.archive_cell for record in distilled}), 2)
        self.assertEqual(_distill_continuation_records(records, max_records=None), records)

        pathological = make_candidate(
            expression=f"CSRank($open){'0' * 3000}",
            ic_max=9.9,
            coverage=0.5,
            label="pathological",
            oos_stability=9.9,
        )
        pathological.candidate_id = "pathological"
        distilled_without_pathological = _distill_continuation_records(
            [*records, pathological],
            max_records=5,
        )
        self.assertNotIn("pathological", {record.candidate_id for record in distilled_without_pathological})

    def test_auto_long_only_replay_selection_filters_pathology_and_keeps_diversity(self) -> None:
        records = [
            {
                "candidate_id": "score",
                "expression": "CSRank($close)",
                "retained": True,
                "frontier_lane": "score_frontier",
                "archive_cell": "cell-a",
                "ic_max": 0.7,
                "oos_stability": 0.4,
                "min_behavior_distance": 0.2,
            },
            {
                "candidate_id": "bridge",
                "expression": "CSRank($open)",
                "retained": True,
                "frontier_lane": "bridge_frontier",
                "archive_cell": "cell-b",
                "ic_max": 0.6,
                "oos_stability": 0.4,
                "min_behavior_distance": 0.3,
            },
            {
                "candidate_id": "pathological",
                "expression": "CSRank($volume)" + ("0" * 3000),
                "retained": True,
                "frontier_lane": "bridge_frontier",
                "archive_cell": "cell-c",
                "ic_max": 9.9,
                "oos_stability": 9.9,
                "min_behavior_distance": 9.9,
            },
            {
                "candidate_id": "discarded",
                "expression": "CSRank($low)",
                "retained": False,
                "frontier_lane": "novelty_frontier",
                "archive_cell": "cell-d",
                "ic_max": 9.0,
            },
        ]

        selected, report = _select_replay_records(records, max_candidates=2)

        self.assertEqual(report["excluded_pathological_retained_count"], 1)
        self.assertEqual(report["selected_count"], 2)
        self.assertNotIn("pathological", {record["candidate_id"] for record in selected})
        self.assertIn("bridge_frontier", {record["frontier_lane"] for record in selected})

    def test_auto_long_only_replay_selection_prefers_not_yet_replayed_candidates(self) -> None:
        records = [
            {
                "candidate_id": "already-top",
                "expression": "CSRank($close)",
                "retained": True,
                "frontier_lane": "score_frontier",
                "archive_cell": "cell-a",
                "ic_max": 0.9,
                "oos_stability": 0.9,
                "min_behavior_distance": 0.9,
            },
            {
                "candidate_id": "fresh-bridge",
                "expression": "CSRank($open)",
                "retained": True,
                "frontier_lane": "bridge_frontier",
                "archive_cell": "cell-b",
                "ic_max": 0.5,
                "oos_stability": 0.5,
                "min_behavior_distance": 0.5,
            },
            {
                "candidate_id": "fresh-novelty",
                "expression": "CSRank($volume)",
                "retained": True,
                "frontier_lane": "novelty_frontier",
                "archive_cell": "cell-c",
                "ic_max": 0.4,
                "oos_stability": 0.4,
                "min_behavior_distance": 0.4,
            },
        ]

        selected, report = _select_replay_records(
            records,
            max_candidates=2,
            already_replayed_candidate_ids={"already-top"},
        )

        self.assertEqual(report["already_replayed_candidate_count"], 1)
        self.assertFalse(report["used_replayed_fallback"])
        self.assertNotIn("already-top", {record["candidate_id"] for record in selected})
        self.assertEqual({record["candidate_id"] for record in selected}, {"fresh-bridge", "fresh-novelty"})

    def test_auto_long_only_replay_excludes_family_replay_reports(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-replay-family-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        run_root = temp_root / "current" / "phase2-current"
        family_root = temp_root / "family"
        report_root = family_root / "cycle_001" / "phase2-family"
        report_root.mkdir(parents=True)
        replay_report = {
            "validation": {
                "evaluations": [
                    {"candidate_id": "already-family", "expression": "CSRank($close)"},
                    {"candidate_id": "another-family", "expression": "CSRank($open)"},
                ]
            }
        }
        (report_root / "auto_long_only_replay_report.json").write_text(
            json.dumps(replay_report),
            encoding="utf-8",
        )
        run_root.mkdir(parents=True)
        (run_root / "search_memory.json").write_text(
            json.dumps({"records": [], "replay_enrichment_paths": []}),
            encoding="utf-8",
        )

        replayed, report = _already_replayed_candidate_ids(run_root, [family_root])

        self.assertIn("already-family", replayed)
        self.assertIn("another-family", replayed)
        self.assertEqual(report["extra_root_count"], 1)
        self.assertEqual(report["report_path_count"], 1)

    def test_auto_long_only_replay_exclusion_is_dataset_role_scoped(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-replay-role-scope-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        run_root = temp_root / "current" / "phase2-current"
        family_root = temp_root / "family"
        sector_report_root = family_root / "cycle_001" / "phase2-sector"
        stock_report_root = family_root / "cycle_002" / "phase2-stock"
        sector_report_root.mkdir(parents=True)
        stock_report_root.mkdir(parents=True)
        sector_report = {
            "dataset_path": r"G:\Project_V7_Rotation\scripts\data\tdx_sector_data_p3_enhanced.csv",
            "validation": {"evaluations": [{"candidate_id": "sector-only"}]},
        }
        stock_report = {
            "dataset_path": r"G:\Project_V7_Rotation\scripts\data\phase2_stock_validation_slice_2026-04-27.parquet",
            "validation": {"evaluations": [{"candidate_id": "stock-only"}]},
        }
        (sector_report_root / "auto_long_only_replay_report.json").write_text(
            json.dumps(sector_report),
            encoding="utf-8",
        )
        (stock_report_root / "auto_long_only_replay_report.json").write_text(
            json.dumps(stock_report),
            encoding="utf-8",
        )
        run_root.mkdir(parents=True)
        (run_root / "search_memory.json").write_text(
            json.dumps({"records": [], "replay_enrichment_paths": []}),
            encoding="utf-8",
        )

        replayed, report = _already_replayed_candidate_ids(
            run_root,
            [family_root],
            expected_dataset_role="stock_pit_panel",
        )

        self.assertIn("stock-only", replayed)
        self.assertNotIn("sector-only", replayed)
        self.assertEqual(report["expected_dataset_role"], "stock_pit_panel")
        self.assertTrue(report["dataset_role_strict_replay_exclusion"])
        self.assertEqual(report["skipped_report_path_count"], 1)

    def test_auto_long_only_decision_prefers_tradable_long_only_candidates(self) -> None:
        self.assertEqual(
            _long_only_decision(
                {
                    "mean_window_rank_ic": 0.02,
                    "mean_window_long_return": 0.001,
                    "mean_window_long_sortino": 1.2,
                }
            ),
            "LONG_ONLY_REVIEW",
        )
        self.assertEqual(
            _long_only_decision(
                {
                    "mean_window_rank_ic": 0.02,
                    "mean_window_long_return": -0.001,
                    "mean_window_long_sortino": 2.0,
                }
            ),
            "REJECT_NON_POSITIVE_LONG_RETURN",
        )

    def test_real_market_data_contract_accepts_ohlcv_panel(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-market-"))
        try:
            panel_path = temp_root / "panel.csv"
            panel_path.write_text(
                "\n".join(
                    [
                        "date,open,high,low,close,amount,volume,code,return_1d,return_5d,return_20d",
                        "2025-01-02,10,11,9,10.5,1000000,10000,880001,0.01,0.03,0.05",
                        "2025-01-03,10.5,12,10,11.5,1200000,11000,880001,0.02,0.04,0.06",
                        "2025-01-02,20,21,19,20.2,2000000,20000,880002,-0.01,0.01,0.02",
                    ]
                ),
                encoding="utf-8",
            )

            contract = build_real_market_data_contract(panel_path, full_scan=True)

            self.assertTrue(contract["exists"])
            self.assertTrue(contract["can_start_real_validation"])
            self.assertEqual(contract["missing_required_columns"], [])
            self.assertEqual(contract["validation_period_months"], 3)
            self.assertEqual(contract["validation_period_policy"], "quarterly_3_month_windows")
            self.assertEqual(contract["full_scan"]["row_count"], 3)
            self.assertEqual(contract["full_scan"]["instrument_count"], 2)
            self.assertEqual(contract["full_scan"]["min_date"], "2025-01-02")
            self.assertEqual(contract["full_scan"]["max_date"], "2025-01-03")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_uses_quarterly_three_month_windows(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-01-09",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
                "2025-04-07",
                "2025-04-08",
            ]
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    code = f"88000{code_index + 1}"
                    close = (10.0 + code_index) * (1.0 + (0.002 * code_index * day_index))
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(1_000_000 + code_index * 10_000),
                                str(10_000 + code_index * 100),
                                code,
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel("CSRank($close)", path=panel_path)

            self.assertEqual(report["validation_period_months"], 3)
            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
            self.assertGreaterEqual(report["window_count"], 2)
            self.assertEqual([item["window"] for item in report["windows"][:2]], ["2025Q1", "2025Q2"])
            self.assertIsNotNone(report["mean_window_rank_ic"])
            self.assertIn("mean_window_sortino", report)
            self.assertGreater(report["row_count_after_signal_and_target"], 0)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_accepts_runtime_alias_and_relation_ops(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-01-09",
                "2025-01-10",
                "2025-01-13",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.03 * (code_index + 1))
                    volume = 10_000 + (day_index * (code_index + 1) ** 2 * 100)
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel("CSRank(Corr($close,$volt))", path=panel_path)

            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
            self.assertGreater(report["row_count_after_signal_and_target"], 0)
            self.assertEqual(report["windows"][0]["window"], "2025Q1")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_accepts_cfg_style_rolling_ops(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-cfg-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index in range(45):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.05 * (code_index + 1))
                    volume = 10_000 + (day_index + 1) * (code_index + 2) * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel(
                "CSRank(Add(Corr(WMA($close,3),Med($amount,5),3),Add(Kurt($high,5),Skew($low,5))))",
                path=panel_path,
            )

            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
            self.assertGreater(report["row_count_after_signal_and_target"], 0)
            self.assertEqual(report["unsupported_reason"] if "unsupported_reason" in report else None, None)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_accepts_zscore_and_mul(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-a5-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index in range(12):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.07 * (code_index + 1))
                    volume = 10_000 + (day_index + 2) * (code_index + 1) * 120
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel(
                "CSRank(Mul(ZScore(Mom($close,2)),ZScore(Div(Mean($volume,2),Mean($volume,5)))))",
                path=panel_path,
            )

            self.assertGreater(report["row_count_after_signal_and_target"], 0)
            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_loads_enhanced_feature_columns(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-enhanced-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,money_flow,crowding,rps_score,overnight"]
            for day_index in range(12):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.05 * (code_index + 1))
                    volume = 10_000 + (day_index + 1) * (code_index + 2) * 100
                    money_flow = (code_index - 2) * 0.1 + day_index * 0.01
                    crowding = code_index / 10.0
                    rps_score = 50 + code_index * 3 + day_index
                    overnight = 0.001 * (code_index - day_index)
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                                f"{money_flow:.6f}",
                                f"{crowding:.6f}",
                                f"{rps_score:.6f}",
                                f"{overnight:.6f}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel(
                "CSRank(Add($money_flow,Sub($rps_score,$crowding)))",
                path=panel_path,
            )

            self.assertGreater(report["row_count_after_signal_and_target"], 0)
            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_accepts_cross_sectional_residual(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-residual-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index in range(8):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.03 * code_index)
                    volume = 10_000 + (code_index + 1) * 100 + day_index * 30
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel(
                "CSRank(CSResidual(Mom($close,2),Mean($close,2)))",
                path=panel_path,
            )

            self.assertGreater(report["row_count_after_signal_and_target"], 0)
            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_panel_exposure_neutrality_probe_reports_group_demean_when_viable(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-exposure-neutrality-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,sector,money_flow,crowding,rps_score"]
            for day_index in range(12):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.04 * (code_index + 1))
                    volume = 10_000 + (code_index + 1) * 100 + day_index * 30
                    sector = "sector-a" if code_index < 4 else "sector-b"
                    money_flow = (code_index % 4) * 0.2 + day_index * 0.01
                    crowding = code_index / 10.0
                    rps_score = 50 + code_index + day_index
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{volume * close:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                sector,
                                f"{money_flow:.6f}",
                                f"{crowding:.6f}",
                                f"{rps_score:.6f}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = audit_expression_panel_exposure_neutrality(
                "CSRank(Add($money_flow,Sub($rps_score,$crowding)))",
                path=panel_path,
                horizon_days=1,
                execution_lag_days=1,
                signal_clock="after_open",
                recent_quarter_window_count=None,
                exposure_controls=("crowding", "rps_score"),
                min_group_size=3,
            )

            self.assertEqual(report["audit_type"], "panel_exposure_neutrality_probe")
            self.assertTrue(report["group_neutrality_diagnostics"]["neutralization_viable"])
            self.assertIsNotNone(report["group_neutral_metrics"])
            self.assertIsNotNone(report["exposure_residualized_metrics"])
            self.assertIn("crowding", report["exposure_controls_available"])
            self.assertEqual(report["gatekeeper_decision"], "HOLD_RESEARCH")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_panel_exposure_neutrality_probe_refuses_one_code_per_sector_claim(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-exposure-neutrality-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,sector,crowding"]
            for day_index in range(10):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.03 * (code_index + 1))
                    volume = 10_000 + (code_index + 1) * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{volume * close:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                f"board-{code_index + 1}",
                                f"{code_index / 10.0:.6f}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = audit_expression_panel_exposure_neutrality(
                "CSRank($crowding)",
                path=panel_path,
                horizon_days=1,
                execution_lag_days=1,
                recent_quarter_window_count=None,
                exposure_controls=("crowding",),
                min_group_size=2,
            )

            self.assertFalse(report["group_neutrality_diagnostics"]["neutralization_viable"])
            self.assertEqual(report["group_neutrality_diagnostics"]["reason"], "insufficient_codes_per_group")
            self.assertIsNone(report["group_neutral_metrics"])
            self.assertIn("true_group_neutralization_not_available_on_current_panel", report["blocker_flags"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_a5_real_parameterized_lane_does_not_depend_on_registered_window_prior(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-a5-param-"))
        try:
            panel_path = temp_root / "panel.csv"
            archive_root = temp_root / "a5"
            archive_root.mkdir()
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index in range(80):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(3):
                    close = 10.0 + code_index + day_index * 0.01
                    volume = 10_000 + day_index * 100 + code_index * 10
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            (archive_root / "sample.json").write_text(
                json.dumps(
                    {
                        "seed_reports": [
                            {"seed_formula": "rank(GAP(lag=7))"},
                            {"seed_formula": "rank(vol_ratio_11_37d)"},
                            {"seed_formula": "rank(MOM(close,13))"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            observed = extract_a5_observed_windows(archive_root)
            parameter_space = infer_real_data_windows(panel_path, archive_root=archive_root, target_window_count=5)
            ledger = build_a5_real_parameterized_ledger(
                path=panel_path,
                archive_root=archive_root,
                candidate_limit=12,
            )

            self.assertIn(7, observed)
            self.assertIn(13, observed)
            self.assertFalse(parameter_space["depends_on_registered_window_prior"])
            self.assertIn(7, parameter_space["windows"])
            self.assertIn(13, parameter_space["windows"])
            self.assertEqual(len(ledger["records"]), 12)
            self.assertFalse(ledger["parameter_space"]["depends_on_registered_window_prior"])
            self.assertTrue(any("ZScore" in record["expression"] for record in ledger["records"]))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_infer_real_data_windows_reads_parquet_stock_panel(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-window-parquet-"))
        try:
            panel_path = temp_root / "phase2_stock_validation_slice_test.parquet"
            archive_root = temp_root / "a5"
            archive_root.mkdir()
            rows = []
            for day_index in range(24):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(2):
                    rows.append(
                        {
                            "date": day,
                            "open": 10.0,
                            "high": 10.5,
                            "low": 9.5,
                            "close": 10.2,
                            "amount": 1000000.0,
                            "volume": 10000.0,
                            "code": f"sh60000{code_index}",
                        }
                    )
            pd.DataFrame(rows).to_parquet(panel_path)

            parameter_space = infer_real_data_windows(panel_path, archive_root=archive_root, target_window_count=4)

            self.assertEqual(parameter_space["dataset_path"], str(panel_path))
            self.assertEqual(parameter_space["trading_day_count"], 24)
            self.assertEqual(parameter_space["min_date"], "2025-01-02")
            self.assertIn(1, parameter_space["windows"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_search_core_v2_dedupes_scale_twins_without_merging_direction(self) -> None:
        candidates = [
            {
                "candidate_id": "normal-rank",
                "expression": "CSRank(Mom($close,9))",
                "recent_mean_rank_ic": 0.03,
            },
            {
                "candidate_id": "normal-z",
                "expression": "ZScore(Mom($close,9))",
                "recent_mean_rank_ic": 0.02,
            },
            {
                "candidate_id": "inverted-rank",
                "expression": "Neg(CSRank(Mom($close,9)))",
                "recent_mean_rank_ic": 0.01,
            },
        ]

        deduped, duplicates = dedupe_scale_twins(candidates)

        self.assertEqual(scale_twin_key("CSRank(Mom($close,9))"), scale_twin_key("ZScore(Mom($close,9))"))
        self.assertNotEqual(scale_twin_key("CSRank(Mom($close,9))"), scale_twin_key("Neg(CSRank(Mom($close,9)))"))
        self.assertEqual(len(deduped), 2)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["candidate_id"], "normal-z")

    def test_search_core_v2_promotes_family_representative_and_preserves_shadows(self) -> None:
        fast_report = {
            "ledger_path": "fast.json",
            "evaluations": [
                {
                    "candidate_id": "a5-gap9-rank",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "recent_mean_rank_ic": 0.039913,
                    "recent_positive_rank_ic_ratio": 1.0,
                    "mean_window_rank_ic": 0.039913,
                    "mean_window_sortino": 1.284742,
                    "promoted_to_full_history_review": True,
                    "estimated_validation_cost_score": 11.1,
                },
                {
                    "candidate_id": "a5-gap9-z",
                    "primitive_family": "a5_gap",
                    "expression": "ZScore(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "recent_mean_rank_ic": 0.039,
                    "recent_positive_rank_ic_ratio": 1.0,
                    "mean_window_rank_ic": 0.039,
                    "mean_window_sortino": 1.2,
                    "promoted_to_full_history_review": True,
                    "estimated_validation_cost_score": 11.1,
                },
                {
                    "candidate_id": "a5-devma3",
                    "primitive_family": "a5_dev_ma",
                    "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
                    "recent_mean_rank_ic": 0.020371,
                    "recent_positive_rank_ic_ratio": 0.75,
                    "mean_window_rank_ic": 0.020371,
                    "mean_window_sortino": 0.8,
                    "promoted_to_full_history_review": True,
                    "estimated_validation_cost_score": 11.08,
                },
            ],
        }
        full_report = {
            "ledger_path": "full.json",
            "evaluations": [
                {
                    "candidate_id": "a5-devma3",
                    "primitive_family": "a5_dev_ma",
                    "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
                    "recent_fast_screen_rank_ic": 0.020371,
                    "recent_mean_rank_ic": 0.006096,
                    "recent_positive_rank_ic_ratio": 0.75,
                    "mean_window_rank_ic": 0.02634,
                    "mean_window_sortino": 1.950278,
                    "passes_real_market_smoke": True,
                    "estimated_validation_cost_score": 11.08,
                },
                {
                    "candidate_id": "a5-gap9-rank",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "recent_fast_screen_rank_ic": 0.039913,
                    "recent_mean_rank_ic": 0.020976,
                    "recent_positive_rank_ic_ratio": 0.625,
                    "mean_window_rank_ic": 0.007526,
                    "mean_window_sortino": 0.41488,
                    "passes_real_market_smoke": True,
                    "estimated_validation_cost_score": 11.1,
                },
                {
                    "candidate_id": "a5-vol8",
                    "primitive_family": "a5_volatility",
                    "expression": "CSRank(Std($ret,8))",
                    "recent_fast_screen_rank_ic": 0.026044,
                    "recent_mean_rank_ic": 0.008398,
                    "recent_positive_rank_ic_ratio": 0.75,
                    "mean_window_rank_ic": 0.002522,
                    "mean_window_sortino": 1.145835,
                    "passes_real_market_smoke": True,
                    "estimated_validation_cost_score": 6.0,
                },
            ],
        }
        strict_report = {
            "candidate_id": "a5-devma3",
            "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
            "gatekeeper_decision": "HOLD_RESEARCH",
            "horizon_days": [2, 5, 10, 20, 60],
            "blocker_flags": [
                "sector_neutralization_not_run",
                "capacity_model_not_run",
                "survivorship_and_universe_policy_not_promotion_grade",
            ],
            "exposure_summary": {
                "amount": {"abs_mean_daily_rank_corr": 0.080158},
                "turnover_rate": {"abs_mean_daily_rank_corr": 0.309362},
            },
        }

        plan = build_phase2_search_core_v2_plan(
            fast_screen_report=fast_report,
            full_history_report=full_report,
            strict_audit_report=strict_report,
            total_promotion_limit=4,
        )

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V2")
        self.assertEqual(plan["promoted_representatives"][0]["candidate_id"], "a5-devma3")
        self.assertEqual(plan["family_budget"][0]["primitive_family"], "a5_dev_ma")
        self.assertEqual(plan["family_budget"][0]["budget_tier"], "audit_expand")
        self.assertEqual(plan["candidate_counts"]["scale_twin_duplicate_count"], 1)
        self.assertTrue(
            any(item["candidate_id"] == "a5-gap9-rank" for item in plan["shadow_queues"]["regime_local_shadow"])
        )
        self.assertTrue(
            any(item["candidate_id"] == "a5-vol8" for item in plan["shadow_queues"]["tail_economics_shadow"])
        )
        self.assertEqual(plan["shadow_queues"]["residualization_queue"][0]["candidate_id"], "a5-devma3")
        self.assertIn("turnover_rate_residualized_strict_audit", plan["next_audits"])
        self.assertIn("Mean($close,3)", plan["feature_store_precompute_plan"]["rolling_subexpressions"])

    def test_search_core_v3_scores_conditional_edge_without_requiring_broad_stability(self) -> None:
        candidate = {
            "candidate_id": "specialist-gap",
            "primitive_family": "a5_gap",
            "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
            "windows": [
                {"window": "2024Q1", "mean_rank_ic": 0.12, "long_short_sortino": 2.0, "rank_ic_hit_rate": 0.70},
                {"window": "2024Q2", "mean_rank_ic": 0.10, "long_short_sortino": 1.5, "rank_ic_hit_rate": 0.65},
                {"window": "2024Q3", "mean_rank_ic": 0.09, "long_short_sortino": 1.2, "rank_ic_hit_rate": 0.62},
                {"window": "2024Q4", "mean_rank_ic": 0.08, "long_short_sortino": 1.1, "rank_ic_hit_rate": 0.60},
                {"window": "2025Q1", "mean_rank_ic": -0.04, "long_short_sortino": -1.0, "rank_ic_hit_rate": 0.42},
                {"window": "2025Q2", "mean_rank_ic": -0.03, "long_short_sortino": -0.8, "rank_ic_hit_rate": 0.45},
                {"window": "2025Q3", "mean_rank_ic": 0.00, "long_short_sortino": -0.2, "rank_ic_hit_rate": 0.50},
                {"window": "2025Q4", "mean_rank_ic": -0.02, "long_short_sortino": -0.5, "rank_ic_hit_rate": 0.48},
            ],
        }

        profile = candidate_regime_profile(candidate)

        self.assertEqual(profile["edge_mode"], "regime_specialist_edge")
        self.assertLess(profile["positive_rank_ic_window_ratio"], 0.65)
        self.assertGreater(profile["specialist_score"], profile["broad_score"])
        self.assertEqual(profile["activation_windows"][0]["window"], "2024Q1")

    def test_search_core_v3_allocates_budget_to_specialist_family(self) -> None:
        full_report = {
            "ledger_path": "full.json",
            "evaluations": [
                {
                    "candidate_id": "specialist-gap",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "windows": [
                        {"window": "2024Q1", "mean_rank_ic": 0.12, "long_short_sortino": 2.0, "rank_ic_hit_rate": 0.70},
                        {"window": "2024Q2", "mean_rank_ic": 0.10, "long_short_sortino": 1.5, "rank_ic_hit_rate": 0.65},
                        {"window": "2024Q3", "mean_rank_ic": 0.09, "long_short_sortino": 1.2, "rank_ic_hit_rate": 0.62},
                        {"window": "2024Q4", "mean_rank_ic": 0.08, "long_short_sortino": 1.1, "rank_ic_hit_rate": 0.60},
                        {"window": "2025Q1", "mean_rank_ic": -0.04, "long_short_sortino": -1.0, "rank_ic_hit_rate": 0.42},
                        {"window": "2025Q2", "mean_rank_ic": -0.03, "long_short_sortino": -0.8, "rank_ic_hit_rate": 0.45},
                        {"window": "2025Q3", "mean_rank_ic": 0.00, "long_short_sortino": -0.2, "rank_ic_hit_rate": 0.50},
                        {"window": "2025Q4", "mean_rank_ic": -0.02, "long_short_sortino": -0.5, "rank_ic_hit_rate": 0.48},
                    ],
                },
                {
                    "candidate_id": "watch-amihud",
                    "primitive_family": "a5_amihud",
                    "expression": "CSRank(Mean(Div(Abs($ret),$amount),6))",
                    "windows": [
                        {"window": "2024Q1", "mean_rank_ic": 0.01, "long_short_sortino": 0.1, "rank_ic_hit_rate": 0.52},
                        {"window": "2024Q2", "mean_rank_ic": -0.01, "long_short_sortino": -0.1, "rank_ic_hit_rate": 0.49},
                        {"window": "2024Q3", "mean_rank_ic": 0.00, "long_short_sortino": 0.0, "rank_ic_hit_rate": 0.50},
                        {"window": "2024Q4", "mean_rank_ic": 0.01, "long_short_sortino": 0.1, "rank_ic_hit_rate": 0.51},
                    ],
                },
            ],
        }

        plan = build_phase2_search_core_v3_plan(full_history_report=full_report)

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V3_CONDITIONAL_EDGE_SEARCH")
        self.assertEqual(plan["family_allocation"][0]["primitive_family"], "a5_gap")
        self.assertEqual(plan["family_allocation"][0]["next_action"], "specialist_gate_search")
        self.assertEqual(plan["candidate_counts"]["specialist_candidate_count"], 1)
        self.assertEqual(plan["activation_map"][0]["candidate_id"], "specialist-gap")
        self.assertIn("train_lightweight_gate_to_predict_candidate_activation", plan["next_computational_tasks"])

    def test_search_core_v3_builds_activation_gate_dataset_from_market_states(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-v3-gate-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            for day_index in range(130):
                day = (date(2025, 1, 2) + timedelta(days=day_index)).isoformat()
                for code_index in range(4):
                    close = 10.0 + code_index + day_index * 0.03 * (code_index + 1)
                    volume = 10_000 + (day_index + 1) * (code_index + 1) * 20
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            plan = {
                "activation_map": [
                    {
                        "candidate_id": "specialist-gap",
                        "primitive_family": "a5_gap",
                        "edge_mode": "regime_specialist_edge",
                        "activation_windows": [
                            {"window": "2025Q1"},
                        ],
                    }
                ]
            }

            dataset = build_phase2_activation_gate_dataset(v3_plan=plan, market_panel_path=panel_path)

            self.assertEqual(dataset["candidate_count"], 1)
            self.assertGreaterEqual(dataset["window_count"], 2)
            self.assertGreater(dataset["activated_row_count"], 0)
            self.assertIn("market_return_state", dataset["feature_columns"])
            self.assertTrue(any(row["activated"] and row["window"] == "2025Q1" for row in dataset["rows"]))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_search_core_v4_preserves_novel_specialist_on_pareto_front(self) -> None:
        candidates = [
            {
                "candidate_id": "broad",
                "math_search_value": 0.3,
                "objective_vector": {
                    "edge_strength": 0.3,
                    "activation_novelty": 0.2,
                    "gate_separability": 0.2,
                    "low_fragility": 0.9,
                },
            },
            {
                "candidate_id": "specialist",
                "math_search_value": 0.28,
                "objective_vector": {
                    "edge_strength": 0.22,
                    "activation_novelty": 1.0,
                    "gate_separability": 0.8,
                    "low_fragility": 0.7,
                },
            },
            {
                "candidate_id": "dominated",
                "math_search_value": 0.1,
                "objective_vector": {
                    "edge_strength": 0.1,
                    "activation_novelty": 0.1,
                    "gate_separability": 0.1,
                    "low_fragility": 0.6,
                },
            },
        ]

        front = pareto_front(candidates)

        self.assertIn("broad", {item["candidate_id"] for item in front})
        self.assertIn("specialist", {item["candidate_id"] for item in front})
        self.assertNotIn("dominated", {item["candidate_id"] for item in front})

    def test_search_core_v4_computes_activation_novelty_and_gate_geometry(self) -> None:
        novelty = activation_pattern_novelty(
            {
                "gap": {"2025Q1", "2025Q2"},
                "momentum": {"2025Q1", "2025Q2"},
                "amihud": {"2024Q1"},
            }
        )
        dataset = {
            "feature_columns": ["market_return_state", "breadth_state"],
            "rows": [
                {"candidate_id": "gap", "activated": True, "market_return_state": 1.0, "breadth_state": 0.8},
                {"candidate_id": "gap", "activated": True, "market_return_state": 1.2, "breadth_state": 0.7},
                {"candidate_id": "gap", "activated": False, "market_return_state": -1.0, "breadth_state": 0.3},
                {"candidate_id": "gap", "activated": False, "market_return_state": -0.8, "breadth_state": 0.2},
            ],
        }
        geometry = gate_separability_scores(dataset)

        self.assertEqual(novelty["gap"], 0.0)
        self.assertEqual(novelty["amihud"], 1.0)
        self.assertGreater(geometry["gap"]["gate_separability_score"], 1.0)
        self.assertGreater(geometry["gap"]["feature_z_deltas"]["market_return_state"], 0.0)

    def test_search_core_v4_builds_mathematical_pareto_plan(self) -> None:
        v3_plan = {
            "activation_map": [
                {
                    "candidate_id": "broad-devma",
                    "activation_windows": [{"window": "2025Q1"}, {"window": "2025Q2"}],
                },
                {
                    "candidate_id": "specialist-gap",
                    "activation_windows": [{"window": "2024Q4"}],
                },
            ],
            "candidate_regime_profiles": [
                {
                    "candidate_id": "broad-devma",
                    "primitive_family": "a5_dev_ma",
                    "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
                    "edge_mode": "broad_edge",
                    "broad_score": 0.20,
                    "specialist_score": 0.24,
                    "fragility_score": 0.10,
                },
                {
                    "candidate_id": "specialist-gap",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "edge_mode": "regime_specialist_edge",
                    "broad_score": 0.05,
                    "specialist_score": 0.18,
                    "fragility_score": 0.25,
                },
            ],
        }
        dataset = {
            "feature_columns": ["market_return_state", "breadth_state"],
            "rows": [
                {
                    "candidate_id": "broad-devma",
                    "activated": True,
                    "window": "2025Q1",
                    "market_return_state": 0.2,
                    "breadth_state": 0.6,
                },
                {
                    "candidate_id": "broad-devma",
                    "activated": False,
                    "window": "2024Q1",
                    "market_return_state": 0.2,
                    "breadth_state": 0.6,
                },
                {
                    "candidate_id": "specialist-gap",
                    "activated": True,
                    "window": "2024Q4",
                    "market_return_state": -1.0,
                    "breadth_state": 0.2,
                },
                {
                    "candidate_id": "specialist-gap",
                    "activated": False,
                    "window": "2025Q1",
                    "market_return_state": 1.0,
                    "breadth_state": 0.8,
                },
            ],
        }

        plan = build_phase2_search_core_v4_plan(v3_plan=v3_plan, activation_gate_dataset=dataset)

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V4_MATHEMATICAL_SEARCH")
        self.assertEqual(plan["candidate_count"], 2)
        self.assertGreaterEqual(plan["pareto_front_count"], 1)
        self.assertIn("specialist-gap", plan["expansion_weights"])
        self.assertIn("activation_pattern_novelty", plan["mathematical_objectives"])

    def test_search_core_v5_hypervolume_improvement_separates_dominated_candidate(self) -> None:
        frontier = [
            {
                "objective_vector": {
                    "edge_strength": 0.20,
                    "activation_novelty": 0.40,
                    "gate_separability": 0.80,
                    "low_fragility": 0.90,
                }
            }
        ]
        frontier_vectors = np.array(
            [
                [
                    item["objective_vector"]["edge_strength"],
                    item["objective_vector"]["activation_novelty"],
                    item["objective_vector"]["gate_separability"],
                    item["objective_vector"]["low_fragility"],
                ]
                for item in frontier
            ],
            dtype=float,
        )
        dominated = np.array([0.10, 0.20, 0.60, 0.70], dtype=float)
        novel = np.array([0.18, 0.90, 0.85, 0.85], dtype=float)
        upper = np.array([0.35, 1.0, 1.2, 1.0], dtype=float)

        current_hv = monte_carlo_hypervolume(frontier_vectors, upper=upper, mc_points=2048, seed=7)
        dominated_gain = hypervolume_improvement(frontier_vectors, dominated, upper=upper, mc_points=2048, seed=7)
        novel_gain = hypervolume_improvement(frontier_vectors, novel, upper=upper, mc_points=2048, seed=7)

        self.assertGreater(current_hv, 0.0)
        self.assertEqual(dominated_gain, 0.0)
        self.assertGreater(novel_gain, 0.0)

    def test_search_core_v5_builds_expected_hypervolume_plan(self) -> None:
        v4_plan = {
            "pareto_front": [
                {
                    "candidate_id": "broad",
                    "objective_vector": {
                        "edge_strength": 0.24,
                        "activation_novelty": 0.30,
                        "gate_separability": 0.60,
                        "low_fragility": 0.92,
                    },
                },
                {
                    "candidate_id": "specialist",
                    "objective_vector": {
                        "edge_strength": 0.18,
                        "activation_novelty": 0.90,
                        "gate_separability": 1.10,
                        "low_fragility": 0.75,
                    },
                },
            ],
            "candidate_math_profiles": [
                {
                    "candidate_id": "broad",
                    "primitive_family": "a5_dev_ma",
                    "edge_mode": "broad_edge",
                    "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
                    "math_search_value": 0.50,
                    "fragility_score": 0.08,
                    "objective_vector": {
                        "edge_strength": 0.24,
                        "activation_novelty": 0.30,
                        "gate_separability": 0.60,
                        "low_fragility": 0.92,
                    },
                    "gate_geometry": {"active_count": 16},
                },
                {
                    "candidate_id": "specialist",
                    "primitive_family": "a5_gap",
                    "edge_mode": "regime_specialist_edge",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "math_search_value": 0.49,
                    "fragility_score": 0.20,
                    "objective_vector": {
                        "edge_strength": 0.18,
                        "activation_novelty": 0.90,
                        "gate_separability": 1.10,
                        "low_fragility": 0.75,
                    },
                    "gate_geometry": {"active_count": 3},
                },
            ],
        }

        plan = build_phase2_search_core_v5_plan(v4_plan=v4_plan, posterior_sample_count=24, hv_mc_points=1024, seed=11)

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V5_EXPECTED_HYPERVOLUME_SEARCH")
        self.assertEqual(plan["candidate_count"], 2)
        self.assertEqual(set(plan["expansion_weights"]), {"broad", "specialist"})
        self.assertGreaterEqual(plan["ehi_ranked_candidates"][0]["expected_hypervolume_improvement"], 0.0)
        self.assertIn("edge_strength", plan["objective_keys"])

    def test_search_core_v6_estimates_family_neighborhood_covariance(self) -> None:
        fast_report = {
            "evaluations": [
                {
                    "candidate_id": "gap-a",
                    "primitive_family": "a5_gap",
                    "recent_mean_rank_ic": 0.03,
                    "mean_window_rank_ic": 0.03,
                    "recent_positive_rank_ic_ratio": 1.0,
                    "recent_mean_sortino": 1.5,
                    "estimated_validation_cost_score": 10.0,
                },
                {
                    "candidate_id": "gap-b",
                    "primitive_family": "a5_gap",
                    "recent_mean_rank_ic": 0.01,
                    "mean_window_rank_ic": 0.01,
                    "recent_positive_rank_ic_ratio": 0.5,
                    "recent_mean_sortino": 0.0,
                    "estimated_validation_cost_score": 10.0,
                },
                {
                    "candidate_id": "mom-a",
                    "primitive_family": "a5_momentum",
                    "recent_mean_rank_ic": 0.02,
                    "mean_window_rank_ic": 0.02,
                    "recent_positive_rank_ic_ratio": 0.75,
                    "recent_mean_sortino": 0.5,
                    "estimated_validation_cost_score": 5.0,
                },
            ]
        }

        proxy = fast_screen_proxy_objective(fast_report["evaluations"][0])
        stats = family_neighborhood_statistics(fast_report)

        self.assertEqual(proxy.shape[0], 4)
        self.assertEqual(stats["a5_gap"]["sample_count"], 2)
        self.assertGreater(stats["a5_gap"]["mutation_radius"], 0.0)
        self.assertEqual(len(stats["a5_gap"]["proxy_covariance"]), 4)

    def test_search_core_v6_builds_correlated_posterior_plan(self) -> None:
        v5_plan = {
            "ehi_ranked_candidates": [
                {
                    "candidate_id": "gap",
                    "primitive_family": "a5_gap",
                    "edge_mode": "regime_specialist_edge",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                    "math_search_value": 0.6,
                    "fragility_score": 0.2,
                    "objective_vector": {
                        "edge_strength": 0.20,
                        "activation_novelty": 0.80,
                        "gate_separability": 1.00,
                        "low_fragility": 0.80,
                    },
                    "gate_geometry": {"active_count": 4},
                },
                {
                    "candidate_id": "dev",
                    "primitive_family": "a5_dev_ma",
                    "edge_mode": "broad_edge",
                    "expression": "CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))",
                    "math_search_value": 0.55,
                    "fragility_score": 0.08,
                    "objective_vector": {
                        "edge_strength": 0.18,
                        "activation_novelty": 0.30,
                        "gate_separability": 0.80,
                        "low_fragility": 0.92,
                    },
                    "gate_geometry": {"active_count": 8},
                },
            ]
        }
        fast_report = {
            "evaluations": [
                {
                    "candidate_id": "gap-a",
                    "primitive_family": "a5_gap",
                    "recent_mean_rank_ic": 0.04,
                    "mean_window_rank_ic": 0.04,
                    "recent_positive_rank_ic_ratio": 1.0,
                    "recent_mean_sortino": 1.5,
                    "estimated_validation_cost_score": 10.0,
                },
                {
                    "candidate_id": "gap-b",
                    "primitive_family": "a5_gap",
                    "recent_mean_rank_ic": 0.00,
                    "mean_window_rank_ic": 0.00,
                    "recent_positive_rank_ic_ratio": 0.25,
                    "recent_mean_sortino": -0.5,
                    "estimated_validation_cost_score": 12.0,
                },
                {
                    "candidate_id": "dev-a",
                    "primitive_family": "a5_dev_ma",
                    "recent_mean_rank_ic": 0.02,
                    "mean_window_rank_ic": 0.02,
                    "recent_positive_rank_ic_ratio": 0.75,
                    "recent_mean_sortino": 0.5,
                    "estimated_validation_cost_score": 8.0,
                },
                {
                    "candidate_id": "dev-b",
                    "primitive_family": "a5_dev_ma",
                    "recent_mean_rank_ic": 0.018,
                    "mean_window_rank_ic": 0.018,
                    "recent_positive_rank_ic_ratio": 0.70,
                    "recent_mean_sortino": 0.4,
                    "estimated_validation_cost_score": 8.0,
                },
            ]
        }

        plan = build_phase2_search_core_v6_plan(
            v5_plan=v5_plan,
            fast_screen_report=fast_report,
            posterior_sample_count=24,
            hv_mc_points=1024,
            seed=13,
        )
        gap_candidate = next(item for item in plan["correlated_ehi_ranked_candidates"] if item["candidate_id"] == "gap")
        samples = correlated_posterior_samples(
            gap_candidate,
            plan["neighborhood_statistics"]["a5_gap"],
            sample_count=8,
            seed=13,
        )

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V6_CORRELATED_POSTERIOR_SEARCH")
        self.assertEqual(plan["neighborhood_family_count"], 2)
        self.assertGreater(gap_candidate["mutation_radius"], 0.0)
        self.assertEqual(samples.shape, (8, 4))
        self.assertIn("gap", plan["expansion_weights"])

    def test_search_core_v7_builds_local_formula_neighborhood_ledger(self) -> None:
        v6_plan = {
            "run_id": "v6",
            "correlated_ehi_ranked_candidates": [
                {
                    "candidate_id": "vol",
                    "primitive_family": "a5_volatility",
                    "expression": "CSRank(Std($ret,8))",
                },
                {
                    "candidate_id": "mom",
                    "primitive_family": "a5_momentum",
                    "expression": "CSRank(Mom($close,9))",
                },
                {
                    "candidate_id": "gap",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))",
                },
            ],
        }

        ledger = build_local_formula_neighborhood_ledger(v6_plan=v6_plan, top_family_count=3)

        self.assertEqual(ledger["record_count"], 18)
        self.assertTrue(any(record["primitive_family"] == "a5_volatility" for record in ledger["records"]))
        self.assertTrue(any("Mom($close,9)" in record["expression"] for record in ledger["records"]))
        self.assertTrue(any("Delay($close,9)" in record["expression"] for record in ledger["records"]))

    def test_search_core_v7_builds_actual_objective_covariance_from_validation_report(self) -> None:
        validation_report = {
            "ledger_path": "local.json",
            "evaluations": [
                {
                    "candidate_id": "vol-8",
                    "primitive_family": "a5_volatility",
                    "expression": "CSRank(Std($ret,8))",
                    "windows": [
                        {"window": "2025Q1", "mean_rank_ic": 0.04, "long_short_sortino": 1.0, "rank_ic_hit_rate": 0.6},
                        {"window": "2025Q2", "mean_rank_ic": 0.03, "long_short_sortino": 0.8, "rank_ic_hit_rate": 0.58},
                        {"window": "2025Q3", "mean_rank_ic": -0.01, "long_short_sortino": -0.2, "rank_ic_hit_rate": 0.48},
                        {"window": "2025Q4", "mean_rank_ic": 0.02, "long_short_sortino": 0.5, "rank_ic_hit_rate": 0.55},
                    ],
                },
                {
                    "candidate_id": "vol-9",
                    "primitive_family": "a5_volatility",
                    "expression": "CSRank(Std($ret,9))",
                    "windows": [
                        {"window": "2025Q1", "mean_rank_ic": 0.02, "long_short_sortino": 0.6, "rank_ic_hit_rate": 0.56},
                        {"window": "2025Q2", "mean_rank_ic": 0.01, "long_short_sortino": 0.2, "rank_ic_hit_rate": 0.52},
                        {"window": "2025Q3", "mean_rank_ic": -0.02, "long_short_sortino": -0.4, "rank_ic_hit_rate": 0.46},
                        {"window": "2025Q4", "mean_rank_ic": 0.01, "long_short_sortino": 0.1, "rank_ic_hit_rate": 0.51},
                    ],
                },
            ],
        }
        activation_dataset = {
            "feature_columns": ["market_return_state"],
            "rows": [
                {"candidate_id": "vol-8", "activated": True, "window": "2025Q1", "market_return_state": 1.0},
                {"candidate_id": "vol-8", "activated": False, "window": "2025Q3", "market_return_state": -1.0},
                {"candidate_id": "vol-9", "activated": True, "window": "2025Q1", "market_return_state": 0.8},
                {"candidate_id": "vol-9", "activated": False, "window": "2025Q3", "market_return_state": -0.8},
            ],
        }

        plan = build_actual_neighborhood_objective_plan(
            validation_report=validation_report,
            activation_gate_dataset=activation_dataset,
        )

        self.assertEqual(plan["decision"], "CONTINUE_PHASE2_SEARCH_CORE_V7_ACTUAL_OBJECTIVE_COVARIANCE")
        self.assertEqual(plan["candidate_count"], 2)
        self.assertEqual(plan["family_actual_covariance"][0]["primitive_family"], "a5_volatility")
        self.assertEqual(plan["family_actual_covariance"][0]["sample_count"], 2)
        self.assertGreaterEqual(plan["pareto_front_count"], 1)

    def test_search_core_v8_infers_natural_parameter_posterior_from_objective_values(self) -> None:
        actual_plan = {
            "run_id": "actual",
            "actual_objective_profiles": [
                {
                    "candidate_id": "gap-7",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,7)),Delay($close,7)))",
                    "math_search_value": 0.30,
                },
                {
                    "candidate_id": "gap-10",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,10)),Delay($close,10)))",
                    "math_search_value": 0.60,
                },
                {
                    "candidate_id": "gap-11",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,11)),Delay($close,11)))",
                    "math_search_value": 0.59,
                },
                {
                    "candidate_id": "gap-14",
                    "primitive_family": "a5_gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,14)),Delay($close,14)))",
                    "math_search_value": 0.35,
                },
            ],
        }

        posterior = infer_family_parameter_posterior(actual_plan)
        family = posterior["family_parameter_posteriors"][0]

        self.assertEqual(extract_expression_window(actual_plan["actual_objective_profiles"][1]["expression"]), 10)
        self.assertEqual(family["primitive_family"], "a5_gap")
        self.assertGreater(family["weighted_window_mean"], 9.0)
        self.assertLess(family["weighted_window_mean"], 12.0)
        self.assertEqual(family["best_window"], 10)

    def test_search_core_v8_builds_natural_parameter_proposal_ledger(self) -> None:
        actual_plan = {
            "run_id": "actual",
            "actual_objective_profiles": [
                {
                    "candidate_id": "mom-8",
                    "primitive_family": "a5_momentum",
                    "expression": "CSRank(Mom($close,8))",
                    "math_search_value": 0.40,
                },
                {
                    "candidate_id": "mom-11",
                    "primitive_family": "a5_momentum",
                    "expression": "CSRank(Mom($close,11))",
                    "math_search_value": 0.60,
                },
                {
                    "candidate_id": "mom-14",
                    "primitive_family": "a5_momentum",
                    "expression": "CSRank(Mom($close,14))",
                    "math_search_value": 0.55,
                },
            ],
        }

        ledger = build_natural_parameter_proposal_ledger(
            actual_objective_plan=actual_plan,
            max_windows_per_family=5,
            include_structural_variants=True,
        )

        self.assertGreaterEqual(ledger["record_count"], 5)
        self.assertTrue(any(record["proposal_kind"] == "posterior_window" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "momentum_acceleration" for record in ledger["records"]))

    def test_search_core_v8_rank_quotient_dedupes_monotone_validation_twins(self) -> None:
        self.assertEqual(
            rank_validation_canonical_expression("ZScore(Mom($close,9))"),
            "RankEquivalent(Mom($close,9))",
        )
        self.assertEqual(
            rank_validation_canonical_expression("CSRank(Mom($close,9))"),
            "RankEquivalent(Mom($close,9))",
        )
        ledger = {
            "run_id": "natural",
            "records": [
                {
                    "candidate_id": "rank",
                    "expression": "CSRank(Mom($close,9))",
                    "retained": True,
                },
                {
                    "candidate_id": "zscore",
                    "expression": "ZScore(Mom($close,9))",
                    "retained": True,
                },
                {
                    "candidate_id": "interaction",
                    "expression": "CSRank(Mul(ZScore(Mom($close,9)),ZScore(Std($ret,4))))",
                    "retained": True,
                },
            ],
        }

        quotient = build_rank_quotient_proposal_ledger(ledger)

        self.assertEqual(quotient["source_record_count"], 3)
        self.assertEqual(quotient["record_count"], 2)
        self.assertEqual(quotient["dropped_rank_equivalent_count"], 1)
        self.assertEqual(
            quotient["dropped_rank_equivalent_records"][0]["drop_reason"],
            "rank_validation_monotone_equivalent_duplicate",
        )

    def test_search_core_v9_infers_rank_quotient_posterior(self) -> None:
        full_history = {
            "source_run_id": "full",
            "evaluations": [
                {
                    "candidate_id": "mom-rank",
                    "expression": "CSRank(Mom($close,12))",
                    "primitive_family": "a5_momentum",
                    "window": 12,
                    "mean_window_rank_ic": 0.02,
                    "mean_window_sortino": 0.8,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mom-z",
                    "expression": "ZScore(Mom($close,12))",
                    "primitive_family": "a5_momentum",
                    "window": 12,
                    "mean_window_rank_ic": 0.02,
                    "mean_window_sortino": 0.8,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "gap",
                    "expression": "CSRank(Div(Sub($open,Delay($close,11)),Delay($close,11)))",
                    "primitive_family": "a5_gap",
                    "window": 11,
                    "mean_window_rank_ic": 0.012,
                    "mean_window_sortino": 0.6,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        posterior = infer_rank_quotient_posterior(full_history_report=full_history)

        self.assertEqual(posterior["full_history_evaluation_count"], 3)
        self.assertEqual(posterior["full_history_quotient_count"], 2)
        self.assertEqual(posterior["full_history_rank_duplicate_count"], 1)
        self.assertEqual(posterior["family_posteriors"][0]["primitive_family"], "a5_momentum")

    def test_search_core_v9_builds_continuous_mix_ledger_without_rank_twins(self) -> None:
        full_history = {
            "source_run_id": "full",
            "evaluations": [
                {
                    "candidate_id": "mom12",
                    "expression": "CSRank(Mom($close,12))",
                    "primitive_family": "a5_momentum",
                    "window": 12,
                    "mean_window_rank_ic": 0.02,
                    "mean_window_sortino": 0.8,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mom11",
                    "expression": "CSRank(Mom($close,11))",
                    "primitive_family": "a5_momentum",
                    "window": 11,
                    "mean_window_rank_ic": 0.018,
                    "mean_window_sortino": 0.9,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "gap12",
                    "expression": "CSRank(Div(Sub($open,Delay($close,12)),Delay($close,12)))",
                    "primitive_family": "a5_gap",
                    "window": 12,
                    "mean_window_rank_ic": 0.014,
                    "mean_window_sortino": 0.6,
                    "recent_mean_rank_ic": 0.01,
                    "passes_real_market_smoke": True,
                },
            ],
        }
        fast_screen = {
            "evaluations": [
                {
                    "candidate_id": "vol11",
                    "expression": "CSRank(Std($ret,11))",
                    "primitive_family": "a5_volatility",
                    "window": 11,
                    "mean_window_rank_ic": 0.029,
                    "mean_window_sortino": 1.4,
                    "recent_mean_rank_ic": 0.029,
                    "fast_screen_decision": "needs_full_history_review",
                    "passes_real_market_smoke": False,
                }
            ]
        }

        ledger = build_v9_continuous_proposal_ledger(
            full_history_report=full_history,
            fast_screen_report=fast_screen,
            max_windows_per_family=4,
        )
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "posterior_continuous_mix_weight" for record in ledger["records"]))
        self.assertTrue(any(record["frontier_lane"] == "search_core_v9_recent_regime_shadow" for record in ledger["records"]))

    def test_search_core_v10_infers_local_continuous_surface_from_tradable_results(self) -> None:
        report = {
            "experiment_id": "tradable",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "evaluations": [
                {
                    "candidate_id": "mix-a",
                    "proposal_kind": "posterior_continuous_mix_weight",
                    "momentum_weight": 0.46,
                    "gap_weight": 0.54,
                    "momentum_window": 10,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.023,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix-b",
                    "proposal_kind": "posterior_continuous_mix_weight",
                    "momentum_weight": 0.56,
                    "gap_weight": 0.44,
                    "momentum_window": 9,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.021,
                    "mean_window_sortino": 1.0,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "gap",
                    "proposal_kind": "rank_quotient_posterior_window",
                    "primitive_family": "a5_gap",
                    "window": 9,
                    "mean_window_rank_ic": 0.026,
                    "mean_window_sortino": 1.0,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        surface = infer_v10_local_surface(report)

        self.assertEqual(surface["mix_sample_count"], 2)
        self.assertGreater(surface["local_momentum_weight_mean"], 0.45)
        self.assertLess(surface["local_momentum_weight_mean"], 0.57)
        self.assertTrue(surface["momentum_weight_grid"])
        self.assertEqual(surface["top_window_pairs"][0]["momentum_window"], 10)

    def test_search_core_v10_builds_rank_quotient_local_ledger(self) -> None:
        report = {
            "experiment_id": "tradable",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "evaluations": [
                {
                    "candidate_id": "mix-a",
                    "proposal_kind": "posterior_continuous_mix_weight",
                    "momentum_weight": 0.46,
                    "gap_weight": 0.54,
                    "momentum_window": 10,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.023,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix-b",
                    "proposal_kind": "posterior_continuous_mix_weight",
                    "momentum_weight": 0.56,
                    "gap_weight": 0.44,
                    "momentum_window": 9,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.021,
                    "mean_window_sortino": 1.0,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "vol",
                    "proposal_kind": "recent_shadow_rank_quotient",
                    "primitive_family": "a5_volatility",
                    "window": 10,
                    "mean_window_rank_ic": 0.024,
                    "mean_window_sortino": 2.0,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        ledger = build_v10_local_continuous_ledger(report, top_pair_count=2)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "local_surface_continuous_mix_weight" for record in ledger["records"]))
        self.assertTrue(any(record["frontier_lane"] == "search_core_v10_recent_regime_shadow" for record in ledger["records"]))

    def test_search_core_v11_extends_tplus1_momentum_heavy_surface(self) -> None:
        report = {
            "experiment_id": "tplus1-tradable",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mix-a",
                    "proposal_kind": "local_surface_continuous_mix_weight",
                    "momentum_weight": 0.681,
                    "gap_weight": 0.319,
                    "momentum_window": 9,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.0215,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix-b",
                    "proposal_kind": "local_surface_continuous_mix_weight",
                    "momentum_weight": 0.608,
                    "gap_weight": 0.392,
                    "momentum_window": 10,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.019,
                    "mean_window_sortino": 0.8,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mom",
                    "proposal_kind": "local_anchor_rank_quotient",
                    "primitive_family": "a5_momentum",
                    "window": 9,
                    "mean_window_rank_ic": 0.0237,
                    "mean_window_sortino": 0.5,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        surface = infer_v11_tplus1_surface(report)

        self.assertTrue(surface["best_at_upper_edge"])
        self.assertGreater(max(surface["momentum_weight_grid"]), 0.681)
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v11_builds_deduped_tplus1_momentum_heavy_ledger(self) -> None:
        report = {
            "experiment_id": "tplus1-tradable",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mix-a",
                    "proposal_kind": "local_surface_continuous_mix_weight",
                    "momentum_weight": 0.681,
                    "gap_weight": 0.319,
                    "momentum_window": 9,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.0215,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix-b",
                    "proposal_kind": "local_surface_continuous_mix_weight",
                    "momentum_weight": 0.608,
                    "gap_weight": 0.392,
                    "momentum_window": 10,
                    "gap_window": 9,
                    "mean_window_rank_ic": 0.019,
                    "mean_window_sortino": 0.8,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        ledger = build_v11_tplus1_momentum_heavy_ledger(report, top_pair_count=2)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "tplus1_momentum_heavy_mix_weight" for record in ledger["records"]))
        self.assertTrue(any(record["frontier_lane"] == "search_core_v11_tplus1_volatility_shadow" for record in ledger["records"]))
        self.assertEqual(ledger["surface_report"]["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v12_inferrs_natural_residual_surface_from_tplus1_results(self) -> None:
        report = {
            "experiment_id": "v11-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mom8",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_anchor_rank_quotient",
                    "window": 8,
                    "mean_window_rank_ic": 0.027,
                    "mean_window_sortino": 1.3,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mom9",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_anchor_rank_quotient",
                    "window": 9,
                    "mean_window_rank_ic": 0.024,
                    "mean_window_sortino": 0.5,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix",
                    "primitive_family": "a5_momentum+a5_gap",
                    "proposal_kind": "tplus1_momentum_heavy_mix_weight",
                    "momentum_window": 9,
                    "gap_window": 9,
                    "momentum_weight": 0.92,
                    "gap_weight": 0.08,
                    "mean_window_rank_ic": 0.023,
                    "mean_window_sortino": 0.4,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        surface = infer_v12_tplus1_residual_surface(report)

        self.assertEqual(surface["top_momentum_anchor_window"], 8)
        self.assertIn(7, surface["momentum_window_grid"])
        self.assertIn(9, surface["momentum_window_grid"])
        self.assertIn(0.08, surface["gap_residual_weight_grid"])
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v12_builds_deduped_natural_residual_ledger(self) -> None:
        report = {
            "experiment_id": "v11-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mom8",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_anchor_rank_quotient",
                    "window": 8,
                    "mean_window_rank_ic": 0.027,
                    "mean_window_sortino": 1.3,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mix",
                    "primitive_family": "a5_momentum+a5_gap",
                    "proposal_kind": "tplus1_momentum_heavy_mix_weight",
                    "momentum_window": 9,
                    "gap_window": 9,
                    "momentum_weight": 0.92,
                    "gap_weight": 0.08,
                    "mean_window_rank_ic": 0.023,
                    "mean_window_sortino": 0.4,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        ledger = build_v12_tplus1_residual_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "tplus1_natural_momentum_anchor" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "tplus1_natural_gap_residual_weight" for record in ledger["records"]))
        self.assertTrue(any(record["frontier_lane"] == "search_core_v12_tplus1_volatility_shadow" for record in ledger["records"]))

    def test_search_core_v13_inferrs_higher_order_surface_from_momentum8(self) -> None:
        report = {
            "experiment_id": "v12-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mom8",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_natural_momentum_anchor",
                    "window": 8,
                    "mean_window_rank_ic": 0.027,
                    "mean_window_sortino": 1.3,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "mom9",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_natural_momentum_anchor",
                    "window": 9,
                    "mean_window_rank_ic": 0.024,
                    "mean_window_sortino": 0.5,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        surface = infer_v13_higher_order_surface(report)

        self.assertEqual(surface["center_momentum_window"], 8)
        self.assertEqual(surface["momentum_window_grid"], [7, 8, 9])
        self.assertIn(4, surface["short_window_grid"])
        self.assertIn(10, surface["long_window_grid"])
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v13_builds_higher_order_momentum_ledger(self) -> None:
        report = {
            "experiment_id": "v12-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "mom8",
                    "primitive_family": "a5_momentum",
                    "proposal_kind": "tplus1_natural_momentum_anchor",
                    "window": 8,
                    "mean_window_rank_ic": 0.027,
                    "mean_window_sortino": 1.3,
                    "passes_real_market_smoke": True,
                }
            ],
        }

        ledger = build_v13_higher_order_momentum_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "higher_order_smoothed_momentum" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "higher_order_momentum_acceleration" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "higher_order_momentum_curvature" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "higher_order_return_skew_shadow" for record in ledger["records"]))

    def test_search_core_v14_inferrs_curvature_and_volnorm_manifold(self) -> None:
        report = {
            "experiment_id": "v13-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "curv9",
                    "proposal_kind": "higher_order_momentum_curvature",
                    "primitive_family": "a5_momentum_curvature",
                    "window": 9,
                    "slope_lag": 1,
                    "mean_window_rank_ic": 0.041,
                    "mean_window_sortino": 0.9,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "vol9-8",
                    "proposal_kind": "higher_order_vol_normalized_momentum",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "window": 9,
                    "volatility_window": 8,
                    "mean_window_rank_ic": 0.040,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        surface = infer_v14_curvature_volnorm_surface(report)

        self.assertEqual(surface["curvature_window_grid"], [8, 9, 10])
        self.assertIn("mean_signal", surface["curvature_transform_grid"])
        self.assertIn("mean_abs_ret", surface["volnorm_denominator_grid"])
        self.assertIn(8, surface["volnorm_denominator_window_grid"])
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v14_builds_curvature_and_volnorm_ledger(self) -> None:
        report = {
            "experiment_id": "v13-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "curv9",
                    "proposal_kind": "higher_order_momentum_curvature",
                    "primitive_family": "a5_momentum_curvature",
                    "window": 9,
                    "slope_lag": 1,
                    "mean_window_rank_ic": 0.041,
                    "mean_window_sortino": 0.9,
                    "passes_real_market_smoke": True,
                },
                {
                    "candidate_id": "vol9-8",
                    "proposal_kind": "higher_order_vol_normalized_momentum",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "window": 9,
                    "volatility_window": 8,
                    "mean_window_rank_ic": 0.040,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                },
            ],
        }

        ledger = build_v14_curvature_volnorm_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["proposal_kind"] == "v14_momentum_curvature_manifold" for record in ledger["records"]))
        self.assertTrue(any(record["proposal_kind"] == "v14_vol_normalized_momentum_manifold" for record in ledger["records"]))
        self.assertTrue(any(record.get("base_transform") == "wma_price" for record in ledger["records"]))
        self.assertTrue(any(record.get("denominator_family") == "mean_abs_ret" for record in ledger["records"]))

    def test_search_core_v15_inferrs_robust_denominator_surface(self) -> None:
        report = {
            "experiment_id": "v14-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "volnorm",
                    "proposal_kind": "v14_vol_normalized_momentum_manifold",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "window": 9,
                    "numerator_window": 9,
                    "denominator_window": 6,
                    "denominator_family": "mean_abs_ret",
                    "mean_window_rank_ic": 0.042,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                }
            ],
        }

        surface = infer_v15_robust_denominator_surface(report)

        self.assertEqual(surface["numerator_window_grid"], [8, 9, 10])
        self.assertEqual(surface["denominator_window_grid"], [5, 6, 7])
        self.assertIn("med_abs_ret", surface["denominator_family_grid"])
        self.assertIn("wma_downside_abs_ret", surface["denominator_family_grid"])
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v15_builds_robust_denominator_ledger(self) -> None:
        report = {
            "experiment_id": "v14-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "volnorm",
                    "proposal_kind": "v14_vol_normalized_momentum_manifold",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "window": 9,
                    "numerator_window": 9,
                    "denominator_window": 6,
                    "denominator_family": "mean_abs_ret",
                    "mean_window_rank_ic": 0.042,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                }
            ],
        }

        ledger = build_v15_robust_denominator_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["denominator_family"] == "mean_abs_ret" for record in ledger["records"]))
        self.assertTrue(any(record["denominator_family"] == "med_abs_ret" for record in ledger["records"]))
        self.assertTrue(any(record["denominator_family"] == "wma_abs_ret" for record in ledger["records"]))
        self.assertTrue(any("Div(Sub(Abs($ret),$ret),2)" in record["expression"] for record in ledger["records"]))

    def test_search_core_v16_scores_quarter_floor_stats(self) -> None:
        stable = quarter_floor_stats(
            {
                "mean_window_rank_ic": 0.04,
                "mean_window_sortino": 1.0,
                "recent_windows": [
                    {"mean_rank_ic": 0.02},
                    {"mean_rank_ic": 0.03},
                    {"mean_rank_ic": 0.04},
                    {"mean_rank_ic": 0.05},
                ],
            }
        )
        spiky = quarter_floor_stats(
            {
                "mean_window_rank_ic": 0.05,
                "mean_window_sortino": 1.0,
                "recent_windows": [
                    {"mean_rank_ic": 0.02},
                    {"mean_rank_ic": -0.02},
                    {"mean_rank_ic": 0.01},
                    {"mean_rank_ic": 0.19},
                ],
            }
        )

        self.assertTrue(stable["quarter_floor_pass"])
        self.assertFalse(spiky["quarter_floor_pass"])
        self.assertEqual(spiky["negative_quarter_count"], 1)
        self.assertGreater(stable["quarter_floor_score"], 0)

    def test_search_core_v16_inferrs_quarter_floor_surface(self) -> None:
        report = {
            "experiment_id": "v15-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,9),Mean(Abs($ret),6)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "denominator_family": "mean_abs_ret",
                    "numerator_window": 9,
                    "denominator_window": 6,
                    "mean_window_rank_ic": 0.04,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.01},
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                    ],
                },
                {
                    "candidate_id": "spiky",
                    "expression": "CSRank(Div(Mom($close,8),Med(Div(Sub(Abs($ret),$ret),2),5)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "denominator_family": "med_downside_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 5,
                    "mean_window_rank_ic": 0.05,
                    "mean_window_sortino": 1.6,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.01},
                        {"mean_rank_ic": -0.02},
                        {"mean_rank_ic": 0.17},
                    ],
                },
            ],
        }

        surface = infer_v16_quarter_floor_surface(report)

        self.assertEqual(surface["stable_candidate_count"], 1)
        self.assertEqual(surface["spiky_candidate_count"], 1)
        self.assertEqual(surface["stable_numerator_window_grid"], [8, 9, 10])
        self.assertIn(6, surface["stable_denominator_window_grid"])
        self.assertEqual(surface["source_execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")

    def test_search_core_v16_builds_quarter_floor_and_audit_ledger(self) -> None:
        report = {
            "experiment_id": "v15-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,9),Mean(Abs($ret),6)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "denominator_family": "mean_abs_ret",
                    "numerator_window": 9,
                    "denominator_window": 6,
                    "mean_window_rank_ic": 0.04,
                    "mean_window_sortino": 0.7,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.01},
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                    ],
                },
                {
                    "candidate_id": "spiky",
                    "expression": "CSRank(Div(Mom($close,8),Med(Div(Sub(Abs($ret),$ret),2),5)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "denominator_family": "med_downside_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 5,
                    "mean_window_rank_ic": 0.05,
                    "mean_window_sortino": 1.6,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.01},
                        {"mean_rank_ic": -0.02},
                        {"mean_rank_ic": 0.17},
                    ],
                },
            ],
        }

        ledger = build_v16_quarter_floor_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["research_track"] == "stable_quarter_floor" for record in ledger["records"]))
        self.assertTrue(any(record["research_track"] == "spiky_regime_conditional_audit" for record in ledger["records"]))
        self.assertTrue(any(record["quarter_floor_required"] for record in ledger["records"]))
        self.assertTrue(any(record["regime_conditional_audit"] for record in ledger["records"]))

    def test_search_core_v17_inferrs_stable_denominator_surface_only(self) -> None:
        report = {
            "experiment_id": "v16-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,9),Std($ret,4)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "denominator_family": "std_ret",
                    "numerator_window": 9,
                    "denominator_window": 4,
                    "mean_window_rank_ic": 0.042,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                },
                {
                    "candidate_id": "audit",
                    "expression": "CSRank(Div(Mom($close,8),Med(Div(Sub(Abs($ret),$ret),2),5)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "spiky_regime_conditional_audit",
                    "denominator_family": "med_downside_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 5,
                    "mean_window_rank_ic": 0.05,
                    "mean_window_sortino": 1.5,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": -0.01},
                        {"mean_rank_ic": 0.01},
                        {"mean_rank_ic": 0.18},
                    ],
                },
            ],
        }

        surface = infer_v17_stable_denominator_surface(report)

        self.assertEqual(surface["stable_input_count"], 1)
        self.assertEqual(surface["numerator_window_grid"], [8, 9])
        self.assertEqual(surface["denominator_window_grid"], [3, 4, 5, 6, 7, 8])
        self.assertEqual(surface["ranking_objective"], "quarter_floor_score_then_mean_ic")

    def test_search_core_v17_builds_stable_denominator_ledger(self) -> None:
        report = {
            "experiment_id": "v16-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,9),Std($ret,4)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "denominator_family": "std_ret",
                    "numerator_window": 9,
                    "denominator_window": 4,
                    "mean_window_rank_ic": 0.042,
                    "mean_window_sortino": 0.6,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                }
            ],
        }

        ledger = build_v17_stable_denominator_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(ledger["record_count"], 36)
        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(all(record["research_track"] == "stable_quarter_floor" for record in ledger["records"]))
        self.assertTrue(all(record["quarter_floor_required"] for record in ledger["records"]))
        self.assertFalse(any(record["regime_conditional_audit"] for record in ledger["records"]))

    def test_search_core_v18_inferrs_light_smoothing_surface(self) -> None:
        report = {
            "experiment_id": "v17-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,8),Mean(Abs($ret),3)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "denominator_family": "mean_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 3,
                    "mean_window_rank_ic": 0.043,
                    "mean_window_sortino": 1.9,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                }
            ],
        }

        surface = infer_v18_light_smoothing_surface(report)

        self.assertEqual(surface["center_candidate_id"], "stable")
        self.assertEqual(surface["denominator_window_grid"], [2, 3, 4])
        self.assertIn("wma_price", surface["numerator_transform_grid"])
        self.assertIn("mean_abs", surface["denominator_transform_grid"])

    def test_search_core_v18_builds_light_smoothing_ledger(self) -> None:
        report = {
            "experiment_id": "v17-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,8),Mean(Abs($ret),3)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "denominator_family": "mean_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 3,
                    "mean_window_rank_ic": 0.043,
                    "mean_window_sortino": 1.9,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                }
            ],
        }

        ledger = build_v18_light_smoothing_ledger(report)
        canonical = [record["canonical_rank_validation_expression"] for record in ledger["records"]]

        self.assertEqual(len(canonical), len(set(canonical)))
        self.assertTrue(any(record["numerator_transform"] == "wma_price" for record in ledger["records"]))
        self.assertTrue(any(record["denominator_transform"] == "wma_abs" for record in ledger["records"]))
        self.assertTrue(all(record["turnover_cost_shadow_required"] for record in ledger["records"]))
        self.assertTrue(all(record["research_track"] == "stable_quarter_floor" for record in ledger["records"]))

    def test_search_core_v18_builds_compact_validation_subset(self) -> None:
        report = {
            "experiment_id": "v17-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "stable",
                    "expression": "CSRank(Div(Mom($close,8),Mean(Abs($ret),3)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "denominator_family": "mean_abs_ret",
                    "numerator_window": 8,
                    "denominator_window": 3,
                    "mean_window_rank_ic": 0.043,
                    "mean_window_sortino": 1.9,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                }
            ],
        }

        full = build_v18_light_smoothing_ledger(report)
        compact = build_v18_compact_validation_ledger(full)

        self.assertLess(compact["record_count"], full["record_count"])
        self.assertTrue(any(record["numerator_transform"] == "raw" for record in compact["records"]))
        self.assertTrue(any(record["numerator_transform"] == "mean_signal" for record in compact["records"]))
        self.assertTrue(any(record["denominator_transform"] == "mean_abs" for record in compact["records"]))
        self.assertFalse(
            any(
                record["numerator_transform"] != "raw" and record["denominator_transform"] != "raw"
                for record in compact["records"]
            )
        )

    def test_search_core_v19_builds_continuous_kernel_and_residual_ledger(self) -> None:
        report = {
            "run_id": "v18-tplus1",
            "screening_mode": "recent_4_quarter_multi_cycle_smoke",
            "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
            "evaluations": [
                {
                    "candidate_id": "v18-center",
                    "expression": "CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))",
                    "primitive_family": "a5_vol_normalized_momentum",
                    "research_track": "stable_quarter_floor",
                    "numerator_window": 8,
                    "denominator_window": 2,
                    "mean_window_rank_ic": 0.047,
                    "mean_window_sortino": 2.1,
                    "passes_real_market_smoke": True,
                    "recent_windows": [
                        {"mean_rank_ic": 0.02},
                        {"mean_rank_ic": 0.03},
                        {"mean_rank_ic": 0.04},
                        {"mean_rank_ic": 0.05},
                    ],
                }
            ],
        }

        surface = infer_v19_continuous_kernel_surface(report)
        full = build_v19_continuous_kernel_ledger(report)
        compact = build_v19_compact_validation_ledger(full)

        self.assertEqual(surface["center_candidate_id"], "v18-center")
        self.assertIn("cs_residual_to_v18_center", surface["orthogonalization_modes"])
        self.assertTrue(any("Mul(0.8" in spec["kernel_expression"] for spec in surface["kernel_specs"]))
        self.assertTrue(any("CSResidual(" in record["expression"] for record in full["records"]))
        self.assertTrue(any(record["orthogonalization_mode"] == "raw" for record in compact["records"]))
        self.assertTrue(any(record["orthogonalization_mode"] == "cs_residual_to_v18_center" for record in compact["records"]))
        self.assertLess(compact["record_count"], full["record_count"])
        self.assertTrue(all(record["center_overlap_audit_required"] for record in compact["records"]))

    def test_search_core_v20_builds_activation_geometry_report(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-v20-activation-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-01-09",
                "2025-01-10",
                "2025-01-13",
                "2025-01-14",
                "2025-01-15",
            ]
            for day_index, day in enumerate(dates):
                breadth_boost = 0.03 if day_index % 3 == 0 else -0.01
                for code_index in range(8):
                    drift = breadth_boost + 0.006 * code_index
                    close = 10.0 + code_index + day_index * drift
                    volume = 10_000 + day_index * 120 + code_index * 80
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                "1" if day_index == 2 and code_index == 7 else "0",
                                "1" if day_index == 4 and code_index == 0 else "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = build_v20_activation_geometry_report(
                "CSRank(Mom($close,2))",
                path=panel_path,
                recent_quarter_window_count=1,
                recent_warmup_days=5,
                min_active_day_count=2,
            )

            self.assertEqual(report["gate_role"], "same_sample_activation_hypothesis_not_production_rule")
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertEqual(report["execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")
            self.assertGreater(report["daily_observation_count"], 0)
            self.assertIn("mean_cost_adjusted_spread", report["baseline_metrics"])
            self.assertGreater(report["gate_count"], 0)
            self.assertIn("active_metrics", report["top_gates"][0])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_search_core_v20_builds_two_half_activation_holdout_report(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-v20-holdout-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
                "2025-04-07",
            ]
            for day_index, day in enumerate(dates):
                breadth_boost = 0.03 if day_index % 2 == 0 else -0.01
                for code_index in range(8):
                    drift = breadth_boost + 0.007 * code_index
                    close = 10.0 + code_index + day_index * drift
                    volume = 10_000 + day_index * 90 + code_index * 70
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                "0",
                                "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = build_v20_activation_holdout_report(
                "CSRank(Mom($close,2))",
                path=panel_path,
                recent_quarter_window_count=2,
                recent_warmup_days=5,
                min_train_active_day_count=2,
                min_test_active_day_count=1,
                top_k_train_gates=5,
            )

            self.assertEqual(report["gate_role"], "two_half_holdout_activation_hypothesis_not_production_rule")
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertEqual(report["train_windows"], ["2025Q1"])
            self.assertEqual(report["test_windows"], ["2025Q2"])
            self.assertGreater(report["train_gate_count"], 0)
            self.assertGreater(report["holdout_gate_count"], 0)
            self.assertIn("test_active_metrics", report["top_holdout_gates"][0])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_search_core_v20_builds_rolling_activation_search_report(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-v21-rolling-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
                "2025-07-01",
                "2025-07-02",
                "2025-07-03",
                "2025-07-04",
            ]
            for day_index, day in enumerate(dates):
                breadth_boost = 0.02 if day_index % 2 == 0 else -0.01
                for code_index in range(8):
                    drift = breadth_boost + 0.006 * code_index
                    close = 10.0 + code_index + day_index * drift
                    volume = 10_000 + day_index * 80 + code_index * 60
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                "0",
                                "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = build_v21_rolling_activation_search_report(
                "CSRank(Mom($close,2))",
                path=panel_path,
                recent_quarter_window_count=3,
                recent_warmup_days=5,
                min_train_active_day_count=1,
                min_test_active_day_count=1,
            )

            self.assertEqual(report["gate_role"], "rolling_activation_search_hypothesis_not_production_rule")
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertGreaterEqual(report["split_count"], 2)
            self.assertGreater(report["gate_summary_count"], 0)
            self.assertIn("test_pass_count", report["top_gate_summaries"][0])
            self.assertIn("split_reports", report)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_rejects_unsupported_expression(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            panel_path.write_text(
                "\n".join(
                    [
                        "date,open,high,low,close,amount,volume,code",
                        "2025-01-02,10,11,9,10,1000000,10000,880001",
                        "2025-01-03,10,11,9,10.1,1000000,10000,880001",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(UnsupportedExpressionError):
                validate_expression_on_real_market_panel("Mystery($close)", path=panel_path)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_cost_report_routes_binary_and_nested_relations(self) -> None:
        cheap = expression_validation_cost_report("CSRank(Mom($close,20))")
        costly = expression_validation_cost_report("Sign(Cov(Corr(Cov($open,$low),$volume),Cov($high,$close)))")
        cfg_style = expression_validation_cost_report("CSRank(Med(WMA(Kurt($retf,40),30),20))")

        self.assertEqual(cheap["validation_lane"], "cheap_fast_path")
        self.assertEqual(cheap["validation_role"], "cross_sectional_rank_validation")
        self.assertEqual(cheap["relation_operator_count"], 0)
        self.assertGreaterEqual(cfg_style["rolling_operator_count"], 3)
        self.assertTrue(costly["binary_output"])
        self.assertEqual(costly["validation_role"], "group_spread_regime_shadow")
        self.assertGreater(costly["estimated_validation_cost_score"], cheap["estimated_validation_cost_score"])

    def test_real_replay_feedback_objective_uses_weak_positive_priors_without_edge_claim(self) -> None:
        feedback = build_real_replay_feedback_objective(
            {
                "experiment_id": "test-replay",
                "dataset_path": "panel.csv",
                "screening_mode": "recent_4_quarter_multi_cycle_smoke",
                "evaluation_start_date": "2025-04-01",
                "evaluation_end_date": "2026-02-04",
                "evaluations": [
                    {
                        "candidate_id": "weak-positive",
                        "expression": "Div(Mean($amount,2),Mean($volume,5))",
                        "frontier_lane": "novelty_frontier",
                        "validation_lane": "cheap_fast_path",
                        "source_mode": "variation",
                        "archive_cell": "cell-a",
                        "mean_window_rank_ic": 0.002,
                        "mean_window_sortino": -0.1,
                        "passes_real_market_smoke": False,
                        "smoke_flags": ["weak_mean_rank_ic_below_0_01"],
                    },
                    {
                        "candidate_id": "negative",
                        "expression": "Cov($close,$volume)",
                        "frontier_lane": "bridge_frontier",
                        "validation_lane": "moderate_fast_path",
                        "source_mode": "variation",
                        "archive_cell": "cell-b",
                        "mean_window_rank_ic": -0.02,
                        "mean_window_sortino": -1.0,
                        "passes_real_market_smoke": False,
                        "smoke_flags": ["non_positive_recent_mean_rank_ic"],
                    },
                ],
            }
        )

        self.assertEqual(feedback["decision"], "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH")
        self.assertFalse(feedback["real_edge_claim_allowed"])
        self.assertEqual(feedback["weak_positive_count"], 1)
        self.assertEqual(feedback["weak_positive_candidates"][0]["candidate_id"], "weak-positive")
        self.assertIn("field:$amount", {item["group"] for item in feedback["watched_soft_prior_groups"]})
        self.assertIn("synthetic_ic_without_real_replay_support", feedback["search_objective_adjustment"]["decrease_weight"])

    def test_real_replay_feedback_objective_tracks_saturated_positive_candidates(self) -> None:
        feedback = build_real_replay_feedback_objective(
            {
                "experiment_id": "test-passed-replay",
                "evaluations": [
                    {
                        "candidate_id": "passed",
                        "expression": "CSRank(Div($amount,$volume))",
                        "frontier_lane": "uncertainty_frontier",
                        "validation_lane": "cheap_fast_path",
                        "source_mode": "variation",
                        "archive_cell": "cell-a",
                        "mean_window_rank_ic": 0.012,
                        "mean_window_sortino": 0.3,
                        "passes_real_market_smoke": True,
                        "smoke_flags": [],
                    }
                ],
            }
        )

        self.assertEqual(feedback["decision"], "PROMOTE_REAL_REPLAY_PRIORS_TO_CANDIDATE_REVIEW")
        self.assertEqual(feedback["passed_smoke_count"], 1)
        self.assertEqual(feedback["saturated_positive_candidates"][0]["candidate_id"], "passed")
        self.assertFalse(feedback["real_edge_claim_allowed"])

    def test_real_replay_feedback_objective_rejects_all_negative_motifs(self) -> None:
        feedback = build_real_replay_feedback_objective(
            {
                "experiment_id": "test-negative-replay",
                "evaluations": [
                    {
                        "candidate_id": "a",
                        "expression": "Cov($close,$volume)",
                        "frontier_lane": "bridge_frontier",
                        "validation_lane": "moderate_fast_path",
                        "source_mode": "variation",
                        "archive_cell": "cell-a",
                        "mean_window_rank_ic": -0.01,
                        "mean_window_sortino": -1.0,
                        "passes_real_market_smoke": False,
                        "smoke_flags": ["non_positive_recent_mean_rank_ic"],
                    },
                    {
                        "candidate_id": "b",
                        "expression": "Corr($close,$amount)",
                        "frontier_lane": "bridge_frontier",
                        "validation_lane": "moderate_fast_path",
                        "source_mode": "variation",
                        "archive_cell": "cell-a",
                        "mean_window_rank_ic": 0.0,
                        "mean_window_sortino": -0.5,
                        "passes_real_market_smoke": False,
                        "smoke_flags": ["weak_mean_rank_ic_below_0_01"],
                    },
                ],
            }
        )

        self.assertEqual(feedback["decision"], "REJECT_CURRENT_SYNTHETIC_MOTIFS_FOR_REAL_REPLAY")
        self.assertEqual(feedback["weak_positive_count"], 0)
        self.assertTrue(feedback["demoted_soft_prior_groups"])
        self.assertEqual(feedback["next_action"], "change_math_operator_family_or_objective_before_more_synthetic_scale")

    def test_batch_real_market_validation_scores_retained_ledger_records(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            ledger_path = temp_root / "candidate_ledger.json"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-01-09",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    volume = 10_000 + code_index * 200 + day_index * 50
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "test-run",
                        "records": [
                            {
                                "candidate_id": "supported",
                                "expression": "CSRank($close)",
                                "retained": True,
                                "source_mode": "variation",
                                "archive_cell": "cell-a",
                            },
                            {
                                "candidate_id": "unsupported",
                                "expression": "Mystery($close)",
                                "retained": True,
                                "source_mode": "variation",
                                "archive_cell": "cell-b",
                            },
                            {
                                "candidate_id": "discarded",
                                "expression": "CSRank($open)",
                                "retained": False,
                                "source_mode": "variation",
                                "archive_cell": "cell-c",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = batch_validate_candidate_ledger(ledger_path, path=panel_path)

            self.assertEqual(report["source_run_id"], "test-run")
            self.assertEqual(report["requested_candidate_count"], 2)
            self.assertEqual(report["evaluated_count"], 1)
            self.assertEqual(report["unsupported_count"], 1)
            self.assertEqual(report["promoted_to_full_history_review_count"], 0)
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertEqual(report["validation_period_policy"], "quarterly_3_month_windows")
            self.assertGreater(report["cached_expression_count"], 0)
            self.assertEqual(report["evaluations"][0]["candidate_id"], "supported")
            self.assertEqual(report["evaluations"][0]["validation_lane"], "cheap_fast_path")
            self.assertIn("mean_window_long_return", report["evaluations"][0])
            self.assertIn("mean_window_long_sortino", report["evaluations"][0])
            self.assertEqual(report["unsupported"][0]["candidate_id"], "unsupported")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_batch_real_market_validation_reuses_duplicate_expression_reports(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-cache-"))
        try:
            panel_path = temp_root / "panel.csv"
            ledger_path = temp_root / "candidate_ledger.json"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-04-01",
                "2025-04-02",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.03 * (code_index + 1))
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(100_000 + code_index),
                                str(10_000 + code_index),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "duplicate-expression-test",
                        "records": [
                            {
                                "candidate_id": "duplicate-a",
                                "expression": "CSRank($close)",
                                "retained": True,
                            },
                            {
                                "candidate_id": "duplicate-b",
                                "expression": " CSRank($close) ",
                                "retained": True,
                            },
                            {
                                "candidate_id": "unsupported-a",
                                "expression": "Mystery($close)",
                                "retained": True,
                            },
                            {
                                "candidate_id": "unsupported-b",
                                "expression": " Mystery($close) ",
                                "retained": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = batch_validate_candidate_ledger(ledger_path, path=panel_path)

            self.assertEqual(report["requested_candidate_count"], 4)
            self.assertEqual(report["evaluated_count"], 2)
            self.assertEqual(report["unsupported_count"], 2)
            self.assertEqual(report["unique_validated_expression_count"], 1)
            self.assertEqual(report["validation_report_cache_hit_count"], 1)
            self.assertEqual(report["unsupported_validation_cache_hit_count"], 1)
            self.assertEqual(
                report["validation_report_cache_key_policy"],
                "expanded_stripped_expression_plus_validation_contract",
            )
            self.assertEqual(
                report["evaluations"][0]["mean_window_rank_ic"],
                report["evaluations"][1]["mean_window_rank_ic"],
            )
            self.assertCountEqual(
                [item["candidate_id"] for item in report["evaluations"]],
                ["duplicate-a", "duplicate-b"],
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_batch_real_market_validation_fast_context_matches_baseline(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-fast-context-"))
        try:
            panel_path = temp_root / "panel.csv"
            ledger_path = temp_root / "candidate_ledger.json"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down,susp"]
            base = date(2025, 1, 2)
            for day_index in range(28):
                day = base + timedelta(days=day_index)
                for code_index in range(7):
                    close = 10.0 + code_index + (day_index * 0.04 * (code_index + 1))
                    is_limit_up = "1" if day_index == 12 and code_index == 2 else "0"
                    is_limit_down = "1" if day_index == 13 and code_index == 3 else "0"
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 0.995:.4f}",
                                f"{close * 1.015:.4f}",
                                f"{close * 0.985:.4f}",
                                f"{close:.4f}",
                                str(100_000 + code_index * 1000 + day_index),
                                str(10_000 + code_index * 100),
                                f"88000{code_index + 1}",
                                is_limit_up,
                                is_limit_down,
                                "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "fast-context-equivalence-test",
                        "records": [
                            {
                                "candidate_id": "rank-close",
                                "expression": "CSRank($close)",
                                "retained": True,
                            },
                            {
                                "candidate_id": "turnover-like",
                                "expression": "CSRank(Div(Mean($amount,3),Add(Abs(Mean($amount,5)),0.000001)))",
                                "retained": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            baseline = batch_validate_candidate_ledger(ledger_path, path=panel_path)
            fast = batch_validate_candidate_ledger(ledger_path, path=panel_path, use_fast_context=True)

            self.assertEqual(fast["validation_acceleration_mode"], "precomputed_work_context")
            self.assertEqual(baseline["evaluated_count"], fast["evaluated_count"])
            baseline_by_id = {item["candidate_id"]: item for item in baseline["evaluations"]}
            fast_by_id = {item["candidate_id"]: item for item in fast["evaluations"]}
            self.assertEqual(set(baseline_by_id), set(fast_by_id))
            keys = [
                "mean_window_rank_ic",
                "mean_window_long_return",
                "mean_window_long_sortino",
                "mean_window_sortino",
                "tradability_ic_excluded_row_count",
                "row_count_after_signal_and_target",
                "signal_clock",
                "feature_lag_days",
            ]
            for candidate_id, baseline_item in baseline_by_id.items():
                fast_item = fast_by_id[candidate_id]
                for key in keys:
                    self.assertEqual(baseline_item[key], fast_item[key], (candidate_id, key))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_batch_real_market_validation_can_fast_screen_recent_window(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            ledger_path = temp_root / "candidate_ledger.json"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
                "2025-04-07",
                "2025-04-08",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.03 * code_index)
                    volume = 10_000 + code_index * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "test-run",
                        "records": [
                            {
                                "candidate_id": "recent-supported",
                                "expression": "CSRank($close)",
                                "retained": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = batch_validate_candidate_ledger(
                ledger_path,
                path=panel_path,
                fast_recent_window_only=True,
                recent_lookback_days=10,
                recent_warmup_days=10,
            )

            self.assertEqual(report["screening_mode"], "recent_3_month_fast_screen")
            self.assertEqual(report["evaluation_end_date"], "2025-04-08")
            self.assertEqual(report["evaluation_start_date"], "2025-03-29")
            self.assertLess(report["loaded_panel_rows"], 60)
            self.assertGreater(report["cached_expression_count"], 0)
            self.assertEqual(report["evaluations"][0]["evaluation_start_date"], "2025-03-29")
            self.assertEqual(report["evaluations"][0]["window_count"], 1)
            self.assertIn(report["evaluations"][0]["fast_screen_decision"], {"needs_full_history_review", "watchlist_weak_positive_recent_ic", "reject_non_positive_recent_ic"})
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_batch_real_market_validation_can_run_bounded_recent_quarter_cycles(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            ledger_path = temp_root / "candidate_ledger.json"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2024-12-20",
                "2025-01-02",
                "2025-01-03",
                "2025-03-31",
                "2025-04-01",
                "2025-04-02",
                "2025-04-08",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    volume = 10_000 + code_index * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "test-run",
                        "records": [
                            {
                                "candidate_id": "bounded-supported",
                                "expression": "CSRank($close)",
                                "retained": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = batch_validate_candidate_ledger(
                ledger_path,
                path=panel_path,
                recent_quarter_window_count=2,
                recent_warmup_days=5,
            )

            self.assertEqual(report["screening_mode"], "recent_2_quarter_multi_cycle_smoke")
            self.assertEqual(report["evaluation_start_date"], "2025-01-01")
            self.assertEqual(report["evaluation_end_date"], "2025-04-08")
            self.assertEqual(report["recent_quarter_window_count"], 2)
            self.assertLess(report["loaded_panel_rows"], 42)
            self.assertEqual(report["evaluations"][0]["evaluation_start_date"], "2025-01-01")
            self.assertEqual(report["evaluations"][0]["window_count"], 2)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_filters_limit_up_down_from_tradable_ic(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = ["2025-01-02", "2025-01-03", "2025-01-06"]
            for day_index, day in enumerate(dates):
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.03 * code_index)
                    is_limit_up = 1 if code_index == 7 and day_index < 2 else 0
                    is_limit_down = 1 if code_index == 0 and day_index < 2 else 0
                    volume = 10_000 + code_index * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                                str(is_limit_up),
                                str(is_limit_down),
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel("CSRank($close)", path=panel_path)

            self.assertTrue(report["tradability_filter_available"])
            self.assertEqual(report["tradability_limit_up_source"], "is_limit_up")
            self.assertEqual(report["tradability_limit_down_source"], "is_limit_down")
            self.assertEqual(report["execution_lag_days"], 1)
            self.assertEqual(report["tradability_entry_limit_up_row_count"], 1)
            self.assertEqual(report["tradability_entry_limit_down_row_count"], 1)
            self.assertEqual(report["tradability_ic_excluded_row_count"], 2)
            self.assertEqual(report["windows"][0]["tradability_long_excluded_unbuyable_or_unsellable_row_count"], 1)
            self.assertEqual(report["windows"][0]["tradability_short_excluded_unsellable_or_unbuyable_row_count"], 1)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_defaults_to_tplus1_execution_without_signal_day_limit_filter(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-validation-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = ["2025-01-02", "2025-01-03", "2025-01-06"]
            for day_index, day in enumerate(dates):
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    signal_day_limit_up = 1 if day_index == 0 and code_index == 7 else 0
                    entry_day_limit_up = 1 if day_index == 1 and code_index == 6 else 0
                    entry_day_limit_down = 1 if day_index == 1 and code_index == 1 else 0
                    volume = 10_000 + code_index * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                                str(max(signal_day_limit_up, entry_day_limit_up)),
                                str(entry_day_limit_down),
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel("CSRank($close)", path=panel_path)

            self.assertEqual(report["execution_lag_days"], 1)
            self.assertEqual(report["execution_policy"], "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close")
            self.assertEqual(report["tradability_entry_limit_up_row_count"], 1)
            self.assertEqual(report["tradability_entry_limit_down_row_count"], 1)
            self.assertEqual(report["tradability_ic_excluded_row_count"], 2)
            self.assertEqual(report["windows"][0]["tradability_long_excluded_unbuyable_or_unsellable_row_count"], 1)
            self.assertEqual(report["windows"][0]["tradability_short_excluded_unsellable_or_unbuyable_row_count"], 1)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_real_market_validation_feature_lag_uses_previous_day_signal_for_open_decision(self) -> None:
        rows = []
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        for code_index in range(8):
            code = f"88000{code_index + 1}"
            day0_close = 10.0 + code_index
            day1_close = 100.0 - code_index
            day2_close = 100.0
            day3_close = 100.0 + code_index
            for day, close in zip(dates, [day0_close, day1_close, day2_close, day3_close]):
                rows.append(
                    {
                        "date": day,
                        "open": close,
                        "high": close,
                        "low": close,
                        "close": close,
                        "amount": 100_000.0,
                        "volume": 10_000.0,
                        "code": code,
                    }
                )
        frame = pd.DataFrame(rows).sort_values(["date", "code"]).reset_index(drop=True)

        unlagged = validate_expression_on_loaded_panel(
            "CSRank($close)",
            frame,
            dataset_path="memory://feature-lag-test",
            feature_lag_days=0,
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )
        lagged = validate_expression_on_loaded_panel(
            "CSRank($close)",
            frame,
            dataset_path="memory://feature-lag-test",
            feature_lag_days=1,
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )

        self.assertEqual(unlagged["feature_lag_days"], 0)
        self.assertEqual(lagged["feature_lag_days"], 1)
        self.assertLess(unlagged["mean_window_rank_ic"], -0.99)
        self.assertGreater(lagged["mean_window_rank_ic"], 0.99)

    def test_real_market_validation_after_open_clock_shifts_full_day_close_fields(self) -> None:
        rows = []
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        for code_index in range(8):
            code = f"88000{code_index + 1}"
            closes = [10.0 + code_index, 100.0 - code_index, 100.0, 100.0 + code_index]
            for day, close in zip(dates, closes):
                rows.append(
                    {
                        "date": day,
                        "open": close,
                        "high": close,
                        "low": close,
                        "close": close,
                        "amount": 100_000.0,
                        "volume": 10_000.0,
                        "code": code,
                    }
                )
        frame = pd.DataFrame(rows).sort_values(["date", "code"]).reset_index(drop=True)

        after_close = validate_expression_on_loaded_panel(
            "CSRank($close)",
            frame,
            dataset_path="memory://signal-clock-test",
            signal_clock="after_close",
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )
        after_open = validate_expression_on_loaded_panel(
            "CSRank($close)",
            frame,
            dataset_path="memory://signal-clock-test",
            signal_clock="after_open",
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )

        self.assertEqual(after_open["signal_clock"], "after_open")
        self.assertEqual(after_open["field_lags"]["close"], 1)
        self.assertLess(after_close["mean_window_rank_ic"], -0.99)
        self.assertGreater(after_open["mean_window_rank_ic"], 0.99)

    def test_real_market_validation_expression_cache_separates_field_lag_policies(self) -> None:
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2025-01-02",
                        "2025-01-03",
                        "2025-01-02",
                        "2025-01-03",
                    ]
                ),
                "code": ["000001", "000001", "000002", "000002"],
                "close": [10.0, 11.0, 20.0, 22.0],
            }
        )
        cache: dict[str, pd.Series] = {}

        unlagged = evaluate_panel_expression(frame, "$close", cache=cache, field_lags={})
        lagged = evaluate_panel_expression(frame, "$close", cache=cache, field_lags={"close": 1})

        self.assertEqual(float(unlagged.iloc[1]), 11.0)
        self.assertEqual(float(lagged.iloc[1]), 10.0)
        self.assertGreaterEqual(len(cache), 2)

    def test_stock_pit_compact_ensemble_sector_cap_limits_each_side(self) -> None:
        pool = pd.DataFrame(
            {
                "code": [f"00000{index}" for index in range(1, 8)],
                "signal": [7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
                "sector": ["bank", "bank", "bank", "tech", "tech", "health", "health"],
            }
        )

        selected = _select_sector_capped_codes(
            pool,
            side_count=4,
            descending=True,
            sector_cap_ratio=0.5,
        )

        selected_sectors = pool.set_index("code").loc[selected, "sector"].value_counts()
        self.assertEqual(len(selected), 4)
        self.assertLessEqual(int(selected_sectors.max()), 2)

    def test_stock_pit_compact_ensemble_report_preserves_ashare_execution_contract(self) -> None:
        rows = []
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"])
        for code_index in range(10):
            code = f"8800{code_index + 1:02d}"
            sector = ["bank", "tech", "health", "energy", "consumer"][code_index % 5]
            for day_index, day in enumerate(dates):
                open_ = 10.0 + code_index + (day_index * 0.1)
                close = open_ * (1.0 + (0.002 * (code_index - 4)))
                rows.append(
                    {
                        "date": day,
                        "open": open_,
                        "high": max(open_, close) * 1.01,
                        "low": min(open_, close) * 0.99,
                        "close": close,
                        "amount": 100_000.0 + (code_index * 10_000.0),
                        "volume": 10_000.0 + (code_index * 100.0),
                        "code": code,
                        "sector": sector,
                        "is_limit_up": 1 if code_index == 9 and day_index == 2 else 0,
                        "is_limit_down": 1 if code_index == 0 and day_index == 2 else 0,
                    }
                )
        frame = pd.DataFrame(rows)
        component_specs = (
            {
                "candidate_id": "test-open-rank",
                "research_family": "test",
                "expression": "CSRank($open)",
            },
            {
                "candidate_id": "test-close-rank",
                "research_family": "test",
                "expression": "CSRank($close)",
            },
        )

        report = build_stock_pit_compact_top6_ensemble_report(
            [
                {
                    "label": "unit",
                    "frame": frame,
                    "dataset_path": "memory://stock-pit-contract-test",
                    "evaluation_start_date": "2025-01-03",
                    "evaluation_end_date": "2025-01-07",
                }
            ],
            component_specs=component_specs,
            cost_bps_grid=(20.0,),
            sector_cap_ratio_per_side=0.5,
            include_daily=False,
        )

        item = report["slices"][0]
        self.assertFalse(report["commercial_edge_claim_allowed"])
        self.assertEqual(report["parameters"]["signal_clock"], "after_open")
        self.assertEqual(report["parameters"]["execution_lag_days"], 1)
        self.assertEqual(item["signal_clock_report"]["field_lags"]["close"], 1)
        self.assertNotIn("open", item["signal_clock_report"]["field_lags"])
        self.assertTrue(item["tradability_masks"]["available"])
        self.assertGreater(item["day_count"], 0)
        self.assertEqual(item["stress"][0]["cost_bps"], 20.0)

    def test_real_market_validation_loader_supports_parquet_panels(self) -> None:
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
                "open": [10.0, 10.2],
                "high": [10.5, 10.6],
                "low": [9.8, 10.0],
                "close": [10.1, 10.3],
                "amount": [100_000.0, 120_000.0],
                "volume": [10_000.0, 12_000.0],
                "code": ["000001", "000001"],
                "is_limit_up": [0, 1],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "panel.parquet"
            try:
                frame.to_parquet(path)
            except (ImportError, ValueError) as exc:
                self.skipTest(f"parquet engine unavailable: {exc}")

            loaded = _load_market_panel(path)

        self.assertEqual(len(loaded), 2)
        self.assertIn("is_limit_up", loaded.columns)
        self.assertEqual(str(loaded["code"].iloc[0]), "000001")

    def test_real_market_validation_after_open_clock_keeps_current_open_but_pre_open_lags_it(self) -> None:
        rows = []
        dates = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        for code_index in range(8):
            code = f"88000{code_index + 1}"
            opens = [100.0 - code_index, 10.0 + code_index, 100.0, 100.0]
            closes = [100.0, 100.0, 100.0, 100.0 + code_index]
            for day, open_, close in zip(dates, opens, closes):
                rows.append(
                    {
                        "date": day,
                        "open": open_,
                        "high": max(open_, close),
                        "low": min(open_, close),
                        "close": close,
                        "amount": 100_000.0,
                        "volume": 10_000.0,
                        "code": code,
                    }
                )
        frame = pd.DataFrame(rows).sort_values(["date", "code"]).reset_index(drop=True)

        after_open = validate_expression_on_loaded_panel(
            "CSRank($open)",
            frame,
            dataset_path="memory://signal-clock-open-test",
            signal_clock="after_open",
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )
        pre_open = validate_expression_on_loaded_panel(
            "CSRank($open)",
            frame,
            dataset_path="memory://signal-clock-open-test",
            signal_clock="pre_open",
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )

        self.assertEqual(after_open["signal_clock"], "after_open")
        self.assertNotIn("open", after_open["field_lags"])
        self.assertEqual(pre_open["signal_clock"], "pre_open")
        self.assertEqual(pre_open["field_lags"]["open"], 1)
        self.assertGreater(after_open["mean_window_rank_ic"], 0.99)
        self.assertLess(pre_open["mean_window_rank_ic"], -0.99)

    def test_real_market_validation_after_open_clock_does_not_double_shift_explicit_delay(self) -> None:
        rows = []
        dates = pd.to_datetime(["2024-12-31", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        for code_index in range(8):
            code = f"88000{code_index + 1}"
            prior_prior_close = 50.0 + (code_index * 10.0)
            prior_close = 10.0
            signal_open = 10.0 + code_index
            closes = [prior_prior_close, prior_close, 100.0, 100.0, 100.0 + code_index]
            opens = [prior_prior_close, prior_close, signal_open, 100.0, 100.0]
            for day, open_, close in zip(dates, opens, closes):
                rows.append(
                    {
                        "date": day,
                        "open": open_,
                        "high": max(open_, close),
                        "low": min(open_, close),
                        "close": close,
                        "amount": 100_000.0,
                        "volume": 10_000.0,
                        "code": code,
                    }
                )
        frame = pd.DataFrame(rows).sort_values(["date", "code"]).reset_index(drop=True)

        report = validate_expression_on_loaded_panel(
            "CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1)))",
            frame,
            dataset_path="memory://signal-clock-delay-test",
            signal_clock="after_open",
            evaluation_start_date=pd.Timestamp("2025-01-03"),
            evaluation_end_date=pd.Timestamp("2025-01-03"),
        )

        self.assertEqual(report["field_lags"]["close"], 1)
        self.assertNotIn("open", report["field_lags"])
        self.assertGreater(report["mean_window_rank_ic"], 0.99)

    def test_ashare_adapter_annotates_ledger_without_mutating_core_search_records(self) -> None:
        source = {
            "run_id": "core-ledger",
            "records": [
                {
                    "candidate_id": "core-001",
                    "expression": "CSRank(Mom($close,8))",
                    "retained": True,
                }
            ],
        }

        adapted = annotate_ledger_for_ashare(source, signal_clock="after_open")

        self.assertNotIn("market_adapter", source["records"][0])
        self.assertFalse(adapted["core_search_system_modified"])
        self.assertEqual(adapted["market_adapter"], "china_a_share")
        self.assertTrue(adapted["does_not_define_formula_space"])
        self.assertEqual(adapted["recommended_validation_kwargs"]["signal_clock"], "after_open")
        self.assertEqual(adapted["records"][0]["market_adapter"], "china_a_share")
        self.assertTrue(adapted["ashare_trading_contract"]["portable_core_runtime_unchanged"])
        self.assertEqual(
            adapted["ashare_trading_contract"]["interaction_policy"],
            "adapter_never_locks_formula_interactions_only_validation_availability_and_tradability",
        )

    def test_batch_validation_uses_ashare_ledger_recommended_clock_by_default(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-ashare-validated-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            for day_index in range(8):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.05 * (code_index + 1))
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                "100000",
                                "10000",
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            core_ledger = {
                "run_id": "core-generated-ledger",
                "records": [
                    {
                        "candidate_id": "core-close-001",
                        "expression": "CSRank($close)",
                        "retained": True,
                    }
                ],
            }
            adapted = annotate_ledger_for_ashare(core_ledger, signal_clock="after_open")
            ledger_path = temp_root / "adapted.json"
            ledger_path.write_text(json.dumps(adapted), encoding="utf-8")

            report = batch_validate_candidate_ledger(ledger_path, path=panel_path)

            self.assertEqual(report["source_run_id"], "core-generated-ledger-ashare-adapted")
            self.assertEqual(report["signal_clock"], "after_open")
            self.assertEqual(report["execution_lag_days"], 1)
            self.assertEqual(report["feature_lag_days"], 0)
            self.assertEqual(
                report["validation_defaults_source"]["signal_clock"],
                "ledger_recommended_validation_kwargs",
            )
            self.assertEqual(report["signal_clock_field_lags"]["close"], 1)
            self.assertEqual(report["evaluations"][0]["signal_clock"], "after_open")
            self.assertEqual(report["evaluations"][0]["field_lags"]["close"], 1)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_ashare_targeted_search_ledger_generates_clock_aware_gap_and_anti_momentum_candidates(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-ashare-adapter-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            dates = [base + timedelta(days=index) for index in range(45)]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.01)
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                "100000",
                                "10000",
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            contract = ashare_trading_contract(signal_clock="after_open")
            ledger = build_ashare_targeted_search_ledger(
                path=panel_path,
                start_round=0,
                round_count=2,
                candidates_per_family_per_round=4,
                target_window_count=6,
                signal_clock="after_open",
            )

            self.assertEqual(contract["market_adapter"], "china_a_share")
            self.assertFalse(ledger["core_search_system_modified"])
            self.assertTrue(ledger["can_reuse_core_for_other_markets"])
            self.assertEqual(ledger["recommended_validation_kwargs"]["signal_clock"], "after_open")
            self.assertEqual(ledger["round_scheduler"]["round_count"], 2)
            self.assertEqual(ledger["round_scheduler"]["candidates_per_family_per_round"], 4)
            self.assertEqual(
                ledger["search_budget_semantics"],
                "training_style_rounds_for_this_diagnostic_seed_lane_not_candidate_space_limit",
            )
            self.assertFalse(ledger["primary_search_generator"])
            self.assertTrue(ledger["does_not_define_formula_space"])
            self.assertTrue(ledger["infinite_space_preserved_by_main_core_generation_then_ashare_annotation"])
            self.assertGreater(ledger["full_space_candidate_count_for_current_parameter_slice"], ledger["record_count"])
            self.assertTrue(ledger["ashare_constraints_apply_to_all_candidates"])
            families = {record["primitive_family"] for record in ledger["records"]}
            self.assertIn("ashare_gap_reversal", families)
            self.assertIn("ashare_short_term_anti_momentum", families)
            self.assertTrue(all(record["ashare_constraints_apply_to_all_candidates"] for record in ledger["records"]))
            self.assertTrue(any("$open" in record["expression"] for record in ledger["records"]))
            self.assertTrue(all(record["recommended_signal_clock"] == "after_open" for record in ledger["records"]))
            self.assertTrue(ledger["efficiency_contract"]["does_not_expand_full_formula_grammar"])
            self.assertTrue(ledger["efficiency_contract"]["diagnostic_seed_lane_not_primary_generator"])
            self.assertTrue(ledger["efficiency_contract"]["does_not_lock_formula_interactions"])
            self.assertTrue(ledger["efficiency_contract"]["main_search_interactions_remain_owned_by_core_or_external_generators"])
            self.assertTrue(ledger["efficiency_contract"]["rounds_are_compute_schedule_not_space_cap"])
            self.assertTrue(ledger["efficiency_contract"]["all_families_receive_each_round"])
            self.assertTrue(ledger["efficiency_contract"]["constraints_are_global_not_gap_specific"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_forward_first_large_search_ledger_is_qlib_compatible_and_scheduled(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-forward-first-search-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            for day_index in range(70):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.02)
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                "100000",
                                "10000",
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            ledger = build_stock_pit_forward_first_large_search_ledger(
                path=panel_path,
                round_count=2,
                candidates_per_round=120,
                target_window_count=8,
                max_window=40,
            )

            self.assertFalse(ledger["core_search_system_modified"])
            self.assertTrue(ledger["can_reuse_core_for_other_markets"])
            self.assertEqual(ledger["recommended_validation_kwargs"]["signal_clock"], "after_open")
            self.assertEqual(ledger["record_count"], 240)
            self.assertGreater(ledger["full_space_candidate_count_for_current_parameter_slice"], ledger["record_count"])
            self.assertEqual(
                ledger["search_budget_semantics"],
                "training_style_rounds_are_compute_schedule_not_formula_space_cap",
            )
            self.assertFalse(ledger["parameter_space"]["depends_on_registered_window_prior"])
            self.assertTrue(ledger["field_contract"]["does_not_use_overnight_field"])
            self.assertTrue(ledger["efficiency_contract"]["stage1_fast_train_screen_with_existing_batch_validate_candidate_ledger"])
            expressions = [record["expression"] for record in ledger["records"]]
            self.assertTrue(any("$open" in expression for expression in expressions))
            self.assertTrue(any("CSResidual" in expression or "Mul(" in expression for expression in expressions))
            self.assertTrue(all("$overnight" not in expression for expression in expressions))
            fields = {
                field
                for expression in expressions
                for field in extract_field_names(expression)
            }
            self.assertTrue(fields.issubset(QLIB_FORWARD_COMPATIBLE_FIELDS), fields)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_ledger_selection_policy_filters_previous_and_caps_family(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-ledger-policy-"))
        try:
            previous_root = temp_root / "previous"
            previous_root.mkdir(parents=True)
            previous_ledger = {
                "run_id": "previous-stock-pit",
                "dataset_role": "stock_pit_panel",
                "records": [
                    {
                        "candidate_id": "prev-1",
                        "expression": "CSRank($open)",
                        "primitive_family": "open_rank",
                    }
                ],
            }
            (previous_root / "candidate_ledger.json").write_text(
                json.dumps(previous_ledger, ensure_ascii=False),
                encoding="utf-8",
            )
            ledger = {
                "run_id": "current-stock-pit",
                "dataset_role": "stock_pit_panel",
                "record_count": 5,
                "records": [
                    {"candidate_id": "cur-dup", "expression": "CSRank($open)", "primitive_family": "open_rank"},
                    {"candidate_id": "cur-a1", "expression": "CSRank($close)", "primitive_family": "price_rank"},
                    {"candidate_id": "cur-a2", "expression": "CSRank($high)", "primitive_family": "price_rank"},
                    {"candidate_id": "cur-a3", "expression": "CSRank($low)", "primitive_family": "price_rank"},
                    {"candidate_id": "cur-b1", "expression": "CSRank($amount)", "primitive_family": "amount_rank"},
                ],
            }

            selected = apply_stock_pit_ledger_selection_policy(
                ledger,
                previous_roots=[previous_root],
                expected_dataset_role="stock_pit_panel",
                max_family_share=0.4,
            )

            selected_ids = {record["candidate_id"] for record in selected["records"]}
            self.assertNotIn("cur-dup", selected_ids)
            self.assertEqual(selected["record_count"], 3)
            self.assertEqual(selected["ledger_selection_policy"]["skipped_duplicate_expression_count"], 1)
            self.assertEqual(selected["ledger_selection_policy"]["skipped_family_cap_count"], 1)
            self.assertLessEqual(selected["family_counts"]["price_rank"], 2)
            self.assertTrue(selected["ledger_selection_policy"]["default_behavior_unchanged_without_cli_flags"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_diversified_top_candidates_limits_single_family_dominance(self) -> None:
        ranked = [
            {"candidate_id": "a1", "primitive_family": "a", "mean_window_long_sortino": 5.0},
            {"candidate_id": "a2", "primitive_family": "a", "mean_window_long_sortino": 4.9},
            {"candidate_id": "a3", "primitive_family": "a", "mean_window_long_sortino": 4.8},
            {"candidate_id": "b1", "primitive_family": "b", "mean_window_long_sortino": 4.7},
            {"candidate_id": "c1", "primitive_family": "c", "mean_window_long_sortino": 4.6},
        ]

        selected = diversified_top_candidates(ranked, limit=5, max_per_family=2)

        self.assertEqual([item["candidate_id"] for item in selected], ["a1", "a2", "b1", "c1"])

    def test_stock_pit_search_control_policy_routes_from_prior_terminal_rewards(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-search-control-"))
        try:
            report = {
                "dataset_path": str(temp_root / "phase2_stock_validation_slice_test.parquet"),
                "evaluations": [
                    {
                        "candidate_id": "good-1",
                        "primitive_family": "winner_family",
                        "proposal_kind": "interaction_probe",
                        "mean_window_long_return": 0.004,
                        "mean_window_long_sortino": 4.0,
                        "mean_window_sortino": 3.0,
                        "mean_window_rank_ic": 0.05,
                        "recent_positive_rank_ic_ratio": 0.8,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 20,
                        "expression": "CSRank(Mul($open,$amount))",
                    },
                    {
                        "candidate_id": "bad-1",
                        "primitive_family": "weak_family",
                        "proposal_kind": "single_probe",
                        "mean_window_long_return": -0.002,
                        "mean_window_long_sortino": -1.0,
                        "mean_window_sortino": -0.8,
                        "mean_window_rank_ic": -0.02,
                        "recent_positive_rank_ic_ratio": 0.2,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 20,
                        "expression": "CSRank($close)",
                    },
                ],
            }
            (temp_root / "stage1_validation_report.json").write_text(
                json.dumps(report, ensure_ascii=False),
                encoding="utf-8",
            )

            policy_state_path = temp_root / "stock_pit_policy_state.json"
            policy = build_stock_pit_search_control_policy(
                [temp_root],
                expected_dataset_role="stock_pit_panel",
                exploration_share=0.2,
                policy_state_path=policy_state_path,
            )
            scheduled, audit = apply_stock_pit_search_control_schedule(
                [
                    {"candidate_id": "weak-next", "primitive_family": "weak_family", "proposal_kind": "single_probe"},
                    {
                        "candidate_id": "winner-next",
                        "primitive_family": "winner_family",
                        "proposal_kind": "interaction_probe",
                        "expression": "CSRank(Mul($open,$amount))",
                    },
                    {
                        "candidate_id": "amount-motif-next",
                        "primitive_family": "amount_ratio_x_momentum_curve",
                        "proposal_kind": "cross_axis_interaction_probe",
                        "expression": "CSRank(Mul($amount,$open))",
                    },
                    {
                        "candidate_id": "random-next",
                        "primitive_family": "random_family",
                        "proposal_kind": "random_probe",
                        "expression": "CSRank($close)",
                    },
                    {"candidate_id": "new-next", "primitive_family": "new_family", "proposal_kind": "novel_probe"},
                ],
                search_control_policy=policy,
            )

            self.assertTrue(policy["active"])
            self.assertTrue(policy_state_path.exists())
            self.assertEqual(policy["bandit_method"], "ucb")
            self.assertGreater(policy["bandit_total_observation_count"], 0)
            self.assertIn("field", policy["bandit_key_type_count"])
            self.assertIn("amount", policy["bandit_policy_state"]["key_stats"]["field"])
            self.assertIn("Mul", policy["bandit_policy_state"]["key_stats"]["operator"])
            self.assertGreater(
                policy["family_priors"]["winner_family"]["routing_score"],
                policy["family_priors"]["weak_family"]["routing_score"],
            )
            self.assertTrue(audit["active"])
            self.assertEqual(audit["bandit_method"], "ucb")
            self.assertEqual(scheduled[0]["candidate_id"], "winner-next")
            self.assertIn("search_control_score", scheduled[0])
            self.assertIn("search_control_bandit", scheduled[0])
            scheduled_ids = [item["candidate_id"] for item in scheduled]
            self.assertLess(scheduled_ids.index("amount-motif-next"), scheduled_ids.index("random-next"))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_policy_state_can_drive_later_search_without_reloading_reports(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-policy-state-reuse-"))
        try:
            policy_state_path = temp_root / "stock_pit_policy_state.json"
            (temp_root / "stage1_validation_report.json").write_text(
                json.dumps(
                    {
                        "dataset_role": "stock_pit_panel",
                        "evaluations": [
                            {
                                "candidate_id": "field-good",
                                "primitive_family": "open_amount_cross",
                                "proposal_kind": "interaction_probe",
                                "mean_window_long_return": 0.003,
                                "mean_window_long_sortino": 3.0,
                                "mean_window_sortino": 2.0,
                                "mean_window_rank_ic": 0.04,
                                "recent_positive_rank_ic_ratio": 0.7,
                                "tradability_filter_available": True,
                                "row_count_after_signal_and_target": 1000,
                                "tradability_ic_excluded_row_count": 10,
                                "expression": "CSRank(Mul($open,$amount))",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            build_stock_pit_search_control_policy(
                [temp_root],
                expected_dataset_role="stock_pit_panel",
                policy_state_path=policy_state_path,
            )

            policy = build_stock_pit_search_control_policy(
                [],
                expected_dataset_role="stock_pit_panel",
                policy_state_path=policy_state_path,
            )
            scheduled, audit = apply_stock_pit_search_control_schedule(
                [
                    {
                        "candidate_id": "inherits-field-memory",
                        "primitive_family": "new_family",
                        "proposal_kind": "new_probe",
                        "expression": "CSRank(Mul($open,$amount))",
                    },
                    {
                        "candidate_id": "unseen-low-info",
                        "primitive_family": "other_family",
                        "proposal_kind": "other_probe",
                        "expression": "CSRank($close)",
                    },
                ],
                search_control_policy=policy,
            )

            self.assertTrue(policy["active"])
            self.assertGreater(policy["bandit_total_observation_count"], 0)
            self.assertEqual(audit["scope"], "bandit_ucb_record_scheduling_before_validation_budget_cut")
            self.assertEqual(scheduled[0]["candidate_id"], "inherits-field-memory")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_forward_first_policy_state_adds_rx_crossover_probes(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-rx-crossover-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            for day_index in range(70):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.02)
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                "100000",
                                "10000",
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            policy_root = temp_root / "prior"
            policy_root.mkdir()
            (policy_root / "stage1_validation_report.json").write_text(
                json.dumps(
                    {
                        "dataset_role": "stock_pit_panel",
                        "evaluations": [
                            {
                                "candidate_id": "good-cross",
                                "primitive_family": "open_amount_cross",
                                "proposal_kind": "interaction_probe",
                                "mean_window_long_return": 0.003,
                                "mean_window_long_sortino": 3.0,
                                "mean_window_sortino": 2.0,
                                "mean_window_rank_ic": 0.04,
                                "recent_positive_rank_ic_ratio": 0.7,
                                "tradability_filter_available": True,
                                "row_count_after_signal_and_target": 1000,
                                "tradability_ic_excluded_row_count": 10,
                                "expression": "CSRank(Mul($open,$amount))",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            policy = build_stock_pit_search_control_policy(
                [policy_root],
                expected_dataset_role="stock_pit_panel",
            )

            ledger = build_stock_pit_forward_first_large_search_ledger(
                path=panel_path,
                round_count=1,
                candidates_per_round=500,
                target_window_count=8,
                max_window=40,
                search_control_policy=policy,
            )

            crossover_records = [
                record
                for record in ledger["records"]
                if record.get("proposal_kind") == "policy_crossover_probe"
            ]
            self.assertTrue(crossover_records)
            self.assertTrue(all(record["generator_project"] == "rx_v1_policy_crossover" for record in crossover_records))
            self.assertTrue(any("Mul(" in record["expression"] for record in crossover_records))
            self.assertEqual(
                ledger["search_control_schedule_audit"]["scope"],
                "bandit_ucb_record_scheduling_before_validation_budget_cut",
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_rx_typed_beam_ledger_generates_priority_programs(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-rx-beam-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            for day_index in range(70):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.02)
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                str(100000 + code_index * 1000),
                                str(10000 + code_index * 100),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            ledger = build_stock_pit_rx_typed_beam_search_ledger(
                path=panel_path,
                round_count=1,
                candidates_per_round=80,
                target_window_count=8,
                max_window=40,
                beam_width=12,
                max_beam_records=120,
            )

            self.assertEqual(ledger["search_version"], "phase2-stock-pit-rx-typed-beam-search-v1-2026-05-10")
            self.assertEqual(ledger["record_count"], 80)
            self.assertTrue(ledger["efficiency_contract"]["typed_beam_generation"])
            self.assertFalse(ledger["efficiency_contract"]["uses_learned_surrogate"])
            self.assertTrue(ledger["rx_beam_report"]["emitted_record_count"] > 0)
            self.assertTrue(any(record.get("generator_project") == "rx_v1_typed_beam" for record in ledger["records"]))
            self.assertTrue(
                any(
                    record.get("proposal_kind") == "rx_typed_beam_interaction"
                    for record in ledger["records"]
                )
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_rx_beam_uses_canonical_capacity_fields_when_present(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-rx-beam-cap-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = [
                "date,open,high,low,close,amount,volume,code,"
                "final_float_market_cap,float_market_cap_billion,final_float_market_cap_billion,"
                "final_total_market_cap,market_cap_billion"
            ]
            base = date(2025, 1, 2)
            for day_index in range(70):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + (day_index * 0.02)
                    float_cap = 1_000_000_000 + code_index * 100_000_000 + day_index * 1_000_000
                    total_cap = float_cap * 1.35
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                str(100000 + code_index * 1000),
                                str(10000 + code_index * 100),
                                f"88000{code_index + 1}",
                                f"{float_cap:.4f}",
                                f"{float_cap / 1_000_000_000:.6f}",
                                f"{float_cap / 1_000_000_000:.6f}",
                                f"{total_cap:.4f}",
                                f"{total_cap / 1_000_000_000:.6f}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            ledger = build_stock_pit_rx_typed_beam_search_ledger(
                path=panel_path,
                round_count=1,
                candidates_per_round=120,
                target_window_count=8,
                max_window=40,
                beam_width=16,
                max_beam_records=180,
            )

            canonical = ledger["field_contract"]["canonical_capacity_generation_fields"]
            expressions = [record["expression"] for record in ledger["records"]]
            self.assertEqual(canonical["float_cap"], "final_float_market_cap")
            self.assertEqual(canonical["total_cap"], "final_total_market_cap")
            self.assertIn("final_float_market_cap", "\n".join(expressions))
            self.assertNotIn("$final_float_market_cap_billion", "\n".join(expressions))
            self.assertEqual(
                ledger["rx_beam_report"]["collinear_capacity_field_policy"],
                "one_canonical_field_per_semantic_family; redundant same-source fields kept for diagnostics only",
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_proof_suite_reports_cluster_dominance_and_validation_yields(self) -> None:
        rows = [
            {
                "candidate_id": f"a{index}",
                "primitive_family": "limit_pressure_x_turnover",
                "proposal_kind": "rx_typed_beam_interaction",
                "mean_window_rank_ic": 0.05 if index < 2 else 0.01,
                "mean_window_long_sortino": 4.2 if index == 0 else 1.0,
                "mean_window_sortino": 0.8,
                "tradability_filter_available": True,
                "row_count_after_signal_and_target": 100,
                "tradability_ic_excluded_row_count": 2,
                "expression": "CSRank(Mul($limit_up_pressure,$turnover_rate))",
            }
            for index in range(4)
        ]
        report = {"evaluated_count": 4, "unsupported_count": 0, "evaluations": rows}

        coverage = stock_pit_coverage_cluster_health(rows)
        summary = summarize_stock_pit_validation_report(report, strong_ic_threshold=0.045, strong_sortino_threshold=4.0)

        self.assertEqual(coverage["decision"], "FLAG_CLUSTER_HEALTH")
        self.assertIn("family_dominance", coverage["warnings"])
        self.assertEqual(summary["strong_ic_count"], 2)
        self.assertEqual(summary["joint_strong_count"], 1)
        self.assertEqual(summary["coverage_cluster_health"]["row_count"], 4)

    def test_stock_pit_search_ab_test_runs_equal_budget_variants(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-proof-suite-ab-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,limit_up_pressure,limit_down_pressure"]
            base = date(2025, 1, 2)
            for day_index in range(48):
                day = base + timedelta(days=day_index)
                for code_index in range(8):
                    drift = 0.015 * day_index * (code_index + 1)
                    close = 10.0 + code_index + drift
                    amount = (100_000 + code_index * 8_000) * (1.0 + day_index * 0.002)
                    volume = 10_000 + code_index * 300 + day_index * 20
                    limit_up_pressure = 1.0 if code_index >= 6 and day_index % 5 == 0 else 0.0
                    limit_down_pressure = 1.0 if code_index <= 1 and day_index % 7 == 0 else 0.0
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 0.998:.4f}",
                                f"{close * 1.010:.4f}",
                                f"{close * 0.990:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                f"{limit_up_pressure:.1f}",
                                f"{limit_down_pressure:.1f}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = run_stock_pit_search_ab_test(
                output_root=temp_root / "proof",
                dataset_path=panel_path,
                candidate_budget=6,
                target_window_count=3,
                max_window=10,
                beam_width=4,
                max_beam_records=16,
                top_bottom_quantile=0.25,
                recent_quarter_window_count=1,
                recent_warmup_days=12,
                include_ucb=True,
            )

            variants = {item["variant"]: item for item in report["variants"]}
            self.assertEqual(report["experiment_id"], "stock_pit_search_ab_test")
            self.assertEqual(set(variants), {"baseline_forward_first", "rx_typed_beam_no_policy", "rx_typed_beam_ucb"})
            self.assertTrue((temp_root / "proof" / "baseline_forward_first" / "candidate_ledger.json").exists())
            self.assertEqual(variants["baseline_forward_first"]["candidate_count"], 6)
            self.assertEqual(len(report["comparisons_to_baseline"]), 2)
            self.assertTrue(report["pairwise_comparisons"])
            self.assertIn(report["ab_gate_decision"], {"PASS_AB_ADVANTAGE_RESEARCH_EVIDENCE", "NO_AB_ADVANTAGE_DETECTED"})
            self.assertIn("coverage_cluster_health", variants["rx_typed_beam_no_policy"]["summary"])
            self.assertIn("top_reward_coverage_cluster_health", variants["rx_typed_beam_no_policy"]["summary"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_fast_to_strict_calibration_links_fast_proxy_to_strict_audit(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-proof-suite-strict-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            base = date(2025, 1, 2)
            for day_index in range(24):
                day = base + timedelta(days=day_index)
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.025 * code_index)
                    volume = 10_000 + code_index * 200 + day_index * 30
                    amount = close * volume
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 0.997:.4f}",
                                f"{close * 1.011:.4f}",
                                f"{close * 0.989:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            fast_report = {
                "ledger_path": "synthetic-fast-report",
                "evaluations": [
                    {
                        "candidate_id": "fast-1",
                        "primitive_family": "price_rank",
                        "proposal_kind": "test",
                        "mean_window_rank_ic": 0.04,
                        "mean_window_long_return": 0.002,
                        "mean_window_long_sortino": 3.0,
                        "mean_window_sortino": 2.0,
                        "recent_positive_rank_ic_ratio": 0.75,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 100,
                        "tradability_ic_excluded_row_count": 0,
                        "expression": "CSRank($close)",
                    }
                ],
            }

            report = run_stock_pit_fast_to_strict_calibration(
                fast_report,
                output_root=temp_root / "strict",
                dataset_path=panel_path,
                top_n=1,
                horizons=(1,),
                top_bottom_quantile=0.25,
                cost_bps=5.0,
                recent_quarter_window_count=1,
                recent_warmup_days=8,
            )

            self.assertEqual(report["experiment_id"], "stock_pit_fast_to_strict_calibration")
            self.assertEqual(report["top_n"], 1)
            self.assertEqual(len(report["strict_rows"]), 1)
            self.assertTrue(Path(report["strict_rows"][0]["strict_report_path"]).exists())
            self.assertIn("strict_pass_proxy_rate", report)
            self.assertIn(
                report["calibration_gate_decision"],
                {"PASS_FAST_TO_STRICT_CALIBRATION_SMOKE", "FLAG_FAST_TO_STRICT_CALIBRATION_NEEDS_MORE_EVIDENCE"},
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_after_open_lags_capacity_fields_and_reports_long_diagnostics(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-capacity-diagnostics-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = [
                "date,open,high,low,close,amount,volume,code,"
                "final_float_market_cap,final_total_market_cap,market_cap_conflict_gt5pct"
            ]
            base = date(2025, 1, 2)
            for day_index in range(16):
                day = base + timedelta(days=day_index)
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.03)
                    amount = 5_000_000 + code_index * 500_000 + day_index * 1000
                    float_cap = 800_000_000 + code_index * 120_000_000 + day_index * 2_000_000
                    conflict = 1 if code_index == 7 and day_index % 3 == 0 else 0
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * 1.001:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(10000 + code_index * 100),
                                f"88000{code_index + 1}",
                                f"{float_cap:.4f}",
                                f"{float_cap * 1.4:.4f}",
                                str(conflict),
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = validate_expression_on_real_market_panel(
                "CSRank($final_float_market_cap)",
                path=panel_path,
                signal_clock="after_open",
                top_bottom_quantile=0.25,
            )

            self.assertEqual(report["field_lags"]["final_float_market_cap"], 1)
            self.assertEqual(report["field_lags"]["final_total_market_cap"], 1)
            self.assertIsNotNone(report["mean_window_long_selected_amount"])
            self.assertIsNotNone(report["mean_window_long_selected_final_float_market_cap"])
            self.assertIsNotNone(report["mean_window_long_selected_market_cap_conflict_rate"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_prepare_market_panel_uses_float_share_for_turnover_rate_when_available(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02"],
                "code": ["880001", "880001"],
                "open": [10.0, 10.2],
                "high": [10.5, 10.6],
                "low": [9.8, 10.0],
                "close": [10.1, 10.3],
                "amount": [1_000_000.0, 1_200_000.0],
                "volume": [100_000.0, 120_000.0],
                "float_share": [10_000_000.0, 10_000_000.0],
            }
        )

        prepared = _prepare_market_panel(frame)

        self.assertAlmostEqual(float(prepared.loc[0, "turnover_rate"]), 0.01)
        self.assertAlmostEqual(float(prepared.loc[1, "turnover_rate"]), 0.012)

    def test_prepare_market_panel_filters_non_stock_rows_when_metadata_available(self) -> None:
        frame = pd.DataFrame(
            {
                "date": ["2026-01-01"] * 5,
                "code": ["sz000001", "sh000001", "sz399001", "bj899050", "bj920001"],
                "market": ["sz", "sh", "sz", "bj", "bj"],
                "instrument_type": ["stock", "index", "stock", "stock", "stock"],
                "open": [10.0, 11.0, 12.0, 13.0, 14.0],
                "high": [10.5, 11.5, 12.5, 13.5, 14.5],
                "low": [9.8, 10.8, 11.8, 12.8, 13.8],
                "close": [10.1, 11.1, 12.1, 13.1, 14.1],
                "amount": [1_000_000.0] * 5,
                "volume": [100_000.0] * 5,
            }
        )

        prepared = _prepare_market_panel(frame)

        self.assertEqual(prepared["code"].tolist(), ["bj920001", "sz000001"])

    def test_limit_state_masks_falls_back_when_limit_columns_are_all_missing(self) -> None:
        frame = pd.DataFrame(
            {
                "code": ["sz000001", "sz000002", "sz000003"],
                "is_limit_up": [np.nan, np.nan, np.nan],
                "is_limit_down": [np.nan, np.nan, np.nan],
                "rt_change_pct": [10.1, -10.2, 1.2],
                "susp": [0.0, 0.0, 0.0],
            }
        )

        masks = _limit_state_masks(frame)

        self.assertEqual(masks["limit_up_source"], "rt_change_pct>=9.8")
        self.assertEqual(masks["limit_down_source"], "rt_change_pct<=-9.8")
        self.assertEqual(masks["limit_up"].tolist(), [True, False, False])
        self.assertEqual(masks["limit_down"].tolist(), [False, True, False])

    def test_load_market_panel_attaches_tdxgp_limit_status_before_rt_fallback(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-tdxgp-limit-status-"))
        try:
            market_path = temp_root / "phase2_stock_tdx_official_20260101_to_20260103_maxopt.parquet"
            pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-01", "2026-01-01"],
                    "code": ["sz000001", "sz000002", "sz000003"],
                    "market": ["sz", "sz", "sz"],
                    "instrument_type": ["stock", "stock", "stock"],
                    "open": [10.0, 10.0, 10.0],
                    "high": [11.0, 10.8, 10.5],
                    "low": [9.9, 9.0, 9.7],
                    "close": [11.0, 9.0, 10.4],
                    "amount": [1_000_000.0, 1_000_000.0, 1_000_000.0],
                    "volume": [100_000.0, 100_000.0, 100_000.0],
                    "is_limit_up": [np.nan, np.nan, np.nan],
                    "is_limit_down": [np.nan, np.nan, np.nan],
                    "rt_change_pct": [10.1, -10.1, 10.2],
                    "susp": [0.0, 0.0, 0.0],
                }
            ).to_parquet(market_path, index=False)
            pd.DataFrame(
                {
                    "date": ["2026-01-01", "2026-01-01", "2026-01-01"],
                    "symbol": ["sz000001", "sz000002", "sz000003"],
                    "type_id": [15, 15, 15],
                    "value1": [2.0, -2.0, 1.0],
                    "value2": [1000.0, -1000.0, 0.0],
                }
            ).to_parquet(
                temp_root / "tdxgp_gpjvalue_types_1-3-6-11-12-13-15-16_since_20260101.parquet",
                index=False,
            )

            frame = _load_market_panel(market_path)
            masks = _limit_state_masks(frame)

            self.assertEqual(masks["limit_up_source"], "tdxgp_gpjvalue_15_status==2")
            self.assertEqual(masks["limit_down_source"], "tdxgp_gpjvalue_15_status==-2")
            self.assertFalse(masks["derived_from_rt_change"])
            self.assertEqual(masks["limit_up"].tolist(), [True, False, False])
            self.assertEqual(masks["limit_down"].tolist(), [False, True, False])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_terminal_reward_proxy_includes_capacity_and_cap_conflict_terms(self) -> None:
        row = {
            "expression": "CSRank(Div(Mean($amount,3),Mean($final_float_market_cap,20)))",
            "mean_window_long_return": 0.002,
            "mean_window_long_sortino": 1.2,
            "mean_window_sortino": 0.6,
            "mean_window_rank_ic": 0.03,
            "recent_positive_rank_ic_ratio": 0.7,
            "tradability_filter_available": True,
            "tradability_ic_excluded_row_count": 10,
            "row_count_after_signal_and_target": 1000,
            "mean_window_long_selected_amount": 30_000_000,
            "mean_window_long_selected_final_float_market_cap": 2_000_000_000,
            "mean_window_long_selected_market_cap_conflict_rate": 0.25,
        }

        reward = stock_pit_terminal_reward_proxy(row)

        self.assertGreater(reward["components"]["capacity_component"], 0.0)
        self.assertEqual(reward["components"]["cap_coverage_component"], 0.02)
        self.assertGreater(reward["components"]["cap_conflict_penalty"], 0.0)
        self.assertEqual(
            reward["scope"],
            "terminal_validation_reward_proxy_for_search_control_only",
        )

    def test_stock_pit_successive_halving_runs_cheap_stage_before_survivor_stage(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-successive-halving-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down,susp"]
            base = date(2025, 1, 2)
            for day_index in range(90):
                day = base + timedelta(days=day_index)
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.015)
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close * (1.0 + code_index * 0.0001):.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                str(100000 + code_index * 1000 + day_index * 10),
                                str(10000 + code_index * 100),
                                f"88000{code_index + 1}",
                                "0",
                                "0",
                                "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger = {
                "run_id": "test-halving-ledger",
                "recommended_validation_kwargs": {
                    "signal_clock": "after_open",
                    "feature_lag_days": 0,
                    "execution_lag_days": 1,
                },
                "records": [
                    {
                        "candidate_id": f"cand-{index}",
                        "expression": expression,
                        "retained": True,
                        "primitive_family": family,
                        "research_family": family,
                        "proposal_kind": "test_probe",
                    }
                    for index, (expression, family) in enumerate(
                        [
                            ("CSRank($open)", "open"),
                            ("CSRank($close)", "close"),
                            ("CSRank($amount)", "amount"),
                            ("CSRank($volume)", "volume"),
                            ("CSRank(Mom($close,2))", "momentum"),
                            ("Neg(CSRank($open))", "open"),
                        ]
                    )
                ],
            }
            ledger_path = temp_root / "candidate_ledger.json"
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False), encoding="utf-8")

            report = run_stock_pit_successive_halving_validation(
                ledger_path,
                output_root=temp_root / "halving",
                path=panel_path,
                top_bottom_quantile=0.2,
                stage0_recent_quarter_window_count=1,
                stage1_recent_quarter_window_count=1,
                recent_warmup_days=10,
                use_fast_context=True,
                survivor_fraction=0.5,
                min_survivors=2,
                max_family_share=1.0,
            )

            self.assertIn("successive_halving", report)
            self.assertEqual(report["successive_halving"]["stage0_candidate_count"], 6)
            self.assertLess(report["successive_halving"]["stage1_candidate_count"], 6)
            self.assertTrue((temp_root / "halving" / "successive_halving_stage0_report.json").exists())
            self.assertTrue((temp_root / "halving" / "successive_halving_stage1_report.json").exists())
            self.assertTrue(str(report["validation_acceleration_mode"]).startswith("successive_halving_"))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_factor_library_optimizer_dedupes_and_caps_family_weight(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-factor-library-"))
        try:
            report = {
                "dataset_role": "stock_pit_panel",
                "evaluations": [
                    {
                        "candidate_id": "limit-a",
                        "primitive_family": "limit_pressure_x_turnover",
                        "proposal_kind": "interaction_probe",
                        "mean_window_long_return": 0.004,
                        "mean_window_long_sortino": 4.2,
                        "mean_window_sortino": 2.0,
                        "mean_window_rank_ic": 0.05,
                        "recent_positive_rank_ic_ratio": 0.75,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 10,
                        "expression": "CSRank(Mul(ZScore($open),ZScore($turnover_rate)))",
                    },
                    {
                        "candidate_id": "limit-dup-weaker",
                        "primitive_family": "limit_pressure_x_turnover",
                        "proposal_kind": "interaction_probe",
                        "mean_window_long_return": 0.001,
                        "mean_window_long_sortino": 1.0,
                        "mean_window_sortino": 0.5,
                        "mean_window_rank_ic": 0.01,
                        "recent_positive_rank_ic_ratio": 0.55,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 10,
                        "expression": "CSRank(Mul(ZScore($open),ZScore($turnover_rate)))",
                    },
                    {
                        "candidate_id": "limit-b",
                        "primitive_family": "limit_pressure_x_turnover",
                        "proposal_kind": "interaction_probe",
                        "mean_window_long_return": 0.003,
                        "mean_window_long_sortino": 3.7,
                        "mean_window_sortino": 1.8,
                        "mean_window_rank_ic": 0.04,
                        "recent_positive_rank_ic_ratio": 0.72,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 12,
                        "expression": "CSRank(Mul(ZScore($close),ZScore($amount)))",
                    },
                    {
                        "candidate_id": "gap-a",
                        "primitive_family": "open_gap_reversal",
                        "proposal_kind": "shape_probe",
                        "mean_window_long_return": 0.0025,
                        "mean_window_long_sortino": 3.0,
                        "mean_window_sortino": 1.2,
                        "mean_window_rank_ic": 0.035,
                        "recent_positive_rank_ic_ratio": 0.68,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 8,
                        "expression": "Neg(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))))",
                    },
                    {
                        "candidate_id": "vol-a",
                        "primitive_family": "volatility_compression",
                        "proposal_kind": "state_probe",
                        "mean_window_long_return": 0.0015,
                        "mean_window_long_sortino": 2.5,
                        "mean_window_sortino": 1.1,
                        "mean_window_rank_ic": 0.025,
                        "recent_positive_rank_ic_ratio": 0.62,
                        "tradability_filter_available": True,
                        "row_count_after_signal_and_target": 1000,
                        "tradability_ic_excluded_row_count": 5,
                        "expression": "CSRank(Div(Mean(Abs($ret),3),Mean(Abs($ret),20)))",
                    },
                ],
            }
            (temp_root / "stage1_validation_report.json").write_text(
                json.dumps(report, ensure_ascii=False),
                encoding="utf-8",
            )

            optimized = build_stock_pit_factor_library_optimizer_report(
                [temp_root],
                max_factors=4,
                max_per_family=1,
                max_per_cluster=1,
                shrinkage=0.25,
                max_family_weight=0.45,
                max_cluster_weight=0.45,
            )

            selected = optimized["selected_factors"]
            self.assertEqual(optimized["dedupe_report"]["duplicate_expression_count"], 1)
            self.assertEqual(len(selected), 3)
            self.assertEqual(sum(1 for item in selected if item["primitive_family"] == "limit_pressure_x_turnover"), 1)
            self.assertAlmostEqual(
                sum(float(item["optimizer_weight"]) for item in selected),
                1.0,
                places=6,
            )
            family_weights = {
                item["family"]: item["weight"]
                for item in optimized["weight_report"]["family_weights"]
            }
            self.assertLessEqual(family_weights["limit_pressure_x_turnover"], 0.45 + 1e-6)
            self.assertFalse(optimized["method_contract"]["uses_markowitz"])
            self.assertEqual(optimized["commercial_readiness_decision"], "RESEARCH_LIBRARY_ONLY")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_search_control_policy_quarantines_wrong_dataset_role(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-search-control-role-"))
        try:
            (temp_root / "stage1_validation_report.json").write_text(
                json.dumps(
                    {
                        "dataset_role": "sector_panel",
                        "evaluations": [
                            {
                                "candidate_id": "sector-1",
                                "primitive_family": "sector_family",
                                "mean_window_long_sortino": 10.0,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            policy = build_stock_pit_search_control_policy(
                [temp_root],
                expected_dataset_role="stock_pit_panel",
            )

            self.assertFalse(policy["active"])
            self.assertEqual(policy["family_count"], 0)
            self.assertEqual(policy["skipped_sources"][0]["reason"], "dataset_role_mismatch_or_unscoped")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_chain_audit_marks_discovery_ready_but_not_commercial_ready(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-chain-audit-"))
        try:
            panel_path = temp_root / "phase2_stock_validation_slice_test.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down,susp"]
            base = date(2025, 1, 2)
            for day_index in range(12):
                day = base + timedelta(days=day_index)
                for code_index in range(5):
                    close = 10.0 + code_index + day_index * 0.01
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{close:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.99:.4f}",
                                f"{close:.4f}",
                                "100000",
                                "10000",
                                f"88000{code_index + 1}",
                                "0",
                                "0",
                                "0",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            previous_root = temp_root / "previous"
            previous_root.mkdir()
            (previous_root / "candidate_ledger.json").write_text(
                json.dumps(
                    {
                        "run_id": "previous",
                        "dataset_role": "stock_pit_panel",
                        "records": [{"candidate_id": "p1", "expression": "CSRank($open)"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            audit = build_stock_pit_chain_audit(
                dataset_path=panel_path,
                previous_search_roots=[previous_root],
                use_fast_context=True,
                parallel_workers=1,
                max_family_share=0.12,
            )

            self.assertTrue(audit["next_search_ready"])
            self.assertFalse(audit["commercial_ready"])
            self.assertEqual(audit["commercial_readiness_decision"], "HOLD_RESEARCH")
            self.assertEqual(audit["chain"]["data_fields"]["status"], "PARTIAL")
            self.assertEqual(audit["chain"]["reward"]["status"], "PARTIAL")
            self.assertEqual(audit["chain"]["validation"]["status"], "RESEARCH_ONLY")
            self.assertEqual(audit["chain"]["search_memory"]["previous_source_ledger_count"], 1)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_ashare_state_ledger_uses_limit_flags_only_for_validation(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-ashare-state-search-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,is_limit_up,is_limit_down,code"]
            base = date(2025, 1, 2)
            for day_index in range(80):
                day = base + timedelta(days=day_index)
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.03)
                    prior_close = close / 1.01
                    is_limit_up = 1 if day_index % 17 == 0 and code_index == 0 else 0
                    is_limit_down = 1 if day_index % 19 == 0 and code_index == 1 else 0
                    lines.append(
                        ",".join(
                            [
                                day.isoformat(),
                                f"{prior_close * 1.004:.4f}",
                                f"{close * 1.012:.4f}",
                                f"{close * 0.988:.4f}",
                                f"{close:.4f}",
                                str(100000 + code_index * 1000),
                                str(10000 + code_index * 100),
                                str(is_limit_up),
                                str(is_limit_down),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            ledger = build_stock_pit_ashare_state_ledger(
                path=panel_path,
                shard_index=0,
                shard_count=4,
                target_window_count=8,
                max_window=40,
            )

            self.assertEqual(ledger["recommended_validation_kwargs"]["signal_clock"], "after_open")
            self.assertTrue(ledger["field_contract"]["current_open_allowed"])
            self.assertTrue(ledger["field_contract"]["full_day_bar_fields_lagged_by_evaluator"])
            self.assertTrue(ledger["field_contract"]["limit_up_down_flags_not_used_as_signal_features"])
            self.assertTrue(ledger["efficiency_contract"]["core_search_system_modified"] is False)
            self.assertGreater(ledger["full_space_candidate_count"], ledger["record_count"])
            expressions = [record["expression"] for record in ledger["records"]]
            self.assertTrue(any("$open" in expression for expression in expressions))
            self.assertTrue(any("CSResidual" in expression or "Mul(" in expression for expression in expressions))
            self.assertTrue(all("$is_limit_up" not in expression for expression in expressions))
            self.assertTrue(all("$is_limit_down" not in expression for expression in expressions))
            self.assertTrue(all(record["uses_limit_flags_as_features"] is False for record in ledger["records"]))
            self.assertTrue(any(record.get("uses_prior_limit_event_features") is True for record in ledger["records"]))

            ledger_path = temp_root / "candidate_ledger.json"
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            validation = batch_validate_candidate_ledger(
                ledger_path,
                path=panel_path,
                retained_only=True,
                max_candidates=8,
                top_bottom_quantile=0.2,
                recent_quarter_window_count=1,
                recent_warmup_days=20,
            )
            self.assertEqual(validation["unsupported_count"], 0)
            self.assertEqual(validation["signal_clock"], "after_open")
            self.assertTrue(all(item["tradability_filter_available"] for item in validation["evaluations"]))
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_limit_event_fields_are_after_open_lagged(self) -> None:
        rows = []
        dates = pd.date_range("2026-01-01", periods=5, freq="D")
        flags_by_code = {
            "000001.SZ": [0, 1, 1, 0, 0],
            "000002.SZ": [0, 0, 0, 0, 0],
        }
        for code, flags in flags_by_code.items():
            for offset, (day, is_limit_up) in enumerate(zip(dates, flags)):
                close = 10.0 + offset
                rows.append(
                    {
                        "date": day,
                        "code": code,
                        "open": close * 0.99,
                        "high": close * 1.01,
                        "low": close * 0.98,
                        "close": close,
                        "amount": 1_000_000 + offset,
                        "volume": 100_000 + offset,
                        "is_limit_up": is_limit_up,
                        "is_limit_down": 0,
                        "rt_change_pct": 9.9 if is_limit_up else 0.0,
                        "susp": 0,
                    }
                )
        frame = _prepare_market_panel(pd.DataFrame(rows))
        signal_frame, clock_report = _signal_evaluation_frame(frame, signal_clock="after_open")
        self.assertEqual(clock_report["field_lags"]["limit_up_streak"], 1)
        self.assertEqual(clock_report["field_lags"]["limit_up_break"], 1)

        streak = evaluate_panel_expression(
            signal_frame,
            "$limit_up_streak",
            cache={},
            field_lags=clock_report["field_lags"],
        )
        break_flag = evaluate_panel_expression(
            signal_frame,
            "$limit_up_break",
            cache={},
            field_lags=clock_report["field_lags"],
        )
        one = frame["code"] == "000001.SZ"
        by_date = frame.loc[one, ["date"]].copy()
        by_date["streak_signal_value"] = streak.loc[one].to_numpy()
        by_date["break_signal_value"] = break_flag.loc[one].to_numpy()
        values = {
            pd.Timestamp(row.date).date().isoformat(): (row.streak_signal_value, row.break_signal_value)
            for row in by_date.itertuples(index=False)
        }
        self.assertTrue(pd.isna(values["2026-01-01"][0]))
        self.assertEqual(values["2026-01-03"][0], 1.0)
        self.assertEqual(values["2026-01-04"][0], 2.0)
        self.assertEqual(values["2026-01-05"][1], 1.0)

    def test_stock_pit_trend_state_fields_are_optional_and_after_open_lagged(self) -> None:
        rows = []
        dates = pd.date_range("2026-01-01", periods=26, freq="D")
        for code_index in range(6):
            code = f"00000{code_index + 1}.SZ"
            slope = 0.2 * (code_index - 2)
            for offset, day in enumerate(dates):
                close = 20.0 + code_index + (offset * slope)
                rows.append(
                    {
                        "date": day,
                        "code": code,
                        "open": close * 0.99,
                        "high": close * 1.01,
                        "low": close * 0.98,
                        "close": close,
                        "amount": 1_000_000 + (offset * 10_000),
                        "volume": 100_000 + (offset * 100),
                    }
                )
        raw = pd.DataFrame(rows)
        base_frame = _prepare_market_panel(raw.copy())
        enriched = _prepare_market_panel(raw.copy(), enable_trend_state_features=True)
        self.assertNotIn("stock_trend_eff", base_frame.columns)
        self.assertIn("stock_trend_eff", enriched.columns)

        signal_frame, clock_report = _signal_evaluation_frame(enriched, signal_clock="after_open")
        self.assertEqual(clock_report["field_lags"]["stock_trend_eff"], 1)
        self.assertEqual(clock_report["field_lags"]["market_trend_eff"], 1)
        lagged = evaluate_panel_expression(
            signal_frame,
            "$stock_trend_eff",
            cache={},
            field_lags=clock_report["field_lags"],
        )
        one = enriched["code"] == "000006.SZ"
        raw_values = enriched.loc[one, "stock_trend_eff"].reset_index(drop=True)
        signal_values = lagged.loc[one].reset_index(drop=True)
        self.assertAlmostEqual(float(signal_values.iloc[-1]), float(raw_values.iloc[-2]), places=12)

    def test_batch_validation_can_enable_pit_trend_state_adapter_from_ledger(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-trend-state-adapter-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = pd.date_range("2026-01-01", periods=34, freq="D")
            for code_index in range(6):
                slope = 0.15 * (code_index - 2)
                for offset, day in enumerate(dates):
                    close = 30.0 + code_index + (offset * slope)
                    lines.append(
                        ",".join(
                            [
                                day.date().isoformat(),
                                f"{close * 0.99:.6f}",
                                f"{close * 1.01:.6f}",
                                f"{close * 0.98:.6f}",
                                f"{close:.6f}",
                                "1000000",
                                "100000",
                                f"00000{code_index + 1}.SZ",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")
            ledger_path = temp_root / "candidate_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "trend-state-ledger",
                        "recommended_validation_kwargs": {
                            "signal_clock": "after_open",
                            "feature_lag_days": 0,
                            "execution_lag_days": 1,
                            "enable_trend_state_features": True,
                        },
                        "records": [
                            {
                                "candidate_id": "trend-001",
                                "expression": "CSRank($stock_trend_eff)",
                                "retained": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = batch_validate_candidate_ledger(
                ledger_path,
                path=panel_path,
                retained_only=True,
                recent_quarter_window_count=1,
                recent_warmup_days=30,
                top_bottom_quantile=0.2,
            )

            self.assertTrue(report["enable_trend_state_features"])
            self.assertEqual(report["validation_defaults_source"]["enable_trend_state_features"], "ledger_recommended_validation_kwargs")
            self.assertEqual(report["unsupported_count"], 0)
            self.assertEqual(report["evaluated_count"], 1)
            self.assertIn("stock_trend_eff", report["trend_state_feature_contract"]["feature_fields"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_stock_pit_forward_first_replay_aware_shortlist_uses_family_priors_without_candidate_forward_labels(self) -> None:
        stage1_report = {
            "shard_index": 0,
            "evaluations": [
                {
                    "candidate_id": "candidate-momentum",
                    "expression": "Neg(CSRank(Mom($close,6)))",
                    "primitive_family": "momentum_rank",
                    "proposal_kind": "side_directional_probe",
                    "mean_window_rank_ic": 0.03,
                    "mean_window_sortino": 1.0,
                    "recent_positive_rank_ic_ratio": 1.0,
                },
                {
                    "candidate_id": "candidate-volume",
                    "expression": "CSRank(Mul(ZScore($volume),ZScore(Mom($close,6))))",
                    "primitive_family": "volume_ratio_x_momentum_curve",
                    "proposal_kind": "cross_axis_interaction_probe",
                    "mean_window_rank_ic": 0.02,
                    "mean_window_sortino": 1.2,
                    "recent_positive_rank_ic_ratio": 1.0,
                },
                {
                    "candidate_id": "candidate-volatility",
                    "expression": "Neg(CSRank(Mean(Abs($ret),4)))",
                    "primitive_family": "volatility_rank",
                    "proposal_kind": "side_directional_probe",
                    "mean_window_rank_ic": 0.06,
                    "mean_window_sortino": 0.2,
                    "recent_positive_rank_ic_ratio": 1.0,
                },
                {
                    "candidate_id": "candidate-old",
                    "expression": "Neg(CSRank(Mom($close,10)))",
                    "primitive_family": "momentum_rank",
                    "proposal_kind": "side_directional_probe",
                    "mean_window_rank_ic": 0.04,
                    "mean_window_sortino": 1.5,
                    "recent_positive_rank_ic_ratio": 1.0,
                },
            ],
        }
        prior_replay = {
            "paired_primary_20bps": [
                {
                    "candidate_id": "replayed-momentum",
                    "primitive_family": "momentum_rank",
                    "train_positive": True,
                    "forward_positive": True,
                    "forward_net_mean": 0.001,
                    "forward_net_sortino": 1.3,
                },
                {
                    "candidate_id": "replayed-volume",
                    "primitive_family": "volume_ratio_x_momentum_curve",
                    "train_positive": True,
                    "forward_positive": False,
                    "forward_net_mean": -0.001,
                    "forward_net_sortino": -0.2,
                },
            ]
        }
        previous_shortlist = {"candidates": [{"candidate_id": "candidate-old", "expression": "Neg(CSRank(Mom($close,10)))"}]}

        report = build_stock_pit_forward_first_replay_aware_shortlist(
            stage1_reports=[stage1_report],
            prior_replay_reports=[prior_replay],
            previous_shortlists=[previous_shortlist],
            candidate_limit=3,
            max_per_family=2,
        )

        ids = [row["candidate_id"] for row in report["candidates"]]
        self.assertEqual(report["selection_status"], "forward_blind_candidate_selection_with_family_level_replay_soft_prior")
        self.assertFalse(report["commercial_edge_claim_allowed"])
        self.assertFalse(report["selection_rules"]["candidate_forward_labels_used"])
        self.assertIn("candidate-momentum", ids)
        self.assertIn("candidate-volume", ids)
        self.assertNotIn("candidate-old", ids)
        self.assertNotIn("candidate-volatility", ids)
        self.assertGreater(report["family_priors"]["momentum_rank"], report["family_priors"]["volume_ratio_x_momentum_curve"])

    def test_stock_pit_forward_first_five_day_proof_gate_blocks_without_independent_forward_periods(self) -> None:
        replay_report = {
            "experiment_id": "test-replay",
            "paired_primary_20bps": [
                {
                    "candidate_id": "candidate-5d",
                    "primitive_family": "momentum_rank",
                    "expression": "Neg(CSRank(Mom($close,6)))",
                    "rebalance_frequency_days": 5,
                    "mode": "long_short",
                    "cost_bps": 20.0,
                    "train_positive": True,
                    "forward_positive": True,
                    "train_net_mean": 0.0002,
                    "train_net_sortino": 0.5,
                    "forward_net_mean": 0.0008,
                    "forward_net_sortino": 1.1,
                    "forward_avg_turnover": 0.15,
                    "forward_max_drawdown": -0.02,
                },
                {
                    "candidate_id": "candidate-1d",
                    "primitive_family": "momentum_rank",
                    "expression": "Neg(CSRank(Mom($close,1)))",
                    "rebalance_frequency_days": 1,
                    "mode": "long_short",
                    "cost_bps": 20.0,
                    "train_positive": True,
                    "forward_positive": True,
                    "train_net_mean": 0.01,
                    "forward_net_mean": 0.01,
                    "forward_net_sortino": 3.0,
                    "forward_avg_turnover": 0.1,
                    "forward_max_drawdown": -0.01,
                },
            ],
        }
        audit_report = {
            "targets": [
                {
                    "candidate_id": "candidate-5d",
                    "summary": [
                        {
                            "label": "qlib_forward_shadow",
                            "strict_blockers": ["non_positive_cost_adjusted_primary_spread"],
                            "exposure_blockers": [],
                        }
                    ],
                }
            ]
        }

        gate = build_stock_pit_forward_first_five_day_proof_gate(
            [replay_report],
            audit_reports=[audit_report],
        )

        self.assertFalse(gate["commercial_edge_claim_allowed"])
        self.assertEqual(gate["counts"]["five_day_rows"], 1)
        self.assertEqual(gate["counts"]["qualified_rows"], 1)
        self.assertIn("independent_forward_period_count_below_2", gate["blockers"])
        self.assertIn("focused_audit_reports_contain_strict_or_exposure_blockers", gate["blockers"])
        self.assertEqual(gate["qualified_rows"][0]["candidate_id"], "candidate-5d")

    def test_validation_cost_report_from_ledger_sorts_candidates_by_cost(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-cost-"))
        try:
            ledger_path = temp_root / "candidate_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "run_id": "cost-test",
                        "records": [
                            {
                                "candidate_id": "slow",
                                "expression": "Cov(Corr(Cov($open,$low),$volume),Cov($high,$close))",
                                "retained": True,
                            },
                            {
                                "candidate_id": "cheap",
                                "expression": "CSRank($close)",
                                "retained": True,
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = build_validation_cost_report_from_ledger(ledger_path)

            self.assertEqual(report["source_run_id"], "cost-test")
            self.assertEqual(report["candidate_count"], 2)
            self.assertEqual(report["candidates"][0]["candidate_id"], "cheap")
            self.assertIn("cheap_fast_path", report["lane_counts"])
            self.assertIn("slow_relation_path", report["lane_counts"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_forward_shadow_watchlist_is_not_a_backtest_or_edge_claim(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-watchlist-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = ["2025-04-01", "2025-04-02", "2025-04-03", "2025-04-04", "2025-04-07"]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + day_index * 0.1 * code_index
                    volume = 10_000 + code_index * 100
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                str(volume * close),
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = build_forward_shadow_watchlist(
                "CSRank($close)",
                candidate_id="watch",
                path=panel_path,
                lookback_days=10,
                warmup_days=10,
                top_bottom_quantile=0.2,
            )

            self.assertEqual(report["status"], "regime_local_forward_watchlist")
            self.assertEqual(report["candidate_id"], "watch")
            self.assertEqual(report["as_of_date"], "2025-04-07")
            self.assertTrue(report["not_a_backtest"])
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertTrue(report["cannot_guarantee_next_3_months"])
            self.assertGreater(len(report["top_watchlist"]), 0)
            self.assertGreater(len(report["bottom_watchlist"]), 0)
            self.assertEqual(len(report["top_watchlist"]), report["side_count"])
            self.assertEqual(len(report["bottom_watchlist"]), report["side_count"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_strict_real_market_audit_reports_cost_turnover_and_exposure(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-strict-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2025-01-02",
                "2025-01-03",
                "2025-01-06",
                "2025-01-07",
                "2025-01-08",
                "2025-01-09",
                "2025-04-01",
                "2025-04-02",
                "2025-04-03",
                "2025-04-04",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    volume = 10_000 + code_index * 200 + day_index * 50
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = strict_audit_expression_on_real_market_panel(
                "CSRank(Mean($amount,2))",
                candidate_id="strict-test",
                path=panel_path,
                cost_bps=5.0,
            )

            self.assertEqual(report["candidate_id"], "strict-test")
            self.assertFalse(report["real_edge_claim_allowed"])
            self.assertEqual(report["cost_bps"], 5.0)
            self.assertEqual(report["operator_window_prior"], list(WINDOW_PRIOR))
            self.assertEqual(report["default_validation_horizon_days"], list(WINDOW_PRIOR))
            self.assertEqual(report["horizon_days"], list(WINDOW_PRIOR))
            self.assertEqual(report["horizon_policy"], "feature_algebra_window_prior")
            self.assertEqual(
                [item["horizon_days"] for item in report["horizon_reports"]],
                list(WINDOW_PRIOR),
            )
            self.assertIn("mean_cost_adjusted_window_spread", report["horizon_reports"][0])
            self.assertIn("mean_one_way_turnover", report["horizon_reports"][0])
            self.assertIn("amount", report["exposure_summary"])
            self.assertIn("sector_neutralization_not_run", report["blocker_flags"])
            self.assertIn(report["gatekeeper_decision"], {"HOLD_RESEARCH", "ALLOW_KEEP_REVIEW"})

            override_report = strict_audit_expression_on_real_market_panel(
                "CSRank(Mean($amount,2))",
                candidate_id="strict-test-override",
                path=panel_path,
                horizons=(1, 2),
                cost_bps=5.0,
            )
            self.assertEqual(override_report["horizon_days"], [1, 2])
            self.assertEqual(override_report["horizon_policy"], "explicit_override")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_strict_real_market_audit_can_run_bounded_recent_quarters(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-strict-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code"]
            dates = [
                "2024-12-20",
                "2025-01-02",
                "2025-01-03",
                "2025-03-31",
                "2025-04-01",
                "2025-04-02",
                "2025-04-08",
            ]
            for day_index, day in enumerate(dates):
                for code_index in range(6):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    volume = 10_000 + code_index * 100
                    amount = volume * close
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = strict_audit_expression_on_real_market_panel(
                "CSRank($close)",
                path=panel_path,
                horizons=(1,),
                recent_quarter_window_count=2,
                recent_warmup_days=5,
            )

            self.assertEqual(report["screening_mode"], "recent_2_quarter_strict_audit")
            self.assertEqual(report["evaluation_start_date"], "2025-01-01")
            self.assertEqual(report["evaluation_end_date"], "2025-04-08")
            self.assertEqual(report["recent_quarter_window_count"], 2)
            self.assertLess(report["loaded_panel_rows"], 42)
            self.assertEqual(report["horizon_reports"][0]["window_count"], 2)
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_strict_real_market_audit_uses_tradability_filtered_cost_shadow(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-real-strict-"))
        try:
            panel_path = temp_root / "panel.csv"
            lines = ["date,open,high,low,close,amount,volume,code,is_limit_up,is_limit_down"]
            dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"]
            for day_index, day in enumerate(dates):
                for code_index in range(8):
                    close = 10.0 + code_index + (day_index * 0.02 * code_index)
                    volume = 10_000 + code_index * 100
                    amount = volume * close
                    is_limit_up = 1 if day == "2025-01-03" and code_index == 7 else 0
                    is_limit_down = 1 if day == "2025-01-06" and code_index == 0 else 0
                    lines.append(
                        ",".join(
                            [
                                day,
                                f"{close * 0.99:.4f}",
                                f"{close * 1.01:.4f}",
                                f"{close * 0.98:.4f}",
                                f"{close:.4f}",
                                f"{amount:.4f}",
                                str(volume),
                                f"88000{code_index + 1}",
                                str(is_limit_up),
                                str(is_limit_down),
                            ]
                        )
                    )
            panel_path.write_text("\n".join(lines), encoding="utf-8")

            report = strict_audit_expression_on_real_market_panel(
                "CSRank($close)",
                path=panel_path,
                horizons=(1,),
                cost_bps=10.0,
            )

            self.assertTrue(report["turnover_cost_shadow_tradability_filtered"])
            self.assertEqual(report["tradability_limit_up_source"], "is_limit_up")
            self.assertEqual(report["tradability_limit_down_source"], "is_limit_down")
            self.assertGreater(report["tradability_entry_limit_up_row_count"], 0)
            self.assertGreater(report["tradability_exit_limit_down_row_count"], 0)
            self.assertIn("mean_one_way_turnover", report["horizon_reports"][0])
            self.assertIn("mean_cost_adjusted_window_spread", report["horizon_reports"][0])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_edge_reality_gate_is_report_only_and_penalizes_friction(self) -> None:
        liquid = make_candidate(
            expression="Corr(CSRank($volume),Log(Abs($amtm)))",
            ic_max=0.82,
            coverage=0.9,
            label="robust",
            oos_stability=0.88,
            archive_cell="liquid-cell",
        )
        liquid.retained = True
        liquid.oos_ic = 0.72
        liquid.fingerprint.update(
            {
                "size_tilt": 0.9,
                "turnover_proxy": 0.15,
                "decay_halflife": 0.85,
                "sector_concentration": 0.1,
                "beta_to_market": 0.15,
                "ic_regime_volatile": 0.2,
            }
        )

        costly = make_candidate(
            expression="Sign($vrat)",
            ic_max=0.55,
            coverage=0.2,
            label="weak",
            oos_stability=0.25,
            archive_cell="costly-cell",
        )
        costly.retained = True
        costly.oos_ic = 0.36
        costly.fingerprint.update(
            {
                "size_tilt": 0.05,
                "turnover_proxy": 0.95,
                "decay_halflife": 0.05,
                "sector_concentration": 0.95,
                "beta_to_market": 0.9,
                "ic_regime_volatile": 0.95,
            }
        )

        liquid_eval = evaluate_edge_reality(liquid)
        costly_eval = evaluate_edge_reality(costly)
        self.assertGreater(liquid_eval["net_edge_score"], costly_eval["net_edge_score"])
        self.assertTrue(liquid_eval["passes_reality_proxy"])
        self.assertFalse(costly_eval["passes_reality_proxy"])

        real_market_contract = {
            "dataset_path": "G:\\Project_V7_Rotation\\scripts\\data\\tdx_sector_data_p3_enhanced.csv",
            "dataset_kind": "ohlcv_cross_section_panel_csv",
            "exists": True,
            "can_start_real_validation": True,
        }
        report = build_edge_reality_gate_report(
            run_id="test-run",
            records=[liquid, costly],
            real_market_data_contract=real_market_contract,
        )
        self.assertTrue(report["does_not_change_archive_retention"])
        self.assertTrue(report["not_claiming_tradable_alpha"])
        self.assertEqual(report["evidence_tier"], "synthetic_proxy_only")
        self.assertEqual(report["proxy_role"], "candidate_triage_only_not_real_edge_evidence")
        self.assertTrue(report["real_market_data_contract"]["can_start_real_validation"])
        self.assertFalse(report["real_market_data_consumed_by_runtime"])
        self.assertIn("walk_forward_oos_not_run", report["real_edge_promotion_blockers"])
        self.assertIn("tradable_net_edge", report["cannot_support_claims"])
        self.assertIn("quarterly_3_month_purged_embargoed_walk_forward_oos", report["required_validation_before_real_edge_claim"])
        self.assertEqual(report["retained_candidate_count"], 2)
        self.assertEqual(report["reality_proxy_pass_count"], 1)

    def test_discarded_shadow_archive_is_report_only_and_surfaces_counterfactual_hits(self) -> None:
        retained = make_candidate(
            expression="CSRank($close)",
            ic_max=0.58,
            coverage=0.25,
            label="regime_conditional",
            oos_stability=0.45,
            archive_cell="cell-retained",
        )
        retained.retained = True
        retained.oos_ic = 0.12
        retained.round_index = 1

        discarded = make_candidate(
            expression="Div(Mean($amount,20),Mean($volume,5))",
            ic_max=0.62,
            coverage=0.25,
            label="regime_conditional",
            oos_stability=0.82,
            archive_cell="cell-retained",
        )
        discarded.retained = False
        discarded.oos_ic = 0.42
        discarded.round_index = 1
        discarded.fingerprint.update(
            {
                "size_tilt": 0.9,
                "turnover_proxy": 0.1,
                "decay_halflife": 0.8,
                "sector_concentration": 0.1,
                "beta_to_market": 0.1,
                "ic_regime_volatile": 0.2,
            }
        )

        report = build_discarded_space_shadow_report(
            run_id="shadow-test",
            records=[retained, discarded],
            sample_limit=4,
        )

        self.assertTrue(report["does_not_change_archive_retention"])
        self.assertEqual(report["discarded_candidate_count"], 1)
        self.assertGreater(report["discarded_best_net_edge_score"], report["retained_best_net_edge_score"])
        self.assertEqual(report["counterfactual_hit_count_in_sample"], 1)
        self.assertEqual(
            report["recommendation"],
            "review_archive_dominance_against_edge_proxy_before_tightening_filters",
        )

    def test_feature_algebra_treats_common_windows_as_prior_not_whitelist(self) -> None:
        self.assertEqual(expand_derived_fields("$ma2"), "Mean($close,2)")
        self.assertEqual(expand_derived_fields("$ma_2"), "Mean($close,2)")
        arbitrary = parse_derived_feature_name("close_ma_137")
        self.assertIsNotNone(arbitrary)
        self.assertEqual(arbitrary.expression, "Mean($close,137)")
        self.assertFalse(arbitrary.window_from_prior)

        report = operator_catalog_report()
        self.assertTrue(report["window_policy"]["parameterized"])
        self.assertTrue(report["window_policy"]["sampling_prior_is_not_a_whitelist"])

    def test_feature_algebra_is_connected_to_fingerprint_surrogate_and_variation(self) -> None:
        encoder = FieldEncoder()
        encoded = encoder.encode("ma2")
        self.assertEqual(encoded.field_name, "close_mean_2")
        self.assertEqual(encoded.field_type, "derived_price_ts")
        self.assertLess(encoded.behavior_profile["turnover"], encoder.encode("close").behavior_profile["turnover"])

        alias_fingerprint = build_behavioral_fingerprint("$ma2")
        explicit_fingerprint = build_behavioral_fingerprint("Mean($close,2)")
        self.assertEqual(alias_fingerprint, explicit_fingerprint)

        structures = extract_structural_features("$close_ma_137")
        self.assertIn("mean", structures["operators"])
        self.assertTrue(structures["has_time_series_operator"])
        self.assertIn("$close", structures["fields"])

        residual_structures = extract_structural_features("CSRank(Mul(CSResidual($open,$volume),ZScore($mbrd)))")
        self.assertIn("csresidual", residual_structures["operators"])
        self.assertIn("mul", residual_structures["operators"])
        self.assertIn("zscore", residual_structures["operators"])
        self.assertTrue(residual_structures["has_pair_operator"])

        edits = enumerate_single_step_edits("$close", "novelty_frontier")
        self.assertTrue(any("Mean(" in expression for expression in edits))
        self.assertTrue(any("Std(" in expression for expression in edits))
        self.assertTrue(any("CSResidual(" in expression for expression in edits))
        self.assertTrue(any("$price_pos" in expression or "$rps_score" in expression for expression in edits))

    def test_generator_hygiene_canonicalizes_equivalent_idempotent_wrappers(self) -> None:
        expression = " CSRank( CSRank( Abs( Abs($close) ) ) ) "
        canonical = canonicalize_expression_light(expression)
        self.assertEqual(canonical, "CSRank(Abs($close))")
        self.assertEqual(extract_structural_skeleton(expression), "CSRank(Abs(FIELD))")

    def test_single_step_variation_projects_pathological_parent_before_wrapping(self) -> None:
        pathological_parent = ("CSRank(" * 320) + "$close" + (")" * 320)
        self.assertTrue(is_pathological_expression(pathological_parent))
        edits = enumerate_single_step_edits(pathological_parent, "bridge_frontier")
        self.assertTrue(edits)
        self.assertTrue(all(not is_pathological_expression(expression) for expression in edits))
        self.assertTrue(all(expression_complexity(expression)["char_count"] < 800 for expression in edits))

    def test_archive_synthesis_ignores_pathological_skeleton_sources(self) -> None:
        pathological_source = make_candidate(
            expression=("CSRank(" * 320) + "$close" + (")" * 320),
            ic_max=0.9,
            coverage=0.8,
            label="pathological",
            oos_stability=0.2,
            archive_cell="pathological-cell",
        )
        normal_source = make_candidate(
            expression="Corr(CSRank($close),Sign($amtm))",
            ic_max=0.7,
            coverage=0.5,
            label="robust",
            oos_stability=0.8,
            archive_cell="normal-cell",
        )
        generated = generate_from_scratch_from_archive(
            target_behavior=build_behavioral_fingerprint("Cov($mbrd,Sign($pldn))"),
            archive=[pathological_source, normal_source],
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=4,
            seed_key="pathological-skeleton-test",
        )
        self.assertEqual(len(generated), 4)
        self.assertTrue(all(item["source_candidate_id"] != pathological_source.candidate_id for item in generated))
        self.assertTrue(all(not is_pathological_expression(str(item["expression"])) for item in generated))

    def test_local_search_memory_records_keys_reward_and_production_stats(self) -> None:
        record = make_candidate(
            expression="CSRank(CSRank($close))",
            ic_max=0.72,
            coverage=0.5,
            label="robust",
            oos_stability=0.75,
            archive_cell="memory-cell",
        )
        record.retained = True
        record.source_mode = "coverage_refresh_synthesis"
        record.frontier_lane = "bridge_frontier"
        memory = LocalSearchMemory()
        memory.record_evaluation(
            record=record,
            run_id="phase2-memory-test",
            generation_context={"coverage_refresh_source": "phase2_native_ast_expansion"},
        )
        report = memory.report(run_id="phase2-memory-test")
        self.assertTrue(memory.has_seen_expression("CSRank($close)"))
        self.assertEqual(expression_memory_key("CSRank(CSRank($close))"), expression_memory_key("CSRank($close)"))
        self.assertEqual(skeleton_memory_key("CSRank(CSRank($close))"), skeleton_memory_key("CSRank($close)"))
        key = production_rule_key(
            source_mode="coverage_refresh_synthesis",
            frontier_lane="bridge_frontier",
            generation_context={"coverage_refresh_source": "phase2_native_ast_expansion"},
        )
        self.assertIn(key, report["production_rule_stats"])
        self.assertGreater(candidate_reward_proxy(record)["reward"], 0.0)
        self.assertEqual(report["reward_policy"], "local_generator_training_proxy_not_tradable_edge_claim")

    def test_local_search_memory_inheritance_is_dataset_role_scoped(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-search-memory-role-filter-"))
        try:
            sector_record = make_candidate(
                expression="CSRank($open)",
                ic_max=0.7,
                coverage=0.5,
                label="sector",
                oos_stability=0.6,
                archive_cell="cell-sector",
            )
            stock_record = make_candidate(
                expression="CSRank($volume)",
                ic_max=0.6,
                coverage=0.5,
                label="stock",
                oos_stability=0.6,
                archive_cell="cell-stock",
            )
            unscoped_record = make_candidate(
                expression="CSRank($low)",
                ic_max=0.5,
                coverage=0.5,
                label="unscoped",
                oos_stability=0.5,
                archive_cell="cell-unscoped",
            )
            memory = LocalSearchMemory()
            memory.record_evaluation(record=sector_record, run_id="phase2-role-filter-test")
            memory.record_evaluation(record=stock_record, run_id="phase2-role-filter-test")
            memory.record_evaluation(record=unscoped_record, run_id="phase2-role-filter-test")
            memory.records[0]["real_replay_dataset_role"] = "legacy_sector_panel"
            memory.records[1]["real_replay_dataset_role"] = "stock_pit_panel"
            (temp_root / "search_memory.json").write_text(
                json.dumps(memory.report(run_id="phase2-role-filter-test"), ensure_ascii=False),
                encoding="utf-8",
            )

            inherited = LocalSearchMemory.from_previous_run(
                temp_root,
                expected_dataset_role="stock_pit_panel",
            )

            self.assertTrue(inherited.has_seen_expression("CSRank($volume)"))
            self.assertFalse(inherited.has_seen_expression("CSRank($open)"))
            self.assertFalse(inherited.has_seen_expression("CSRank($low)"))
            self.assertEqual(inherited.dataset_role_filter_report["quarantined_record_count"], 2)
            self.assertTrue(inherited.dataset_role_filter_report["unscoped_records_are_not_inherited"])
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_local_search_memory_enriches_reward_with_long_only_sortino_replay(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-search-memory-replay-"))
        try:
            record = make_candidate(
                expression="Corr(CSRank($close),Sign($amtm))",
                ic_max=0.65,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.62,
                archive_cell="memory-cell",
            )
            record.retained = True
            memory = LocalSearchMemory()
            memory.record_evaluation(record=record, run_id="phase2-memory-replay-test")
            write_json = {
                "run_id": "phase2-memory-replay-test",
                **memory.report(run_id="phase2-memory-replay-test"),
            }
            (temp_root / "search_memory.json").write_text(json.dumps(write_json, ensure_ascii=False), encoding="utf-8")
            replay_item = {
                "candidate_id": record.candidate_id,
                "expression": record.expression,
                "auto_long_only_decision": "WATCHLIST_LONG_ONLY",
                "mean_window_long_return": 0.002,
                "mean_window_long_sortino": 1.5,
                "mean_window_rank_ic": 0.004,
                "window_count": 4,
                "execution_lag_days": 1,
                "signal_clock": "after_open",
                "tradability_filter_available": True,
                "smoke_flags": [],
            }
            (temp_root / "auto_long_only_replay_report.json").write_text(
                json.dumps(
                    {
                        "run_id": "phase2-memory-replay-test",
                        "summary": {"watchlist_long_only_count": 1},
                        "validation": {"evaluations": [replay_item]},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            enrichment = enrich_search_memory_with_auto_long_only_replay(temp_root)
            enriched = json.loads((temp_root / "search_memory.json").read_text(encoding="utf-8"))
            reward = enriched["records"][0]["reward_proxy"]
            self.assertTrue(enrichment["active"])
            self.assertEqual(enrichment["enriched_count"], 1)
            self.assertGreater(replay_reward_proxy(replay_item)["reward"], 0.0)
            self.assertIn("real_replay_reward_proxy", reward)
            self.assertGreater(reward["reward_after_real_replay"], reward["reward"])
            self.assertEqual(
                enriched["real_replay_reward_policy"],
                "transparent_sortino_long_only_component_no_reward_model_training",
            )
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def test_behavioral_fingerprint_uses_exact_contract_dimensions(self) -> None:
        fingerprint = build_behavioral_fingerprint("Corr(CSRank($close), Sign($amtm))")
        self.assertEqual(set(fingerprint), set(FINGERPRINT_DIMENSIONS))
        self.assertTrue(set(fingerprint).isdisjoint(FORBIDDEN_FINGERPRINT_DIMENSIONS))
        validate_fingerprint_contract(fingerprint)

    def test_fingerprint_semantics_orders_similar_pairs_closer_than_distant_pairs(self) -> None:
        report = semantic_pair_report(
            {
                "similar": [
                    ("CSRank($close)", "Sign($amtm)"),
                    ("Corr($volume,$vrat)", "Cov($volt,Log(Abs($volume)))"),
                ],
                "distant": [
                    ("CSRank($close)", "Cov($mbrd,Sign($arat))"),
                    ("Corr($volume,$vrat)", "Cov($low,$pldn)"),
                ],
            }
        )
        self.assertGreater(report["semantic_pair_margin"], 0.0)
        self.assertLessEqual(report["misordered_pair_rate"], 0.5)

    def test_transition_sensitive_expression_scores_higher_on_transition_dims(self) -> None:
        base = build_behavioral_fingerprint("CSRank($close)")
        transition = build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))")
        self.assertGreater(transition["predictive_of_regime_change"], base["predictive_of_regime_change"])
        self.assertGreater(transition["ic_at_bull_to_bear"], base["ic_at_bull_to_bear"])

    def test_generate_from_scratch_trigger_path_is_real_and_windowed(self) -> None:
        self.assertTrue(novelty_saturation([0.05, 0.06], 0.1))
        self.assertFalse(novelty_saturation([0.05, 0.2], 0.1))
        generated = generate_from_scratch(
            "CSRank($close)",
            build_behavioral_fingerprint("Cov($mbrd,Sign($arat))"),
            2,
        )
        self.assertEqual(len(generated), 2)
        self.assertNotEqual(generated[0], generated[1])

    def test_memory_duplicate_saturation_triggers_zero_generation_escape(self) -> None:
        self.assertTrue(
            memory_duplicate_saturation(
                generated_count=0,
                duplicate_skip_count=1,
                per_lane_budget=10,
            )
        )
        self.assertTrue(
            memory_duplicate_saturation(
                generated_count=8,
                duplicate_skip_count=24,
                per_lane_budget=10,
            )
        )
        self.assertFalse(
            memory_duplicate_saturation(
                generated_count=20,
                duplicate_skip_count=10,
                per_lane_budget=10,
            )
        )

    def test_generated_expressions_use_registered_fields(self) -> None:
        target_expressions = [
            "Cov($mbrd,Sign($pldn))",
            "CSRank(Mom($close,10))",
            "Cov(Log(Abs($amount)),CSRank($turnover_rate))",
            "Cov($low,$pldn)",
        ]
        for target_expression in target_expressions:
            generated = generate_from_scratch(
                "registry-check",
                build_behavioral_fingerprint(target_expression),
                8,
            )
            self.assertEqual(len(generated), 8)
            self.assertEqual(len(set(generated)), 8)
            for expression in generated:
                self.assertExpressionFieldsRegistered(expression)

        archive = [
            make_candidate(
                expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
                ic_max=0.72,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.4,
                archive_cell="transition-cell",
            ),
            make_candidate(
                expression="Corr(CSRank($close), Sign($amtm))",
                ic_max=0.7,
                coverage=0.5,
                label="robust",
                oos_stability=0.8,
                archive_cell="momentum-cell",
            ),
        ]
        generated_from_archive = generate_from_scratch_from_archive(
            target_behavior=build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))"),
            archive=archive,
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=4,
            seed_key="registry-check",
        )
        self.assertEqual(len(generated_from_archive), 4)
        for item in generated_from_archive:
            self.assertExpressionFieldsRegistered(str(item["expression"]))

    def test_archive_aware_from_scratch_uses_neighbors_and_skeletons(self) -> None:
        archive = [
            make_candidate(
                expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
                ic_max=0.72,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.4,
                archive_cell="transition-cell",
            ),
            make_candidate(
                expression="Corr(CSRank($close), Sign($amtm))",
                ic_max=0.7,
                coverage=0.5,
                label="robust",
                oos_stability=0.8,
                archive_cell="momentum-cell",
            ),
        ]
        for record in archive:
            record.retained = True
        skeletons = extract_structural_skeletons(archive)
        self.assertTrue(skeletons)
        target = build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))")
        generated = generate_from_scratch_from_archive(
            target_behavior=target,
            archive=archive,
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=1,
        )
        self.assertEqual(len(generated), 1)
        self.assertIn("skeleton", generated[0])
        self.assertIn("source_candidate_id", generated[0])
        self.assertNotIn("FIELD", str(generated[0]["expression"]))

    def test_archive_aware_from_scratch_prefers_unseen_skeletons_when_requested(self) -> None:
        archive = [
            make_candidate(
                expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
                ic_max=0.72,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.4,
                archive_cell="transition-cell",
            ),
            make_candidate(
                expression="Corr(CSRank($close), Sign($amtm))",
                ic_max=0.7,
                coverage=0.5,
                label="robust",
                oos_stability=0.8,
                archive_cell="momentum-cell",
            ),
        ]
        for record in archive:
            record.retained = True
        generated = generate_from_scratch_from_archive(
            target_behavior=build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))"),
            archive=archive,
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=2,
            avoid_skeletons={item["skeleton"] for item in extract_structural_skeletons(archive)},
            seed_key="test-seed",
        )
        self.assertEqual(len(generated), 2)
        self.assertEqual(len({item["skeleton"] for item in generated}), 2)
        self.assertTrue(any(item["source_candidate_id"] is None for item in generated))

    def test_archive_aware_from_scratch_can_avoid_prior_generated_skeletons_across_rounds(self) -> None:
        archive = [
            make_candidate(
                expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
                ic_max=0.72,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.4,
                archive_cell="transition-cell",
            ),
            make_candidate(
                expression="Corr(CSRank($close), Sign($amtm))",
                ic_max=0.7,
                coverage=0.5,
                label="robust",
                oos_stability=0.8,
                archive_cell="momentum-cell",
            ),
        ]
        for record in archive:
            record.retained = True
        target = build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))")
        first = generate_from_scratch_from_archive(
            target_behavior=target,
            archive=archive,
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=1,
            avoid_skeletons={item["skeleton"] for item in extract_structural_skeletons(archive)},
            seed_key="round-1",
        )
        avoided = {item["skeleton"] for item in extract_structural_skeletons(archive)} | {first[0]["skeleton"]}
        second = generate_from_scratch_from_archive(
            target_behavior=target,
            archive=archive,
            surrogate_fingerprint=SurrogateFingerprintHead(),
            budget=1,
            avoid_skeletons=avoided,
            seed_key="round-2",
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0]["skeleton"], second[0]["skeleton"])

    def test_distant_axis_recomposition_adds_seeded_unseen_structures(self) -> None:
        target = build_behavioral_fingerprint("Cov($mbrd, Sign($pldn))")
        first = generate_distant_axis_recompositions(
            target_behavior=target,
            budget=6,
            seed_key="escape-a",
        )
        second = generate_distant_axis_recompositions(
            target_behavior=target,
            budget=6,
            seed_key="escape-b",
        )

        self.assertEqual(len(first), 6)
        self.assertGreaterEqual(len({extract_structural_skeleton(item) for item in first}), 4)
        self.assertNotEqual(first, second)
        for expression in first:
            self.assertExpressionFieldsRegistered(expression)
            self.assertFalse(is_pathological_expression(expression))

    def test_behavior_guided_crossover_uses_two_parents_and_midpoint_target(self) -> None:
        left = make_candidate(
            expression="Corr(CSRank($close), Sign($amtm))",
            ic_max=0.7,
            coverage=0.5,
            label="robust",
            oos_stability=0.8,
            archive_cell="left",
        )
        right = make_candidate(
            expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
            ic_max=0.72,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.5,
            archive_cell="right",
        )
        crossover = behavior_guided_crossover(
            left=left,
            right=right,
            surrogate_fingerprint=SurrogateFingerprintHead(),
        )
        self.assertEqual(crossover["left_candidate_id"], left.candidate_id)
        self.assertEqual(crossover["right_candidate_id"], right.candidate_id)
        self.assertIn("target_behavior", crossover)
        self.assertNotEqual(crossover["expression"], left.expression)

    def test_behavior_guided_crossover_bounds_subtree_pair_count(self) -> None:
        left_expression = "$close"
        right_expression = "$open"
        fields = ["$close", "$open", "$amount", "$volume", "$ret", "$vwap"]
        for index in range(12):
            left_expression = f"Corr(CSRank({left_expression}),Sign(Mom({fields[index % len(fields)]},{index + 2})))"
            right_expression = f"Cov(CSRank({right_expression}),Log(Abs(Mean({fields[(index + 1) % len(fields)]},{index + 3}))))"
        left = make_candidate(
            expression=left_expression,
            ic_max=0.7,
            coverage=0.5,
            label="robust",
            oos_stability=0.8,
            archive_cell="left-complex",
        )
        right = make_candidate(
            expression=right_expression,
            ic_max=0.69,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.7,
            archive_cell="right-complex",
        )
        crossover = behavior_guided_crossover(
            left=left,
            right=right,
            surrogate_fingerprint=SurrogateFingerprintHead(),
        )
        self.assertTrue(crossover["bounded_subtree_sampling"])
        self.assertLessEqual(crossover["evaluated_subtree_pairs"], 64)
        self.assertFalse(is_pathological_expression(str(crossover["expression"])))

    def test_classify_frontiers_can_expand_parent_pool_with_limit(self) -> None:
        archive = []
        for index in range(5):
            record = make_candidate(
                expression=f"Corr(CSRank($close), Sign(Mom($amtm,{index + 2})))",
                ic_max=0.6 + (index * 0.01),
                coverage=0.5,
                label="robust",
                oos_stability=0.7,
                archive_cell=f"cell-{index}",
            )
            record.retained = True
            archive.append(record)
        frontiers = classify_frontiers(archive, limit=4)
        self.assertEqual(len(frontiers["score_frontier"]), 4)
        self.assertEqual(len(frontiers["novelty_frontier"]), 4)
        self.assertEqual(len(frontiers["uncertainty_frontier"]), 4)
        self.assertEqual(len(frontiers["bridge_frontier"]), 4)

    def test_high_budget_quality_control_penalizes_low_yield_non_score_lanes(self) -> None:
        adjusted, report = _apply_high_budget_quality_control(
            proposed_allocation={
                "score_frontier": 2,
                "novelty_frontier": 3,
                "uncertainty_frontier": 3,
                "bridge_frontier": 3,
            },
            recent_outcomes={
                "score_frontier": [LaneOutcome("score_frontier", 2, 1, 0, 0.7, 0.0)],
                "novelty_frontier": [LaneOutcome("novelty_frontier", 3, 0, 0, 0.45, 0.0)],
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 1, 1, 0.62, 0.05)],
                "bridge_frontier": [LaneOutcome("bridge_frontier", 3, 0, 0, 0.5, 0.0)],
            },
            per_lane_budget=3,
            continuation_context=None,
        )
        self.assertTrue(report["active"])
        self.assertEqual(adjusted["novelty_frontier"], 3)
        self.assertEqual(adjusted["bridge_frontier"], 3)
        self.assertGreaterEqual(adjusted["uncertainty_frontier"], 3)
        self.assertGreaterEqual(adjusted["score_frontier"], 2)
        self.assertEqual(report["minimum_absolute_allocation"]["novelty_frontier"], 3)
        self.assertEqual(report["minimum_absolute_allocation"]["bridge_frontier"], 3)
        self.assertEqual(sum(adjusted.values()), 11)

    def test_high_budget_quality_control_prevents_score_from_absorbing_all_recovered_slots(self) -> None:
        adjusted, report = _apply_high_budget_quality_control(
            proposed_allocation={
                "score_frontier": 3,
                "novelty_frontier": 2,
                "uncertainty_frontier": 3,
                "bridge_frontier": 3,
            },
            recent_outcomes={
                "score_frontier": [LaneOutcome("score_frontier", 5, 1, 0, 0.7, 0.0)],
                "novelty_frontier": [LaneOutcome("novelty_frontier", 2, 0, 0, 0.42, 0.0)],
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 1, 1, 0.63, 0.05)],
                "bridge_frontier": [LaneOutcome("bridge_frontier", 3, 0, 0, 0.41, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
        )
        self.assertTrue(report["active"])
        self.assertEqual(adjusted["score_frontier"], 2)
        self.assertEqual(adjusted["novelty_frontier"], 3)
        self.assertEqual(adjusted["bridge_frontier"], 3)
        self.assertEqual(adjusted["uncertainty_frontier"], 3)
        self.assertTrue(report["reassigned"] or report["floor_transfers"])
        self.assertEqual(sum(adjusted.values()), 11)

    def test_high_budget_quality_control_can_relax_repeated_zero_yield_lane_floor(self) -> None:
        adjusted, report = _apply_high_budget_quality_control(
            proposed_allocation={
                "score_frontier": 2,
                "novelty_frontier": 3,
                "uncertainty_frontier": 3,
                "bridge_frontier": 3,
            },
            recent_outcomes={
                "score_frontier": [LaneOutcome("score_frontier", 2, 1, 0, 0.7, 0.0)],
                "novelty_frontier": [LaneOutcome("novelty_frontier", 3, 1, 1, 0.62, 0.05)],
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 1, 1, 0.62, 0.05)],
                "bridge_frontier": [
                    LaneOutcome("bridge_frontier", 3, 0, 0, 0.5, 0.0),
                    LaneOutcome("bridge_frontier", 3, 0, 0, 0.48, 0.0),
                ],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
        )
        self.assertTrue(report["active"])
        self.assertEqual(adjusted["bridge_frontier"], 2)
        self.assertEqual(report["effective_minimum_allocation"]["bridge_frontier"], 2)
        self.assertEqual(report["floor_overrides"][0]["reason"], "repeated_zero_retention_lane_starvation")
        self.assertEqual(sum(adjusted.values()), 11)

    def test_high_budget_quality_control_sheds_saturated_score_lane(self) -> None:
        adjusted, report = _apply_high_budget_quality_control(
            proposed_allocation={
                "score_frontier": 2,
                "novelty_frontier": 3,
                "uncertainty_frontier": 3,
                "bridge_frontier": 3,
            },
            recent_outcomes={
                "score_frontier": [
                    LaneOutcome("score_frontier", 4, 1, 0, 0.66, 0.0),
                    LaneOutcome("score_frontier", 4, 0, 0, 0.64, 0.0),
                ],
                "novelty_frontier": [LaneOutcome("novelty_frontier", 3, 2, 1, 0.62, 0.05)],
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 1, 1, 0.62, 0.05)],
                "bridge_frontier": [LaneOutcome("bridge_frontier", 3, 2, 1, 0.62, 0.05)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
        )

        self.assertTrue(report["active"])
        self.assertEqual(adjusted["score_frontier"], 1)
        self.assertIn("score_frontier", report["suppressed_lanes"])
        self.assertEqual(
            report["floor_overrides"][0]["reason"],
            "score_lane_repeated_zero_adaptive_cell_saturation",
        )
        self.assertEqual(sum(adjusted.values()), 11)

    def test_real_replay_feedback_allocation_moves_budget_from_demoted_to_weak_lane(self) -> None:
        adjusted, report = _apply_real_replay_feedback_allocation(
            proposed_allocation={
                "score_frontier": 2,
                "novelty_frontier": 3,
                "uncertainty_frontier": 2,
                "bridge_frontier": 4,
            },
            real_replay_feedback_objective={
                "decision": "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH",
                "weak_positive_candidates": [
                    {"candidate_id": "weak", "frontier_lane": "uncertainty_frontier"},
                ],
                "demoted_soft_prior_groups": [
                    {"group": "frontier_lane:bridge_frontier", "count": 4, "mean_rank_ic": -0.01},
                ],
            },
        )

        self.assertTrue(report["active"])
        self.assertEqual(report["reason"], "real_replay_soft_prior_lane_transfer")
        self.assertEqual(adjusted["uncertainty_frontier"], 3)
        self.assertEqual(adjusted["bridge_frontier"], 3)
        self.assertEqual(sum(adjusted.values()), 11)

    def test_target_aware_pre_screen_filters_non_score_candidates_before_evaluation(self) -> None:
        evaluator = MultiFidelityEvaluator()
        target_behavior = {
            **{name: 0.2 for name in FINGERPRINT_DIMENSIONS},
            "size_tilt": 0.85,
            "predictive_of_regime_change": 0.8,
            "ic_regime_volatile": 0.75,
        }
        candidates = directed_variation(
            parent_expression="CSRank($close)",
            lane="novelty_frontier",
            target_behavior=target_behavior,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            temperature_top_k=6,
        )
        occupied_cell = behavioral_cell(candidates[0]["predicted_fingerprint"])
        occupied_record = make_candidate(
            expression="CSRank($close)",
            ic_max=0.42,
            coverage=0.4,
            label="regime_conditional",
            oos_stability=0.39,
            archive_cell=occupied_cell,
        )
        occupied_record.retained = True
        selected, report = _target_aware_pre_screen(
            lane="novelty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "novelty_frontier": [LaneOutcome("novelty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[occupied_record],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=evaluator.surrogate_ic,
        )
        self.assertTrue(report["active"])
        self.assertEqual(len(selected), 1)
        self.assertEqual(report["selected_count"], 1)
        self.assertGreater(report["rejected_count"], 0)
        self.assertGreaterEqual(
            report["selected"][0]["pre_screen_score"],
            max(item["pre_screen_score"] for item in report["rejected"]),
        )
        self.assertEqual(report["reason"], "target_aware_lane_pre_screen")
        occupied_items = [
            item
            for item in [*report["selected"], *report["rejected"], *report.get("skipped", [])]
            if item["predicted_archive_cell"] == occupied_cell
        ]
        self.assertTrue(occupied_items)
        self.assertTrue(all(not item["predicted_new_coarse_cell"] for item in occupied_items))

    def test_target_aware_pre_screen_uses_real_replay_feedback_as_soft_prior(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank($open)")
        weak_expression = "Div(Mean($amount,2),Mean($volume,5))"
        other_expression = "Cov($close,$volume)"
        candidates = [
            {
                "expression": other_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(other_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
            {
                "expression": weak_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(weak_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
        ]

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context=None,
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
            real_replay_feedback_objective={
                "decision": "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH",
                "weak_positive_candidates": [
                    {
                        "candidate_id": "weak",
                        "expression": weak_expression,
                        "frontier_lane": "uncertainty_frontier",
                    }
                ],
                "watched_soft_prior_groups": [{"group": "field:$amount"}],
                "demoted_soft_prior_groups": [{"group": "field:$close"}],
            },
        )

        self.assertEqual(selected[0]["expression"], weak_expression)
        self.assertGreater(report["selected"][0]["real_replay_feedback_score"], 0)
        self.assertTrue(report["selected"][0]["real_replay_feedback_reasons"])

    def test_target_aware_pre_screen_penalizes_exact_saturated_positive_candidate(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank($open)")
        saturated_expression = "Div(Mean($amount,2),Mean($volume,5))"
        fresh_expression = "Cov($open,$volume)"
        candidates = [
            {
                "expression": saturated_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(saturated_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
            {
                "expression": fresh_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(fresh_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
        ]

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context=None,
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
            real_replay_feedback_objective={
                "decision": "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH",
                "saturated_positive_candidates": [
                    {
                        "candidate_id": make_candidate_id(saturated_expression),
                        "expression": saturated_expression,
                        "frontier_lane": "uncertainty_frontier",
                    }
                ],
                "weak_positive_candidates": [],
                "watched_soft_prior_groups": [],
                "demoted_soft_prior_groups": [],
            },
        )

        self.assertEqual(selected[0]["expression"], fresh_expression)
        saturated_report = next(
            item
            for item in [*report["selected"], *report["rejected"], *report["skipped"]]
            if item["expression"] == saturated_expression
        )
        self.assertLess(saturated_report["real_replay_feedback_score"], 0.0)
        self.assertIn(
            f"saturated_positive_exact:{make_candidate_id(saturated_expression)}",
            saturated_report["real_replay_feedback_reasons"],
        )

    def test_target_aware_pre_screen_hard_skips_exact_saturated_candidate_in_continuation(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank($open)")
        saturated_expression = "Div(Mean($amount,2),Mean($volume,5))"
        fresh_expression = "Cov($open,$volume)"
        candidates = [
            {
                "expression": saturated_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(saturated_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
            {
                "expression": fresh_expression,
                "predicted_fingerprint": build_behavioral_fingerprint(fresh_expression),
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
        ]

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
            real_replay_feedback_objective={
                "decision": "USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH",
                "saturated_positive_candidates": [
                    {
                        "candidate_id": make_candidate_id(saturated_expression),
                        "expression": saturated_expression,
                        "frontier_lane": "uncertainty_frontier",
                    }
                ],
                "weak_positive_candidates": [],
                "watched_soft_prior_groups": [],
                "demoted_soft_prior_groups": [],
            },
        )

        self.assertEqual(selected[0]["expression"], fresh_expression)
        self.assertEqual(report["saturated_hard_skip_count"], 1)
        self.assertEqual(report["hard_skipped"][0]["expression"], saturated_expression)
        self.assertEqual(report["hard_skipped"][0]["efficiency_skip_reason"], "exact_saturated_positive_candidate")
        self.assertFalse(any(item["expression"] == saturated_expression for item in report["rejected"]))

    def test_target_aware_pre_screen_prefers_three_dimensional_candidate_when_quality_ties(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("Cov(Corr($amount,$volume),Sign($amtm))")
        shared_prediction = build_behavioral_fingerprint("CSRank($close)")
        single_field = "CSRank(Mean($close,20))"
        multi_axis = "Cov(Corr($amount,$volume),Sign($amtm))"
        candidates = [
            {
                "expression": single_field,
                "predicted_fingerprint": shared_prediction,
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
            {
                "expression": multi_axis,
                "predicted_fingerprint": shared_prediction,
                "behavior_distance_to_target": 0.2,
                "alignment_score": 0.0,
            },
        ]

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
        )

        self.assertEqual(selected[0]["expression"], multi_axis)
        self.assertEqual(report["three_dimensional_policy"]["type"], "soft_bonus_not_hard_constraint")
        self.assertGreater(
            report["selected"][0]["three_dimensional_score"],
            report["rejected"][0]["three_dimensional_score"],
        )
        self.assertGreaterEqual(report["selected"][0]["three_dimensional_profile"]["field_count"], 3)

    def test_target_aware_pre_screen_prefers_a_share_stock_pit_compatible_candidate_when_quality_ties(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank(Mul(CSResidual($open,$volume),Sign(CSResidual($amount,$low))))")
        shared_prediction = build_behavioral_fingerprint("CSRank($close)")
        unsupported = "CSRank(Mul(CSResidual($mystery_state,$crowding),Sign(CSResidual($rps_score,$unknown_flow))))"
        compatible = "CSRank(Mul(CSResidual($open,$volume),Sign(CSResidual($amount,$low))))"

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=[
                {
                    "expression": unsupported,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
                {
                    "expression": compatible,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
            ],
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
        )

        selected_profile = report["selected"][0]["three_dimensional_profile"]["ashare_stock_pit_profile"]
        rejected_profile = report["rejected"][0]["three_dimensional_profile"]["ashare_stock_pit_profile"]
        self.assertEqual(selected[0]["expression"], compatible)
        self.assertTrue(selected_profile["stock_pit_supported"])
        self.assertFalse(rejected_profile["stock_pit_supported"])
        self.assertGreater(selected_profile["stock_pit_score"], rejected_profile["stock_pit_score"])
        self.assertIn("a_share_stock_pit_field_compatibility", report["three_dimensional_policy"]["dimensions"])

    def test_target_aware_pre_screen_penalizes_nan_prone_expression_density(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("Cov(Corr($amount,$volume),Sign($amtm))")
        shared_prediction = build_behavioral_fingerprint("CSRank($close)")
        compact = "Cov(Corr($amount,$volume),Sign($amtm))"
        dense = (
            "Cov(Corr(Cov(Corr(Cov(Corr(Cov(Corr($amount,$volume),Mean($close,20)),"
            "Std($ret,20)),Mean($low,20)),Std($volume,20)),Mean($amount,20)),"
            "Std($close,20)),Sign($amtm))"
        )

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=[
                {
                    "expression": dense,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
                {
                    "expression": compact,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
            ],
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
        )

        self.assertEqual(selected[0]["expression"], compact)
        self.assertGreater(report["rejected"][0]["three_dimensional_profile"]["availability_density_penalty"], 0.0)

    def test_target_aware_pre_screen_applies_soft_family_saturation_pressure(self) -> None:
        class FlatIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.55, "uncertainty": 0.1})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("Cov(Corr($amount,$volume),Sign($amtm))")
        shared_prediction = build_behavioral_fingerprint("CSRank($close)")
        crowded_family = "Cov(Corr($amount,$volume),Sign($amtm))"
        fresh_family = "Corr(CSRank($open),Sign(Mom($close,5)))"
        archive = [
            make_candidate(
                expression="Cov(Corr($amount,$volume),Sign($amtm))",
                ic_max=0.60,
                coverage=0.50,
                label="regime_conditional",
                oos_stability=0.60,
            ),
            make_candidate(
                expression="Cov(Corr($arat,$volt),Sign($amtm))",
                ic_max=0.59,
                coverage=0.50,
                label="regime_conditional",
                oos_stability=0.60,
            ),
        ]
        for record in archive:
            record.retained = True

        selected, report = _target_aware_pre_screen(
            lane="uncertainty_frontier",
            source_mode="variation",
            candidates=[
                {
                    "expression": crowded_family,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
                {
                    "expression": fresh_family,
                    "predicted_fingerprint": shared_prediction,
                    "behavior_distance_to_target": 0.2,
                    "alignment_score": 0.0,
                },
            ],
            target_behavior=target_behavior,
            recent_outcomes={
                "uncertainty_frontier": [LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=archive,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=FlatIC(),
        )

        self.assertEqual(selected[0]["expression"], fresh_family)
        crowded_report = next(item for item in report["rejected"] if item["expression"] == crowded_family)
        self.assertGreater(crowded_report["three_dimensional_profile"]["family_saturation_penalty"], 0.0)
        self.assertGreaterEqual(crowded_report["three_dimensional_profile"]["archive_family_count"], 2)

    def test_target_aware_pre_screen_skips_low_quality_existing_cell_candidates(self) -> None:
        class LowQualityIC:
            def predict(self, *, expression: str, fingerprint: dict[str, float]):
                return type("Prediction", (), {"quality_estimate": 0.22, "uncertainty": 0.2})()

        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank($close)")
        candidate_expressions = [
            "CSRank(Cov($low,$pldn))",
            "CSRank(Corr($low,$pldn))",
        ]
        candidates = []
        occupied_records = []
        for expression in candidate_expressions:
            predicted = build_behavioral_fingerprint(expression)
            occupied_cell = behavioral_cell(predicted)
            occupied = make_candidate(
                expression=f"incumbent-{expression}",
                ic_max=0.55,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.45,
                archive_cell=occupied_cell,
            )
            occupied.retained = True
            occupied_records.append(occupied)
            candidates.append(
                {
                    "expression": expression,
                    "predicted_fingerprint": predicted,
                    "behavior_distance_to_target": fingerprint_distance(predicted, target_behavior),
                    "alignment_score": 0.0,
                }
            )

        selected, report = _target_aware_pre_screen(
            lane="novelty_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "novelty_frontier": [LaneOutcome("novelty_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=occupied_records,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=LowQualityIC(),
        )
        self.assertEqual(selected, [])
        self.assertTrue(report["active"])
        self.assertEqual(report["selected_count"], 0)
        self.assertEqual(report["skipped_count"], len(candidates))
        self.assertTrue(all(item["efficiency_skip_reason"] == "low_quality_existing_cell" for item in report["skipped"]))

    def test_target_aware_pre_screen_skips_existing_cell_candidates_that_cannot_dominate(self) -> None:
        evaluator = MultiFidelityEvaluator()
        predicted = {
            **{name: 0.6 for name in FINGERPRINT_DIMENSIONS},
            "ic_at_bull_to_bear": 0.55,
            "ic_at_bear_to_bull": 0.45,
            "decay_halflife": 0.55,
        }
        occupied = make_candidate(
            expression="incumbent-strong-cell",
            ic_max=0.9,
            coverage=1.0,
            label="robust",
            oos_stability=0.9,
            archive_cell=behavioral_cell(predicted),
        )
        occupied.retained = True
        occupied.metadata["adaptive_archive_cell"] = _adaptive_behavior_cell(predicted)

        selected, report = _target_aware_pre_screen(
            lane="bridge_frontier",
            source_mode="operator_aware_bridge_pool",
            candidates=[
                {
                    "expression": "Corr($volume,$vrat)",
                    "predicted_fingerprint": predicted,
                    "behavior_distance_to_target": 0.1,
                    "alignment_score": 0.2,
                },
                {
                    "expression": "Cov($volume,$vrat)",
                    "predicted_fingerprint": predicted,
                    "behavior_distance_to_target": 0.12,
                    "alignment_score": 0.1,
                }
            ],
            target_behavior=predicted,
            recent_outcomes={
                "bridge_frontier": [LaneOutcome("bridge_frontier", 3, 0, 0, 0.42, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[occupied],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=evaluator.surrogate_ic,
        )

        self.assertEqual(selected, [])
        self.assertTrue(report["active"])
        self.assertEqual(report["selected_count"], 0)
        self.assertEqual(report["skipped_count"], 2)
        self.assertEqual(report["skipped"][0]["efficiency_skip_reason"], "non_dominating_existing_cell")
        self.assertFalse(report["skipped"][0]["predicted_dominates_incumbent"])

    def test_target_aware_pre_screen_skips_score_lane_candidate_pool(self) -> None:
        evaluator = MultiFidelityEvaluator()
        target_behavior = build_behavioral_fingerprint("CSRank($close)")
        candidates = directed_variation(
            parent_expression="CSRank($close)",
            lane="score_frontier",
            target_behavior=target_behavior,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            temperature_top_k=3,
        )

        selected, report = _target_aware_pre_screen(
            lane="score_frontier",
            source_mode="variation",
            candidates=candidates,
            target_behavior=target_behavior,
            recent_outcomes={
                "score_frontier": [LaneOutcome("score_frontier", 4, 1, 0, 0.44, 0.0)],
            },
            per_lane_budget=3,
            continuation_context={"previous_run_id": "phase2-prev"},
            archive=[],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            surrogate_ic=evaluator.surrogate_ic,
        )

        self.assertFalse(report["active"])
        self.assertEqual(report["lane"], "score_frontier")
        self.assertEqual(
            report["reason"],
            "score_lane_pre_screen_disabled_to_protect_non_score_exploration",
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(report["candidate_count"], len(candidates))

    def test_non_score_parent_selection_penalizes_repeated_parents(self) -> None:
        records = []
        for index in range(4):
            record = make_candidate(
                expression=f"Cov(CSRank($close), Sign(Mom($amtm,{index + 2})))",
                ic_max=0.6 + (index * 0.01),
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.6,
                archive_cell=f"cell-{index}",
            )
            record.retained = True
            records.append(record)
        selected = select_lane_parents(
            records,
            lane="novelty_frontier",
            allocation=2,
            revisit_counts={
                records[0].candidate_id: 3,
                records[1].candidate_id: 2,
                records[2].candidate_id: 0,
                records[3].candidate_id: 0,
            },
        )
        self.assertEqual([record.candidate_id for record in selected], [records[2].candidate_id, records[3].candidate_id])

    def test_score_parent_refresh_replaces_exhausted_high_score_parents(self) -> None:
        evaluator = MultiFidelityEvaluator()
        records = []
        for index in range(4):
            record = make_candidate(
                expression=(
                    f"Corr(CSRank(Mean($close,{index + 2})), "
                    f"Sign(Mom($amtm,{index + 3})))"
                ),
                ic_max=0.8 - (index * 0.01),
                coverage=0.5,
                label="robust",
                oos_stability=0.7,
                archive_cell=f"score-cell-{index}",
            )
            record.retained = True
            records.append(record)
        selected = select_lane_parents(
            records,
            lane="score_frontier",
            allocation=2,
            revisit_counts={},
        )
        target_behavior = dict(records[0].fingerprint)
        seen_candidate_ids = {
            make_candidate_id(str(proposal["expression"]))
            for parent in selected
            for proposal in directed_variation(
                parent_expression=parent.expression,
                lane="score_frontier",
                target_behavior=target_behavior,
                surrogate_fingerprint=evaluator.surrogate_fingerprint,
                temperature_top_k=3,
            )
        }

        refreshed, report = _refresh_score_lane_parents_for_unseen_variation(
            frontier_records=records,
            selected_parents=selected,
            allocation=2,
            target_behavior=target_behavior,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            archive=records,
            seen_candidate_ids=seen_candidate_ids,
            revisit_counts={},
        )

        self.assertTrue(report["active"])
        self.assertEqual(report["reason"], "score_parent_refresh_for_productive_unseen_variation")
        self.assertEqual(
            report["exhausted_original_parent_ids"],
            [records[0].candidate_id, records[1].candidate_id],
        )
        self.assertEqual([record.candidate_id for record in refreshed], [records[2].candidate_id, records[3].candidate_id])

    def test_coverage_refresh_targets_missing_behavior_cell_after_lane_stalls(self) -> None:
        records = []
        occupied_cells = [
            "low_momentum|low_size|stable|low_vol|trend",
            "high_momentum|low_size|stable|low_vol|trend",
            "low_momentum|high_size|transition|low_vol|mean_revert",
        ]
        for index, cell in enumerate(occupied_cells):
            record = make_candidate(
                expression=f"Cov(CSRank($close), Sign(Mom($amtm,{index + 2})))",
                ic_max=0.62,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.6,
                archive_cell=cell,
            )
            record.retained = True
            records.append(record)

        target, report = _coverage_refresh_target_for_lane(
            lane="bridge_frontier",
            archive=records,
            recent_outcomes={
                "bridge_frontier": [
                    LaneOutcome("bridge_frontier", 3, 0, 0, 0.52, 0.0),
                    LaneOutcome("bridge_frontier", 3, 1, 0, 0.54, 0.05),
                ]
            },
            continuation_context={"previous_run_id": "phase2-prev"},
            per_lane_budget=3,
        )

        self.assertIsNotNone(target)
        validate_fingerprint_contract(target or {})
        self.assertTrue(report["active"])
        self.assertEqual(report["reason"], "coverage_refresh_missing_behavior_cell")
        self.assertNotIn(report["target_cell"], occupied_cells)
        self.assertTrue(str(report["target_cell"]).split("|")[2] == "transition")

    def test_coverage_refresh_target_stops_when_missing_cells_are_not_reachable(self) -> None:
        evaluator = MultiFidelityEvaluator()
        occupied_cells = [
            "low_momentum|low_size|transition|low_vol|mean_revert",
            "high_momentum|high_size|transition|high_vol|mean_revert",
            "high_momentum|high_size|stable|high_vol|mean_revert",
            "high_momentum|low_size|stable|high_vol|mean_revert",
            "high_momentum|low_size|stable|high_vol|trend",
            "low_momentum|high_size|stable|high_vol|trend",
        ]
        records = []
        for index, cell in enumerate(occupied_cells):
            record = make_candidate(
                expression=f"Cov(CSRank($volume), Sign(Mom($amtm,{index + 2})))",
                ic_max=0.62,
                coverage=0.5,
                label="regime_conditional",
                oos_stability=0.6,
                archive_cell=cell,
            )
            record.retained = True
            records.append(record)

        target, report = _coverage_refresh_target_for_lane(
            lane="uncertainty_frontier",
            archive=records,
            recent_outcomes={
                "uncertainty_frontier": [
                    LaneOutcome("uncertainty_frontier", 3, 0, 0, 0.52, 0.0),
                    LaneOutcome("uncertainty_frontier", 3, 1, 0, 0.54, 0.05),
                ]
            },
            continuation_context={"previous_run_id": "phase2-prev"},
            per_lane_budget=3,
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            seen_candidate_ids=set(),
            seen_structural_skeletons=set(),
        )

        self.assertIsNone(target)
        self.assertFalse(report["active"])
        self.assertEqual(report["reason"], "no_reachable_missing_behavior_cell")
        self.assertGreater(report["surveyed_cell_count"], 0)

    def test_coverage_refresh_pool_prioritizes_unseen_new_cell_predictions(self) -> None:
        evaluator = MultiFidelityEvaluator()
        parent = make_candidate(
            expression="Corr(CSRank($close), Sign(Mom($amtm,10)))",
            ic_max=0.65,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.6,
            archive_cell="low_momentum|low_size|stable|low_vol|trend",
        )
        parent.retained = True
        target, _ = _coverage_refresh_target_for_lane(
            lane="uncertainty_frontier",
            archive=[parent],
            recent_outcomes={
                "uncertainty_frontier": [
                    LaneOutcome("uncertainty_frontier", 2, 0, 0, 0.52, 0.0),
                ]
            },
            continuation_context={"previous_run_id": "phase2-prev"},
            per_lane_budget=3,
        )

        pool, report = _coverage_refresh_candidate_pool(
            lane="uncertainty_frontier",
            parent=parent,
            target_behavior=target or dict(parent.fingerprint),
            archive=[parent],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            seen_candidate_ids=set(),
            seen_structural_skeletons=set(),
            per_lane_budget=3,
            seed_key="test-coverage-refresh",
        )

        self.assertGreater(report["deduped_count"], 0)
        self.assertGreater(report["predicted_new_cell_count"], 0)
        self.assertGreater(report["phase2_native_ast_candidate_count"], 0)
        self.assertTrue(pool[0]["predicted_new_cell"])

    def test_phase2_native_ast_expansion_uses_archive_subtrees_without_external_generator(self) -> None:
        evaluator = MultiFidelityEvaluator()
        parent = make_candidate(
            expression="Corr(CSRank($close), Sign(Mom($amtm,10)))",
            ic_max=0.65,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.6,
            archive_cell="low_momentum|low_size|stable|low_vol|trend",
        )
        neighbor = make_candidate(
            expression="Cov(Corr(Sign($mbrd), Log(Abs($arat))), Corr(CSRank($vrat), Sign(Mom($amtm,20))))",
            ic_max=0.61,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.58,
            archive_cell="high_momentum|high_size|transition|high_vol|mean_revert",
        )
        target = _target_behavior_from_cell(
            "high_momentum|high_size|transition|high_vol|mean_revert",
            lane="bridge_frontier",
        )

        candidates = phase2_native_ast_expansion(
            parent_expression=parent.expression,
            target_behavior=target,
            archive=[parent, neighbor],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            budget=8,
            avoid_skeletons={extract_structural_skeleton(parent.expression)},
        )

        self.assertGreaterEqual(len(candidates), 4)
        self.assertTrue(all("expression" in candidate for candidate in candidates))
        self.assertTrue(all(candidate["phase2_native_ast_kind"] for candidate in candidates))
        self.assertTrue(any(candidate["field_count"] > 1 for candidate in candidates))
        self.assertTrue(any("phase2_native_ast_kind" in candidate for candidate in candidates))

    def test_phase2_native_ast_expansion_prioritizes_residual_state_mechanisms(self) -> None:
        evaluator = MultiFidelityEvaluator()
        parent = make_candidate(
            expression="Corr(CSRank($close), Sign(Mom($amtm,10)))",
            ic_max=0.65,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.6,
            archive_cell="low_momentum|low_size|stable|low_vol|trend",
        )
        neighbor = make_candidate(
            expression="Cov(Corr(Sign($mbrd), Log(Abs($arat))), Corr(CSRank($vrat), Sign(Mom($amtm,20))))",
            ic_max=0.61,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.58,
            archive_cell="high_momentum|high_size|transition|high_vol|mean_revert",
        )
        target = _target_behavior_from_cell(
            "high_momentum|high_size|transition|high_vol|mean_revert",
            lane="bridge_frontier",
        )

        candidates = phase2_native_ast_expansion(
            parent_expression=parent.expression,
            target_behavior=target,
            archive=[parent, neighbor],
            surrogate_fingerprint=evaluator.surrogate_fingerprint,
            budget=12,
            avoid_skeletons={extract_structural_skeleton(parent.expression)},
        )
        kinds = {str(candidate["phase2_native_ast_kind"]) for candidate in candidates}

        self.assertTrue(
            kinds
            & {
                "cs_residual_state_gate",
                "residual_local_rank_gate",
                "local_rank_residual_pair",
                "non_liquidity_state_gate",
                "orthogonal_state_spread_gate",
            }
        )
        self.assertTrue(any("CSResidual(" in str(candidate["expression"]) for candidate in candidates))
        self.assertTrue(any("Mul(" in str(candidate["expression"]) or "Sign(" in str(candidate["expression"]) for candidate in candidates))
        self.assertTrue(
            any(
                any(field in str(candidate["expression"]) for field in ("$price_pos", "$crowding", "$rps_score", "$money_flow"))
                for candidate in candidates
            )
        )

    def test_coverage_refresh_pool_uses_target_cell_probe(self) -> None:
        evaluator = MultiFidelityEvaluator()
        parent = make_candidate(
            expression="Corr(CSRank($close), Sign(Mom($amtm,10)))",
            ic_max=0.65,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.6,
            archive_cell="low_momentum|low_size|stable|low_vol|trend",
        )
        parent.retained = True
        for target_cell in (
            "high_momentum|high_size|transition|high_vol|mean_revert",
            "high_momentum|high_size|stable|high_vol|mean_revert",
            "high_momentum|low_size|stable|high_vol|mean_revert",
            "high_momentum|low_size|stable|high_vol|trend",
            "low_momentum|high_size|stable|high_vol|trend",
        ):
            pool, report = _coverage_refresh_candidate_pool(
                lane="uncertainty_frontier",
                parent=parent,
                target_behavior=_target_behavior_from_cell(target_cell, lane="uncertainty_frontier"),
                target_cell=target_cell,
                archive=[parent],
                surrogate_fingerprint=evaluator.surrogate_fingerprint,
                seen_candidate_ids=set(),
                seen_structural_skeletons=set(),
                per_lane_budget=3,
                seed_key=f"test-coverage-refresh-probe-{target_cell}",
            )

            self.assertGreater(report["predicted_new_cell_count"], 0)
            self.assertTrue(
                any(
                    item["predicted_archive_cell"] == target_cell
                    and item["coverage_refresh_source"] == "target_cell_probe"
                    for item in pool
                )
            )

    def test_meta_policy_uses_market_archive_state_and_lane_history(self) -> None:
        transition_parent = make_candidate(
            expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
            ic_max=0.72,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.4,
            archive_cell="transition-cell",
        )
        transition_parent.retained = True
        score_parent = make_candidate(
            expression="Corr(CSRank($close), Sign($amtm))",
            ic_max=0.7,
            coverage=0.5,
            label="robust",
            oos_stability=0.8,
            archive_cell="momentum-cell",
        )
        score_parent.retained = True
        policy = MetaSearchPolicy()
        policy.update(
            [
                LaneOutcome(
                    lane="bridge_frontier",
                    generated_count=2,
                    retained_count=2,
                    new_cell_count=2,
                    mean_ic_max=0.72,
                    non_score_bonus=0.05,
                ),
                LaneOutcome(
                    lane="score_frontier",
                    generated_count=2,
                    retained_count=0,
                    new_cell_count=0,
                    mean_ic_max=0.58,
                    non_score_bonus=0.0,
                ),
            ]
        )
        decision = policy.allocate(
            archive=[transition_parent, score_parent],
            active_lanes={lane: True for lane in ("score_frontier", "novelty_frontier", "uncertainty_frontier", "bridge_frontier")},
            total_budget=8,
        )
        self.assertEqual(decision.market_state["regime"], "transition")
        self.assertGreater(decision.lane_value_estimates["bridge_frontier"], decision.lane_value_estimates["score_frontier"])
        self.assertGreaterEqual(decision.allocation["bridge_frontier"], decision.allocation["score_frontier"])
        self.assertIn("market_regime=transition", decision.reasoning["bridge_frontier"])

    def test_bootstrap_layer_cold_starts_without_v1_archive(self) -> None:
        bootstrap = Phase2BootstrapLayer()
        seed_formulas = bootstrap.cold_start(variants_per_prototype=2)
        self.assertGreaterEqual(len(seed_formulas), len(bootstrap.behavioral_prototypes))
        self.assertTrue(all(seed["source_mode"].startswith("bootstrap_") for seed in seed_formulas))
        result = bootstrap.build_initial_archive(seed_formulas)
        self.assertFalse(result.report["depends_on_v1_archive"])
        self.assertEqual(result.report["seed_lineage_root"], "phase2_bootstrap_cold_start")
        self.assertGreater(result.report["behavior_grid_coverage"], 0.1)
        self.assertTrue(result.archive.records)

    def test_continuous_field_encoder_first_batch_reduces_redundancy(self) -> None:
        encoder = FieldEncoder()
        encoded = [encoder.encode(field) for field in FIRST_BATCH_FIELDS]
        self.assertEqual({item.field_name for item in encoded}, set(FIRST_BATCH_FIELDS))
        self.assertTrue(all(len(item.vector) == encoder.d_model for item in encoded))
        report = field_redundancy_report()
        self.assertLess(report["redundancy_ratio"], 0.60)
        self.assertTrue(report["redundancy_pass"])

    def test_new_fields_affect_behavioral_fingerprint_without_schema_drift(self) -> None:
        price = build_behavioral_fingerprint("Corr(CSRank($close),Sign($open))")
        liquidity = build_behavioral_fingerprint("Cov(Log(Abs($amount)),CSRank($turnover_rate))")
        vwap = build_behavioral_fingerprint("Corr(CSRank($vwap),Sign($close))")
        self.assertEqual(set(price), set(FINGERPRINT_DIMENSIONS))
        self.assertGreater(liquidity["turnover_proxy"], price["turnover_proxy"])
        self.assertGreater(liquidity["size_tilt"], price["size_tilt"])
        self.assertNotEqual(vwap, price)
        profile = aggregate_field_profile("Cov($amount,$turnover_rate)")
        self.assertGreater(profile["turnover"], 0.7)

    def test_lord_targets_qk_projection_parameters_only(self) -> None:
        model = Phase2PolicyNetwork(d_model=16, num_lanes=4)
        lord = NewtonSchulzLowRankDecay(model, target_keywords=("q_proj", "k_proj"))
        target_names = [name for name, _ in lord.target_parameters()]
        self.assertEqual(target_names, ["block.q_proj.weight", "block.k_proj.weight"])
        self.assertFalse(any("v_proj" in name or "out_proj" in name for name in target_names))

    def test_lord_smoke_step_runs_after_optimizer_and_keeps_finite_stable_rank(self) -> None:
        report = run_lord_smoke_step()
        self.assertTrue(report["optimizer_step_completed_before_lord"])
        self.assertEqual(report["target_parameter_names"], ["block.q_proj.weight", "block.k_proj.weight"])
        self.assertTrue(report["finite_stable_rank"])
        self.assertLess(report["elapsed_ms"], 5000.0)
        self.assertIn("not_connected_to_v1_runtime", report["prototype_scope"])

    def test_lord_training_harness_is_multistep_isolated_and_performance_bounded(self) -> None:
        report = run_lord_training_harness(steps=4)
        self.assertFalse(report["connected_to_main_search_runtime"])
        self.assertEqual(report["lord_target_parameter_names"], ["block.k_proj.weight", "block.q_proj.weight"])
        self.assertEqual(len(report["loss_history"]), 4)
        self.assertEqual(len(report["stable_rank_history"]), 4)
        self.assertTrue(report["optimizer_step_before_lord_every_step"])
        self.assertTrue(report["finite_stable_rank"])
        self.assertTrue(report["loss_is_finite"])
        self.assertTrue(report["performance_guard"]["elapsed_within_budget"])

    def test_stable_rank_monitor_uses_frobenius_over_spectral_definition(self) -> None:
        model = Phase2PolicyNetwork(d_model=16, num_lanes=4)
        ranks = StableRankMonitor(model).compute()
        self.assertEqual(set(ranks), {"block.q_proj.weight", "block.k_proj.weight"})
        self.assertTrue(all(value > 0 for value in ranks.values()))

    def test_regime_reward_decomposes_policy_signal_without_oos_veto(self) -> None:
        archive_record = make_candidate(
            expression="CSRank($close)",
            ic_max=0.6,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.5,
            archive_cell="archive-cell",
        )
        archive_record.retained = True
        candidate = make_candidate(
            expression="Cov($mbrd,Sign($arat))",
            ic_max=0.72,
            coverage=0.5,
            label="regime_conditional",
            oos_stability=0.25,
            archive_cell="transition-cell",
        )
        reward = compute_phase2_reward(candidate, [archive_record])
        self.assertFalse(reward["oos_hard_veto_used"])
        self.assertFalse(reward["retention_rule_replaced"])
        self.assertIn("marginal_ic", reward)
        self.assertIn("max_regime_ic", reward)
        self.assertIn("decay_resistance", reward)

    def test_surrogate_tasks_are_split_and_not_single_head(self) -> None:
        fingerprint_head = SurrogateFingerprintHead()
        ic_head = SurrogateICHead()
        fingerprint_output = fingerprint_head.predict("Corr($close,$amtm)")
        ic_output = ic_head.predict(expression="Corr($close,$amtm)", fingerprint=fingerprint_output.fingerprint)
        self.assertEqual(set(fingerprint_output.fingerprint), set(FINGERPRINT_DIMENSIONS))
        self.assertTrue(hasattr(ic_output, "quality_estimate"))
        self.assertFalse(hasattr(fingerprint_output, "quality_estimate"))

    def test_dual_channel_retention_keeps_regime_conditional_without_oos_hard_veto(self) -> None:
        evaluator = MultiFidelityEvaluator()
        record, details = evaluator.evaluate(
            expression="Cov($mbrd, Sign($arat))",
            parent_candidate_id=None,
            source_mode="variation",
            frontier_lane="bridge_frontier",
            round_index=1,
            archive=[],
        )
        self.assertIn(record.label, {"robust", "regime_conditional", "weak"})
        self.assertIn("oos_ic", details["dual_channel"])
        self.assertAlmostEqual(
            details["dual_channel"]["oos_degradation_ratio"],
            round(details["dual_channel"]["oos_ic"] / max(record.short_ic, 1e-6), 6),
        )
        self.assertIn("oos_stability", details["dual_channel"])

    def test_evaluator_marks_unseen_structure_even_for_variation_candidates(self) -> None:
        evaluator = MultiFidelityEvaluator()
        archive = [
            make_candidate(
                expression="Corr(CSRank($close), Sign($amtm))",
                ic_max=0.7,
                coverage=0.5,
                label="robust",
                oos_stability=0.8,
                archive_cell="momentum-cell",
            )
        ]
        record, _ = evaluator.evaluate(
            expression="Cov(Corr(Sign($mbrd), Log(Abs($pldn))), Corr(CSRank($vrat), Abs($low)))",
            parent_candidate_id=None,
            source_mode="variation",
            frontier_lane="novelty_frontier",
            round_index=1,
            archive=archive,
        )
        self.assertTrue(record.novel_structure)
        self.assertFalse(record.metadata["skeleton_previously_seen"])

    def test_archive_dominance_uses_non_scalar_priority_order(self) -> None:
        incumbent = make_candidate(
            expression="CSRank($close)",
            ic_max=0.60,
            coverage=0.50,
            label="regime_conditional",
            oos_stability=0.80,
        )
        challenger = make_candidate(
            expression="Sign($amtm)",
            ic_max=0.63,
            coverage=0.50,
            label="weak",
            oos_stability=0.99,
        )
        stronger = make_candidate(
            expression="Cov($mbrd,Sign($arat))",
            ic_max=0.63,
            coverage=0.75,
            label="regime_conditional",
            oos_stability=0.60,
        )
        self.assertTrue(dominates(challenger, incumbent))
        self.assertTrue(dominates(stronger, challenger))

        archive = PrototypeArchive()
        archive.update(incumbent)
        archive.update(stronger)
        self.assertEqual(archive.cell_index["cell-a"].candidate_id, stronger.candidate_id)
        self.assertFalse(archive.audit_log[-1]["used_scalar_comparator"])
        self.assertFalse(archive.audit_log[-1]["novelty_used_in_retention"])

    def test_archive_keeps_adaptive_refined_cells_after_coarse_cell_saturates(self) -> None:
        incumbent = make_candidate(
            expression="CSRank($close)",
            ic_max=0.60,
            coverage=0.50,
            label="regime_conditional",
            oos_stability=0.80,
        )
        incumbent.metadata["adaptive_archive_cell"] = "cell-a::mom=b1|size=b1"
        refined = make_candidate(
            expression="CSRank($low)",
            ic_max=0.58,
            coverage=0.49,
            label="weak",
            oos_stability=0.70,
        )
        refined.metadata["adaptive_archive_cell"] = "cell-a::mom=b1|size=b2"

        archive = PrototypeArchive()
        archive.update(incumbent)
        archive.update(refined)

        self.assertTrue(refined.retained)
        self.assertEqual(archive.cell_index["cell-a"].candidate_id, incumbent.candidate_id)
        self.assertEqual(
            archive.refined_cell_index["cell-a::mom=b1|size=b2"].candidate_id,
            refined.candidate_id,
        )
        self.assertEqual(archive.audit_log[-1]["outcome"], "retained_new_refined_cell")
        self.assertEqual(
            _new_cell_coverage([refined], {_archive_coverage_key(incumbent)}),
            1.0,
        )

    def test_adaptive_archive_cell_is_deterministic_from_fingerprint(self) -> None:
        record = make_candidate(
            expression="Cov(CSRank($volume), Sign(Mom($amtm,10)))",
            ic_max=0.62,
            coverage=0.50,
            label="regime_conditional",
            oos_stability=0.70,
        )
        record.archive_cell = behavioral_cell(record.fingerprint)

        first = _archive_coverage_key(_ensure_adaptive_archive_cell(record))
        second = _archive_coverage_key(_ensure_adaptive_archive_cell(record))

        self.assertEqual(first, second)
        self.assertTrue(first.startswith(f"{record.archive_cell}::"))

    def test_funnel_statistics_emit_required_levels_and_contract(self) -> None:
        evaluator = MultiFidelityEvaluator()
        expressions = [
            "CSRank($close)",
            "Sign($amtm)",
            "Cov($mbrd,Sign($arat))",
            "Corr($volume,$vrat)",
            "Cov($low,$pldn)",
            "Cov(Corr(Sign($mbrd), Log(Abs($arat))), Corr(CSRank($vrat), Sign($amtmabc123)))",
        ]
        archive: list[CandidateRecord] = []
        for index, expression in enumerate(expressions, start=1):
            record, _ = evaluator.evaluate(
                expression=expression,
                parent_candidate_id=None,
                source_mode="variation",
                frontier_lane="novelty_frontier",
                round_index=index,
                archive=archive,
            )
            archive.append(record)
        stats = evaluator.build_funnel_statistics()
        self.assertEqual(
            stats["funnel_contract"],
            {
                "level_0": "surrogate_ic",
                "level_1": "short_window_ic_60d",
                "level_2": "regime_conditional_ic",
                "level_3": "full_dual_channel_evaluation",
            },
        )
        self.assertIn("calibration_verdict", stats)
        self.assertGreater(stats["levels"]["level_0_surrogate_ic"]["rejection_rate"], 0.0)

    def test_real_replay_feedback_can_trigger_level0_review_without_retention_claim(self) -> None:
        evaluator = MultiFidelityEvaluator()
        record, details = evaluator.evaluate(
            expression="Corr(Abs($low), Cov(Div(Mean($amount,2),Mean($volume,5)), Sign($mbrd)))",
            parent_candidate_id=None,
            source_mode="variation",
            frontier_lane="novelty_frontier",
            round_index=1,
            archive=[],
            screening_context={
                "real_replay_feedback_score": 0.09,
                "real_replay_feedback_reasons": ["weak_positive_expression:v2cand-770b6568d717"],
            },
        )

        stats = evaluator.build_funnel_statistics()
        self.assertTrue(details["surrogate_ic"]["level0_raw_rejected"])
        self.assertTrue(record.metadata["level0_real_replay_feedback_review"])
        self.assertFalse(record.metadata["level0_rejected"])
        self.assertFalse(record.metadata["full_evaluation_reached"])
        self.assertFalse(record.retained)
        self.assertEqual(stats["audit_overrides"]["real_replay_feedback_level0_review_count"], 1)

    def test_gate_failures_block_corresponding_claims(self) -> None:
        self.assertEqual(
            evaluate_m1({"semantic_pair_margin": 0.05, "misordered_pair_rate": 0.5, "metric_definition": {}})["status"],
            "FAIL",
        )
        self.assertEqual(
            evaluate_m2({"novel_structure_ratio": 0.1, "from_scratch_trigger_observed": 0, "metric_definition": {}})["fail_consequence"],
            "open_search_claim_blocked",
        )
        self.assertEqual(
            evaluate_m3(
                {
                    "levels": {"level_0_surrogate_ic": {"rejection_rate": 0.05}},
                    "false_negative_rate": 0.2,
                    "full_evaluation_ratio": 0.9,
                    "fallback_status": "disabled",
                }
            )["status"],
            "FAIL",
        )
        self.assertEqual(
            evaluate_m4({"coverage_gain": 0.0, "quality_noninferiority": -0.1, "metric_definition": {}})["status"],
            "FAIL",
        )
        self.assertEqual(
            evaluate_m5(
                {
                    "oos_only_hard_veto_count": 1,
                    "regime_conditional_retention_rate": 0.0,
                    "channel_merge_leakage": 0.1,
                    "metric_definition": {},
                }
            )["status"],
            "FAIL",
        )
        self.assertEqual(
            evaluate_m6({"transition_alignment_gain": 0.0, "transition_signal_stability": 0.1, "metric_definition": {}})["status"],
            "FAIL",
        )

    def test_runtime_emits_required_artifacts_and_gate_matrix(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-v21-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        result = run_phase2_prototype(
            output_root=temp_root,
            saturation_window_rounds=1,
            saturation_distance_epsilon=1.0,
            rounds=3,
            per_lane_budget=1,
        )
        run_root = Path(result["artifact_root"])
        required = {
            "behavioral_fingerprint_report.json",
            "surrogate_fingerprint_report.json",
            "surrogate_ic_report.json",
            "funnel_statistics.json",
            "archive_dominance_audit.json",
            "bootstrap_report.json",
            "field_encoder_report.json",
            "structural_synthesis_report.json",
            "crossover_report.json",
            "distillation_report.json",
            "meta_policy_report.json",
            "lord_policy_report.json",
            "policy_training_report.json",
            "regime_reward_report.json",
            "edge_reality_gate_report.json",
            "discarded_space_shadow_archive.json",
            "random_search_comparison.json",
            "oos_evaluation_report.json",
            "milestone_gate_matrix.json",
            "round_report.json",
            "candidate_ledger.json",
            "archive_state.json",
            "phase2_execution_report.json",
        }
        self.assertTrue(required.issubset({path.name for path in run_root.iterdir()}))

        gate_matrix = json.loads((run_root / "milestone_gate_matrix.json").read_text(encoding="utf-8"))
        self.assertEqual(gate_matrix["schema_version"], "phase2-v2_1-prototype-v1")
        self.assertEqual(set(gate_matrix["gates"]), {"M1", "M2", "M3", "M4", "M5", "M6"})
        self.assertEqual(gate_matrix["gates"]["M1"]["status"], "PASS")
        self.assertEqual(gate_matrix["gates"]["M2"]["status"], "PASS")

        round_report = json.loads((run_root / "round_report.json").read_text(encoding="utf-8"))
        self.assertTrue(round_report["from_scratch_triggered"])
        self.assertGreaterEqual(round_report["generated_from_scratch_count"], 1)
        self.assertTrue(round_report["archive_aware_synthesis_events"])
        self.assertTrue(round_report["behavior_guided_crossover_events"])
        self.assertTrue(round_report["meta_policy_events"])
        self.assertIn("discarded_space_shadow_summary", round_report)
        self.assertIn("real_market_data_contract", round_report["edge_reality_gate_summary"])
        self.assertFalse(round_report["edge_reality_gate_summary"]["real_market_data_consumed_by_runtime"])

        final_report = json.loads((run_root / "phase2_execution_report.json").read_text(encoding="utf-8"))
        self.assertTrue(final_report["surrogate_split_real"])
        self.assertTrue(final_report["archive_non_scalar"])
        self.assertIn("generate_from_scratch_real_trigger_path", final_report)
        self.assertTrue(final_report["archive_aware_from_scratch_synthesis"])
        self.assertTrue(final_report["behavior_guided_crossover_real"])
        self.assertTrue(final_report["archive_distillation_real"])
        self.assertTrue(final_report["meta_search_policy_real"])
        self.assertTrue(final_report["edge_reality_gate_report_real"])
        self.assertTrue(final_report["edge_reality_gate_report_only"])
        self.assertTrue(final_report["not_claiming_tradable_alpha"])
        self.assertEqual(final_report["real_edge_evidence_tier"], "synthetic_proxy_only")
        self.assertIn("tradable_net_edge", final_report["real_edge_cannot_claim"])
        self.assertIn("transaction_cost_slippage_capacity_backtest", final_report["real_edge_required_validation"])
        self.assertIn("real_market_data_contract", final_report)
        self.assertFalse(final_report["real_market_data_consumed_by_runtime"])
        self.assertIn("candidate_expressions_not_backtested_on_real_market_dataset", final_report["real_edge_promotion_blockers"])
        self.assertIn("discarded_space_shadow_archive_real", final_report)
        self.assertTrue(final_report["discarded_space_shadow_report_only"])
        self.assertEqual(final_report["runtime_mode"], "prototype")
        self.assertEqual(final_report["seed_source"], "bootstrap_cold_start")

        bootstrap_report = json.loads((run_root / "bootstrap_report.json").read_text(encoding="utf-8"))
        self.assertFalse(bootstrap_report["depends_on_v1_archive"])

        meta_policy = json.loads((run_root / "meta_policy_report.json").read_text(encoding="utf-8"))
        self.assertTrue(meta_policy["uses_market_state"])
        self.assertTrue(meta_policy["uses_archive_state"])
        self.assertTrue(meta_policy["uses_recent_lane_outcomes"])
        self.assertTrue(meta_policy["decisions"])

        field_report = json.loads((run_root / "field_encoder_report.json").read_text(encoding="utf-8"))
        self.assertTrue(field_report["first_batch_fields_integrated"])
        self.assertLess(field_report["redundancy_ratio"], 0.60)

        lord_report = json.loads((run_root / "lord_policy_report.json").read_text(encoding="utf-8"))
        self.assertEqual(lord_report["target_parameter_names"], ["block.q_proj.weight", "block.k_proj.weight"])
        self.assertTrue(lord_report["optimizer_step_completed_before_lord"])
        self.assertTrue(lord_report["finite_stable_rank"])

        policy_training = json.loads((run_root / "policy_training_report.json").read_text(encoding="utf-8"))
        self.assertFalse(policy_training["connected_to_main_search_runtime"])
        self.assertTrue(policy_training["finite_stable_rank"])
        self.assertTrue(policy_training["performance_guard"]["elapsed_within_budget"])
        self.assertEqual(policy_training["lord_target_parameter_names"], ["block.k_proj.weight", "block.q_proj.weight"])

        reward_report = json.loads((run_root / "regime_reward_report.json").read_text(encoding="utf-8"))
        self.assertTrue(reward_report["does_not_replace_archive_dominance"])
        self.assertFalse(reward_report["oos_hard_veto_used"])

        edge_reality = json.loads((run_root / "edge_reality_gate_report.json").read_text(encoding="utf-8"))
        self.assertTrue(edge_reality["does_not_change_archive_retention"])
        self.assertTrue(edge_reality["not_claiming_tradable_alpha"])
        self.assertEqual(edge_reality["evidence_tier"], "synthetic_proxy_only")
        self.assertEqual(edge_reality["proxy_role"], "candidate_triage_only_not_real_edge_evidence")
        self.assertIn("real_market_data_contract", edge_reality)
        self.assertFalse(edge_reality["real_market_data_consumed_by_runtime"])
        self.assertIn("production_alpha_quality", edge_reality["cannot_support_claims"])
        self.assertIn("net_edge_score", edge_reality["metric_definition"])
        self.assertIn("evaluations", edge_reality)

        discarded_shadow = json.loads((run_root / "discarded_space_shadow_archive.json").read_text(encoding="utf-8"))
        self.assertTrue(discarded_shadow["does_not_change_archive_retention"])
        self.assertIn("counterfactual_hit_count_in_sample", discarded_shadow)

        oos_report = json.loads((run_root / "oos_evaluation_report.json").read_text(encoding="utf-8"))
        self.assertIn("retained_oos_ic_mean", oos_report)
        self.assertIn("retained_oos_ic_max", oos_report)
        self.assertGreaterEqual(oos_report["oos_ic_mean"], 0.0)

        archive_state = json.loads((run_root / "archive_state.json").read_text(encoding="utf-8"))
        self.assertEqual(archive_state["runtime_mode"], "prototype")
        self.assertGreaterEqual(archive_state["retained_count"], 1)
        self.assertTrue(archive_state["retained_records"])

    def test_compact_artifact_profile_omits_heavy_diagnostics_but_keeps_continuation_state(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-compact-artifacts-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        result = run_phase2_generation(
            output_root=temp_root,
            rounds=1,
            per_lane_budget=1,
            seed_source="bootstrap_cold_start",
            artifact_profile="compact",
        )
        run_root = Path(result["artifact_root"])

        round_report = json.loads((run_root / "round_report.json").read_text(encoding="utf-8"))
        candidate_ledger = json.loads((run_root / "candidate_ledger.json").read_text(encoding="utf-8"))
        archive_state = json.loads((run_root / "archive_state.json").read_text(encoding="utf-8"))
        generation_report = json.loads((run_root / "generation_report.json").read_text(encoding="utf-8"))
        efficiency_audit = json.loads((run_root / "generation_efficiency_audit.json").read_text(encoding="utf-8"))

        self.assertEqual(round_report["artifact_profile"], "compact")
        self.assertTrue(round_report["round_diagnostics_omitted"])
        self.assertEqual(round_report["round_diagnostics"], [])
        self.assertTrue(round_report["rounds"])
        self.assertTrue(round_report["meta_policy_outcome_events"])
        self.assertEqual(candidate_ledger["artifact_profile"], "compact")
        self.assertEqual(candidate_ledger["records_policy"], "retained_records_only; use full artifact_profile for discarded-space probe")
        self.assertEqual(len(candidate_ledger["records"]), archive_state["retained_count"])
        self.assertEqual(archive_state["artifact_profile"], "compact")
        self.assertEqual(generation_report["artifact_profile"], "compact")
        self.assertGreaterEqual(efficiency_audit["total_generated_candidates"], 1)

    def test_runtime_can_self_bootstrap_without_phase1_seed(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-bootstrap-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        result = run_phase2_prototype(
            output_root=temp_root,
            saturation_window_rounds=1,
            saturation_distance_epsilon=1.0,
            rounds=3,
            per_lane_budget=1,
            seed_source="bootstrap_cold_start",
        )
        run_root = Path(result["artifact_root"])
        bootstrap_report = json.loads((run_root / "bootstrap_report.json").read_text(encoding="utf-8"))
        self.assertFalse(bootstrap_report["depends_on_v1_archive"])
        self.assertGreater(bootstrap_report["behavior_grid_coverage"], 0.1)

        final_report = json.loads((run_root / "phase2_execution_report.json").read_text(encoding="utf-8"))
        self.assertTrue(final_report["phase2_self_bootstrap_real"])
        self.assertTrue(final_report["continuous_field_encoder_stage_b_real"])
        self.assertEqual(final_report["seed_source"], "bootstrap_cold_start")

    def test_generation_runtime_supports_continuation_and_independent_reports(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-generation-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        first = run_phase2_generation(
            output_root=temp_root,
            rounds=3,
            per_lane_budget=2,
            seed_source="bootstrap_cold_start",
        )
        first_root = Path(first["artifact_root"])
        first_generation = json.loads((first_root / "generation_report.json").read_text(encoding="utf-8"))
        first_efficiency = json.loads((first_root / "generation_efficiency_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(first_generation["runtime_mode"], "generation")
        self.assertFalse(first_generation["continued"])
        self.assertTrue((first_root / "continuation_manifest.json").exists())
        self.assertTrue((first_root / "candidate_ledger.json").exists())
        self.assertGreaterEqual(first_efficiency["total_generated_candidates"], 1)
        self.assertIn("lane_totals", first_efficiency)
        self.assertIn("lane_yield_guard", first_efficiency)

        second = run_phase2_generation(
            output_root=temp_root,
            previous_run_root=first_root,
            rounds=2,
            per_lane_budget=2,
        )
        second_root = Path(second["artifact_root"])
        continuation_manifest = json.loads((second_root / "continuation_manifest.json").read_text(encoding="utf-8"))
        generation_report = json.loads((second_root / "generation_report.json").read_text(encoding="utf-8"))
        efficiency_audit = json.loads((second_root / "generation_efficiency_audit.json").read_text(encoding="utf-8"))
        archive_state = json.loads((second_root / "archive_state.json").read_text(encoding="utf-8"))
        final_report = json.loads((second_root / "phase2_execution_report.json").read_text(encoding="utf-8"))
        candidate_ledger = json.loads((second_root / "candidate_ledger.json").read_text(encoding="utf-8"))
        score_variation_ids = [
            record["candidate_id"]
            for record in candidate_ledger["records"]
            if record["frontier_lane"] == "score_frontier" and record["source_mode"] == "variation"
        ]

        self.assertEqual(continuation_manifest["schema_version"], "phase2-v2_1-generation-v1")
        self.assertTrue(continuation_manifest["continued"])
        self.assertEqual(continuation_manifest["previous_run_id"], first["run_id"])
        self.assertEqual(generation_report["final_report_runtime_mode"], "generation")
        self.assertEqual(final_report["runtime_mode"], "generation")
        self.assertEqual(final_report["seed_source"], "phase2_generation_continuation")
        self.assertEqual(archive_state["runtime_mode"], "generation")
        self.assertTrue(archive_state["continuation_context"]["continued_from_archive_state"])
        self.assertIn("delta_vs_previous", efficiency_audit)
        self.assertEqual(efficiency_audit["continued"], True)
        self.assertEqual(len(score_variation_ids), len(set(score_variation_ids)))

    def test_discarded_space_probe_reports_counterfactual_candidates_without_retention_changes(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-discarded-probe-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        generation = run_phase2_generation(
            output_root=temp_root,
            rounds=2,
            per_lane_budget=2,
            seed_source="bootstrap_cold_start",
        )
        run_root = Path(generation["artifact_root"])
        probe = run_phase2_discarded_space_probe(run_root=run_root, sample_limit=8)
        payload = json.loads(Path(probe["discarded_space_probe"]).read_text(encoding="utf-8"))

        self.assertEqual(payload["schema_version"], "phase2-v2_1-generation-v1")
        self.assertEqual(payload["runtime_mode"], "discarded_space_reverse_probe")
        self.assertIn("does_not_change_archive_retention", payload["scope"])
        self.assertLessEqual(len(payload["top_discarded_candidates"]), 8)
        self.assertIn("interpretation", payload)

    def test_generation_flow_emits_multi_run_summary(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-generation-flow-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        flow = run_phase2_generation_flow(
            output_root=temp_root,
            flow_length=2,
            rounds=2,
            per_lane_budget=2,
            seed_source="bootstrap_cold_start",
        )
        summary = json.loads(Path(flow["multi_run_generation_summary"]).read_text(encoding="utf-8"))
        self.assertEqual(summary["schema_version"], "phase2-v2_1-generation-v1")
        self.assertEqual(summary["flow_length"], 2)
        self.assertEqual(len(summary["runs"]), 2)
        self.assertEqual(len(summary["archive_growth_trend"]), 2)
        self.assertIn("all_runs_pass", summary)
        self.assertTrue(all("all_gates_pass" in item for item in summary["runs"]))

    def test_budget_profile_comparison_emits_ranked_profiles(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-budget-profiles-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        comparison = run_phase2_budget_profile_comparison(
            output_root=temp_root,
            budgets=[1, 2],
            flow_length=2,
            rounds=2,
            seed_source="bootstrap_cold_start",
        )
        payload = json.loads(Path(comparison["budget_profile_comparison"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "phase2-v2_1-generation-v1")
        self.assertEqual(payload["budgets"], [1, 2])
        self.assertEqual(len(payload["profiles"]), 2)
        self.assertIn("selection_rule", payload)
        self.assertEqual(payload["yield_floor"], YIELD_FLOOR)
        self.assertTrue(all("yield_floor_pass" in profile for profile in payload["profiles"]))
        self.assertTrue(all("selection_eligible" in profile for profile in payload["profiles"]))
        self.assertTrue(all("per_run_yield_floor_warnings" in profile for profile in payload["profiles"]))
        self.assertTrue(all("avg_non_score_retained_ratio" in profile for profile in payload["profiles"]))
        self.assertTrue(all("avg_generated_per_round" in profile for profile in payload["profiles"]))
        self.assertIn(payload["best_budget"], {"1", "2", None})

    def test_budget_selection_blocks_high_non_score_when_yield_below_floor(self) -> None:
        best_budget = _select_best_budget(
            [
                {
                    "budget": 2,
                    "all_runs_pass": True,
                    "avg_non_score_retained_ratio": 0.81,
                    "avg_retained_yield": YIELD_FLOOR + 0.02,
                    "avg_archive_growth": 8.0,
                    "avg_generated_per_round": 6.0,
                },
                {
                    "budget": 3,
                    "all_runs_pass": True,
                    "avg_non_score_retained_ratio": 0.94,
                    "avg_retained_yield": YIELD_FLOOR - 0.01,
                    "avg_archive_growth": 12.0,
                    "avg_generated_per_round": 11.0,
                },
            ]
        )
        self.assertEqual(best_budget, "2")

    def test_continuation_scale_decision_routes_low_yield_runs_to_real_replay(self) -> None:
        decision = _build_continuation_scale_decision(
            [
                {
                    "sequence_index": 1,
                    "run_id": "phase2-a",
                    "generation_report": {"all_gates_pass": True},
                    "generation_efficiency_audit": {
                        "archive_growth": 3,
                        "retained_yield": 0.32,
                        "total_generated_candidates": 28,
                        "total_new_behavior_cells": 3,
                        "lane_yield_guard": {},
                    },
                },
                {
                    "sequence_index": 2,
                    "run_id": "phase2-b",
                    "generation_report": {"all_gates_pass": True},
                    "generation_efficiency_audit": {
                        "archive_growth": 3,
                        "retained_yield": 0.11,
                        "total_generated_candidates": 27,
                        "total_new_behavior_cells": 3,
                        "lane_yield_guard": {},
                    },
                },
            ]
        )

        self.assertEqual(decision["decision"], "HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY")
        self.assertIn("avg_retained_yield_below_floor", decision["blockers"])
        self.assertFalse(decision["real_edge_claim_allowed"])
        self.assertIn("ashare_tplus1_execution_alignment", decision["real_edge_required_before_promotion"])

    def test_continuation_scale_decision_allows_healthy_controlled_search(self) -> None:
        decision = _build_continuation_scale_decision(
            [
                {
                    "sequence_index": 1,
                    "run_id": "phase2-a",
                    "generation_report": {"all_gates_pass": True},
                    "generation_efficiency_audit": {
                        "archive_growth": 6,
                        "retained_yield": YIELD_FLOOR + 0.05,
                        "total_generated_candidates": 24,
                        "total_new_behavior_cells": 5,
                        "lane_yield_guard": {},
                    },
                },
                {
                    "sequence_index": 2,
                    "run_id": "phase2-b",
                    "generation_report": {"all_gates_pass": True},
                    "generation_efficiency_audit": {
                        "archive_growth": 5,
                        "retained_yield": YIELD_FLOOR + 0.03,
                        "total_generated_candidates": 24,
                        "total_new_behavior_cells": 4,
                        "lane_yield_guard": {},
                    },
                },
            ]
        )

        self.assertEqual(decision["decision"], "CONTINUE_CONTROLLED_SYNTHETIC_SEARCH")
        self.assertEqual(decision["blockers"], [])

    def test_bootstrap_independence_precheck_emits_cold_start_decision(self) -> None:
        temp_root = Path(tempfile.mkdtemp(prefix="phase2-bootstrap-precheck-"))
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))

        precheck = run_phase2_bootstrap_independence_precheck(
            output_root=temp_root,
            variants_per_prototype=1,
        )
        payload = json.loads(Path(precheck["bootstrap_independence_precheck"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "phase2-v2_1-generation-v1")
        self.assertFalse(payload["depends_on_v1_archive"])
        self.assertGreater(payload["generated_formula_count"], 0)
        self.assertGreaterEqual(payload["legal_formula_count"], 0)
        self.assertGreaterEqual(payload["occupied_behavior_cell_count"], 0)
        self.assertIn(
            payload["step4_decision"],
            {"direct_bootstrap_independence", "prototype_formula_family_expansion_first"},
        )


if __name__ == "__main__":
    unittest.main()
