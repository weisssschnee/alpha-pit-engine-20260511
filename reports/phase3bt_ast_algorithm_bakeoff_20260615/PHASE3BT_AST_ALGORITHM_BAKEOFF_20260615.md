# Phase3BT AST Algorithm Bakeoff 2026-06-15

Decision: `PHASE3BT_AST_ALGORITHM_BAKEOFF_COMPLETE_DIAGNOSTIC_ONLY`

## Purpose

Lock the next true-1min search-core allocation before any broad large search.
All arms use AST-aware generator variables and the same true `trade_time` minute panels.

## Arm Results

| arm | candidates | sec | rows | rows/sec | hard-blocked | research pool | lanes | fieldsets | ast shapes | top10 abs IC | score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `round1_seed_ast_rx_ucb_fresh` | 160 | 1157.39 | 62131 | 53.682 | 0.964286 | 34 | 29 | 41 | 9 | 0.239337 | 0.591607 |
| `round2_ast_feedback_cem` | 160 | 1146.52 | 62131 | 54.191 | 0.973214 | 29 | 48 | 43 | 12 | 0.241894 | 0.576161 |
| `round3_ast_feedback_hybrid` | 192 | 1338.93 | 62131 | 46.403 | 1 | 23 | 23 | 24 | 9 | 0.223849 | 0.489482 |
| `round4_ast_cem_dominant_ucb` | 192 | 1376.55 | 62131 | 45.135 | 0.946429 | 15 | 42 | 25 | 11 | 0.23614 | 0.468006 |
| `round5_ast_fresh_preserving_hybrid` | 192 | 1745.89 | 62131 | 35.587 | 0.982143 | 42 | 31 | 26 | 8 | 0.220009 | 0.631202 |

## Recommendation

- primary arm: `round5_ast_fresh_preserving_hybrid`
- secondary arm: `round2_ast_feedback_cem`
- exploration arm: `round5_ast_fresh_preserving_hybrid`
- decision: `LOCK_AST_AWARE_ADAPTIVE_SEARCH_CORE_FOR_NEXT_LARGE_SEARCH_DIAGNOSTIC_ONLY`
- reason: ranking uses research-pool quality, AST diversity, fieldset/lane coverage, hard-block ratio, and throughput; not legacy first-up.

## Next Large-search Allocation

- `primary_best_arm`: 45%
- `secondary_adaptive_or_hybrid`: 25%
- `fresh_high_exploration`: 20%
- `control_or_residual_probe`: 10%

## Experiment Record

- experiment_id: `20260615_phase3bt_ast_algorithm_bakeoff`
- python executable: `G:\PythonProject\.venv\Scripts\python.exe`
- package matrix: `{'numpy': '2.1.3', 'pandas': '2.2.3', 'pyarrow': '19.0.1', 'numba': '0.64.0', 'bottleneck': '1.6.0', 'numexpr': '2.14.1', 'polars': '1.41.0', 'joblib': '1.4.2', 'scikit-learn': '1.6.1'}`
- hot path scan: `{'files': {'src\\our_system_phase2\\runtime\\phase3bp_true1min_search_algorithm_smoke.py': [], 'src\\our_system_phase2\\runtime\\phase3bl_bk_priority_signal_materialization.py': ['groupby(', 'sort=False', 'pyarrow'], 'src\\our_system_phase2\\runtime\\phase3bo_mature_cem_bridge_true1min_pack.py': []}, 'interpretation': 'current true1min smoke hot path is pandas/numpy materialization; numba is available only if called by evaluator code'}`
- status: completed
- decision discipline: diagnostic only; no X0/R3 modification; no alpha promotion.

## Boundary

- True `trade_time` 1min panels only.
- Search memory and prior hashes are blocked.
- `research pool` is a deeper-review queue, not deployable proof.
- Freshness is kept as a first-class allocation arm even when feedback CEM wins.
