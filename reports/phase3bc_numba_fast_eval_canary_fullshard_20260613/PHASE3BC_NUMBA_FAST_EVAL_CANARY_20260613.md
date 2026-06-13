# Phase3BC Numba Fast Evaluator Canary

- decision: `PASS_NUMBA_KERNEL_PARITY_CANARY`
- panel: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3au_full_true1min_sharded_20260611\shard_00\phase3aq_wide_true1min\canary\phase3aq_true_1min_formula_canary.parquet`
- rows: `18931032`
- codes: `340`
- trade_time groups: `58563`
- value column: `amount`

## Package Matrix

- `numpy`: `2.1.3`
- `pandas`: `2.2.3`
- `pyarrow`: `19.0.1`
- `numba`: `0.64.0`
- `bottleneck`: `1.6.0`
- `numexpr`: `2.14.1`
- `polars`: `1.41.0`
- `joblib`: `1.4.2`
- `sklearn`: `1.6.1`

## Warm Benchmark

- pandas rank seconds: `27.476269000000002`
- numba rank seconds: `1.5426152999998521`
- rank speedup: `17.81148482061771`
- rank max abs diff: `0.0`
- pandas zscore seconds: `3.5506557000001067`
- numba zscore seconds: `0.0969551999999112`
- zscore speedup: `36.62161183725431`
- zscore max abs diff: `1.4566126083082054e-13`

## Audit Reading

The current true 1min evaluator is pandas-heavy in expression evaluation and grouped rank/zscore. This canary validates the first low-risk numba kernels only. It does not change Phase3AS behavior.

Next allowed step: add rolling `Mean/Delta/Mom` kernels and run expression-level parity on a fixed candidate pack.
