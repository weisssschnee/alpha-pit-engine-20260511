# Phase3O Regime-Conditioned OOS Audit

- decision: `PASS_RECENT_REGIME_CONDITIONED_OOS`
- scope: `locked_daily_returns_lagged_market_regime_no_formula_tuning`
- dataset: `G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet`
- daily_returns: `reports\phase3n_long_history_locked_validation_20260517\phase3n_daily_returns.csv`

## Interpretation

- This audit tests whether regime buckets selected on one window remain useful on the next window.
- The 2025H2 -> 2026 split is the relevant recent-regime OOS test.
- The 2020-2024 -> 2025H2 split tests whether the same book had an earlier stable regime rule.

## Unconditional Splits

| split | book | train ann | train sharpe | oos ann | oos sharpe | oos dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pre2025_train_to_2025h2_oos | candidate_book_6 | -0.255533 | -1.401538 | 0.309629 | 1.06907 | -0.15009484 |
| pre2025_train_to_2025h2_oos | research_pool_9 | -0.271728 | -1.444932 | 0.333555 | 1.092247 | -0.15940497 |
| pre2025_train_to_2025h2_oos | oracle_diagnostic_3 | -0.159563 | -0.907983 | 0.422898 | 1.571394 | -0.11900311 |
| 2025h2_train_to_2026_oos | candidate_book_6 | 0.309629 | 1.06907 | 0.729231 | 2.219926 | -0.10425684 |
| 2025h2_train_to_2026_oos | research_pool_9 | 0.333555 | 1.092247 | 0.846958 | 2.302436 | -0.11058904 |
| 2025h2_train_to_2026_oos | oracle_diagnostic_3 | 0.422898 | 1.571394 | 0.894385 | 2.759306 | -0.07887692 |

## Candidate Book: 2025H2-Selected Regimes Tested on 2026

| axis | bucket | train days | train ann | train sharpe | oos days | oos ann | oos sharpe | oos dd |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| limit_density | limit_density_low | 42 | 0.012025 | 0.047692 | 15 | 4.815346 | 6.890654 | -0.02658464 |
| liquidity | liquidity_low | 42 | 0.518517 | 1.839216 | 38 | 3.918442 | 6.815622 | -0.03442312 |
| volatility | volatility_high | 42 | 1.338667 | 3.073692 | 47 | 1.992347 | 4.638562 | -0.04994616 |
| trend | trend_low | 42 | 0.592557 | 1.7328 | 35 | 1.809913 | 4.282295 | -0.0472475 |
| limit_density | limit_density_high | 42 | 0.863031 | 2.355646 | 48 | 0.340663 | 1.134958 | -0.09227455 |
| limit_density | limit_density_mid | 42 | 0.190862 | 0.727845 | 15 | 0.156777 | 0.836347 | -0.02085725 |
| breadth | breadth_low | 42 | 1.766878 | 3.853313 | 29 | -0.031363 | -0.136509 | -0.08071471 |
| trend | trend_high | 42 | 0.822099 | 2.466047 | 24 | -0.038015 | -0.148899 | -0.06133498 |

## Boundaries

- Regime buckets use lagged market aggregates; no formula or book weights were changed.
- Bucket thresholds for quantile axes are fitted on the train window only, then applied to OOS.
- This is still daily proxy evidence, not execution or live proof.
