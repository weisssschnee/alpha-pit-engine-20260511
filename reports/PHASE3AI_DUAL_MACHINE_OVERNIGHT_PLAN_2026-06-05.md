# Phase3AI Dual-Machine Overnight Plan

date: 2026-06-05

## Objective

Run a guarded overnight wide search on both company and local machines while preventing empty-ledger runs and reward-hacking interpretation.

## Machines

- company machine: primary heavy compute, max active workers 4
- local machine: secondary compute, max active workers 2

## Guardrails

- Each leg runs a canary first.
- Main leg runs only if canary evaluated count clears a minimum threshold.
- All outputs are discovery/checkpoint only.
- No X0/R3 change.
- No candidate promotion from cheap checkpoint metrics.
- Strong-family hits require full-history, OOS/regime, cost/turnover, and new-vs-baseline audit.

## Company Legs

1. `c3_rx_deep_broad`
   - rx typed beam
   - broad/deep continuation
   - 96 shards x 64 stride

2. `c4_forward_fresh`
   - forward-first generator
   - fresh generator family countercheck
   - 96 shards x 96 stride

3. `c5_rx_orthogonal`
   - rx typed beam
   - stronger orthogonal/family pressure
   - 128 shards x 48 stride

4. `c6_forward_lowcap`
   - forward-first
   - broader windows and more exploratory routing

5. `c7_rx_gap_family_deep`
   - rx typed beam
   - deeper gap/volatility-family continuation with wider window coverage
   - 160 shards x 48 stride

6. `c8_forward_extended`
   - forward-first
   - extended fresh generator pass
   - 160 shards x 128 stride

7. `c9_rx_ultra_orthogonal`
   - rx typed beam
   - stronger family cap pressure and wider beam
   - 160 shards x 40 stride

## Local Legs

1. `l1_forward_broad`
2. `l2_rx_low_stride`
3. `l3_forward_orthogonal`
4. `l4_rx_deep_broad`
5. `l5_forward_extended`

Local legs use lower active worker count to avoid destabilizing the desktop.

## Acceleration Contract

- `use_fast_context`: required through mature launcher.
- `successive_halving`: required.
- `parallel_workers`: 1 per shard.
- `NUMEXPR_MAX_THREADS`: company 8, local 6.
- `OMP_NUM_THREADS`: 1.
- `MKL_NUM_THREADS`: 1.
- search memory is enabled, but root expansion is capped to avoid Windows command-line overflow:
  - company: 32-48 previous roots, 16-24 reward roots
  - local: 18-32 previous roots, 8-16 reward roots
- `reward_exploration_share` is capped at 0.80 in launch configs, matching policy limits.

## Expected Checkpoints

- `D:\p3ai\overnight_company_20260605_r2\overnight_status.jsonl`
- `G:\Project_V7_Rotation\runtime\phase3ai_overnight_local_20260605_r2\overnight_status.jsonl`

## Decision After Completion

Aggregate by:

- total evaluated
- non-empty ledger ratio
- top family concentration
- new expressions vs prior checkpoints
- source generator mode
- top candidates by Sortino/return/turnover

Do not modify reward/search axis before this aggregate.
