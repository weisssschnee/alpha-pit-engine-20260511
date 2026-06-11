# Phase3AU True 1min Shard02 Lazy Chain Acceptance

decision: `ACCEPT_CHAIN_SHARD02_LAZY_AS_SMOKE`

## Result

- job: `phase3au_company_shard02_lazy_chain_20260611`
- worker status: `done`
- exit code: `0`
- duration seconds: `670.257`
- AQ true 1min: passed
- AR no-wide sidecars: passed
- AS lazy sidecar eval: passed
- evaluated candidates: `1087/1087`
- errors: `0`
- candidate memory hits: `1007`
- panel rows read for signal evaluation: `771,422`
- panel codes: `340`
- evaluated trade_time groups: `2,400`
- panel direct read columns: `29`
- expression fields: `372`

## Cross-Shard Check

After adding shard02, the aggregate covers `shard_00`, `shard_01`, and `shard_02`.

Fresh robust top remains stable:

- `amount | final_float_market_cap`
- `amount | final_total_market_cap`
- capacity-normalized activity / flow variants

Memory-hit top remains dominated by sparse event/auction structures:

- `evt_limit_fengdan_rate_last_by_1130`
- `evt_limit_fengdan_money_last_by_1130`
- `evt_limit_fengdan_rate_last_by_0935`

Interpretation:

- The true `trade_time` 1min lazy sidecar route is reproducible across three 340-stock shards.
- Fresh structures are consistent but still smoke-level only.
- This is not alpha proof and does not modify X0/R3.

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_02_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_02_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- aggregate report: `reports/phase3au_company_full_true1min_sharded_20260611/PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md`
