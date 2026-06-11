# Phase3AU True 1min Shard04 Lazy Chain Acceptance

decision: `ACCEPT_CHAIN_SHARD04_LAZY_AS_SMOKE`

## Result

- job: `phase3au_company_shard04_lazy_chain_20260611`
- worker status: `done`
- exit code: `0`
- duration seconds: `906.210`
- AQ true 1min: passed
- AR no-wide sidecars: passed
- AS lazy sidecar eval: passed
- evaluated candidates: `1087/1087`
- errors: `0`
- candidate memory hits: `1007`
- panel rows read for signal evaluation: `768,669`
- panel codes: `340`
- evaluated trade_time groups: `2,400`
- panel direct read columns: `29`
- expression fields: `372`

## Aggregate Update

After adding shard04, the aggregate covers:

- `shard_00`
- `shard_01`
- `shard_02`
- `shard_03`
- `shard_04`

Aggregate rows:

- candidate horizon rows: `21,740`
- fresh rows: `1,600`
- memory-hit rows: `20,140`

Fresh robust top remains:

- `amount | final_float_market_cap`
- `amount | final_total_market_cap`
- capacity-normalized flow/activity variants

Interpretation:

- The true `trade_time` 1min lazy sidecar route is reproducible across five 340-stock shards.
- The strongest fresh family is stable but still smoke-level, not promotion-grade alpha proof.
- Memory-hit event/auction structures remain separated from fresh structures.
- X0/R3 remains read-only.

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_04_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_04_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- aggregate report: `reports/phase3au_company_full_true1min_sharded_20260611/PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md`
