# CN Underutilized Field System Smoke Decision

decision: `PASS_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_NO_REPLAY`

## Scope

- This is a system-entry and selector-only smoke.
- It does not claim replay pass, deployability, production readiness, or alpha effectiveness.
- X0/R3 and locked shadow objects remain read-only.

## Confirmed

- A broad underutilized-field pack was built with 344 candidates.
- The existing flow/liquidity pack was regenerated with 306 safe-division candidates.
- Combined enriched shared pool contains 2137 candidates.
- Underutilized pack integration is complete: 344 / 344 rows in shared pool.
- The pack uses 39 fields with zero missing derived-panel fields and zero missing mature signal-vector fields.
- Family-balanced signal-vector smoke passed:
  - factor rows: 650
  - sampled rows: 232
  - vector ok rows: 232
  - operator pathology rows: 0
  - factor lanes sampled: 23
- Mature G2 selector-only 128 smoke passed:
  - selected total: 128
  - `cn_flow_liquidity_feature_layer`: 41 selected
  - `cn_underutilized_field_feature_layer`: 21 selected
  - event bucket selected: 38
  - research bucket selected: 24
  - forbidden replay-label usage: false
  - signal vector proxy requirement: true
- Batched selector256 smoke passed:
  - shard count: 4
  - combined selected rows: 256
  - combined unique selected rows: 215
  - all shards completed
  - forbidden replay-label usage: false for every shard
  - signal vector proxy requirement: true for every shard

## Covered Field Axes

- flow ratio / impulse / volatility
- price-flow confirmation / divergence / correlation
- capacity-normalized and capacity-residual activity
- Amihud-style liquidity cost proxy
- limit seal flow and seal-to-amount
- event x seal-flow interaction
- event x flow-liquidity interaction
- theme activity proxy via `plate_score`
- fundamental x activity and fundamental capacity value

## Not Yet Confirmed

- Replay survival.
- Strict cost-adjusted performance.
- New signal cluster contribution.
- OOS/regime marginal value.
- Production or shadow eligibility.

## Scale Finding

- 128 selector-only is now a valid medium smoke.
- 256 monolithic selector-only timed out after the 60-minute interactive window with no artifacts, despite 815 cached vectors.
- Batched/family-balanced selector256 succeeded and should be the large-coverage path.
- A single interactive selector process is not the right scale-up route for this field-pack layer.

## Batched Selector256 Coverage

- selected unique source lanes:
  - `cn_flow_liquidity_feature_layer`: 89
  - `cn_underutilized_field_feature_layer`: 73
  - `cn_research_feature_layer_v2`: 47
  - `event_derived_feature_layer`: 6
- selected factor lanes include:
  - `event_x_flow_liquidity`: 28
  - `fundamental_quality`: 18
  - `fundamental_x_event`: 17
  - `price_flow_divergence`: 17
  - `fundamental_x_flow`: 16
  - `flow_relative_activity`: 15
  - `limit_seal_flow`: 12
  - `fundamental_x_activity`: 12
  - `event_x_seal_flow`: 12
  - capacity and liquidity-cost lanes are represented but smaller.

## Next Gate

Run one of:

1. `batched selector256 unique frozen queue -> replay smoke` if the goal is early performance evidence.
2. `batched selector512` if the goal is broader field-family coverage before replay.

Do not run replay from an unfinished selector256 attempt.
