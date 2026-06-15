# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_rx_ucb_smoke`
- candidates generated: `72`
- true-1min shard panels: `3`
- sampled signal trade_times per shard: `30`
- total eval rows: `28437`
- followup priority: `1`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_rx_ucb_native` | 48 | 0.2396052927 | 1 | 39 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `rx_interaction::rx_range_location::rx_opening_amount::spread` | 3 | 0.2396052927 | 0 | 3 |
| `rx_range_location::inverted` | 3 | 0.2335275338 | 0 | 3 |
| `rx_range_location::rank` | 3 | 0.2335275338 | 0 | 3 |
| `rx_interaction::rx_range_location::rx_opening_amount::product` | 4 | 0.2266428769 | 0 | 4 |
| `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 2 | 0.2166557938 | 0 | 2 |
| `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | 0.1817700508 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | 0.1815757177 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 2 | 0.1395792855 | 0 | 1 |
| `rx_intraday_return::inverted` | 2 | 0.1311137847 | 0 | 2 |
| `rx_intraday_return::rank` | 2 | 0.1311137847 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 2 | 0.129662384 | 0 | 0 |
| `rx_interaction::rx_intraday_return::rx_range_location::spread` | 2 | 0.1019187669 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 2 | 0.07641788361 | 0 | 2 |
| `rx_interaction::rx_range_location::rx_range_location::product` | 3 | 0.07566551931 | 1 | 1 |
| `rx_interaction::rx_opening_range::rx_range_location::spread` | 1 | 0.06139791368 | 0 | 1 |
| `rx_interaction::rx_opening_divergence::rx_range_location::spread` | 2 | 0.05651802012 | 0 | 2 |
| `rx_interaction::rx_opening_divergence::rx_volatility_state::spread` | 2 | 0.05522149021 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::spread` | 1 | 0.04478274058 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_volatility_state::product` | 2 | 0.03593113351 | 0 | 0 |
| `rx_interaction::rx_intraday_return::rx_volatility_state::product` | 2 | 0.03486939345 | 0 | 0 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2396052927 | `short_top` | 0.8009306063 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2335275338 | `long_top` | 0.7991868886 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2335275338 | `short_top` | 0.7992603724 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2291527661 | `short_top` | 0.7977482203 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2289950433 | `short_top` | 0.8035297299 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2266428769 | `long_top` | 0.7986284258 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2224048892 | `long_top` | 0.8042334987 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_rx_ucb_native` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2224048892 | `short_top` | 0.8030223356 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2183806061 | `long_top` | 0.8036373671 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 10 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `amount|close|high|low` | 0.2166557938 | `short_top` | 0.7979131545 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 11 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2151350101 | `long_top` | 0.8003110998 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2136095241 | `long_top` | 0.8010979943 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 13 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `close|high|low|volume` | 0.2095560978 | `short_top` | 0.7967894994 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 14 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | `close|high|low|open` | 0.1817700508 | `short_top` | 0.7410912899 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 15 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1815757177 | `short_top` | 0.7229013014 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 16 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 15 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.1395792855 | `short_top` | 0.7850278978 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 17 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1311137847 | `long_top` | 0.7874188804 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 18 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1311137847 | `short_top` | 0.7876996178 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 19 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 5 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.129662384 | `long_top` | 0.789099597 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 20 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_range_location::spread` | 1 | `high|low|open|ret_1m` | 0.1019187669 | `short_top` | 0.7499191693 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 21 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 1 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.09186252705 | `short_top` | 0.785940042 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 22 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.08626380158 | `short_top` | 0.7891453087 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 23 | `phase3bp_true1min_rx_ucb_native` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.08626380158 | `long_top` | 0.7886304283 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 24 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 5 | `intraday_ret_from_open|m1_first30_vol|volume` | 0.08586024292 | `long_top` | 0.78711158 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75` |
| 25 | `phase3bp_true1min_rx_ucb_native` | `rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 1 | `amount|intraday_ret_from_open` | 0.07641788361 | `short_top` | 0.7810627486 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
