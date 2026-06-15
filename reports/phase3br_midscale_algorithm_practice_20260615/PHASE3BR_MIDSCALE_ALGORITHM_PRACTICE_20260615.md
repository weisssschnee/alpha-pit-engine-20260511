# Phase3BR Mid-scale Algorithm Practice 2026-06-15

Decision: `PHASE3BR_MIDSCALE_ALGORITHM_PRACTICE_COMPLETE_DIAGNOSTIC_ONLY`

## Purpose

Run a medium true-1min algorithm practice pass that is larger than smoke but smaller than prior broad searches.
The scoring target is research-pool quality, not first clean followup.

Research pool means a non-future-leaking followup queue for deeper review.
It may still include crowded signals; crowding is reported separately and is not promotion evidence.

## Arm Results

| arm | family | status | sec | candidates | rows | rows/sec | legacy followup | hard-blocked | research pool | lanes | fieldsets | top10 abs IC | score |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `template_control_96x4x40` | `template_quota_control` | `completed` | 182.177 | 33 | 51736 | 283.988 | 1 | 0.8125 | 1 | 7 | 12 | 0.108999 | 0.275938 |
| `rx_ucb_mid_128x4x40` | `rx_ucb` | `completed` | 629.816 | 128 | 51736 | 82.145 | 1 | 0.9875 | 27 | 28 | 29 | 0.214471 | 0.569375 |
| `rx_ucb_fresh_128x4x40` | `rx_ucb_high_exploration` | `completed` | 707.912 | 128 | 51736 | 73.083 | 1 | 0.9875 | 33 | 26 | 29 | 0.214022 | 0.618125 |
| `cem_elite_mid_128x4x40` | `cem_elite` | `completed` | 657.653 | 128 | 51736 | 78.668 | 1 | 0.9875 | 20 | 25 | 25 | 0.21623 | 0.5125 |
| `hybrid_rx_cem_mid_160x4x40` | `hybrid_rx_cem` | `completed` | 816.198 | 160 | 51736 | 63.387 | 1 | 0.979167 | 28 | 34 | 20 | 0.216764 | 0.519583 |
| `residual_capped_40x2x24` | `residual_capped_probe` | `completed` | 115.419 | 40 | 15569 | 134.891 | 1 | 0.975 | 11 | 21 | 12 | 0.223249 | 0.331625 |

## Recommendation

- primary scalable arm: `rx_ucb_fresh_128x4x40`
- ranked scalable arms: `['rx_ucb_fresh_128x4x40', 'rx_ucb_mid_128x4x40', 'hybrid_rx_cem_mid_160x4x40', 'cem_elite_mid_128x4x40', 'template_control_96x4x40']`
- residual policy: cap at probe budget; do not let tiny survivor count dominate allocation
- reason: ranking uses research-pool quality, hard-blocked ratio, diversity, and throughput; legacy followup count is diagnostic only

## Budget

- `rx_ucb_or_best_scalable_arm`: 40%
- `fresh_high_exploration`: 20%
- `cem_or_hybrid_if_research_pool_positive`: 20%
- `template_control`: 10%
- `residual_probe`: 10% max until full evaluator is optimized

## Boundary

- True `trade_time` 1min only.
- No X0/R3 modification.
- This is algorithm adaptation and factor-search practice, not alpha promotion.
- Legacy followup is reported but not used as the main winner metric.
- `research pool` excludes future-lag but does not equal deployable; crowded members need later orthogonalization or rejection.

## Acceleration And Reproducibility

- python executable: `G:\PythonProject\.venv\Scripts\python.exe`
- package matrix: `{'numpy': '2.1.3', 'pandas': '2.2.3', 'pyarrow': '19.0.1', 'numba': '0.64.0', 'bottleneck': '1.6.0', 'numexpr': '2.14.1', 'polars': '1.41.0', 'joblib': '1.4.2', 'scikit-learn': '1.6.1'}`
- hot path scan: `{'files': {'src\\our_system_phase2\\runtime\\phase3bp_true1min_search_algorithm_smoke.py': [], 'src\\our_system_phase2\\runtime\\phase3bl_bk_priority_signal_materialization.py': ['groupby(', 'sort=False', 'pyarrow'], 'src\\our_system_phase2\\runtime\\phase3bo_mature_cem_bridge_true1min_pack.py': []}, 'interpretation': 'current true1min smoke hot path is pandas/numpy materialization; numba is available only if called by evaluator code'}`
- commands are embedded in `phase3br_midscale_algorithm_practice_summary.json`.
