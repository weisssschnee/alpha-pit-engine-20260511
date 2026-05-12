from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from our_system_phase2.services.stock_pit_replay_ranker import (
    BASE_PRE_REPLAY_FEATURES,
    POST_REPLAY_FORBIDDEN_FEATURES,
    LaneBandit,
    build_lane_bandit_from_replay,
    build_pre_replay_matrix,
    build_replay_ranker_calibration,
    score_shadow_selector,
    score_with_trained_replay_rankers,
    train_pure_rl_control,
)


def _candidate_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": "a",
                "ast_hash": "hash-a",
                "generator_name": "cem_adaptive_grammar",
                "operator_list": ["CSRank", "Mean"],
                "field_list": ["volume"],
                "field_family_list": ["liquidity"],
                "window_list": [5],
                "complexity_score": 2.0,
                "cheap_backtest_fitness": 0.5,
                "cheap_backtest_turnover": 0.1,
                "cheap_backtest_returns": 0.01,
                "cheap_backtest_ic": 0.02,
                "cheap_backtest_rank_ic": 0.02,
                "cheap_backtest_margin": 1.0,
                "gap_score": 0.0,
                "non_gap_score": 1.0,
                "gap_minus_non_gap": -1.0,
                "subperiod_stability": 0.7,
                "regime_stability": 0.7,
                "replay_attempted": True,
                "replay_pass": True,
                "non_gap_replay_pass": True,
            },
            {
                "candidate_id": "b",
                "ast_hash": "hash-b",
                "generator_name": "typed_random_dark",
                "operator_list": ["CSRank"],
                "field_list": ["open", "close"],
                "field_family_list": ["price_shape"],
                "window_list": [1],
                "complexity_score": 5.0,
                "cheap_backtest_fitness": 0.1,
                "cheap_backtest_turnover": 0.9,
                "cheap_backtest_returns": -0.01,
                "cheap_backtest_ic": -0.01,
                "cheap_backtest_rank_ic": -0.01,
                "cheap_backtest_margin": -1.0,
                "gap_score": 1.0,
                "non_gap_score": 0.0,
                "gap_minus_non_gap": 1.0,
                "subperiod_stability": 0.2,
                "regime_stability": 0.2,
                "replay_attempted": True,
                "replay_pass": False,
                "non_gap_replay_pass": False,
            },
        ]
    )


def test_pre_replay_matrix_excludes_forbidden_replay_columns() -> None:
    matrix, columns = build_pre_replay_matrix(_candidate_frame())
    assert len(matrix) == 2
    assert not (set(columns) & POST_REPLAY_FORBIDDEN_FEATURES)
    assert set(BASE_PRE_REPLAY_FEATURES).issubset(set(columns))
    assert any(column.startswith("cat_generator_name_") for column in columns)
    assert "op__CSRank" in columns


def test_shadow_selector_uses_ranker_scores_and_diversity_buckets() -> None:
    df = _candidate_frame()
    df["p_non_gap_replay"] = [0.9, 0.1]
    df["p_replay"] = [0.9, 0.2]
    selected = score_shadow_selector(df, selection_budget=2)
    assert int(selected["selector_selected"].sum()) == 2
    assert selected.loc[selected["candidate_id"] == "a", "selection_score"].iloc[0] > selected.loc[
        selected["candidate_id"] == "b", "selection_score"
    ].iloc[0]


def test_shadow_selector_respects_tiny_budget() -> None:
    df = _candidate_frame()
    df["p_non_gap_replay"] = [0.9, 0.1]
    df["p_replay"] = [0.9, 0.2]
    selected = score_shadow_selector(df, selection_budget=1)
    assert int(selected["selector_selected"].sum()) == 1


def test_replay_ranker_calibration_records_deciles_and_pure_rl_status() -> None:
    df = _candidate_frame()
    df["strict_pass"] = [True, True]
    df["cost_survives"] = [True, False]
    df["p_non_gap_replay"] = [0.9, 0.1]
    df["p_replay"] = [0.9, 0.2]
    df["pure_rl_score"] = [0.8, 0.3]
    selected = score_shadow_selector(df, selection_budget=2)
    table, report = build_replay_ranker_calibration(selected, bucket_count=2)
    assert not table.empty
    assert "generator_counts_json" in table.columns
    assert report["pure_rl_control_status"] == "premature_shadow_diagnostic_not_formal_ablation"
    assert report["score_lifts"]["p_non_gap_replay"]["top_5pct_pass_rate"] == 1.0
    assert report["score_lifts"]["pure_rl_score"]["status"] == "ok"


