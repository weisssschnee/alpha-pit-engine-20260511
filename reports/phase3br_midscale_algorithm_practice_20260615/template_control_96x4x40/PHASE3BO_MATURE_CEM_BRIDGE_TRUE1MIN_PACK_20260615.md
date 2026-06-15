# Phase3BO Mature CEM Bridge True-1min Pack 2026-06-15

Decision: `PHASE3BO_MATURE_CEM_BRIDGE_TRUE1MIN_COMPLETE_DIAGNOSTIC_ONLY`

## Plain Answer

- The old mature chain does not expose a single `cem.py` file.
- Its CEM-like logic is `rx_typed_beam` plus bandit/UCB policy routing plus family/memory guards.
- Phase3BN used true 1min data, but did not fully call that mature policy stack.
- Phase3BO fixes the route by keeping true 1min shards and adding mature-style quotas, memory, and crowding caps.

## Scope

- candidates generated: `33`
- true-1min shard panels: `4`
- sampled signal trade_times per shard: `40`
- total eval rows: `51736`
- followup priority: `1`

## Lane Counts

| lane | count | best abs aligned IC | followup |
|---|---:|---:|---:|
| `intraday_efficiency_fresh` | 3 | 0.1803127391 | 0 |
| `opening_range_location` | 12 | 0.1257407848 | 0 |
| `opening_divergence_representative` | 1 | 0.1172449353 | 0 |
| `bounded_vwap_mixed` | 2 | 0.07256752947 | 1 |
| `opening_amount_pressure_orthogonal` | 9 | 0.02620350255 | 0 |
| `range_volatility_residual` | 3 | 0.02259058128 | 0 |
| `amount_volume_flow` | 2 | 0.01099899539 | 0 |

## Top Decisions

| rank | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---:|---|---:|---|---:|---|---|
| 1 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1803127391 | `short_top` | 0.7871066788 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 2 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1794068767 | `short_top` | 0.7944426748 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 3 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1511341826 | `short_top` | 0.7896757083 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 4 | `opening_range_location` | 1 | `close|high|low` | 0.1257407848 | `short_top` | 0.7947962333 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 5 | `opening_divergence_representative` | 1 | `m1_first15_vwap_return_vs_open|ret_1m` | 0.1172449353 | `long_top` | 0.7798282374 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 6 | `opening_range_location` | 1 | `close|high|low` | 0.08853819627 | `short_top` | 0.8038488905 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 7 | `opening_range_location` | 1 | `close|high|low` | 0.08666804993 | `short_top` | 0.8039302609 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong` |
| 8 | `bounded_vwap_mixed` | 5 | `amount|m1_first5_amount|vwap` | 0.07256752947 | `long_top` | 0.7525994542 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 9 | `bounded_vwap_mixed` | 5 | `amount|m1_first5_amount|vwap` | 0.06141084383 | `long_top` | 0.7550810968 | `bo_followup_priority` | `` |
| 10 | `opening_range_location` | 5 | `amount|m1_first30_amount|m1_first30_range|open` | 0.02696860168 | `long_top` | 0.5063751453 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 11 | `opening_range_location` | 5 | `amount|m1_first15_amount|m1_first15_range|open` | 0.02667146512 | `long_top` | 0.5295759713 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 12 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.02620350255 | `long_top` | 0.7861928579 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 13 | `opening_range_location` | 5 | `amount|m1_first5_amount|m1_first5_range|open` | 0.02569797055 | `long_top` | 0.5264362436 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 14 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first5_amount|m1_first5_vol|volume` | 0.02527569827 | `long_top` | 0.7891134752 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 15 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.0246046424 | `long_top` | 0.7813694972 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 16 | `range_volatility_residual` | 5 | `high|low|open|ret_1m` | 0.02259058128 | `long_top` | 0.7544990301 | `bo_watch_or_reject` | `too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 17 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first30_amount|m1_first30_vol|volume` | 0.02175213133 | `long_top` | 0.7866132592 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 18 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first5_amount|m1_first5_vol|volume` | 0.02079041013 | `long_top` | 0.7815296085 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 19 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first30_amount|m1_first30_vol|volume` | 0.01867099242 | `long_top` | 0.7862562388 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 20 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.01820224032 | `long_top` | 0.7848575876 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |

## Mature Algorithm Files

- `src/our_system_phase2/runtime/phase3ab_launch_large_search.py`
- `src/our_system_phase2/runtime/stock_pit_large_search_supervisor.py`
- `src/our_system_phase2/runtime/stock_pit_large_search_worker.py`
- `src/our_system_phase2/services/stock_pit_forward_first_search.py`
- `src/our_system_phase2/services/stock_pit_ledger_policy.py`

## Boundary

- True `trade_time` 1min shards only.
- No old 1D default stock-PIT panel is used.
- X0/R3 remains read-only.
- Diagnostic pack, not alpha promotion proof.
