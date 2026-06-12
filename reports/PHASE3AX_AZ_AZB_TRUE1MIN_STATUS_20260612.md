# Phase3AX/AZ/AZB True 1min Status - 2026-06-12

## Scope

This status records completed company-machine true-1min evaluations pulled back and aggregated locally.

Hard boundary:

- Inputs are true 1min panels with real `trade_time`.
- This is research evidence only, not alpha proof.
- X0/R3 remains read-only.
- Memory hits are separated from fresh candidates.

## Completed Aggregates

### Phase3AX Capacity-Flow Refinement

Report root:

`reports/phase3ax_company_capacity_flow_refinement_aggregate_20260612`

Summary:

- Shards completed: 16/16.
- Unique candidates: 384.
- Fresh result rows: 24,576.
- Memory-hit rows: 0.
- Errors observed in aggregate: 0.

Strongest observed family:

- inverse capacity-normalized amount / float-share flow.
- flow volatility normalized by float-share.

Current interpretation:

The strongest signal is not a decorative formula family. It is a clean minute cross-sectional capacity/crowding proxy: heavy near-term traded amount relative to float-like capacity tends to rank as a negative 30-minute signal after inversion.

### Phase3AZ Light Broad Minute Pack

Report root:

`reports/phase3az_company_light_broad_minute_aggregate_20260612`

Summary:

- Shards completed: 16/16.
- Valid unique candidates in aggregate: 298.
- Fresh result rows: 19,008.
- Memory-hit rows: 64.

Known issue:

- The original AZ pack included invalid fields `m1_first*_range_pct`.
- Real fields are `m1_first5_range`, `m1_first15_range`, and `m1_first30_range`.
- Therefore AZ is retained as a broad reference only; clean opening-window conclusions should use AZB.

### Phase3AZB Corrected Opening-Window Pack

Report root:

`reports/phase3azb_company_opening_window_corrected_aggregate_20260612`

Summary:

- Shards completed: 16/16.
- Unique candidates: 144.
- Fresh result rows: 9,216.
- Memory-hit rows: 0.
- Errors observed in aggregate: 0.

Strongest observed family:

- first30 amount inverse.
- first15 amount inverse.
- first30 opening range inverse.
- opening range residualized against volume / first-window volume.

Current interpretation:

The corrected opening-window features are usable. The strongest pattern is again a crowding/exhaustion style effect: large opening money/range over the first 15-30 minutes tends to work better as an inverse 30-minute cross-sectional rank in this canary.

## Still Running

Phase3AY X0/core-family minute transfer is still running on company PC at the time this note was written:

- Completed shards already observed: 00-12, all `512/512`, `0 errors`, `0 memory_hits`.
- Current observed process: shard 13.
- Panel path contains `phase3aq_true_1min_formula_canary.parquet`; this is not old 1D kline.

## Next Validation Needs

Before treating any family as a serious candidate:

- aggregate Phase3AY after completion.
- compare AX/AZB top structures against existing memory and X0/core-family transfer output.
- run sign-stability and block/time-slice validation.
- run cost/turnover and tradability checks.
- build a deeper follow-up pack around capacity-normalized flow and opening-window exhaustion.

## Decision

Hold research. The completed lines are useful and appear structurally meaningful, but they are not deployable alpha proof.
