# Phase3L-F Low-Order Rescue

- generated_at: 2026-05-17T02:03:11+08:00
- decision: `HOLD_PHASE3L_F_RESCUE_INSUFFICIENT_START_FRESH_HARVEST`
- strict_row_count: 64
- full_formula_survivor_count: 3
- eligible_low_order_rescue_count: 18
- unique_low_order_rescue_signal_clusters: 4
- survivor_after_rescue_count: 6

## Interpretation

- This is a no-search rescue pass using Phase3L-E replayed low-order ablations.
- Rescued low-order formulas are simpler candidate structures, not confirmed production alphas.
- Rescued formulas still need their own sign-flip and regime tests before Grade-A proof promotion.

## Rescue Book

| signal_cluster | from_cluster | role | score | margin_vs_full | turnover | source_lane |
| --- | --- | --- | ---: | ---: | ---: | --- |
| cluster_002 | s47_cluster_005 | component_3 | 1.671616 | 0.053931 | 0.073418 | agnostic_freeform_ast |
| cluster_010 | s47_cluster_005 | drop_component_1 | 1.617685 | 0.0 | 0.199872 | agnostic_freeform_ast |
| cluster_007 | s47_cluster_006 | component_2 | 1.486393 | 0.0 | 0.151724 | formula_gen_v2_repair_expansion |
| cluster_006 | cluster_017 | drop_component_1 | 1.462002 | 0.0 | 0.076805 | agnostic_freeform_ast |

## Survivor Book After Rescue

| type | signal_cluster | source_cluster | score | turnover | remaining_blocker |
| --- | --- | --- | ---: | ---: | --- |
| full_formula_survivor | cluster_011 | s50_cluster_005 | 1.590935 | 0.065529 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_007 | s48_cluster_008 | 1.564433 | 0.051814 | true_regime_bucket_replay_not_run |
| full_formula_survivor | cluster_009 | cluster_014 | 1.229064 | 0.027425 | true_regime_bucket_replay_not_run |
| low_order_rescue | cluster_002 | s47_cluster_005 | 1.671616 | 0.073418 | own_sign_flip_and_regime_tests_not_run |
| low_order_rescue | cluster_010 | s47_cluster_005 | 1.617685 | 0.199872 | own_sign_flip_and_regime_tests_not_run |
| low_order_rescue | cluster_006 | cluster_017 | 1.462002 | 0.076805 | own_sign_flip_and_regime_tests_not_run |
