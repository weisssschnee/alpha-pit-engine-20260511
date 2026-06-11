# Phase3AU True 1min Shard03 Lazy Chain Acceptance

decision: `ACCEPT_CHAIN_SHARD03_LAZY_AS_SMOKE`

## Result

- job: `phase3au_company_shard03_lazy_chain_20260611`
- worker status: `done`
- exit code: `0`
- duration seconds: `964.689`
- AQ true 1min: passed
- AR no-wide sidecars: passed
- AS lazy sidecar eval: passed
- evaluated candidates: `1087/1087`
- errors: `0`
- candidate memory hits: `1007`
- panel rows read for signal evaluation: `770,948`
- panel codes: `340`
- evaluated trade_time groups: `2,400`
- panel direct read columns: `29`
- expression fields: `372`

## Aggregate Update

After adding shard03, the aggregate covers:

- `shard_00`
- `shard_01`
- `shard_02`
- `shard_03`

Aggregate rows:

- candidate horizon rows: `17,392`
- fresh rows: `1,280`
- memory-hit rows: `16,112`

Interpretation:

- The true `trade_time` 1min lazy sidecar route is reproducible across four 340-stock shards.
- Fresh top remains capacity-normalized minute flow/activity.
- Memory-hit top remains sparse limit/auction event structures.
- This remains smoke-level research evidence only; X0/R3 is read-only.

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_03_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_03_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- aggregate report: `reports/phase3au_company_full_true1min_sharded_20260611/PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md`
