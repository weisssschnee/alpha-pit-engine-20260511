# Phase3O2 Regime-Gated Portfolio Replay

- decision: `PASS_REGIME_GATED_FULL_CALENDAR_CANDIDATE`
- book: `candidate_book_6`
- train_window: `2025-07-01` to `2025-12-31`
- oos_window: `2026-01-01` to `2026-05-08`

## OOS Full-Calendar Gates

| gate | active ratio | full ann | sharpe | sortino | max dd | active ann | inactive ann | switches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| R3_liquidity_low | 0.487179 | 1.175657 | 4.547115 | 6.085253 | -0.03442312 | 3.918442 | -0.361992 | 3 |
| R5_vol_or_trendlow_or_liqlow | 0.666667 | 1.12819 | 3.827856 | 7.265461 | -0.04184402 | 2.102041 | -0.46483 | 8 |
| R6_at_least_2_of_vol_trend_liq | 0.551282 | 0.983379 | 3.842269 | 6.113946 | -0.04667989 | 2.458477 | -0.264002 | 4 |
| R1_volatility_high | 0.602564 | 0.936759 | 3.541104 | 6.113221 | -0.04994616 | 1.992347 | -0.248754 | 3 |
| R7_weighted_train_score_gate | 0.602564 | 0.936759 | 3.541104 | 6.113221 | -0.04994616 | 1.992347 | -0.248754 | 3 |
| R0_no_gate | 1.0 | 0.729231 | 2.219926 | 4.391617 | -0.10425684 | 0.729231 | None | 0 |
| R2_trend_low | 0.448718 | 0.590611 | 2.812692 | 4.087046 | -0.0472475 | 1.809913 | 0.163962 | 10 |
| R4_limit_density_high | 0.615385 | 0.197755 | 0.88946 | 1.443628 | -0.09227455 | 0.340663 | 1.597015 | 8 |
| F1_breadth_low_failed_control | 0.371795 | -0.011777 | -0.083235 | -0.090794 | -0.08071471 | -0.031363 | 1.435238 | 38 |
| F2_trend_high_failed_control | 0.307692 | -0.011854 | -0.082592 | -0.088514 | -0.06133498 | -0.038015 | 1.24314 | 10 |
| F3_liquidity_high_failed_control | 0.205128 | -0.060578 | -0.503754 | -0.506358 | -0.0653037 | -0.262721 | 1.153729 | 2 |

## Random Placebo Summary

| gate | true full ann | random mean | random p95 | true > random p95 |
| --- | ---: | ---: | ---: | --- |
| R1_volatility_high | 0.936759 | 0.415551 | 1.009145 | False |
| R2_trend_low | 0.590611 | 0.310146 | 0.916849 | False |
| R3_liquidity_low | 1.175657 | 0.355316 | 0.868295 | True |
| R5_vol_or_trendlow_or_liqlow | 1.12819 | 0.434331 | 0.966584 | True |
| R6_at_least_2_of_vol_trend_liq | 0.983379 | 0.386968 | 0.912343 | True |
| R7_weighted_train_score_gate | 0.936759 | 0.415551 | 1.009145 | False |

## Boundaries

- Bucket thresholds are fitted only on 2025H2 and applied to 2026.
- Full-calendar gated return is zero on inactive days; bucket annualization is not used as the headline.
- Placebo tests are diagnostic; this is still daily proxy evidence, not execution proof.
