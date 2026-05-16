# Phase3L Alpha Proof Pack

- generated_at: 2026-05-17T01:05:42+08:00
- decision: PASS_PHASE3L_C_DAILY_PROXY_PROOF_PACK
- proof_scope: daily_proxy_only__not_production_ready
- champion_count: 30
- daily_proxy_pass_count: 13
- grade_a_count: 13
- reserve_count: 17

## Book Candidates

| book | clusters | p90_turnover | mean_cost | median_capacity | max_raw_share | source_top_share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L0_grade_a_daily_proxy | 13 | 0.182115 | 3.342089 | 61115043.581 | 0.210526 | 0.538462 |
| L1_grade_a_low_turnover_capacity | 13 | 0.182115 | 3.342089 | 61115043.581 | 0.210526 | 0.538462 |
| L2_grade_a_diversified | 12 | 0.185914 | 3.353168 | 62948134.113 | 0.133333 | 0.5 |

## Top Daily-Proxy Cards

| rank | cluster | status | lane | p90_turnover | cost | capacity | new_vs_149_proxy |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | s47_cluster_006 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.151724 | 7.468191 | 66581701.945 | True |
| 2 | cluster_018 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.128412 | 3.209146 | 26582522.4 | False |
| 3 | cluster_014 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.041078 | 2.682759 | 118236558.781 | False |
| 4 | s48_cluster_006 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | agnostic_freeform_ast | 0.094871 | 4.221407 | 20723887.29 | True |
| 5 | s50_cluster_005 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.065529 | 3.742877 | 49459578.094 | True |
| 6 | s49_cluster_007 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | r0_cem_led | 0.025655 | 2.293998 | 119191295.125 | True |
| 7 | cluster_008 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.148589 | 3.494263 | 46935603.135 | False |
| 8 | s47_cluster_013 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | r0_cem_led | 0.033048 | 2.493115 | 115067321.087 | True |
| 9 | s50_cluster_006 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.221826 | 2.795691 | 64781224.645 | True |
| 10 | cluster_017 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | agnostic_freeform_ast | 0.125839 | 2.098815 | 61115043.581 | False |
| 11 | cluster_001 | RESERVE_DAILY_PROXY__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.100297 | 3.727779 | 124777879.491 | False |
| 12 | s47_cluster_003 | RESERVE_DAILY_PROXY__DEEP_TESTS_PENDING | r0_cem_led | 0.032797 | 4.30643 | 32814617.295 | True |

## Audit Limits

- This is a daily proxy proof pack, not production deployment proof.
- Sign-flip placebo, low-order ablation, full subperiod replay, and true execution/capacity tests remain required before KEEP/promotion.
- If fewer than 8 clusters survive those missing tests, Phase3L-B fresh locked harvest is required.
