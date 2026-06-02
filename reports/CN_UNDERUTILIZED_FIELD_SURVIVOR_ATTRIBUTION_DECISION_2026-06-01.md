# CN Underutilized Field Survivor Attribution Decision - 2026-06-01

## Decision

decision: `PASS_SURVIVOR_ATTRIBUTION_READY_FOR_REGISTRY_REVIEW`

scope: posthoc attribution over frozen replay128 rows; no selection or replay rerun.

## Core Result

- audited rows: `128`
- survivor rows: `54`
- raw non-gap replay pass: `42`
- deployable rows: `14`
- deployable unique clusters: `14`
- deployable cluster representatives: `14`
- top raw non-gap cluster share: `4.76%`

## Source Lane Attribution

Deployable unique clusters:

- `cn_research_feature_layer_v2`: `7`
- `cn_underutilized_field_feature_layer`: `5`
- `cn_flow_liquidity_feature_layer`: `2`
- `event_derived_feature_layer`: `0`

Interpretation:

- The best deployable contribution is still from research/fundamental-derived formulas.
- The new underutilized-field layer contributes directly: `5` deployable clusters.
- Flow/liquidity contributes fewer deployable clusters but remains useful.
- Standalone event-derived rows have cost-survive cases but no deployable rows in this replay128 attribution.

## Factor Lane Attribution

Primary deployable contributors:

- `fundamental_x_activity`: `4` deployable clusters
- `fundamental_risk_inverse`: `3`
- `fundamental_quality`: `2`
- `fundamental_size_residual`: `2`
- `fundamental_x_flow`: `2`
- `capacity_residual_activity`: `1`

Diagnostic but not currently deployable:

- `event_x_theme`: cost-survive signal but high-turnover / no non-gap replay pass
- `limit_seal_flow`: cost-survive signal but no deployable row
- `event_x_seal_flow`: cost-survive signal but no deployable row

## Registry Proxy Review

Using the complete 149 representative registry:

- registry rows loaded: `149`
- exact representative matches: `0 / 14`
- skeleton representative matches: `2 / 14`
- high symbolic-similarity representatives: `2 / 14`

This is symbolic/proxy review only, not a fresh signal-vector recluster. Still, the lack of exact matches means these deployable representatives are not simply copied expressions from the current 149 registry.

## Important Correction

Earlier replay smoke reports used `raw_pass_count` for strict proxy pass in the replay-gate attribution helper. The authoritative return-cluster raw pass count is the replay report's `raw_non_gap_replay_pass`, which is `42 / 128` here. This decision record uses the corrected terminology.

## Boundary

Confirmed:

- frozen replay128 survivor attribution is reproducible,
- deployable signal is multi-source and low concentration,
- underutilized field families add real deployable candidates,
- direct event/limit standalone remains diagnostic in this slice.

Not confirmed:

- official matrix stability,
- OOS book value,
- registry baseline update,
- production deployment,
- minute execution or capacity.

## Next Gate

Recommended next gate:

1. Perform a true signal-vector recluster of the 14 deployable representatives against the 149 registry.
2. Re-evaluate the remaining selector256 unique rows only if survivor novelty remains high.
3. Expand larger shared-pool search only after the recluster confirms new cluster value.

