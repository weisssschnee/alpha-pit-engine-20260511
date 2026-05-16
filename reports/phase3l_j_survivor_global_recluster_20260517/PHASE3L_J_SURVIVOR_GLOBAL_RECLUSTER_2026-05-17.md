# Phase3L-J Survivor Global Recluster

- generated_at: 2026-05-17T05:03:13+08:00
- decision: `PASS_PHASE3L_J_GLOBAL_SURVIVOR_BOOK_EX_REGIME`
- survivor_input_count: 10
- strict_row_count: 20
- global_daily_pass_count: 10
- global_daily_pass_signal_clusters: 9

## Interpretation

- This run reclusters all survivor expressions in one batch, so global signal-cluster labels are comparable within this survivor book.
- Sign-flip was rerun for every survivor expression, including low-order rescues.
- Regime replay and minute execution remain blockers.

## Survivor Rows

| decision | global_cluster | source_cluster | type | score | turnover | sign_flip_passed | source_lane | blockers |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_001 | s47_cluster_005 | low_order_rescue | 1.671616 | 0.073418 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_005 | s47_cluster_005 | low_order_rescue | 1.617685 | 0.199872 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_008 | s50_cluster_005 | full_formula_survivor | 1.590935 | 0.065529 | False | formula_gen_v2_repair_expansion |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_006 | s48_cluster_008 | full_formula_survivor | 1.564433 | 0.051814 | False | r0_cem_led |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_009 | cluster_031 | full_formula_survivor | 1.541851 | 0.103397 | False | formula_gen_v2_repair_expansion |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_003 | s52_cluster_013 | full_formula_survivor | 1.507126 | 0.069113 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_002 | cluster_017 | low_order_rescue | 1.462002 | 0.076805 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_007 | s53_cluster_002 | full_formula_survivor | 1.420147 | 0.143169 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_001 | s53_cluster_001 | full_formula_survivor | 1.254644 | 0.03179 | False | agnostic_freeform_ast |  |
| GLOBAL_DAILY_PASS_EX_REGIME | cluster_004 | cluster_014 | full_formula_survivor | 1.229064 | 0.027425 | False | formula_gen_v2_repair_expansion |  |
