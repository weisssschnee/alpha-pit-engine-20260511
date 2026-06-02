# Phase3AB Candidate Deep Validation

- version: `phase3ab-candidate-deep-validation-v1-2026-05-30`
- input: `reports\phase3ab_large_search_aggregate_retry_20260530\phase3ab_top_candidates.csv`
- dataset: `G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet`
- selected_candidates: `80`
- succeeded: `80`
- failed: `0`

## Interpretation

- This is a no-search deep validation audit for Stage1 Phase3AB candidates.
- It is not a promotion decision and does not modify X0/R3.
- Candidates that look strong here still require frozen forward/shadow handling before promotion.

## Top Deep-Validated Candidates

| rank | candidate_id | lane | score | oos ann | oos sortino | p90 turnover | top3 share | expr_hash |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | `stockpit-ff-b92e5c7f2608` | volume_ratio_x_momentum_curve | 10.074416 | 0.197154 | 0.775457 | 0.375411 | 0.187619 | `e6252f08e69ad8d6` |
| 2 | `stockpit-ff-3ee9c3a1f8f5` | turnover_ratio_x_momentum_curve | 9.614132 | 0.215528 | 0.839301 | 0.373127 | 0.188385 | `fffd416185fdebbc` |
| 3 | `stockpit-ff-a2b13a0dbbec` | turnover_ratio_x_momentum_curve | 9.56574 | 0.316351 | 1.270719 | 0.385669 | 0.168525 | `484fe78c1bb617b8` |
| 4 | `stockpit-ff-08fe1d506822` | volume_ratio_x_momentum_curve | 9.298104 | 0.349244 | 1.40215 | 0.385224 | 0.171473 | `5300fdcfa9b49791` |
| 5 | `stockpit-ff-2f4d9c19e4cb` | volume_ratio_x_momentum_curve | 8.779476 | 0.493515 | 1.941671 | 0.362132 | 0.193736 | `ba657e86b0d4e718` |
| 6 | `stockpit-ff-fc20dd3d038f` | turnover_ratio_x_momentum_curve | 8.512672 | 0.441617 | 1.93783 | 0.402649 | 0.198635 | `b2a3887020490f67` |
| 7 | `stockpit-ff-0a58d92200b7` | volume_ratio_x_momentum_curve | 8.481405 | 0.469956 | 1.900531 | 0.378619 | 0.207006 | `8d3101cda2e69852` |
| 8 | `stockpit-ff-dace82c379f7` | turnover_ratio_x_momentum_curve | 8.469799 | 0.224498 | 0.935491 | 0.410248 | 0.198251 | `68ec56b58252cf8f` |
| 9 | `stockpit-ff-9271529e5176` | volume_ratio_x_momentum_curve | 8.39059 | 0.412149 | 1.824861 | 0.396224 | 0.199151 | `8af2c4ae5230c9bd` |
| 10 | `stockpit-ff-51bf0b160b63` | turnover_ratio_x_momentum_curve | 8.366352 | 0.491699 | 1.941533 | 0.366311 | 0.193532 | `f23397bd843addc8` |
| 11 | `stockpit-ff-599a79d51d68` | volume_ratio_x_momentum_curve | 8.220873 | 0.621905 | 2.273037 | 0.375366 | 0.197287 | `e29c71b91ad724fd` |
| 12 | `stockpit-ff-a5a5c0b43b0c` | turnover_ratio_x_momentum_curve | 8.013809 | 0.443181 | 1.743925 | 0.344122 | 0.202898 | `606aeee5118e0e2b` |
| 13 | `stockpit-ff-4c9648437531` | volume_ratio_x_momentum_curve | 7.882342 | 0.470419 | 1.80605 | 0.352027 | 0.201942 | `82be1cc905a59ff6` |
| 14 | `stockpit-ff-2b20d34a88e3` | turnover_ratio_x_momentum_curve | 7.754061 | 0.41368 | 1.699488 | 0.367582 | 0.200561 | `9140f857fc9deea6` |
| 15 | `stockpit-ff-49c98f0c516d` | turnover_ratio_x_momentum_curve | 7.749866 | 0.38244 | 1.44344 | 0.438352 | 0.182258 | `1dd1be3d11cd0963` |
| 16 | `stockpit-ff-e09287e69612` | turnover_ratio_x_momentum_curve | 7.739117 | 0.431758 | 1.742374 | 0.383974 | 0.202406 | `38292732f7a8fb65` |
| 17 | `stockpit-ff-73f509a63a9d` | volume_ratio_x_momentum_curve | 7.737314 | 0.397856 | 1.633311 | 0.366787 | 0.200539 | `a82655d3c65e25c0` |
| 18 | `stockpit-ff-ea303ea70696` | volume_ratio_x_momentum_curve | 7.522126 | 0.436465 | 1.733656 | 0.392362 | 0.204169 | `1665c2367651dd90` |
| 19 | `stockpit-ff-cd79110ba257` | turnover_ratio_x_momentum_curve | 7.50299 | 0.264821 | 1.209637 | 0.411552 | 0.204204 | `675913c6ee6674cc` |
| 20 | `stockpit-ff-935f767640f4` | turnover_ratio_x_momentum_curve | 7.393995 | 0.271925 | 1.037624 | 0.52971 | 0.189063 | `c28173c9df73505e` |

## Outputs

- scoreboard: `reports\phase3ab_candidate_deep_validation_20260530_top80\phase3ab_deep_scoreboard.csv`
- window metrics: `reports\phase3ab_candidate_deep_validation_20260530_top80\phase3ab_deep_window_metrics.csv`
- cost stress: `reports\phase3ab_candidate_deep_validation_20260530_top80\phase3ab_deep_cost_stress.csv`
- failures: `reports\phase3ab_candidate_deep_validation_20260530_top80\phase3ab_deep_failures.csv`
- json: `reports\phase3ab_candidate_deep_validation_20260530_top80\phase3ab_candidate_deep_validation.json`
