# Phase3AU True 1min Shard14 Lazy Chain Acceptance

decision: `ACCEPT_CHAIN_SHARD14_LAZY_AS_SMOKE`

## Result

- job: `phase3au_company_shard14_lazy_chain_20260612`
- worker status: `done`
- exit code: `0`
- duration seconds: `951.366`
- AQ true 1min: passed
- AR no-wide sidecars: passed
- AS lazy sidecar eval: passed
- evaluated candidates: `1087/1087`
- errors: `0`
- candidate memory hits: `1007`
- panel rows read for signal evaluation: `772,588`
- panel codes: `339`
- evaluated trade_time groups: `2,400`
- panel direct read columns: `29`
- expression fields: `372`

## Aggregate Update

After adding shard14, the aggregate covers:

- `shard_00`
- `shard_01`
- `shard_02`
- `shard_03`
- `shard_04`
- `shard_05`
- `shard_06`
- `shard_07`
- `shard_08`
- `shard_09`
- `shard_10`
- `shard_11`
- `shard_12`
- `shard_13`
- `shard_14`

Aggregate rows:

- candidate horizon rows: `65,220`
- fresh rows: `4,800`
- memory-hit rows: `60,420`

Interpretation:

- The true `trade_time` 1min lazy sidecar route is reproducible across fifteen shards.
- Fresh top remains capacity-normalized minute flow/activity.
- Memory-hit limit/auction structures remain separated from fresh structures.
- This is still smoke-level research evidence, not alpha proof or X0/R3 promotion evidence.

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_14_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_14_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- aggregate report: `reports/phase3au_company_full_true1min_sharded_20260611/PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md`
