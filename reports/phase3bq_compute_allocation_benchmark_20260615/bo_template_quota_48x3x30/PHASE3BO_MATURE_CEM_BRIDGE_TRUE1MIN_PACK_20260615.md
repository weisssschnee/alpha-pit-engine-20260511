# Phase3BO Mature CEM Bridge True-1min Pack 2026-06-15

Decision: `PHASE3BO_MATURE_CEM_BRIDGE_TRUE1MIN_COMPLETE_DIAGNOSTIC_ONLY`

## Plain Answer

- The old mature chain does not expose a single `cem.py` file.
- Its CEM-like logic is `rx_typed_beam` plus bandit/UCB policy routing plus family/memory guards.
- Phase3BN used true 1min data, but did not fully call that mature policy stack.
- Phase3BO fixes the route by keeping true 1min shards and adding mature-style quotas, memory, and crowding caps.

## Scope

- candidates generated: `26`
- true-1min shard panels: `3`
- sampled signal trade_times per shard: `30`
- total eval rows: `28437`
- followup priority: `1`

## Lane Counts

| lane | count | best abs aligned IC | followup |
|---|---:|---:|---:|
| `intraday_efficiency_fresh` | 3 | 0.1964292876 | 0 |
| `opening_divergence_representative` | 1 | 0.1123796312 | 0 |
| `bounded_vwap_mixed` | 2 | 0.07100017169 | 1 |
| `opening_amount_pressure_orthogonal` | 7 | 0.02570580173 | 0 |
| `opening_range_location` | 7 | 0.02389944898 | 0 |
| `range_volatility_residual` | 3 | 0.02290073064 | 0 |
| `amount_volume_flow` | 3 | 0.01903501111 | 0 |

## Top Decisions

| rank | lane | h | fields | abs IC | direction | turnover | decision | blockers |
|---:|---|---:|---|---:|---|---:|---|---|
| 1 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1964292876 | `short_top` | 0.8042617001 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 2 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1757192929 | `short_top` | 0.8017761605 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 3 | `intraday_efficiency_fresh` | 1 | `intraday_ret_from_open|ret_1m` | 0.1500979565 | `short_top` | 0.7891157883 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 4 | `opening_divergence_representative` | 1 | `m1_first15_vwap_return_vs_open|ret_1m` | 0.1123796312 | `long_top` | 0.7736582842 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 5 | `bounded_vwap_mixed` | 5 | `amount|m1_first5_amount|vwap` | 0.07100017169 | `long_top` | 0.7627801661 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong` |
| 6 | `bounded_vwap_mixed` | 5 | `amount|m1_first5_amount|vwap` | 0.06353036917 | `long_top` | 0.7641448575 | `bo_followup_priority` | `` |
| 7 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.02570580173 | `long_top` | 0.784082087 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|weak_dense_primary_abs_ic` |
| 8 | `opening_range_location` | 30 | `amount|m1_first15_amount|m1_first15_range|open` | 0.02389944898 | `short_top` | 0.5990803859 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 9 | `opening_range_location` | 30 | `amount|m1_first5_amount|m1_first5_range|open` | 0.02384672229 | `short_top` | 0.6065348764 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 10 | `opening_amount_pressure_orthogonal` | 15 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.02333863863 | `long_top` | 0.7928451322 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|weak_dense_primary_abs_ic` |
| 11 | `opening_amount_pressure_orthogonal` | 30 | `amount|m1_first5_amount|m1_first5_vol|volume` | 0.02327580109 | `long_top` | 0.7825272341 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|weak_dense_primary_abs_ic` |
| 12 | `opening_range_location` | 30 | `amount|m1_first15_amount|m1_first15_range|open` | 0.02321606674 | `short_top` | 0.5297486261 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 13 | `range_volatility_residual` | 1 | `high|low|open|ret_1m` | 0.02290073064 | `short_top` | 0.752037865 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong|weak_dense_primary_abs_ic` |
| 14 | `opening_amount_pressure_orthogonal` | 15 | `amount|m1_first5_amount|m1_first5_vol|volume` | 0.02236878421 | `long_top` | 0.7947161072 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 15 | `opening_range_location` | 30 | `amount|m1_first5_amount|m1_first5_range|open` | 0.02141166562 | `short_top` | 0.5480794589 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 16 | `opening_amount_pressure_orthogonal` | 1 | `amount|m1_first15_amount|m1_first15_vol|volume` | 0.02111983287 | `long_top` | 0.7881563642 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 17 | `opening_amount_pressure_orthogonal` | 1 | `amount|m1_first30_amount|m1_first30_vol|volume` | 0.02050275574 | `long_top` | 0.7943210564 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|weak_dense_primary_abs_ic` |
| 18 | `opening_amount_pressure_orthogonal` | 15 | `amount|m1_first5_amount|m1_first5_vol|volume` | 0.01936024835 | `long_top` | 0.7918573009 | `bo_watch_or_reject` | `signal_corr_abs_ge_0.75|future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 19 | `range_volatility_residual` | 1 | `high|low|open|ret_1m` | 0.01911770915 | `short_top` | 0.7503581943 | `bo_watch_or_reject` | `future_signal_wrong_lag_too_strong|too_few_positive_horizons|weak_dense_primary_abs_ic` |
| 20 | `amount_volume_flow` | 30 | `amount|volume` | 0.01903501111 | `short_top` | 0.7396970772 | `bo_watch_or_reject` | `too_few_positive_horizons|weak_dense_primary_abs_ic` |

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
