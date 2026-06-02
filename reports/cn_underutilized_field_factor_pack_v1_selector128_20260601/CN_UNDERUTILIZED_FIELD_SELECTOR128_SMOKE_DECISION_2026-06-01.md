# CN Underutilized Field Selector128 Smoke Decision

decision: `PASS_UNDERUTILIZED_FIELD_PACK_AND_SELECTOR128_SMOKE_NO_REPLAY`

## Scope

- selector-only smoke; no replay/deployability claims
- X0/R3 read-only; no promotion

## Pack Coverage

- underutilized candidate count: 344
- flow/liquidity candidate count: 306
- enriched pool rows: 2137
- underutilized pack rows in enriched pool: 344 / 344
- factor fields used: 39
- missing derived fields: 0
- missing mature signal-vector fields: 0

## Selector128 Result

- selected total: 128
- selected source counts:
  - cn_flow_liquidity_feature_layer: 41
  - cn_underutilized_field_feature_layer: 21
  - mature/legacy sources: 66
- event bucket selected: 38
- research bucket selected: 24
- forbidden replay-label usage: false
- signal vector proxy requirement: true

## Selected Field-Lane Finding

- selected underutilized lanes include `fundamental_x_activity`, `event_x_seal_flow`, and `theme_activity_proxy`.
- flow pack selected lanes include `event_x_flow_liquidity` and `fundamental_x_flow`.
- capacity/price-flow lanes were vector-valid but not naturally selected in this 128 queue; this requires either larger selector or explicit family-balanced smoke, not a replay claim.

## Selector256 Status

- a 256-budget / pool-cap 1024 selector-only run exceeded the 60-minute interactive timeout.
- cache reached 815 vectors, but no selector artifacts were written.
- the residual process showed no cache growth after observation and was stopped to avoid wasting compute.
- treat selector256 as `TIMEOUT_NO_ARTIFACT`, not as field failure.
- next scale-up should use batched/family-balanced selector execution rather than one monolithic interactive run.
