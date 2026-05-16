# Phase3L-F Low-Order Rescue

- generated_at: 2026-05-17T03:40:49+08:00
- decision: `HOLD_PHASE3L_F_RESCUE_INSUFFICIENT_START_FRESH_HARVEST`
- strict_row_count: 46
- full_formula_survivor_count: 5
- eligible_low_order_rescue_count: 12
- unique_low_order_rescue_signal_clusters: 2
- survivor_after_rescue_count: 6

## Interpretation

- This is a no-search rescue pass using Phase3L-E replayed low-order ablations.
- Rescued low-order formulas are simpler candidate structures, not confirmed production alphas.
- Rescued formulas still need their own sign-flip and regime tests before Grade-A proof promotion.

## Rescue Book

| signal_cluster | from_cluster | role | score | margin_vs_full | turnover | source_lane |
| --- | --- | --- | ---: | ---: | ---: | --- |
| cluster_002 | cluster_008 | component_2 | 1.494432 | 0.019342 | 0.077411 | formula_gen_v2_repair_expansion |
| cluster_005 | cluster_017 | drop_component_1 | 1.462002 | 0.0 | 0.076805 | agnostic_freeform_ast |

## Survivor Book After Rescue

| type | signal_cluster | source_cluster | score | turnover | remaining_blocker |
| --- | --- | --- | ---: | ---: | --- |
| full_formula_survivor | cluster_007 | cluster_031 | 1.541851 | 0.103397 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_008 | s52_cluster_013 | 1.507126 | 0.069113 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_011 | s53_cluster_002 | 1.420147 | 0.143169 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_002 | s53_cluster_001 | 1.254644 | 0.03179 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_009 | cluster_014 | 1.229064 | 0.027425 | true_regime_bucket_replay_not_run |
| low_order_rescue | cluster_005 | cluster_017 | 1.462002 | 0.076805 | own_sign_flip_and_regime_tests_not_run |
