# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_rx_ucb_native_smoke`
- candidates generated: `72`
- true-1min shard panels: `6`
- sampled signal trade_times per shard: `50`
- total eval rows: `96822`
- followup priority: `1`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_rx_ucb_native` | 48 | 0.2318839218 | 1 | 32 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `rx_interaction::rx_range_location::rx_opening_amount::spread` | 3 | 0.2318839218 | 0 | 3 |
| `rx_range_location::inverted` | 3 | 0.2312620844 | 0 | 3 |
| `rx_range_location::rank` | 3 | 0.2312620844 | 0 | 3 |
| `rx_interaction::rx_range_location::rx_opening_amount::product` | 4 | 0.2245485543 | 0 | 4 |
| `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 2 | 0.2135879367 | 0 | 2 |
| `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | 0.1832020183 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | 0.1824785735 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 2 | 0.1431386196 | 0 | 1 |
| `rx_intraday_return::rank` | 2 | 0.1401787217 | 0 | 1 |
| `rx_intraday_return::inverted` | 2 | 0.1401787217 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 2 | 0.1365866264 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_range_location::spread` | 2 | 0.1039715089 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 2 | 0.08424810493 | 0 | 0 |
| `rx_interaction::rx_range_location::rx_range_location::product` | 3 | 0.06913781874 | 1 | 1 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::spread` | 1 | 0.04545075862 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::product` | 3 | 0.03447508339 | 0 | 0 |
| `rx_interaction::rx_range_location::rx_volatility_state::product` | 2 | 0.03284216731 | 0 | 0 |
| `rx_interaction::rx_opening_divergence::rx_range_location::spread` | 2 | 0.03061414754 | 0 | 2 |
| `rx_interaction::rx_opening_divergence::rx_volatility_state::spread` | 2 | 0.03050546987 | 0 | 2 |
| `rx_interaction::rx_opening_range::rx_range_location::spread` | 1 | 0.02931499329 | 0 | 0 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2318839218 | `short_top` | 0.7936191592 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2312620844 | `long_top` | 0.7865205043 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2312620844 | `short_top` | 0.7867580461 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2250349309 | `short_top` | 0.7914614546 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2245485543 | `long_top` | 0.7858389187 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2219645682 | `short_top` | 0.7969041748 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.221726401 | `long_top` | 0.7948971347 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.221726401 | `short_top` | 0.7943505221 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2182393279 | `long_top` | 0.7858127632 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 10 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2170932897 | `long_top` | 0.7937936586 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 11 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `amount|close|high|low` | 0.2135879367 | `short_top` | 0.7819308049 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2117805715 | `long_top` | 0.7843793885 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 13 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `close|high|low|volume` | 0.2092519226 | `short_top` | 0.7786408367 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 14 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1832020183 | `short_top` | 0.7014966415 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 15 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | `close|high|low|open` | 0.1824785735 | `short_top` | 0.7178824314 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 16 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 1 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.1431386196 | `short_top` | 0.7758650804 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 17 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1401787217 | `short_top` | 0.7802800652 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 18 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1401787217 | `long_top` | 0.7803136078 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 19 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 1 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.1365866264 | `long_top` | 0.7785112252 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 20 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::spread` | 1 | `high|low|open|ret_1m` | 0.1039715089 | `short_top` | 0.7264450945 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 21 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 15 | `intraday_ret_from_open` | 0.09226904334 | `short_top` | 0.7719267303 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 22 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 15 | `intraday_ret_from_open` | 0.09226904334 | `long_top` | 0.7719263022 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 23 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 30 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.09177210979 | `short_top` | 0.7709826918 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 24 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 30 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.08834930508 | `long_top` | 0.7719432997 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 25 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 30 | `amount|intraday_ret_from_open` | 0.08424810493 | `short_top` | 0.7554624366 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
