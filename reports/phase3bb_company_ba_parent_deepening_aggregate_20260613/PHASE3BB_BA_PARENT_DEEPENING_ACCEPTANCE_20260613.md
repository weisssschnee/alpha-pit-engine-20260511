# Phase3BB BA-Parent True 1min Deepening Acceptance

## Status

Phase3BB company retry completed and merged successfully on 2026-06-13.

This is a true 1min cross-section research aggregate. It uses real `trade_time` shard panels from `phase3au_company_full_true1min_sharded_20260611`; it is not an old 1D/TDX run and does not modify X0/R3.

## Execution Result

- Remote task: `job_20260613_114653_1623d1`
- Initial failed chunks retried: `14`
- Completed chunks after retry: `96 / 96`
- Merged shards: `16 / 16`
- Merged shard version: `shard_##_as_v2`
- Candidate result rows: `49,152`
- Unique candidates: `768`
- Unique expressions: `768`
- Memory-hit rows: `0`
- Error rows after retry: `0`

The original failures were pandas/numpy memory allocation failures in early chunks, not missing fields, old data paths, or expression syntax failures. A single-worker retry completed all bad chunks.

## Top Result

Top robust candidate:

- candidate: `phase3ba_focused_minute_expansion_00269`
- horizon: `30`
- lane: `sidecar_context_formula`
- factor lane: `ba_ay_ax_add`
- shard coverage: `16`
- mean abs IC: `0.1712189612649549`
- mean IC: `0.05085478976073222`
- mean IC count: `2037`

Relative to Phase3BA top (`~0.171042` mean abs IC), Phase3BB is a small local improvement, not a new effect family breakthrough.

## Lane Reading

Best lanes by top mean abs IC:

| factor_lane | candidates | top_abs_ic | reading |
| --- | ---: | ---: | --- |
| `ba_ay_ax_add` | 40 | 0.171219 | strongest stable parent combination |
| `ba_triple_add` | 58 | 0.168294 | useful intensifier, slightly below top |
| `ba_ay_resid_opening` | 88 | 0.159576 | opening-window residual contributes but is not the main backbone |
| `ba_ay_azb_add` | 88 | 0.159543 | opening add helps but does not beat BA parent |
| `ba_ax_azb_add` / inverse | 54 | 0.156402 | capacity plus opening remains secondary |

The result confirms BA's prior interpretation: capacity-flow plus old/minute-transfer structure is the strongest current family; opening-window features mainly act as secondary interaction or residual adjustment.

## Acceleration Note

The retry succeeded by reducing concurrency, but this is not the final engineering answer. Phase3AS still relies heavily on pandas groupby/rank/rolling inside the expression evaluator. `numba` is installed locally, but the active true 1min evaluator does not yet use a numba backend.

Recommended next engineering lane:

- `Phase3BC`: implement a numba-backed true 1min evaluator canary for high-frequency operators:
  - `CSRank`
  - `ZScore`
  - `Mean`
  - `Delta`
  - `Mom`
- Run parity checks against the current pandas evaluator before using it for large search.

## Decision

`HOLD_RESEARCH`.

Phase3BB is accepted as a completed true 1min deepening pass. It should feed stability and parent-family analysis, but it is not production proof and cannot promote or modify X0/R3.

