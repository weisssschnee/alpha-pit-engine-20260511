# CN Underutilized Field Replay Smoke Decision - 2026-06-01

## Decision

decision: `PASS_REPLAY_SMOKE_EXECUTION_GATE`

algorithmic_decision: `PASS_REPLAY_SMOKE_HAS_DEPLOYABLE_SIGNAL`

This is a smoke gate, not a promotion-grade official matrix.

## Input

- source: batched selector256 unique queue
- source rows: `215`
- frozen replay queue: `48`
- queue mode: `lane-balanced`
- selected factor lanes: `23`
- replay labels in selection: `0 forbidden-field hits`

## Replay Result

- strict rows: `48`
- raw pass: `5`
- portfolio replay pass: `16`
- cost survive: `12`
- deployable clusters: `5`
- raw-pass unique signal clusters: `5`
- top cluster share: `6.25%` from replay summary
- top raw-pass signal cluster share: `20.0%`

## Raw Pass Attribution

Raw pass by source lane:

- `cn_flow_liquidity_feature_layer`: `1`
- `cn_research_feature_layer_v2`: `2`
- `cn_underutilized_field_feature_layer`: `1`
- `event_derived_feature_layer`: `1`

Raw pass by factor lane:

- `event_x_seal_flow`: `1`
- `event_x_theme`: `1`
- `flow_impulse`: `1`
- `fundamental_risk_inverse`: `1`
- `fundamental_size_residual`: `1`

## Interpretation

The broad underutilized-field layer survived the first frozen replay gate.

The useful signal is not concentrated in a single field family. It appears across event x seal-flow, event x theme, pure flow impulse, and fundamental risk/size residual families. This supports continuing with frozen replay expansion and source-lane attribution.

## Boundary

Confirmed:

- frozen selected queue can replay without candidate regeneration,
- no replay-label fields were used in selection,
- broad field families can produce deployable clusters after strict/replay/cluster,
- concentration is low in this smoke.

Not confirmed:

- official matrix performance,
- stable OOS performance,
- book-readiness,
- production readiness,
- execution or capacity.

## Next Gate

Recommended next gate:

1. Expand from replay48 to a frozen replay128 or full unique replay, still without candidate regeneration.
2. Attribute survivors by source lane, factor lane, and formula skeleton.
3. Recluster against the current discovery registry.
4. Only then decide whether to launch larger shared-pool search over these field families.

