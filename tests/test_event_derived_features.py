from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from our_system_phase2.runtime.phase3r_limit_motif_pack_diagnostic import _candidate_rows, run as run_limit_motif_diagnostic
from our_system_phase2.services.event_derived_features import (
    attach_event_derived_features,
    event_derived_feature_coverage_report,
    event_derived_feature_contract,
)
from our_system_phase2.services.field_encoder import FieldEncoder, canonical_field_name
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _prepare_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key


def _sample_panel() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": "2026-01-01", "code": "000001", "open": 10.0, "high": 10.2, "low": 9.9, "close": 10.0, "amount": 100, "volume": 10},
            {"date": "2026-01-02", "code": "000001", "open": 10.98, "high": 10.98, "low": 10.8, "close": 10.98, "amount": 110, "volume": 10},
            {"date": "2026-01-03", "code": "000001", "open": 12.05604, "high": 12.05604, "low": 11.3, "close": 11.5, "amount": 120, "volume": 10},
            {"date": "2026-01-04", "code": "000001", "open": 11.5, "high": 12.627, "low": 11.4, "close": 12.627, "amount": 130, "volume": 10},
            {"date": "2026-01-01", "code": "000002", "open": 20.0, "high": 20.1, "low": 19.9, "close": 20.0, "amount": 100, "volume": 10},
            {"date": "2026-01-02", "code": "000002", "open": 20.0, "high": 21.96, "low": 19.9, "close": 20.5, "amount": 110, "volume": 10},
            {"date": "2026-01-03", "code": "000002", "open": 20.5, "high": 20.7, "low": 20.0, "close": 20.3, "amount": 120, "volume": 10},
            {"date": "2026-01-04", "code": "000002", "open": 20.3, "high": 20.4, "low": 18.3, "close": 18.3, "amount": 130, "volume": 10},
        ]
    )


def test_event_derived_feature_layer_distinguishes_open_touch_close_and_streaks() -> None:
    frame = attach_event_derived_features(_sample_panel(), max_streak_n=4)
    a = frame[frame["code"].eq("000001")].reset_index(drop=True)
    b = frame[frame["code"].eq("000002")].reset_index(drop=True)

    assert a.loc[1, "limit_up_close_event"] == 1.0
    assert a.loc[1, "limit_up_open_event"] == 1.0
    assert a.loc[2, "limit_up_close_event"] == 0.0
    assert a.loc[2, "limit_up_open_event"] == 1.0
    assert a.loc[2, "limit_up_touch_not_close"] == 1.0
    assert a.loc[2, "limit_up_open_not_close"] == 1.0
    assert a.loc[2, "limit_up_break"] == 1.0
    assert a.loc[2, "break_board_after_streak_ge_1"] == 1.0

    assert b.loc[1, "limit_up_touch_event"] == 1.0
    assert b.loc[1, "limit_up_close_event"] == 0.0
    assert b.loc[1, "limit_up_touch_not_close"] == 1.0

    assert "market_high_board" in frame.columns
    assert "post_market_high_board_tplus_1" in frame.columns
    assert frame["limit_up_streak_ge_2"].notna().all()


