from __future__ import annotations

import pandas as pd

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

