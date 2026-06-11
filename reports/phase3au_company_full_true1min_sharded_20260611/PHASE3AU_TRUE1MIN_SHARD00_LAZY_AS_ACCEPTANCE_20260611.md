# Phase3AU True 1min Shard00 Lazy AS Acceptance

decision: `ACCEPT_CHAIN_SHARD00_LAZY_AS_SMOKE`

## What Passed

- AQ full-universe local shard materialization completed for `16/16` shards.
- AQ total rows: `302,344,381`; stock count sum: `5,435`; each shard has real `trade_time`.
- Shard00 no-wide AR completed on company machine without building a giant augmented panel.
- Shard00 lazy AS completed on company machine with exit code `0`.
- X0/R3 remained read-only; no promotion decision is made here.

## Shard00 AS Result

- evaluated candidates: `1087/1087`
- errors: `0`
- panel rows read for signal evaluation: `775,781`
- panel codes: `340`
- original trade_time groups: `58,563`
- evaluated trade_time groups: `2,400`
- label read trade_time groups: `58,563`
- panel schema columns: `49`
- panel direct read columns: `29`
- expression fields: `372`
- lazy sidecar loaded fields: `353`
- lazy sidecar source files: `5`

Lane counts:

- `sidecar_context_formula`: `1002`
- `event_state_cutoff_canary`: `85`

Search-memory status:

- candidate memory hits: `1007`
- fresh candidates: `80`
- result rows marked fresh across horizons: `320`

## Key Finding

The engineering chain is now viable:

`true 1min AQ shard -> no-wide AR sidecars -> lazy AS evaluator`

The earlier failure mode was memory-bound wide materialization. The fix is to keep non-minute data as sidecars and load only the fields required by the candidate expressions.

The alpha result is more conservative:

- robust top ranks are still dominated by memory-hit event/auction structures
- no fresh candidate enters the robust top buckets
- strongest fresh structures are mostly capacity-normalized activity/flow, for example `amount | final_float_market_cap`

This is a valid chain acceptance, not an alpha promotion.

## Top Fresh Diagnostic Family

Examples from shard00:

- `cn_underutil_v1_capacity_normalized_activity_0115`
  - fields: `amount | final_float_market_cap`
  - horizon: `30m`
  - abs IC: `0.1351`
  - IC count: `2379`

- `cn_flow_liq_v1_capacity_normalized_flow_0087`
  - fields: `amount | final_float_market_cap`
  - horizon: `30m`
  - abs IC: `0.1351`
  - IC count: `2379`

- `phase3ae_brepair_v1_00358`
  - fields: `ctx_holder_close_price`
  - horizon: `30m`
  - abs IC: `0.1250`
  - IC count: `2388`

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_00_lazy_as_v1_retry1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- runtime rows: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_00_lazy_as_v1_retry1/phase3as_true_1min_sidecar_canary_eval_rows.csv`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_00_lazy_as_v1_retry1/phase3as_true_1min_sidecar_canary_eval_summary.json`

## Next Step

Run the same no-wide AR + lazy AS route across more shards. Do not return to a single full-universe wide augmented parquet.

Before large expansion, add shard aggregation so results are compared across shards instead of accepted from shard00 alone.
