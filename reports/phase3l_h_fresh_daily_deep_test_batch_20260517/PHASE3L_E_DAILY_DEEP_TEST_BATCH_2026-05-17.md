# Phase3L-E Daily Deep Test Batch

- generated_at: 2026-05-17T03:40:36+08:00
- decision: `HOLD_PHASE3L_E_DAILY_DEEP_TEST_ATTRITION`
- selected_test_count: 46
- strict_row_count: 46
- cluster_count: 12
- pass_ex_regime_count: 5
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
| cluster_031 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.541851 | 1.494432 | 0.047419 | False | 0.5 |  | regime_bucket_replay_not_run |
| s51_cluster_002 | HOLD_DAILY_DEEP_TEST | 1.349823 | 1.494432 | -0.144609 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s52_cluster_011 | HOLD_DAILY_DEEP_TEST | 1.179842 | 1.252757 | -0.072915 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s52_cluster_012 | HOLD_DAILY_DEEP_TEST | 1.279167 | 1.487411 | -0.208244 | False | 1.0 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s52_cluster_013 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.507126 | None | None | False | 0.5 |  | regime_bucket_replay_not_run |
| s53_cluster_001 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.254644 | None | None | False | 0.5 |  | regime_bucket_replay_not_run |
| s53_cluster_002 | DAILY_DEEP_TEST_PASS_EX_REGIME | 1.420147 | None | None | False | 0.5 |  | regime_bucket_replay_not_run |
| s53_cluster_005 | HOLD_DAILY_DEEP_TEST | 1.446549 | 1.494432 | -0.047883 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
| s54_cluster_007 | HOLD_DAILY_DEEP_TEST | 1.446549 | 1.494432 | -0.047883 | False | 0.5 | low_order_ablation_explains_full | regime_bucket_replay_not_run |
