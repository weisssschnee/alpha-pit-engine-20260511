# Phase3AI Wide Search Checkpoint Launch

date: 2026-06-04

## Decision

Start wide-search checkpoint on the company machine only. Local machine is used for orchestration and status checks.

## CP1 / CP1b Finding

Initial CP1 and CP1b used `rx_typed_beam` with `candidates_per_shard=4096`.

Observed result:

- generated full slice: about 1.8k-2.1k candidates
- shard0 could contain candidates
- shards after shard0 were mostly empty because the shard stride exceeded the full slice

This was a sharding configuration error, not a hardware issue and not a full search-policy failure.

## CP1c Fix

`phase3ai_wide_cp1c_20260604_company` uses:

- company machine
- mature `phase3ab_launch_large_search` / `stock_pit_large_search_supervisor`
- `rx_typed_beam`
- successive halving
- search memory enabled
- `candidates_per_shard=256`
- `shard_count=8`
- `max_active=4`

Expected coverage:

- about 8 x 256 selected slots
- covers the observed rx typed-beam slice without wasting empty shards

## Early Checkpoint

After launch, first completed shards showed nonzero ledgers and validation:

- shard00: ledger 71, validation 64
- shard01: ledger 80, validation 64
- shard02: ledger 125, validation 64
- shard03: ledger 175, validation 64

Early top Sortino values in supervisor status included about 1.08, 1.55, 4.60, and 3.80. These are checkpoint diagnostics only, not promotion evidence.

## Boundaries

- no local heavy search
- no promotion from CP1c checkpoint alone
- no official X0/R3 modification
- aggregate and new-vs-baseline checks are required before interpreting alpha value
