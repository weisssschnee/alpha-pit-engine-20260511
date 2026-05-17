# Phase3O6 Active Return Sanity Audit

- decision: `PASS_ACTIVE_RETURN_SANITY_AUDIT`
- book: `candidate_book_6`
- window: `2026-01-01` to `2026-05-08`
- scope: no formula, cluster, gate, or weight changes.

## Gate Lag

- gate_lag_decision: `PASS`
- gate features are `liquidity_ratio_lag1` and `limit_density_lag1`.
- checked_oos_rows: `78`
- violations: `0`

## R3 Performance Decomposition

- full_calendar_ann_compound: `1.175657`
- active_ann_compound: `3.918442`
- active_days: `38`
- active_mean_daily: `0.00634142`
- active_median_daily: `0.0070612`
- active_total_return: `0.266314`

## Active-Day Concentration

- top_1_share_of_active_arithmetic_sum: `0.154022`
- top_3_share_of_active_arithmetic_sum: `0.38279`
- top_5_share_of_active_arithmetic_sum: `0.596353`

## R3 x Limit-Density 2x2

| R3 | limit state | days | mean daily | ann compound | return sum | max dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| R3_on | limit_high | 14 | 0.00841991 | 7.27247 | 0.11787867 | -0.03073301 |
| R3_on | limit_not_high | 24 | 0.00512897 | 2.629869 | 0.12309522 | -0.02658464 |
| R3_off | limit_high | 34 | -0.00182369 | -0.368709 | -0.06200533 | -0.09118558 |
| R3_off | limit_not_high | 6 | -0.0015442 | -0.322563 | -0.0092652 | -0.01774682 |

## Interpretation

- Active-day annualization is a conditional intensity metric, not full strategy annualization.
- The formal strategy headline remains full-calendar gated performance.
- Limit density is evaluated here as an explanatory interaction, not a promoted gate change.
