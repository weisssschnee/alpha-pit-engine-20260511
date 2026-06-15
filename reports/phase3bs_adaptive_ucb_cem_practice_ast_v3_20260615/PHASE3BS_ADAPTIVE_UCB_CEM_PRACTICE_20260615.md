# Phase3BS Adaptive UCB-CEM Practice 2026-06-15

Decision: `PHASE3BS_ADAPTIVE_UCB_CEM_PRACTICE_COMPLETE_DIAGNOSTIC_ONLY`

## Purpose

Test AST-aware adaptive UCB-CEM as a multi-round generator: RX/UCB seed, feedback-updated CEM, adaptive hybrid, and two CEM-dominant variants.
The winner metric is research-pool quality, not first clean followup.

## Round Results

| round | candidates | sec | rows | rows/sec | legacy followup | hard-blocked | research pool | lanes | fieldsets | ast shapes | top10 abs IC | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `round1_seed_rx_ucb_fresh` | 128 | 879.891 | 51736 | 58.798 | 2 | 0.9375 | 31 | 27 | 32 | 8 | 0.213993 | 0.596979 |
| `round2_adaptive_cem_feedback` | 128 | 932.387 | 51736 | 55.488 | 2 | 0.979167 | 37 | 38 | 33 | 12 | 0.211218 | 0.646771 |
| `round3_adaptive_hybrid_rx_cem` | 160 | 1262.94 | 51736 | 40.965 | 2 | 0.979167 | 31 | 21 | 22 | 9 | 0.19367 | 0.557896 |
| `round4_cem_dominant_ucb` | 160 | 1183.73 | 51736 | 43.706 | 1 | 0.989583 | 25 | 33 | 28 | 12 | 0.202123 | 0.551271 |
| `round5_cem_dominant_rx` | 160 | 1493.93 | 51736 | 34.631 | 3 | 0.96875 | 28 | 23 | 19 | 9 | 0.208774 | 0.525583 |

## Recommendation

- best round: `round2_adaptive_cem_feedback`
- decision: `ADAPTIVE_UCB_CEM_SHOWS_INCREMENTAL_SEARCH_VALUE_DIAGNOSTIC_ONLY`
- interpretation: feedback-updated CEM/hybrid improved research-pool score enough to justify a larger adaptive run

## Feedback

- seed feedback updated policy: `phase3bs_adaptive_ucb_cem_feedback_v1`
- top feedback lanes: `[('rx_interaction::rx_range_location::rx_range_location::product', 0.127533), ('rx_interaction::rx_intraday_return::rx_flow_amount_volume::spread', 0.10671), ('rx_interaction::rx_intraday_return::rx_opening_amount::spread', 0.088275), ('rx_interaction::rx_opening_range::rx_range_location::spread', 0.069202), ('rx_interaction::rx_intraday_return::rx_range_location::spread', 0.067706), ('rx_interaction::rx_intraday_return::rx_opening_amount::product', 0.064107), ('rx_intraday_return::inverted', 0.028358), ('rx_intraday_return::rank', 0.028358), ('rx_interaction::rx_range_location::rx_volatility_state::product', 0.025183), ('rx_interaction::rx_range_location::rx_opening_amount::spread', -0.025442), ('rx_interaction::rx_range_location::rx_opening_amount::product', -0.037225), ('rx_interaction::rx_opening_range::rx_range_location::product', -0.041137), ('rx_range_location::inverted', -0.059844), ('rx_interaction::rx_range_location::rx_range_location::spread', -0.062365), ('rx_interaction::rx_range_location::rx_volatility_state::spread', -0.06369), ('rx_interaction::rx_opening_divergence::rx_range_location::spread', -0.09869)]`
- top feedback fields: `[('intraday_ret_from_open', 0.06233), ('m1_first5_vol', 0.058009), ('volume', 0.030477), ('m1_first15_vol', 0.025132), ('m1_first30_vol', 0.003825), ('close', -0.04837), ('high', -0.071595), ('low', -0.071595), ('m1_first30_range', -0.077958), ('m1_first15_amount', -0.091509), ('open', -0.093322), ('ret_1m', -0.10917), ('amount', -0.125376), ('m1_first15_vwap_return_vs_open', -0.127567), ('m1_first30_vwap_return_vs_open', -0.145058), ('m1_first30_amount', -0.16983)]`
- top feedback AST shapes: `[('complexity_le_6', 0.028358), ('complexity_le_10', 0.004403), ('complexity_le_18', -0.031777), ('complexity_gt_18', -0.04837), ('complexity_le_14', -0.069562)]`
- top feedback AST operator sequences: `[('CSRank>Sub>ZScore>Delta>ZScore>Delta', 0.10671), ('CSRank>Sub>ZScore>Delta>ZScore>Div>Add>Abs', 0.088275), ('CSRank>Sub>ZScore>Div>Add>Abs>ZScore>Std>Div>Sub', 0.069202), ('CSRank>Sub>ZScore>Delta>ZScore>Std>Div>Sub>Add>Abs', 0.067706), ('CSRank>Mul>ZScore>Delta>ZScore>Div>Add>Abs', 0.064107), ('Neg>CSRank>ZScore>Delta', 0.028358), ('CSRank>ZScore>Delta', 0.028358), ('Neg>CSRank>ZScore>Sub>Div>Sub>Add>Abs>Sub>Mean', -0.030009), ('CSRank>Sub>ZScore>Sub>Div>Sub>Add>Abs>Sub>Mean', -0.040476), ('CSRank>Mul>ZScore>Div>Add>Abs>ZScore>Std>Div>Sub', -0.041137), ('CSRank>Mul>ZScore>Sub>Div>Sub>Add>Abs>Sub>Mean', -0.054642), ('CSRank>Sub>ZScore>ZScore>Std>Div>Sub>Add>Abs', -0.09869), ('CSRank>Mul>ZScore>Div>Add>Abs>ZScore>Std', -0.113173), ('CSRank>Mul>ZScore>Delta>ZScore>Std>Div>Sub>Add>Abs', -0.127329), ('CSRank>Mul>ZScore>Delta>ZScore>Std', -0.127694), ('CSRank>Sub>ZScore>Div>Add>Abs>ZScore>Std', -0.172761)]`

## Boundary

- True `trade_time` 1min panels only.
- No old daily stock-PIT default panel.
- No X0/R3 modification.
- `research pool` excludes future-lag but is not deployable; crowded members still require orthogonalization/rejection.

## Reproducibility

- python executable: `G:\PythonProject\.venv\Scripts\python.exe`
- package matrix: `{'numpy': '2.1.3', 'pandas': '2.2.3', 'pyarrow': '19.0.1', 'numba': '0.64.0', 'bottleneck': '1.6.0', 'numexpr': '2.14.1', 'polars': '1.41.0', 'joblib': '1.4.2', 'scikit-learn': '1.6.1'}`
- hot path scan: `{'files': {'src\\our_system_phase2\\runtime\\phase3bp_true1min_search_algorithm_smoke.py': [], 'src\\our_system_phase2\\runtime\\phase3bl_bk_priority_signal_materialization.py': ['groupby(', 'sort=False', 'pyarrow'], 'src\\our_system_phase2\\runtime\\phase3bo_mature_cem_bridge_true1min_pack.py': []}, 'interpretation': 'current true1min smoke hot path is pandas/numpy materialization; numba is available only if called by evaluator code'}`
