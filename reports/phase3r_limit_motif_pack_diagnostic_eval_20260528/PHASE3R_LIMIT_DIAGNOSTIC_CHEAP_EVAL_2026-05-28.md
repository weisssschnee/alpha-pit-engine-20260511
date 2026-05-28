# Phase3R Limit Diagnostic Cheap Evaluation

- decision: `HOLD_DIRECT_LIMIT_DIAGNOSTIC_NO_SMOKE_PASS`
- evaluated_count: `45`
- unsupported_count: `0`
- passed_smoke_count: `0`
- promoted_to_full_history_review_count: `0`
- screening_mode: `recent_1_quarter_multi_cycle_smoke`
- signal_clock: `after_open`
- execution_policy: `signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close`
- boundary: diagnostic only; no X0/R3 changes.

## By Role

| role | evaluated | pass smoke | promoted | best rank IC | best long sortino | mean turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| event_factor | 24 | 0 | 0 | 0.016198 | 2.473886 | 0.071099 |
| interaction_factor | 21 | 0 | 0 | 0.038908 | 4.55783 | 0.068692 |

## Top Candidate

- candidate_id: `limit_diag_interaction_factor_016`
- role: `interaction_factor`
- expression: `CSRank(Mul(ZScore(Mean($amount,8)),ZScore(Mean($high_board_rank,2))))`
- mean_window_rank_ic: `0.003655`
- mean_window_long_sortino: `4.55783`
- smoke_flags: `weak_mean_rank_ic_below_0_01|insufficient_quarterly_windows`

## Interpretation

- A smoke pass would still require strict replay and leakage/tradability audit.
- No result here is eligible to modify the locked X0/R3 shadow object.
