from __future__ import annotations

import json
from pathlib import Path

from features.build_features import (
    FORBIDDEN_RANKER_COLUMNS,
    POST_REPLAY_LABEL_COLUMNS,
    PRE_REPLAY_RANKER_FEATURE_COLUMNS,
    build_tables,
    write_outputs,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_ranker_feature_contract_excludes_post_replay_labels() -> None:
    assert not (set(PRE_REPLAY_RANKER_FEATURE_COLUMNS) & set(POST_REPLAY_LABEL_COLUMNS))
    assert "replay_pass" in FORBIDDEN_RANKER_COLUMNS
    assert "shadow_replay_aware_reward" in FORBIDDEN_RANKER_COLUMNS


def test_build_tables_from_true_limit_bakeoff_artifacts(tmp_path: Path) -> None:
    run = tmp_path / "run"
    report = {
        "experiment_id": "unit_seed",
        "created_at": "2026-05-11T00:00:00+00:00",
        "dataset_path": "unit.parquet",
        "dataset_role": "stock_pit_panel",
        "fixed_contract": {
            "execution_lag_days": 1,
            "reward_for_selection": "R0_current_true_limit",
        },
        "parameters": {"seed": "unit_seed"},
        "variant_stage1_reports": [{"variant": "cem_adaptive_grammar"}],
    }
    ledger = {
        "created_at": "2026-05-11T00:01:00+00:00",
        "records": [
            {
                "candidate_id": "cand-1",
                "expression": "Neg(CSRank(Std($volume,13)))",
                "primitive_family": "cem_single",
                "proposal_kind": "cem_adaptive_grammar_sample",
                "retained": True,
            }
        ],
    }
    validation = {
        "evaluations": [
            {
                "candidate_id": "cand-1",
                "expression": "Neg(CSRank(Std($volume,13)))",
                "mean_window_rank_ic": 0.03,
                "mean_window_long_return": 0.001,
                "mean_window_long_sortino": 1.2,
                "mean_window_sortino": 0.8,
                "mean_window_long_selected_turnover_rate": 0.02,
                "horizon_reports": [
                    {
                        "windows": [
                            {"window": "2026Q1", "mean_rank_ic": 0.02},
                            {"window": "2026Q2", "mean_rank_ic": 0.04},
                        ]
                    }
                ],
            }
        ]
    }
    strict = {
        "strict_rows": [
            {
                "proof_variant": "cem_adaptive_grammar",
                "candidate_id": "cand-1",
                "expression": "Neg(CSRank(Std($volume,13)))",
                "strict_selection_role": "top_fast_reward",
                "reward_decile": 10,
                "strict_pass_proxy": True,
                "portfolio_replay_pass": True,
                "signal_cluster_id": "cluster_001",
                "max_abs_signal_corr_to_prior": 0.1,
            }
        ]
    }

    _write_json(run / "true_limit_search_bakeoff_v2_report.json", report)
    _write_json(run / "variants" / "cem_adaptive_grammar" / "candidate_ledger.json", ledger)
    _write_json(run / "variants" / "cem_adaptive_grammar" / "stage1_validation_report.json", validation)
    _write_json(run / "strict_by_variant_rows.json", strict)

    candidates, replay, manifest = build_tables([run])

    assert manifest["candidate_row_count"] == 1
    assert manifest["replay_row_count"] == 1
    assert candidates.loc[0, "generator_name"] == "cem_adaptive_grammar"
    assert bool(candidates.loc[0, "replay_pass"]) is True
    assert bool(candidates.loc[0, "non_gap_replay_pass"]) is True
    assert candidates.loc[0, "operator_list"] == ["Neg", "CSRank", "Std"]
    assert candidates.loc[0, "field_list"] == ["volume"]
    assert candidates.loc[0, "window_list"] == [13]

    out = tmp_path / "data"
    write_outputs(candidates, replay, manifest, out)
    assert (out / "candidates.parquet").exists()
    assert (out / "replay_results.parquet").exists()
    assert (out / "candidate_feature_manifest.json").exists()
