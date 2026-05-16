# Phase3L-A Champion Cluster Selection

- created_at: `2026-05-17T03:30:58+08:00`
- decision: `PASS_PHASE3L_A_CHAMPION_SELECTION`
- candidate_count: `217`
- champion_count: `30`
- grade_a_count: `14`
- grade_b_count: `16`

## Interpretation

Grade A means eligible for Phase3L-C deep audit. It is not a production-ready alpha label.
The current selection uses daily replay/book-readiness proxies, J2/J4 retention, cost/capacity proxies, and new-vs-149 proxy evidence.

## Top Champions

| rank | grade | score | cluster | source | lane | p90_turnover | cost | capacity | new_vs_149 | decision |
| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | A | 79.167244 | cluster_018 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.128412 | 3.209146 | 26582522.4 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 2 | A | 78.487142 | s51_cluster_002 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.113772 | 4.157599 | 41240100.479346 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 3 | A | 77.801143 | cluster_014 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.041078 | 2.682759 | 118236558.78125 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 4 | A | 76.098578 | cluster_008 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.148589 | 3.494263 | 46935603.134766 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 5 | A | 75.532379 | s52_cluster_013 | kb_fresh_g2 | agnostic_freeform_ast | 0.069113 | 3.905575 | 27201787.563672 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 6 | A | 74.870983 | s54_cluster_007 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.098279 | 3.080926 | 25480245.859375 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 7 | A | 73.090563 | s52_cluster_012 | kb_fresh_g2 | r0_cem_led | 0.146011 | 2.555187 | 31496725.0 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 8 | A | 71.922162 | s52_cluster_011 | kb_fresh_g2 | r0_cem_led | 0.028193 | 2.283187 | 118609766.951953 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 9 | A | 71.819599 | s53_cluster_005 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.098279 | 3.080926 | 25480245.859375 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 10 | A | 71.739812 | cluster_017 | phase3j_locked_book | agnostic_freeform_ast | 0.125839 | 2.098815 | 61115043.58125 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 11 | B | 71.657696 | cluster_001 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.100297 | 3.727779 | 124777879.490625 | False | KEEP_AS_GRADE_B_RESERVE |
| 12 | A | 71.636592 | s53_cluster_001 | kb_fresh_g2 | agnostic_freeform_ast | 0.052267 | 3.835719 | 32905658.172363 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 13 | A | 71.390912 | s53_cluster_002 | kb_fresh_g2 | agnostic_freeform_ast | 0.143169 | 3.181867 | 22877982.360352 | True | ENTER_PHASE3L_C_DEEP_AUDIT |
| 14 | A | 70.942226 | cluster_031 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.103397 | 3.074003 | 23895134.562695 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 15 | A | 70.211866 | s54_cluster_002 | kb_fresh_g2 | r0_cem_led | 0.060015 | 3.763897 | 25044245.442773 | False | ENTER_PHASE3L_C_DEEP_AUDIT |
| 16 | B | 68.839473 | cluster_004 | phase3j_locked_book | formula_gen_v2_repair_expansion | 0.219893 | 2.788897 | 48305024.689453 | False | KEEP_AS_GRADE_B_RESERVE |
| 17 | B | 68.762764 | s51_cluster_001 | kb_fresh_g2 | agnostic_freeform_ast | 0.195914 | 2.207932 | 61038750.60332 | True | KEEP_AS_GRADE_B_RESERVE |
| 18 | B | 68.193751 | cluster_016 | phase3j_locked_book | agnostic_freeform_ast | 0.061503 | 2.629757 | 20861176.640332 | False | KEEP_AS_GRADE_B_RESERVE |
| 19 | B | 68.073333 | registry_112 | registry_149 | agnostic_freeform_ast | 0.069145 | 6.029984 | None | False | KEEP_AS_GRADE_B_RESERVE |
| 20 | B | 66.480719 | s51_cluster_005 | kb_fresh_g2 | r0_cem_led | 0.036741 | 2.732301 | 114899314.978125 | False | KEEP_AS_GRADE_B_RESERVE |
| 21 | B | 66.047734 | s52_cluster_002 | kb_fresh_g2 | r0_cem_led | 0.1414 | 2.96599 | 69546080.957031 | False | KEEP_AS_GRADE_B_RESERVE |
| 22 | B | 65.844944 | s51_cluster_011 | kb_fresh_g2 | agnostic_freeform_ast | 0.144215 | 1.065551 | 67648509.121875 | True | KEEP_AS_GRADE_B_RESERVE |
| 23 | B | 65.640872 | s54_cluster_005 | kb_fresh_g2 | agnostic_freeform_ast | 0.139171 | 1.105188 | 57611127.090234 | True | KEEP_AS_GRADE_B_RESERVE |
| 24 | B | 65.539945 | s54_cluster_010 | kb_fresh_g2 | formula_gen_v2_repair_expansion | 0.132702 | 2.435467 | 21990144.123828 | True | KEEP_AS_GRADE_B_RESERVE |
| 25 | B | 65.191189 | s53_cluster_004 | kb_fresh_g2 | r0_cem_led | 0.037819 | 2.517883 | 114204507.063281 | False | KEEP_AS_GRADE_B_RESERVE |
| 26 | B | 64.481207 | cluster_005 | phase3j_locked_book | r0_cem_led | 0.186745 | 2.183766 | 66173875.644141 | False | KEEP_AS_GRADE_B_RESERVE |
| 27 | B | 64.027174 | cluster_035 | phase3j_locked_book | r0_cem_led | 0.057486 | 1.193926 | 90645992.81875 | False | KEEP_AS_GRADE_B_RESERVE |
| 28 | B | 63.963883 | s51_cluster_006 | kb_fresh_g2 | agnostic_freeform_ast | 0.120017 | 0.803214 | 66178692.158203 | True | KEEP_AS_GRADE_B_RESERVE |
| 29 | B | 62.503016 | s52_cluster_030 | kb_fresh_g2 | r0_cem_led | 0.047298 | 1.714116 | 18203547.140625 | True | KEEP_AS_GRADE_B_RESERVE |
| 30 | B | 61.956733 | cluster_003 | phase3j_locked_book | r0_cem_led | 0.302583 | 3.497901 | 8286721.671289 | False | KEEP_AS_GRADE_B_RESERVE |

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
