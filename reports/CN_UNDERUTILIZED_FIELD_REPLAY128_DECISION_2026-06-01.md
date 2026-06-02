# CN Underutilized Field Replay128 Decision - 2026-06-01

## Decision

decision: `PASS_REPLAY128_EXECUTION_GATE`

algorithmic_decision: `PASS_REPLAY128_HAS_DIVERSE_DEPLOYABLE_SIGNAL`

This remains a frozen replay smoke expansion, not an official promotion matrix.

## Input

- source: batched selector256 unique queue
- source rows: `215`
- frozen replay queue: `128`
- queue mode: `lane-balanced`
- selected factor lanes: `23`
- forbidden replay-field hits: `0`

## Replay Result

- strict rows: `128`
- strict proxy pass: `12`
- raw non-gap replay pass: `42`
- portfolio replay pass: `42`
- cost survive: `27`
- deployable clusters: `14`
- strict-proxy-pass unique signal clusters: `9`
- raw non-gap replay clusters: `36`
- replay summary top cluster share: `4.76%`
- top raw-pass signal cluster share: `25.0%`

## Source Attribution

Strict proxy pass by source lane:

- `cn_flow_liquidity_feature_layer`: `1`
- `cn_research_feature_layer_v2`: `5`
- `cn_underutilized_field_feature_layer`: `3`
- `event_derived_feature_layer`: `3`

Replay pass by source lane:

- `cn_flow_liquidity_feature_layer`: `10`
- `cn_research_feature_layer_v2`: `21`
- `cn_underutilized_field_feature_layer`: `11`

Cost-survive by source lane:

- `cn_flow_liquidity_feature_layer`: `6`
- `cn_research_feature_layer_v2`: `7`
- `cn_underutilized_field_feature_layer`: `9`
- `event_derived_feature_layer`: `5`

Strict proxy pass by factor lane:

- `event_x_seal_flow`: `1`
- `event_x_theme`: `3`
- `flow_impulse`: `1`
- `fundamental_risk_inverse`: `3`
- `fundamental_size_residual`: `2`
- `fundamental_x_activity`: `1`
- `limit_seal_flow`: `1`

## Interpretation

Replay128 strengthens the replay48 conclusion.

The underutilized-field layer produced non-trivial deployable signal after frozen selection, strict audit, portfolio replay, and signal clustering. The strongest contribution is still mixed across research/fundamental/event/underutilized fields rather than a single field family. This argues for survivor attribution and registry reclustering before any larger search.

## Boundary

Confirmed:

- frozen replay from selector256 can run without candidate regeneration,
- no replay/deployable/final-cluster fields are used in selection,
- the field layer produces deployable clusters with low concentration,
- event-derived fields still contribute at cost-survive and raw-pass levels.

Not confirmed:

- stable official matrix performance,
- long OOS robustness,
- book readiness,
- execution/capacity,
- production viability.

## Next Gate

Recommended next gate:

1. Run survivor attribution by formula skeleton, source lane, factor lane, and field family.
2. Recluster replay128 survivors against the current discovery registry.
3. Decide whether to replay the remaining unique selected rows or launch a larger shared-pool search.
