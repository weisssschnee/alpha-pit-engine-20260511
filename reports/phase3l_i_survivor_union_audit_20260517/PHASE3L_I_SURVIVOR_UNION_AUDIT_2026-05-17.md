# Phase3L-I Survivor Union Audit

- generated_at: 2026-05-17T03:42:39+08:00
- decision: `PASS_PHASE3L_I_SURVIVOR_COUNT_READY_FOR_GLOBAL_RECLUSTER_AND_PROOF_PACK`
- raw_survivor_rows: 12
- unique_expression_survivors: 10
- local_signal_cluster_count: 10
- median_turnover: 0.071265

## Interpretation

- The survivor count is now sufficient by expression uniqueness.
- Signal cluster IDs are batch-local and remain diagnostic until a global survivor recluster is run.
- Low-order rescue entries still need their own sign-flip and regime checks.

## Union Survivors

| harvest | type | local_signal_cluster | cluster_id | score | turnover | source_lane |
| --- | --- | --- | --- | ---: | ---: | --- |
| initial | low_order_rescue | cluster_002 | s47_cluster_005 | 1.671616 | 0.073418 | agnostic_freeform_ast |
| initial | low_order_rescue | cluster_010 | s47_cluster_005 | 1.617685 | 0.199872 | agnostic_freeform_ast |
| initial | full_formula_survivor | cluster_011 | s50_cluster_005 | 1.590935 | 0.065529 | formula_gen_v2_repair_expansion |
| initial | full_formula_survivor | cluster_007 | s48_cluster_008 | 1.564433 | 0.051814 | r0_cem_led |
| fresh | full_formula_survivor | cluster_007 | cluster_031 | 1.541851 | 0.103397 | formula_gen_v2_repair_expansion |
| fresh | full_formula_survivor | cluster_008 | s52_cluster_013 | 1.507126 | 0.069113 | agnostic_freeform_ast |
| initial | low_order_rescue | cluster_006 | cluster_017 | 1.462002 | 0.076805 | agnostic_freeform_ast |
| fresh | full_formula_survivor | cluster_011 | s53_cluster_002 | 1.420147 | 0.143169 | agnostic_freeform_ast |
| fresh | full_formula_survivor | cluster_002 | s53_cluster_001 | 1.254644 | 0.03179 | agnostic_freeform_ast |
| initial | full_formula_survivor | cluster_009 | cluster_014 | 1.229064 | 0.027425 | formula_gen_v2_repair_expansion |
