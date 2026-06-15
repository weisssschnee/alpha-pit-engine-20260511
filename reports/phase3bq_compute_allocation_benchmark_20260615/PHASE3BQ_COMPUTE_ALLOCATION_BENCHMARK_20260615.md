# Phase3BQ Compute Allocation Benchmark 2026-06-15

Decision: `PHASE3BQ_COMPUTE_ALLOCATION_BENCHMARK_COMPLETE_DIAGNOSTIC_ONLY`

## Purpose

Compare true-1min search algorithms by compute efficiency, blocker yield, and clean followup rate.

## Arm Results

| arm | family | status | sec | candidates | rows | rows/sec | followup | hard-blocked | future-lag | crowded | best abs IC | decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `bo_template_quota_48x3x30` | `template_quota` | `completed` | 88.28 | 26 | 28437 | 322.124 | 1 | 0.884615 | 17 | 14 | 0.196429 | `allocation_candidate` |
| `bp_rx_ucb_72x3x30` | `rx_ucb` | `completed` | 207.154 | 72 | 28437 | 137.274 | 1 | 0.958333 | 39 | 42 | 0.239605 | `allocation_candidate` |
| `bp_cem_elite_72x3x30` | `cem_elite` | `completed` | 200.977 | 72 | 28437 | 141.494 | 0 | 1 | 43 | 44 | 0.239605 | `allocation_hold` |
| `bp_hybrid_rx_cem_96x3x30` | `hybrid_rx_cem` | `completed` | 263.424 | 96 | 28437 | 107.951 | 0 | 1 | 46 | 44 | 0.239605 | `allocation_hold` |
| `bp_residual_probe_16x1x12` | `residual_probe` | `completed` | 13.947 | 16 | 3901 | 279.695 | 2 | 0.8125 | 9 | 13 | 0.232628 | `allocation_candidate` |

## Allocation

- recommendation: `USE_STAGED_RX_CEM_PORTFOLIO_WITH_TEMPLATE_CONTROL`
- best throughput arm: `bo_template_quota_48x3x30`
- best clean arm: `bp_residual_probe_16x1x12`
- reason: allocation is based on completed true1min arm throughput, hard-blocked ratio, and clean followup yield; residual remains capped because previous larger residual runs timed out.

## Budget Split

- `stage0_ledger_surrogate`: 10% budget; broad cheap ledger/surrogate generation before strict minute materialization
- `stage1_rx_ucb`: 35% budget; typed exploration with family caps and search memory
- `stage1_cem_elite`: 25% budget; CEM-style elite resampling when it beats rx on clean yield per minute
- `stage1_template_control`: 15% budget; keep BO/template as control and simple-family fallback
- `stage2_hybrid_followup`: 15% budget; only deepen clean no-future-wrong-lag representatives
- `residual_complexity`: 5% budget; run only as tiny probe until evaluator is optimized

## Boundary

- True `trade_time` 1min only.
- This is compute allocation research, not alpha proof.
- `future_signal_wrong_lag_too_strong` remains a hard blocker.
- Residual expressions are not allowed into broad search until evaluator hot path is optimized.

## Acceleration Audit

- python executable: `G:\PythonProject\.venv\Scripts\python.exe`
- package matrix: `{'numpy': '2.1.3', 'pandas': '2.2.3', 'pyarrow': '19.0.1', 'numba': '0.64.0', 'bottleneck': '1.6.0', 'numexpr': '2.14.1', 'polars': '1.41.0', 'joblib': '1.4.2', 'scikit-learn': '1.6.1'}`
- hot path scan: `{'files': {'src\\our_system_phase2\\runtime\\phase3bp_true1min_search_algorithm_smoke.py': [], 'src\\our_system_phase2\\runtime\\phase3bl_bk_priority_signal_materialization.py': ['groupby(', 'sort=False', 'pyarrow'], 'src\\our_system_phase2\\runtime\\phase3bo_mature_cem_bridge_true1min_pack.py': []}, 'interpretation': 'current true1min smoke hot path is pandas/numpy materialization; numba is available only if called by evaluator code'}`
