# Phase3BS Adaptive UCB-CEM Practice 2026-06-15

Decision: `PHASE3BS_ADAPTIVE_UCB_CEM_PRACTICE_COMPLETE_DIAGNOSTIC_ONLY`

## Purpose

Test adaptive UCB-CEM as a multi-round generator: RX/UCB seed, feedback-updated CEM, adaptive hybrid, and two CEM-dominant variants.
The winner metric is research-pool quality, not first clean followup.

## Round Results

| round | candidates | sec | rows | rows/sec | legacy followup | hard-blocked | research pool | lanes | fieldsets | top10 abs IC | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `round1_seed_rx_ucb_fresh` | 128 | 667.911 | 51736 | 77.459 | 1 | 0.979167 | 37 | 29 | 32 | 0.214022 | 0.608854 |
| `round2_adaptive_cem_feedback` | 128 | 656.675 | 51736 | 78.785 | 0 | 1 | 37 | 25 | 26 | 0.214501 | 0.584521 |
| `round3_adaptive_hybrid_rx_cem` | 160 | 897.499 | 51736 | 57.645 | 1 | 0.979167 | 41 | 35 | 24 | 0.196751 | 0.603604 |
| `round4_cem_dominant_ucb` | 160 | 877.624 | 51736 | 58.95 | 3 | 0.90625 | 35 | 42 | 28 | 0.19945 | 0.587313 |
| `round5_cem_dominant_rx` | 160 | 1012.27 | 51736 | 51.109 | 2 | 0.916667 | 23 | 33 | 26 | 0.183549 | 0.495979 |

## Recommendation

- best round: `round1_seed_rx_ucb_fresh`
- decision: `ADAPTIVE_UCB_CEM_HOLD_KEEP_RX_FRESH_PRIMARY`
- interpretation: adaptive feedback ran correctly, but did not beat RX/UCB seed by enough under this budget

## Feedback

- seed feedback updated policy: `phase3bs_adaptive_ucb_cem_feedback_v1`
- top feedback lanes: `[('rx_intraday_return::inverted', 0.14136), ('rx_interaction::rx_range_location::rx_range_location::product', 0.127533), ('rx_interaction::rx_intraday_return::rx_volatility_state::product', 0.106284), ('rx_interaction::rx_intraday_return::rx_volatility_state::spread', 0.106128), ('rx_interaction::rx_intraday_return::rx_opening_amount::spread', 0.088275), ('rx_interaction::rx_intraday_return::rx_opening_amount::product', 0.079079), ('rx_interaction::rx_opening_range::rx_range_location::spread', 0.054195), ('rx_interaction::rx_intraday_return::rx_range_location::spread', 0.032706), ('rx_interaction::rx_range_location::rx_volatility_state::product', 0.025183), ('rx_intraday_return::rank', -0.012163), ('rx_interaction::rx_opening_amount::rx_range_location::product', -0.023693), ('rx_interaction::rx_range_location::rx_opening_amount::spread', -0.025442), ('rx_interaction::rx_range_location::rx_opening_amount::product', -0.037225), ('rx_interaction::rx_range_location::rx_flow_amount_volume::spread', -0.045326), ('rx_interaction::rx_opening_range::rx_range_location::product', -0.057055), ('rx_interaction::rx_range_location::rx_range_location::spread', -0.062365)]`
- top feedback fields: `[('m1_first5_vol', 0.058009), ('intraday_ret_from_open', 0.033167), ('m1_first15_vol', 0.025132), ('volume', 0.007728), ('m1_first30_vol', 0.006742), ('m1_first15_range', -0.011655), ('close', -0.021708), ('high', -0.054198), ('low', -0.054198), ('m1_first30_range', -0.055292), ('m1_first30_amount', -0.059887), ('m1_first5_amount', -0.062288), ('open', -0.065581), ('m1_first5_range', -0.06825), ('amount', -0.074865), ('ret_1m', -0.078857)]`

## Boundary

- True `trade_time` 1min panels only.
- No old daily stock-PIT default panel.
- No X0/R3 modification.
- `research pool` excludes future-lag but is not deployable; crowded members still require orthogonalization/rejection.

## Reproducibility

- python executable: `G:\PythonProject\.venv\Scripts\python.exe`
- package matrix: `{'numpy': '2.1.3', 'pandas': '2.2.3', 'pyarrow': '19.0.1', 'numba': '0.64.0', 'bottleneck': '1.6.0', 'numexpr': '2.14.1', 'polars': '1.41.0', 'joblib': '1.4.2', 'scikit-learn': '1.6.1'}`
- hot path scan: `{'files': {'src\\our_system_phase2\\runtime\\phase3bp_true1min_search_algorithm_smoke.py': [], 'src\\our_system_phase2\\runtime\\phase3bl_bk_priority_signal_materialization.py': ['groupby(', 'sort=False', 'pyarrow'], 'src\\our_system_phase2\\runtime\\phase3bo_mature_cem_bridge_true1min_pack.py': []}, 'interpretation': 'current true1min smoke hot path is pandas/numpy materialization; numba is available only if called by evaluator code'}`
