# Phase3AU True 1min Shard01 Lazy Chain Acceptance

decision: `ACCEPT_CHAIN_SHARD01_LAZY_AS_SMOKE`

## What Changed

Shard01 initially failed in Phase3AQ because `_add_opening_window_features` forced a large pandas `sort_values(...).copy()` consolidation over roughly `19,008,152` minute rows. The hot path was changed to downcast minute numeric columns to `float32` and avoid the redundant deep copy before opening-window feature generation.

This is an engineering fix, not a reward change.

## Shard01 Result

- AQ passed after the memory hot-path fix.
- AR ran in `--no-augmented-panel` mode.
- AS used lazy sidecar loading with `--sidecar-manifest`.
- evaluated candidates: `1087/1087`
- errors: `0`
- candidate memory hits: `1007`
- panel rows read for signal evaluation: `778,939`
- panel codes: `340`
- evaluated trade_time groups: `2,400`
- panel direct read columns: `29`
- expression fields: `372`
- lazy sidecar loaded fields: `353`

## Cross-Shard Signal Check

Top fresh families were stable versus shard00:

- `amount | final_float_market_cap`
- `amount | final_total_market_cap`
- capacity-normalized activity / flow variants

Best shard01 fresh example:

- `cn_underutil_v1_capacity_normalized_activity_0115`
  - fields: `amount | final_float_market_cap`
  - horizon: `30m`
  - abs IC: `0.1353`
  - IC count: `2379`

Interpretation:

- The true 1min no-wide/lazy chain is now reproducible across at least two 340-stock shards.
- Fresh structures remain weaker than memory-hit event/auction structures.
- This is still not alpha proof or promotion evidence.

## Output Files

- runtime summary: `runtime/phase3au_company_full_true1min_sharded_20260611/shard_01_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`
- report summary: `reports/phase3au_company_full_true1min_sharded_20260611/shard_01_lazy_as_v1/phase3as_true_1min_sidecar_canary_eval_summary.json`

## Next Step

Batch the same lazy chain across additional shards only after adding a shard aggregation report. The next decision should be based on cross-shard consistency, not a single shard's top rows.
