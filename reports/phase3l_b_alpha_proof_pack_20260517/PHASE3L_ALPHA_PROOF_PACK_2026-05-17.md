# Phase3L Alpha Proof Pack

- generated_at: 2026-05-17T03:31:18+08:00
- decision: HOLD_PHASE3L_C_INSUFFICIENT_DAILY_PROXY_BOOK
- proof_scope: daily_proxy_only__not_production_ready
- champion_count: 30
- daily_proxy_pass_count: 14
- grade_a_count: 14
- reserve_count: 16

## Book Candidates

| book | clusters | p90_turnover | mean_cost | median_capacity | max_raw_share | source_top_share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L0_grade_a_daily_proxy | 14 | 0.145158 | 3.171705 | 29349256.282 | 0.166667 | 0.5 |
| L1_grade_a_low_turnover_capacity | 14 | 0.145158 | 3.171705 | 29349256.282 | 0.166667 | 0.5 |
| L2_grade_a_diversified | 12 | 0.145727 | 3.119236 | 32201191.586 | 0.1875 | 0.5 |

## Top Daily-Proxy Cards

| rank | cluster | status | lane | p90_turnover | cost | capacity | new_vs_149_proxy |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | cluster_018 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.128412 | 3.209146 | 26582522.4 | False |
| 2 | s51_cluster_002 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.113772 | 4.157599 | 41240100.479 | True |
| 3 | cluster_014 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.041078 | 2.682759 | 118236558.781 | False |
| 4 | cluster_008 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.148589 | 3.494263 | 46935603.135 | False |
| 5 | s52_cluster_013 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | agnostic_freeform_ast | 0.069113 | 3.905575 | 27201787.564 | True |
| 6 | s54_cluster_007 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.098279 | 3.080926 | 25480245.859 | False |
| 7 | s52_cluster_012 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | r0_cem_led | 0.146011 | 2.555187 | 31496725.0 | True |
| 8 | s52_cluster_011 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | r0_cem_led | 0.028193 | 2.283187 | 118609766.952 | True |
| 9 | s53_cluster_005 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.098279 | 3.080926 | 25480245.859 | True |
| 10 | cluster_017 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | agnostic_freeform_ast | 0.125839 | 2.098815 | 61115043.581 | False |
| 11 | cluster_001 | RESERVE_DAILY_PROXY__DEEP_TESTS_PENDING | formula_gen_v2_repair_expansion | 0.100297 | 3.727779 | 124777879.491 | False |
| 12 | s53_cluster_001 | DAILY_PROXY_PASS__DEEP_TESTS_PENDING | agnostic_freeform_ast | 0.052267 | 3.835719 | 32905658.172 | False |

## Audit Limits

- This is a daily proxy proof pack, not production deployment proof.
- Sign-flip placebo, low-order ablation, full subperiod replay, and true execution/capacity tests remain required before KEEP/promotion.
- If fewer than 8 clusters survive those missing tests, Phase3L-B fresh locked harvest is required.
