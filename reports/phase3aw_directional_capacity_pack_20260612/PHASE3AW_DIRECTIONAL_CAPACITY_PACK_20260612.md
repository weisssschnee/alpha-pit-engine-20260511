# Phase3AW Directional Capacity Pack

created_at: 2026-06-12T04:43:18.641852+00:00

## Decision

PHASE3AW_DIRECTIONAL_CAPACITY_PACK_READY

## Purpose

Phase3AV showed a stable negative IC family in capacity-normalized minute flow. This pack flips those stable expressions with `Neg(...)` so Phase3AS can test whether the effect becomes a positive long signal on the same true 1min shards.

## Summary

- candidates: 96
- min_shard_count: 16
- min_abs_ic: 0.09
- require_negative_ic: True
- X0/R3: read-only
- data scope: true trade_time 1min validation only

## Limits

- This is not replay/cost proof.
- This is not a promotion object.
- If the inverted family passes, it still needs turnover, cost, placebo, and new-vs-149 checks.
