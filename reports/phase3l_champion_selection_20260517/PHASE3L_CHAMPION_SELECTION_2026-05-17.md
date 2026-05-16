# Phase3L-A Champion Cluster Selection

- created_at: `2026-05-17T00:48:11+08:00`
- decision: `PASS_PHASE3L_A_CHAMPION_SELECTION`
- candidate_count: `213`
- champion_count: `30`
- grade_a_count: `13`
- grade_b_count: `17`

## Interpretation

Grade A means eligible for Phase3L-C deep audit. It is not a production-ready alpha label.
The current selection uses daily replay/book-readiness proxies, J2/J4 retention, cost/capacity proxies, and new-vs-149 proxy evidence.

## Top Champions

| rank | grade | score | cluster | source | lane | p90_turnover | cost | capacity | new_vs_149 | decision |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | A | 86.640339 | s47_cluster_006 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.151724 | 7.468191 | 66581701.945312 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 2 | A | 79.167244 | cluster_018 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.128412 | 3.209146 | 26582522.4 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 3 | A | 77.801143 | cluster_014 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.041078 | 2.682759 | 118236558.78125 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 4 | A | 77.078222 | s48_cluster_006 | kb_fresh_g2 | agnostic_freeform_ast | 0.094871 | 4.221407 | 20723887.289746 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 5 | A | 76.589442 | s50_cluster_005 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.065529 | 3.742877 | 49459578.09375 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 6 | A | 76.127468 | s49_cluster_007 | kb_fresh_g2 | r0_cem_led | 0.025655 | 2.293998 | 119191295.125 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 7 | A | 76.098578 | cluster_008 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.148589 | 3.494263 | 46935603.134766 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 8 | A | 73.197048 | s47_cluster_013 | kb_fresh_g2 | r0_cem_led | 0.033048 | 2.493115 | 115067321.087109 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 9 | A | 71.858483 | s50_cluster_006 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.221826 | 2.795691 | 64781224.645313 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 10 | A | 71.739812 | cluster_017 | phase3j_locked_book | agnostic_freeform_ast | 0.125839 | 2.098815 | 61115043.58125 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 11 | B | 71.657696 | cluster_001 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.100297 | 3.727779 | 124777879.490625 | False | KEEP_AS_GRADE_B_RESERVE |
| 12 | B | 71.490217 | s47_cluster_003 | kb_fresh_g2 | r0_cem_led | 0.032797 | 4.30643 | 32814617.294922 | True | KEEP_AS_GRADE_B_RESERVE |
| 13 | A | 71.480887 | s49_cluster_008 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.098279 | 3.080926 | 25480245.859375 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 14 | A | 70.846588 | s48_cluster_008 | kb_fresh_g2 | r0_cem_led | 0.051814 | 2.384678 | 69497058.628125 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 15 | A | 70.295767 | s47_cluster_005 | kb_fresh_g2 | agnostic_freeform_ast | 0.189713 | 3.481296 | 25906560.293555 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 16 | B | 69.989021 | s50_cluster_003 | kb_fresh_g2 | r0_cem_led | 0.082567 | 4.186631 | 22952094.072168 | False | KEEP_AS_GRADE_B_RESERVE |
| 17 | B | 69.79916 | s49_cluster_005 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.227858 | 3.568546 | 35105354.828125 | True | KEEP_AS_GRADE_B_RESERVE |
| 18 | B | 68.839473 | cluster_004 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.219893 | 2.788897 | 48305024.689453 | False | KEEP_AS_GRADE_B_RESERVE |
| 19 | B | 68.193751 | cluster_016 | phase3j_locked_book | agnostic_freeform_ast | 0.061503 | 2.629757 | 20861176.640332 | False | KEEP_AS_GRADE_B_RESERVE |
| 20 | B | 68.073333 | registry_112 | registry_149 | agnostic_freeform_ast | 0.069145 | 6.029984 | None | False | KEEP_AS_GRADE_B_RESERVE |
| 21 | B | 67.094236 | s47_cluster_014 | kb_fresh_g2 | r0_cem_led | 0.209031 | 2.326107 | 31418563.935742 | True | KEEP_AS_GRADE_B_RESERVE |
| 22 | B | 66.25866 | s50_cluster_002 | kb_fresh_g2 | agnostic_freeform_ast | 0.390044 | 16.47198 | 23085495.5625 | True | KEEP_AS_GRADE_B_RESERVE |
| 23 | B | 66.249711 | s47_cluster_012 | kb_fresh_g2 | agnostic_freeform_ast | 0.157326 | 2.932785 | 32417481.550781 | True | KEEP_AS_GRADE_B_RESERVE |
| 24 | B | 65.892194 | s47_cluster_002 | kb_fresh_g2 | agnostic_freeform_ast | 0.202809 | 2.234978 | 59230204.139648 | False | KEEP_AS_GRADE_B_RESERVE |
| 25 | B | 64.481207 | cluster_005 | phase3j_locked_book | r0_cem_led | 0.186745 | 2.183766 | 66173875.644141 | False | KEEP_AS_GRADE_B_RESERVE |
| 26 | B | 64.448216 | s48_cluster_003 | kb_fresh_g2 | r0_cem_led | 0.293238 | 4.244284 | 11826138.031836 | False | KEEP_AS_GRADE_B_RESERVE |
| 27 | B | 64.027174 | cluster_035 | phase3j_locked_book | r0_cem_led | 0.057486 | 1.193926 | 90645992.81875 | False | KEEP_AS_GRADE_B_RESERVE |
| 28 | B | 63.186979 | cluster_013 | phase3j_locked_book | agnostic_freeform_ast | 0.148873 | 2.706367 | 6941141.851562 | False | KEEP_AS_GRADE_B_RESERVE |
| 29 | B | 61.956733 | cluster_003 | phase3j_locked_book | r0_cem_led | 0.302583 | 3.497901 | 8286721.671289 | False | KEEP_AS_GRADE_B_RESERVE |
| 30 | B | 60.546628 | cluster_027 | phase3j_locked_book | agnostic_freeform_ast | 0.08501 | 1.064067 | 32125730.722461 | False | KEEP_AS_GRADE_B_RESERVE |

## Required Next Proof

- subperiod stability
- regime bucket performance
- sign-flip placebo
- low-order ablation
- champion-book correlation and family caps

## Scope

- No new search was run.
- No G2/J2/J4 parameter was changed.
- No minute execution, live capacity, or production deployment is confirmed.
