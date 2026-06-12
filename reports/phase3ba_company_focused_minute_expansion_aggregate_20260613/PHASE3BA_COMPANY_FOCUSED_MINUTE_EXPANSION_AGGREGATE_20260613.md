# Phase3BA Company Focused Minute Expansion Aggregate

decision: `HOLD_RESEARCH_NOT_ALPHA_PROOF`

## Scope

- run root: `runtime/phase3ba_company_focused_minute_expansion_20260612`
- report root: `reports/phase3ba_company_focused_minute_expansion_aggregate_20260613`
- input: true `trade_time` 1min shard outputs only
- official X0/R3: read-only, not modified
- evaluator: `phase3as-true-1min-sidecar-canary-eval`
- aggregate command: `app.py phase3au-shard-aggregate --min-ic-count 450`

## Execution

- company task: `job_20260612_235329_e18787`
- status: completed with `exit_code=0`
- parallel chunks completed: 67
- merged shards: 16 / 16
- merged rows per shard: 3072
- shard errors: 0
- memory hits: 0

## Aggregate

- candidate result rows: 49152
- unique candidates: 768
- unique expressions: 768
- fresh result rows: 49152
- robust top rows: 3072
- memory-hit top rows: 0

## Main Finding

The strongest Phase3BA family is not standalone opening-window morphology.
The strongest family is `ba_ay_ax_add`, which combines the old/core minute
transfer axis with capacity-normalized flow:

```text
 old/core transfer
+ amount / market-cap or float-cap flow
+ vwap-style minute structure
```

The top candidate is:

```text
phase3ba_focused_minute_expansion_00296
horizon: 30 minutes
fields: amount | final_total_market_cap | vwap
mean_ic_abs_mean: 0.171042
mean_ic_mean: 0.055491
shard_coverage: 16
```

The second stable family is `ba_triple_add`, where opening-window features
join old/core transfer and capacity-flow. This suggests opening-window data is
currently more useful as an intensifier/interactor than as a standalone alpha
backbone.

## Source Attribution

Top source lanes by mean absolute IC:

```text
ba_ay_ax_add:              0.126310
ba_triple_add:             0.125517
ba_ax_resid_opening:       0.117542
ba_ay_resid_opening:       0.111570
ba_ay_azb_add:             0.103067
ba_ay_resid_ax:            0.100294
ba_triple_interaction:     0.099488
```

## Integrity Note

The first local aggregate pass incorrectly selected per-chunk outputs over
merged shard outputs when both existed in the same run root. The aggregator was
patched to prefer merged `shard_XX_as_vN` directories over
`shard_XX_chunk_YY_as_vN` directories. The corrected aggregate now reports
768 unique candidates and 49152 result rows.

## Next Research Step

Use Phase3BA as a parent for a narrower follow-up:

1. Focus on `ba_ay_ax_add` and `ba_triple_add`.
2. Test polarity, horizon stability, and overlap versus AX/AZB/AY parents.
3. Build a smaller next pack around 30-minute capacity-flow transfer, not a
   generic wide fresh search.
4. Keep X0/R3 read-only until marginal and novelty audits pass.

