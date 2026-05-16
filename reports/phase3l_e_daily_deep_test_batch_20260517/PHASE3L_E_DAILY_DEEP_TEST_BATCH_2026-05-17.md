# Phase3L-E Daily Deep Test Batch

- generated_at: 2026-05-17T01:33:17+08:00
- decision: `HOLD_PHASE3L_E_DAILY_DEEP_TEST_ATTRITION`
- selected_test_count: 64
- strict_row_count: 64
- cluster_count: 12
- pass_ex_regime_count: 3
- blocked_regime_count: 12

## Interpretation

- This batch validates supported daily tests only: full-window replay, sign-flip, and low-order ablation.
- Regime bucket replay is not available in this runner and remains a blocker before KEEP/promotion.
- Passing this batch does not imply production readiness or minute execution capacity.

## Cluster Results

| cluster | decision | full_score | low_order_best | margin | sign_flip_passed | window_ratio | daily_blockers | promotion_blockers |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- | --- |
| cluster_008 | HOLD_DAILY_DEEP_TEST | 1.47509 | 1.494432 | -0.019342 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| cluster_014 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.229064 | 1.221211 | 0.007853 | False | 0.5 |  | regime_bucket_replay_not_run |
| cluster_017 | HOLD_DAILY_DEEP_TEST | 1.462002 | 1.462002 | 0.0 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s47_cluster_005 | HOLD_DAILY_DEEP_TEST | 1.617685 | 1.671616 | -0.053931 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s47_cluster_006 | HOLD_DAILY_DEEP_TEST | 1.486393 | 1.486393 | 0.0 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s47_cluster_013 | HOLD_DAILY_DEEP_TEST | 1.090023 | 1.221211 | -0.131188 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s48_cluster_006 | HOLD_DAILY_DEEP_TEST | 1.594982 | 1.594982 | 0.0 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s48_cluster_008 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.564433 | 1.221211 | 0.343222 | False | 0.5 |  | regime_bucket_replay_not_run |
| s49_cluster_007 | HOLD_DAILY_DEEP_TEST | 0.995883 | 1.252757 | -0.256874 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s49_cluster_008 | HOLD_DAILY_DEEP_TEST | 1.446549 | 1.494432 | -0.047883 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s50_cluster_005 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.590935 | 1.494432 | 0.096503 | False | 0.5 |  | regime_bucket_replay_not_run |
| s50_cluster_006 | HOLD_DAILY_DEEP_TEST | 1.463397 | 1.463397 | 0.0 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
