# Phase3AB Large Daily Search Aggregate

- generated_at: `2026-05-29T18:25:47+00:00`
- version: `phase3ab-large-search-aggregate-v1-2026-05-30`
- total_roots: `6`
- shard_status: completed `46`, failed `2`, partial `0`
- recovered_failed_shards: `2`
- evaluation_rows: `16932`
- unique_expr_count: `14468`
- duplicate_eval_rows: `2464`

## Interpretation

- This is a Stage1/validation aggregate, not a promotion-grade alpha decision.
- Failed shards are retained as infrastructure faults when their failure occurs after candidate generation.
- A failed shard can also be marked recovered when a later retry root contains a completed output for the same run/shard.
- X0/R3 official shadow remains read-only; this report does not modify official alpha objects.

## Top Deduped Candidates

| rank | candidate_id | run | source_lane | sortino | return | expr_hash |
|---:|---|---|---|---:|---:|---|
| 1 | `stockpit-ff-a2b13a0dbbec` | company_forward | turnover_ratio_x_momentum_curve | 63.882001 | 0.003533 | `484fe78c1bb617b8` |
| 2 | `stockpit-ff-08fe1d506822` | company_forward | volume_ratio_x_momentum_curve | 41.319924 | 0.003616 | `5300fdcfa9b49791` |
| 3 | `stockpit-ff-71e0239e38de` | company_forward2 | turnover_ratio_x_momentum_curve | 11.601990 | 0.003239 | `f2878c18d5cc4df2` |
| 4 | `stockpit-ff-f14307093f3c` | company_forward2 | turnover_ratio_x_momentum_curve | 11.567371 | 0.004505 | `e1abdc95261b225e` |
| 5 | `stockpit-ff-771dce7dc1df` | company_forward2 | volume_ratio_x_momentum_curve | 11.272573 | 0.003767 | `9359a99684cafee6` |
| 6 | `stockpit-ff-c965d3b56b9c` | company_forward2 | volume_ratio_x_momentum_curve | 10.607141 | 0.003138 | `2d479cd9561dd792` |
| 7 | `stockpit-ff-bce63bcc912a` | company_forward2 | volume_ratio_x_momentum_curve | 10.320894 | 0.003287 | `eee604cf9e3925c3` |
| 8 | `stockpit-ff-35230d6429f3` | company_forward2 | turnover_ratio_x_momentum_curve | 10.172600 | 0.003435 | `3eac9ce7f4311c2e` |
| 9 | `stockpit-ff-777ab9e072aa` | company_forward2 | turnover_ratio_x_momentum_curve | 9.992871 | 0.003582 | `8673bf3b00d75e0c` |
| 10 | `stockpit-ff-ea303ea70696` | company_forward2 | volume_ratio_x_momentum_curve | 9.852716 | 0.003908 | `1665c2367651dd90` |
| 11 | `stockpit-ff-8ee404186a9d` | local_forward | volume_ratio_x_momentum_curve | 9.443960 | 0.003834 | `69705df78a47038a` |
| 12 | `stockpit-ff-2b20d34a88e3` | company_forward2 | turnover_ratio_x_momentum_curve | 9.299629 | 0.004066 | `9140f857fc9deea6` |
| 13 | `stockpit-ff-f00820e82553` | company_forward2 | turnover_ratio_x_momentum_curve | 9.094064 | 0.004417 | `8ed72d5b0e0ba4a8` |
| 14 | `stockpit-ff-935f767640f4` | local_forward | turnover_ratio_x_momentum_curve | 9.057717 | 0.003901 | `c28173c9df73505e` |
| 15 | `stockpit-ff-73f509a63a9d` | company_forward2 | volume_ratio_x_momentum_curve | 8.854983 | 0.003982 | `a82655d3c65e25c0` |
| 16 | `stockpit-ff-a5a5c0b43b0c` | company_forward2 | turnover_ratio_x_momentum_curve | 8.827205 | 0.003961 | `606aeee5118e0e2b` |
| 17 | `stockpit-ff-e09287e69612` | company_forward2 | turnover_ratio_x_momentum_curve | 8.692908 | 0.003876 | `38292732f7a8fb65` |
| 18 | `stockpit-ff-606f4b69571c` | company_forward2 | volume_ratio_x_momentum_curve | 8.629533 | 0.004210 | `b267db2301841650` |
| 19 | `stockpit-ff-4c9648437531` | company_forward2 | volume_ratio_x_momentum_curve | 8.527017 | 0.004050 | `82be1cc905a59ff6` |
| 20 | `stockpit-ff-f520267d8d03` | company_forward2 | amount_ratio_x_momentum_curve | 8.458213 | 0.002452 | `f9a2eb2c456771e4` |

## Outputs

- top candidates: `reports\phase3ab_large_search_aggregate_retry_20260530\phase3ab_top_candidates.csv`
- source attribution: `reports\phase3ab_large_search_aggregate_retry_20260530\phase3ab_source_attribution.csv`
- shard status: `reports\phase3ab_large_search_aggregate_retry_20260530\phase3ab_shard_status.csv`
- machine-readable report: `reports\phase3ab_large_search_aggregate_retry_20260530\phase3ab_large_search_aggregate.json`

## Failed Shards

- `company_forward2 / supervisor-shard_10_of_16`: return_code=1, error tail recorded in CSV.
- `company_forward2 / supervisor-shard_12_of_16`: return_code=1, error tail recorded in CSV.

## Recovered Failed Shards

- `company_forward2 / supervisor-shard_10_of_16`: original_root=`G:\Project_V7_Rotation\runtime\phase3ab_company_forward2_20260529`, retry_root=`G:\Project_V7_Rotation\runtime\phase3ab_company_forward2_retry_s10_20260530`.
- `company_forward2 / supervisor-shard_12_of_16`: original_root=`G:\Project_V7_Rotation\runtime\phase3ab_company_forward2_20260529`, retry_root=`G:\Project_V7_Rotation\runtime\phase3ab_company_forward2_retry_s12_20260530`.