def test_score_with_trained_replay_rankers_missing_models_defaults_to_zero(tmp_path: Path) -> None:
    scored, report = score_with_trained_replay_rankers(_candidate_frame(), model_dir=tmp_path)
    assert scored["p_non_gap_replay"].tolist() == [0.0, 0.0]
    assert scored["p_replay"].tolist() == [0.0, 0.0]
    assert report["models"]["non_gap_replay_pass"]["status"] == "missing_model"
    assert not report["leakage_guard"]["feature_overlap_with_forbidden"]


def test_lane_bandit_allocates_budget_with_minimum_floor() -> None:
    replay = pd.DataFrame(
        [
            {"generator_name": "cem_adaptive_grammar", "non_gap_replay_pass": True},
            {"generator_name": "cem_adaptive_grammar", "non_gap_replay_pass": True},
            {"generator_name": "typed_random_dark", "non_gap_replay_pass": False},
        ]
    )
    bandit = build_lane_bandit_from_replay(replay, lanes=["cem_adaptive_grammar", "typed_random_dark"])
    allocation = bandit.allocate(100, min_share=0.05, seed=7)
    assert sum(allocation.values()) == 100
    assert allocation["cem_adaptive_grammar"] >= 5
    assert allocation["typed_random_dark"] >= 5


def test_lane_bandit_accepts_new_lane_updates() -> None:
    bandit = LaneBandit(["a"])
    bandit.update("b", 1, 2)
    state = bandit.state()
    assert "b" in state["lanes"]
    assert state["alpha"]["b"] == 2.0


def test_pure_rl_control_scores_without_forbidden_feature_overlap() -> None:
    rows = []
    for idx in range(24):
        rows.append(
            {
                "candidate_id": f"cand-{idx}",
                "ast_hash": f"hash-{idx % 8}",
                "generator_name": "cem_adaptive_grammar" if idx % 3 == 0 else "typed_random_dark",
                "operator_list": ["CSRank", "Mean"] if idx % 3 == 0 else ["CSRank"],
                "field_list": ["volume"] if idx % 3 == 0 else ["open", "close"],
                "field_family_list": ["liquidity"] if idx % 3 == 0 else ["price_shape"],
                "window_list": [5],
                "complexity_score": 2.0 if idx % 3 == 0 else 5.0,
                "cheap_backtest_fitness": 0.5 if idx % 3 == 0 else 0.1,
                "cheap_backtest_turnover": 0.1 if idx % 3 == 0 else 0.9,
                "cheap_backtest_returns": 0.01 if idx % 3 == 0 else -0.01,
                "cheap_backtest_ic": 0.02 if idx % 3 == 0 else -0.01,
                "cheap_backtest_rank_ic": 0.02 if idx % 3 == 0 else -0.01,
                "cheap_backtest_margin": 1.0 if idx % 3 == 0 else -1.0,
                "gap_score": 0.0 if idx % 3 == 0 else 1.0,
                "non_gap_score": 1.0 if idx % 3 == 0 else 0.0,
                "gap_minus_non_gap": -1.0 if idx % 3 == 0 else 1.0,
                "subperiod_stability": 0.7 if idx % 3 == 0 else 0.2,
                "regime_stability": 0.7 if idx % 3 == 0 else 0.2,
                "replay_attempted": True,
                "replay_pass": idx % 3 == 0,
                "non_gap_replay_pass": idx % 3 == 0,
            }
        )
    scored, report = train_pure_rl_control(pd.DataFrame(rows), epochs=20)
    assert report["status"] == "trained_logged_policy_gradient_control"
    assert "pure_rl_score" in scored.columns
    assert int(scored["pure_rl_selected"].sum()) == min(96, len(scored))
    assert not report["leakage_guard"]["feature_overlap_with_forbidden"]
