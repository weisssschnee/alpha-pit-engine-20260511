# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_rx_ucb_smoke`
- candidates generated: `40`
- true-1min shard panels: `2`
- sampled signal trade_times per shard: `24`
- total eval rows: `15569`
- followup priority: `1`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_rx_ucb_native` | 40 | 0.2574961063 | 1 | 28 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `rx_range_location::inverted` | 2 | 0.2574961063 | 0 | 2 |
| `rx_range_location::rank` | 2 | 0.2574961063 | 0 | 2 |
| `rx_interaction::rx_range_location::rx_range_location::residual` | 1 | 0.2566769577 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_volatility_state::residual` | 1 | 0.2565408409 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | 0.2118199642 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | 0.2049633806 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 3 | 0.1606041102 | 0 | 1 |
| `rx_intraday_return::rank` | 2 | 0.1594241433 | 0 | 1 |
| `rx_intraday_return::inverted` | 2 | 0.1594241433 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::residual` | 2 | 0.1546469654 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::spread` | 2 | 0.1200278569 | 1 | 1 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 1 | 0.1003080202 | 0 | 0 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::residual` | 2 | 0.09856232578 | 0 | 0 |
| `rx_interaction::rx_range_location::rx_range_location::product` | 1 | 0.08174773683 | 0 | 0 |
| `rx_interaction::rx_intraday_return::rx_range_location::product` | 4 | 0.04316456962 | 0 | 4 |
| `rx_interaction::rx_range_location::rx_volatility_state::product` | 2 | 0.04263512756 | 0 | 1 |
| `rx_interaction::rx_opening_divergence::rx_volatility_state::residual` | 4 | 0.03043589646 | 0 | 4 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::product` | 1 | 0.02814846527 | 0 | 1 |
| `rx_interaction::rx_opening_divergence::rx_volatility_state::spread` | 2 | 0.02060747943 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::product` | 2 | 0.02051768728 | 0 | 1 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2574961063 | `long_top` | 0.7923216726 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2574961063 | `short_top` | 0.7918406278 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_range_location::residual` | 1 | `close|high|low|open` | 0.2566769577 | `short_top` | 0.7969246706 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_volatility_state::residual` | 1 | `close|high|low|ret_1m` | 0.2565408409 | `short_top` | 0.7953728526 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2337353007 | `short_top` | 0.8042419267 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2337353007 | `long_top` | 0.8031536882 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | `close|high|low|open` | 0.2118199642 | `short_top` | 0.7307416045 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.2049633806 | `short_top` | 0.7250678566 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 1 | `intraday_ret_from_open|ret_1m` | 0.1606041102 | `short_top` | 0.7861924623 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 10 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1594241433 | `short_top` | 0.7879353918 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 11 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1594241433 | `long_top` | 0.7882600629 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::residual` | 1 | `high|low|open|ret_1m` | 0.1546469654 | `short_top` | 0.7913482858 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 13 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::spread` | 1 | `high|low|open|ret_1m` | 0.1200278569 | `short_top` | 0.742172382 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 14 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 5 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.1003080202 | `long_top` | 0.7790428976 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 15 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_flow_amount_volume::residual` | 5 | `amount|intraday_ret_from_open` | 0.09856232578 | `short_top` | 0.7829558072 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 16 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_flow_amount_volume::residual` | 5 | `intraday_ret_from_open|volume` | 0.09824602423 | `short_top` | 0.7808521217 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 17 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 5 | `intraday_ret_from_open` | 0.09682982321 | `short_top` | 0.7786185659 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 18 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 5 | `intraday_ret_from_open` | 0.09682982321 | `long_top` | 0.7794510148 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 19 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 5 | `intraday_ret_from_open|ret_1m` | 0.09676215461 | `short_top` | 0.7787284946 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 20 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_volatility_state::residual` | 5 | `intraday_ret_from_open|ret_1m` | 0.09655752173 | `short_top` | 0.7841803155 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 21 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::residual` | 5 | `high|intraday_ret_from_open|low|open` | 0.09616311735 | `short_top` | 0.7860321489 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 22 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_range_location::product` | 1 | `close|high|low|open` | 0.08174773683 | `long_top` | 0.777071041 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 23 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::spread` | 5 | `high|intraday_ret_from_open|low|open` | 0.07134661225 | `short_top` | 0.7206306555 | `bp_followup_priority` | `` |
| 24 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::product` | 1 | `high|low|open|ret_1m` | 0.04316456962 | `long_top` | 0.7883501449 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 25 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_volatility_state::product` | 1 | `close|high|low|ret_1m` | 0.04263512756 | `long_top` | 0.7697200352 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