def test_event_derived_features_attach_to_real_market_validation_and_lag_policy() -> None:
    prepared = _prepare_market_panel(_sample_panel())
    assert "limit_up_open_not_close" in prepared.columns
    assert "limit_up_streak_ge_3" in prepared.columns

    _signal_frame, clock_report = _signal_evaluation_frame(prepared, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    assert clock_report["field_lags"]["limit_up_open_not_close"] == 1
    assert "limit_up_open_event" not in clock_report["field_lags"]

    raw_signal = evaluate_panel_expression(prepared, "$limit_up_open_not_close")
    lagged_signal = evaluate_panel_expression(
        prepared,
        "$limit_up_open_not_close",
        field_lags=clock_report["field_lags"],
    )
    assert raw_signal.loc[prepared["code"].eq("000001")].fillna(0).tolist()[2] == 1.0
    assert lagged_signal.loc[prepared["code"].eq("000001")].fillna(0).tolist()[3] == 1.0


def test_event_derived_feature_contract_and_field_encoder() -> None:
    contract = event_derived_feature_contract(max_streak_n=4)
    assert "limit_up_streak_ge_4" in contract["fields"]
    assert "limit_up_open_event" in contract["open_print_fields"]
    assert "limit_up_touch_not_close" in contract["full_day_fields"]

    encoder = FieldEncoder()
    encoded = encoder.encode("$limit_up_touch_not_close")
    assert encoded.field_type == "event_ts"
    assert encoded.behavior_profile["volatility"] >= 0.8
    assert canonical_field_name("$limit_up_streak_ge_3") == "limit_up_streak_ge_3"

    report = event_derived_feature_coverage_report(attach_event_derived_features(_sample_panel(), max_streak_n=4), max_streak_n=4)
    assert report["coverage"]["limit_up_open_not_close"]["present"] is True
    assert report["coverage"]["limit_up_open_not_close"]["positive_ratio"] > 0.0


def test_limit_motif_diagnostic_uses_event_adapter_metadata() -> None:
    rows = _candidate_rows(max_per_role=24)
    assert rows
    expressions = "\n".join(str(row["expression"]) for row in rows)
    assert "$limit_up_streak_ge_3" in expressions
    assert "$limit_up_touch_not_close" in expressions
    assert "$market_high_board" in expressions or "$is_market_high_board" in expressions

    formula_rows = [row for row in rows if row["diagnostic_role"] != "r3_secondary_gate"]
    assert formula_rows
    assert any(row["contains_new_event_adapter_field"] for row in formula_rows)
    required = {
        "feature_adapter",
        "event_fields",
        "event_family",
        "lag_rule",
        "tradability_rule",
        "leakage_flag",
        "search_memory_key",
        "pool_priority_score",
        "source_quota_group",
        "source_credit_cap_basis",
    }
    for row in formula_rows:
        assert required.issubset(row)
        assert row["feature_adapter"] == "event_derived_feature_layer"
        assert row["search_memory_key"].startswith("event_adapter:")
        assert float(row["pool_priority_score"]) > 0.0
        assert row["source_credit_cap_basis"] == row["search_memory_key"]


def test_limit_motif_diagnostic_writes_and_inherits_search_memory() -> None:
    first_expression = next(
        row["expression"]
        for row in _candidate_rows(max_per_role=24)
        if row["diagnostic_role"] != "r3_secondary_gate"
    )
    with tempfile.TemporaryDirectory(prefix="event-adapter-memory-test-") as temp:
        root = Path(temp)
        previous = root / "previous"
        previous.mkdir()
        previous_payload = {
            "run_id": "previous-memory",
            "expression_keys": [expression_memory_key(first_expression)],
            "skeleton_keys": [skeleton_memory_key(first_expression)],
            "records": [
                {
                    "candidate_id": "previous-duplicate",
                    "expression_key": expression_memory_key(first_expression),
                    "skeleton_key": skeleton_memory_key(first_expression),
                    "real_replay_dataset_role": "stock_pit_panel",
                }
            ],
            "duplicate_skip_events": [],
            "inherited_paths": [],
            "replay_enrichment_paths": [],
        }
        (previous / "search_memory.json").write_text(json.dumps(previous_payload), encoding="utf-8")

        out = root / "out"
        summary = run_limit_motif_diagnostic(
            motif_pack=Path("src/our_system_phase2/formula_gen_v2/motif_pack_limit_diagnostic.yaml"),
            o7_summary_path=Path("missing-o7.json"),
            output_root=out,
            max_per_role=24,
            previous_memory_root=previous,
            dataset_role="stock_pit_panel",
        )

        assert summary["search_memory"]["duplicate_skip_count"] == 1
        assert summary["candidate_template_count"] == summary["pre_memory_candidate_template_count"] - 1
        memory = json.loads((out / "search_memory.json").read_text(encoding="utf-8"))
        assert memory["duplicate_skip_count"] == 1
        assert memory["dataset_role_filter"]["expected_dataset_role"] == "stock_pit_panel"
