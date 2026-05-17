# Phase3R Limit Diagnostic Cheap Evaluation

- decision: `HOLD_DIRECT_LIMIT_DIAGNOSTIC_NO_SMOKE_PASS`
- evaluated_count: `48`
- unsupported_count: `0`
- passed_smoke_count: `0`
- promoted_to_full_history_review_count: `0`
- screening_mode: `recent_2_quarter_multi_cycle_smoke`
- signal_clock: `after_open`
- execution_policy: `signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close`
- boundary: diagnostic only; no X0/R3 changes.

## By Role

| role | evaluated | pass smoke | promoted | best rank IC | best long sortino | mean turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| event_factor | 24 | 0 | 0 | 0.010892 | 0.425403 | 0.08178 |
| interaction_factor | 24 | 0 | 0 | -0.001329 | 1.922721 | 0.084362 |

## Top Candidate

- candidate_id: `limit_diag_interaction_factor_008`
- role: `interaction_factor`
- expression: `CSRank(Mul(ZScore(Mean(Abs(Delta($close,1)),10)),ZScore(Mean($limit_up_event,5))))`
- mean_window_rank_ic: `-0.004146`
- mean_window_long_sortino: `1.922721`
- smoke_flags: `weak_mean_rank_ic_below_0_01|non_positive_recent_mean_rank_ic|insufficient_quarterly_windows`

## Interpretation

- A smoke pass would still require strict replay and leakage/tradability audit.
- No result here is eligible to modify the locked X0/R3 shadow object.
