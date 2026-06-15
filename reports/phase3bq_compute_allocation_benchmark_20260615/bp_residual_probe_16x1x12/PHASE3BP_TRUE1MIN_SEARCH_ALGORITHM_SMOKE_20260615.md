# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_rx_ucb_smoke`
- candidates generated: `16`
- true-1min shard panels: `1`
- sampled signal trade_times per shard: `12`
- total eval rows: `3901`
- followup priority: `2`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_rx_ucb_native` | 16 | 0.2326280248 | 2 | 9 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `rx_range_location::inverted` | 2 | 0.2326280248 | 0 | 2 |
| `rx_range_location::rank` | 2 | 0.2326280248 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 3 | 0.1700095992 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::residual` | 1 | 0.1697587906 | 0 | 1 |
| `rx_intraday_return::rank` | 2 | 0.1677194019 | 0 | 1 |
| `rx_intraday_return::inverted` | 2 | 0.1677194019 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::spread` | 1 | 0.1043764053 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::product` | 2 | 0.06822486229 | 2 | 0 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::product` | 1 | 0.01254933746 | 0 | 0 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2326280248 | `long_top` | 0.7879048374 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2326280248 | `short_top` | 0.7872169624 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2185853462 | `short_top` | 0.8003729698 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2185853462 | `long_top` | 0.7978877099 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 1 | `intraday_ret_from_open|ret_1m` | 0.1700095992 | `short_top` | 0.7572380462 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::residual` | 1 | `high|low|open|ret_1m` | 0.1697587906 | `short_top` | 0.7847963906 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1677194019 | `short_top` | 0.75964948 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1677194019 | `long_top` | 0.7575413554 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 5 | `intraday_ret_from_open` | 0.1094661511 | `long_top` | 0.7728756556 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 10 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 5 | `intraday_ret_from_open` | 0.1094661511 | `short_top` | 0.7721805663 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 11 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::spread` | 1 | `high|low|open|ret_1m` | 0.1043764053 | `short_top` | 0.7443995028 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 5 | `intraday_ret_from_open|ret_1m` | 0.1015111299 | `short_top` | 0.7806646033 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 13 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 5 | `intraday_ret_from_open|ret_1m` | 0.09794607891 | `short_top` | 0.775976027 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 14 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::product` | 15 | `high|low|open|ret_1m` | 0.06822486229 | `long_top` | 0.7935086129 | `bp_followup_priority` | `` |
| 15 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::product` | 15 | `high|low|open|ret_1m` | 0.04385158075 | `long_top` | 0.7976064319 | `bp_followup_priority` | `` |
| 16 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::product` | 1 | `intraday_ret_from_open|ret_1m` | 0.01254933746 | `long_top` | 0.7593027369 | `bp_watch_or_reject` | `too_few_positive_horizons|weak_dense_primary_abs_ic` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
