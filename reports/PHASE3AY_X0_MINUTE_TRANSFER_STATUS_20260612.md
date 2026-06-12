# Phase3AY X0/Core-Family Minute Transfer Status - 2026-06-12

## Scope

Phase3AY tests whether existing X0 / core-family structures can transfer onto the true 1min panel.

Hard boundary:

- Input panel is true 1min with real `trade_time`.
- This is research evidence only, not production proof.
- X0/R3 remains read-only.

## Execution

The original company run completed shards 00-12 cleanly, then shard 13 stalled with no output. The stalled AY process was stopped and shards 13-15 were rerun with a chunked tail:

- 4 chunks per shard.
- 128 candidates per chunk.
- merged back into standard `shard_13_as_v2`, `shard_14_as_v2`, and `shard_15_as_v2` outputs.

Final aggregate:

- Shards completed: 16/16.
- Unique candidates: 512.
- Fresh result rows: 28,160.
- Memory-hit rows: 0.
- Top CSV: `reports/phase3ay_company_x0_minute_transfer_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv`.

## Main Finding

The old/core family does transfer to 1min better than expected when combined with minute liquidity/capacity context.

Top observed families:

- `ay_old_family_capacity_add`
- `ay_old_family_minute_base`
- `ay_old_family_amount_yuan_alias`
- `ay_old_family_capacity_residual`

The strongest top-row structure combines an old-family residual/cap style term with inverse capacity-normalized amount flow. This lines up with the independent Phase3AX finding that capacity-normalized flow is currently one of the strongest true-1min axes.

## Current Interpretation

Phase3AY does not prove that X0 itself is deployable at 1min. It does show that old daily/core structures should not be discarded. The most valuable path is not a literal X0 copy; it is a controlled transfer where old-family terms are interacted with minute liquidity/capacity exhaustion.

## Next Validation Needs

- Compare Phase3AY top rows against Phase3AX/AZB for redundancy.
- Run sign-stability and time-block validation.
- Run turnover/cost checks.
- Build a focused Phase3BA pack around old-family residual x capacity-flow x opening-window exhaustion.
