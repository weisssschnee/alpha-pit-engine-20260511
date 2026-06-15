# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_hybrid_rx_cem_smoke`
- candidates generated: `96`
- true-1min shard panels: `3`
- sampled signal trade_times per shard: `30`
- total eval rows: `28437`
- followup priority: `0`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_hybrid_rx_cem` | 48 | 0.2396052927 | 0 | 46 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | 0.2396052927 | 0 | 1 |
| `rx_range_location::inverted` | 2 | 0.2335275338 | 0 | 2 |
| `rx_range_location::rank` | 2 | 0.2335275338 | 0 | 2 |
| `cem_atom::rx_range_location::rank` | 3 | 0.2298671097 | 0 | 3 |
| `cem_atom::rx_range_location::inverted` | 2 | 0.2284179933 | 0 | 2 |
| `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | 0.2266428769 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | 0.2166557938 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | 0.1817700508 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | 0.1815757177 | 0 | 1 |
| `cem_interaction::rx_range_location::rx_volatility_state::spread` | 5 | 0.1783362549 | 0 | 5 |
| `rx_intraday_return::inverted` | 2 | 0.1311137847 | 0 | 2 |
| `rx_intraday_return::rank` | 2 | 0.1311137847 | 0 | 2 |
| `cem_atom::rx_intraday_return::inverted` | 3 | 0.1168952644 | 0 | 3 |
| `cem_interaction::rx_intraday_return::rx_range_location::spread` | 6 | 0.1093332146 | 0 | 6 |
| `cem_atom::rx_intraday_return::rank` | 2 | 0.1092232361 | 0 | 2 |
| `rx_interaction::rx_intraday_return::rx_range_location::spread` | 3 | 0.1019187669 | 0 | 3 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::spread` | 1 | 0.09186252705 | 0 | 1 |
| `rx_interaction::rx_intraday_return::rx_opening_amount::product` | 1 | 0.08586024292 | 0 | 0 |
| `rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 1 | 0.07641788361 | 0 | 1 |
| `rx_interaction::rx_range_location::rx_range_location::product` | 1 | 0.07566551931 | 0 | 0 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2396052927 | `short_top` | 0.8009306063 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_hybrid_rx_cem` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2335275338 | `long_top` | 0.7991868886 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_hybrid_rx_cem` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2335275338 | `short_top` | 0.7992603724 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2298671097 | `short_top` | 0.7998504861 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2284179933 | `short_top` | 0.8059880106 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_range_location::inverted` | 1 | `close|high|low` | 0.2284179933 | `long_top` | 0.8061335384 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2266428769 | `long_top` | 0.7986284258 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2252620836 | `short_top` | 0.8067280224 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_range_location::inverted` | 1 | `close|high|low` | 0.2252620836 | `long_top` | 0.8072625335 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 10 | `phase3bp_true1min_hybrid_rx_cem` | `rx_range_location::inverted` | 1 | `close|high|low` | 0.2224048892 | `long_top` | 0.8042334987 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 11 | `phase3bp_true1min_hybrid_rx_cem` | `rx_range_location::rank` | 1 | `close|high|low` | 0.2224048892 | `short_top` | 0.8030223356 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_hybrid_rx_cem` | `rx_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `amount|close|high|low` | 0.2166557938 | `short_top` | 0.7979131545 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 13 | `phase3bp_true1min_hybrid_rx_cem` | `rx_interaction::rx_range_location::rx_range_location::spread` | 1 | `close|high|low|open` | 0.1817700508 | `short_top` | 0.7410912899 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 14 | `phase3bp_true1min_hybrid_rx_cem` | `rx_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1815757177 | `short_top` | 0.7229013014 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 15 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1783362549 | `short_top` | 0.7277270405 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 16 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1779817307 | `short_top` | 0.7274829939 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 17 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1770936746 | `short_top` | 0.7387736229 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 18 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1764210236 | `short_top` | 0.7291987794 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 19 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1705795438 | `short_top` | 0.7358951525 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 20 | `phase3bp_true1min_hybrid_rx_cem` | `rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1311137847 | `long_top` | 0.7874188804 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 21 | `phase3bp_true1min_hybrid_rx_cem` | `rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1311137847 | `short_top` | 0.7876996178 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 22 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1168952644 | `long_top` | 0.785135689 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 23 | `phase3bp_true1min_hybrid_rx_cem` | `cem_interaction::rx_intraday_return::rx_range_location::spread` | 1 | `high|low|open|ret_1m` | 0.1093332146 | `short_top` | 0.7506588751 | `bp_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 24 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_intraday_return::inverted` | 1 | `intraday_ret_from_open` | 0.1092232361 | `long_top` | 0.7815333822 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 25 | `phase3bp_true1min_hybrid_rx_cem` | `cem_atom::rx_intraday_return::rank` | 1 | `intraday_ret_from_open` | 0.1092232361 | `short_top` | 0.7805932022 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
