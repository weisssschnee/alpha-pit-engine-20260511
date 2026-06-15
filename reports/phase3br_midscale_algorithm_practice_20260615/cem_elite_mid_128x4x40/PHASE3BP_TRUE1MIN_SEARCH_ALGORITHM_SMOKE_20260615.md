# Phase3BP True-1min Search Algorithm Smoke 2026-06-15

Decision: `PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY`

## Scope

- generator mode: `true1min_cem_elite_smoke`
- candidates generated: `128`
- true-1min shard panels: `4`
- sampled signal trade_times per shard: `40`
- total eval rows: `51736`
- followup priority: `1`

## Generator Comparison

| generator | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `phase3bp_true1min_cem_elite` | 80 | 0.2205327809 | 1 | 60 |

## Lane Summary

| lane | count | best abs aligned IC | followup | future-wrong-lag |
|---|---:|---:|---:|---:|
| `cem_interaction::rx_range_location::rx_opening_amount::spread` | 8 | 0.2205327809 | 0 | 8 |
| `cem_atom::rx_range_location::rank` | 6 | 0.2178656872 | 0 | 6 |
| `cem_atom::rx_range_location::inverted` | 2 | 0.2178656872 | 0 | 2 |
| `cem_interaction::rx_range_location::rx_opening_amount::product` | 4 | 0.2140891183 | 0 | 4 |
| `cem_interaction::rx_range_location::rx_flow_amount_volume::spread` | 8 | 0.1970152621 | 0 | 8 |
| `cem_interaction::rx_range_location::rx_opening_amount::signed_state` | 3 | 0.1806470249 | 0 | 3 |
| `cem_interaction::rx_range_location::rx_volatility_state::spread` | 4 | 0.1753233905 | 0 | 4 |
| `cem_interaction::rx_range_location::rx_range_location::spread` | 4 | 0.1749935355 | 0 | 4 |
| `cem_interaction::rx_intraday_return::rx_opening_amount::spread` | 4 | 0.1425862867 | 0 | 1 |
| `cem_atom::rx_intraday_return::rank` | 3 | 0.1404750905 | 1 | 1 |
| `cem_atom::rx_intraday_return::inverted` | 2 | 0.1404750905 | 0 | 1 |
| `cem_interaction::rx_intraday_return::rx_opening_amount::product` | 4 | 0.1312842453 | 0 | 1 |
| `cem_interaction::rx_intraday_return::rx_range_location::spread` | 8 | 0.1108368508 | 0 | 6 |
| `cem_interaction::rx_intraday_return::rx_flow_amount_volume::spread` | 2 | 0.08294849091 | 0 | 0 |
| `cem_interaction::rx_intraday_return::rx_opening_amount::signed_state` | 3 | 0.07931596492 | 0 | 0 |
| `cem_interaction::rx_range_location::rx_range_location::product` | 1 | 0.07235596055 | 0 | 0 |
| `cem_interaction::rx_opening_amount::rx_range_location::spread` | 3 | 0.05866342276 | 0 | 3 |
| `cem_atom::rx_volatility_state::rank` | 1 | 0.05636772281 | 0 | 1 |
| `cem_interaction::rx_opening_amount::rx_range_location::product` | 3 | 0.04980295353 | 0 | 3 |
| `cem_interaction::rx_intraday_return::rx_volatility_state::spread` | 1 | 0.04817052364 | 0 | 0 |

## Top Decisions

| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---|---:|---|---:|---|---:|---|---|
| 1 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2205327809 | `short_top` | 0.7891639417 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 2 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2192557261 | `short_top` | 0.7906418451 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 3 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2184429213 | `short_top` | 0.791568991 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 4 | `phase3bp_true1min_cem_elite` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2178656872 | `short_top` | 0.7835046688 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `phase3bp_true1min_cem_elite` | `cem_atom::rx_range_location::inverted` | 1 | `close|high|low` | 0.2178656872 | `long_top` | 0.7822972076 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 6 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2175969885 | `short_top` | 0.7869372939 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 7 | `phase3bp_true1min_cem_elite` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.215048724 | `short_top` | 0.7819060362 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2140891183 | `long_top` | 0.7807579969 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 9 | `phase3bp_true1min_cem_elite` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2114489757 | `short_top` | 0.7913246849 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 10 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first30_vol|volume` | 0.2101501227 | `short_top` | 0.7933770951 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 11 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2096864203 | `short_top` | 0.7947092653 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 12 | `phase3bp_true1min_cem_elite` | `cem_atom::rx_range_location::rank` | 1 | `close|high|low` | 0.2089219328 | `short_top` | 0.7908208988 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 13 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2086609924 | `short_top` | 0.7941979924 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 14 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::spread` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2076829346 | `short_top` | 0.7948023866 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 15 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first15_vol|volume` | 0.2072438784 | `long_top` | 0.7820819562 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 16 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first5_vol|volume` | 0.2070769035 | `long_top` | 0.7817820618 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 17 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::product` | 1 | `close|high|low|m1_first5_vol|volume` | 0.1975846569 | `long_top` | 0.7907195117 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 18 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `amount|close|high|low` | 0.1970152621 | `short_top` | 0.7885456042 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 19 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `amount|close|high|low` | 0.194068437 | `short_top` | 0.7873485588 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 20 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_flow_amount_volume::spread` | 1 | `close|high|low|volume` | 0.1917295408 | `short_top` | 0.7837943763 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 21 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::signed_state` | 1 | `close|high|low|m1_first30_vol|volume` | 0.1806470249 | `long_top` | 0.7919306634 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 22 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_volatility_state::spread` | 1 | `close|high|low|ret_1m` | 0.1753233905 | `short_top` | 0.7363533556 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 23 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::signed_state` | 1 | `close|high|low|m1_first15_vol|volume` | 0.175153297 | `long_top` | 0.792291243 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 24 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_range_location::spread` | 1 | `close|high|low|open` | 0.1749935355 | `short_top` | 0.7476990134 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 25 | `phase3bp_true1min_cem_elite` | `cem_interaction::rx_range_location::rx_opening_amount::signed_state` | 1 | `close|high|low|m1_first5_vol|volume` | 0.1743315196 | `long_top` | 0.7909916054 | `bp_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |

## Interpretation

- This tests the search algorithm, not production alpha.
- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.
- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.
- X0/R3 remains read-only.
