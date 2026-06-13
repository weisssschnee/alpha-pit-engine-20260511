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

- pandas rank seconds: `26.349667599999975`
- numba rank seconds: `1.6487621999999647`
- rank speedup: `15.98148453427701`
- rank max abs diff: `0.0`
- pandas zscore seconds: `3.2432956999998623`
- numba zscore seconds: `0.09864520000019183`
- zscore speedup: `32.87839347473121`
- zscore max abs diff: `1.4566126083082054e-13`
- pandas rolling mean seconds: `2.0016178000000764`
- numba rolling mean seconds: `0.1016465000000153`
- rolling mean speedup: `19.691950042547212`
- rolling mean max abs diff: `0.0`
- pandas delta seconds: `0.2525576999998975`
- numba delta seconds: `0.08691939999994247`
- delta speedup: `2.9056539736821088`
- delta max abs diff: `0.0`
- pandas mom seconds: `0.34694139999987783`
- numba mom seconds: `0.12216549999993731`
- mom speedup: `2.8399294399814665`
- mom max abs diff: `0.0`

## Audit Reading

The current true 1min evaluator is pandas-heavy in expression evaluation and grouped rank/zscore/rolling operators. This canary validates low-risk numba kernels for the most common grouped and rolling operators. It does not change Phase3AS behavior.

Next allowed step: run expression-level parity on a fixed candidate pack, then wire the numba backend behind an explicit evaluator flag.
