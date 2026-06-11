# Phase3AS True 1min Sidecar Canary Eval

decision: `PHASE3AS_TRUE_1MIN_SIDECAR_CANARY_EVAL_COMPLETE`

## Counts

- input candidates: `1087`
- evaluated candidates: `1087`
- memory hits: `1007`
- errors: `0`
- panel rows: `778939`
- panel codes: `340`
- evaluated trade_time groups: `2400`

## Hard Rules

- cross-section key is `trade_time`, not `date`.
- labels are future 1min-bar returns by `code`.
- Phase3AR sidecars must already be PIT/cutoff materialized.
- search-memory hits are tagged, not treated as fresh alpha.
- X0/R3 remains read-only.

## Outputs

- rows: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3au_company_full_true1min_sharded_20260611\shard_01_lazy_as_v1\phase3as_true_1min_sidecar_canary_eval_rows.csv`
- errors: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3au_company_full_true1min_sharded_20260611\shard_01_lazy_as_v1\phase3as_true_1min_sidecar_canary_eval_errors.csv`
- summary: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3au_company_full_true1min_sharded_20260611\shard_01_lazy_as_v1\phase3as_true_1min_sidecar_canary_eval_summary.json`
