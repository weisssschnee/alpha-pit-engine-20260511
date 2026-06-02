# CN Underutilized Field Candidate 162 Decision - 2026-06-01

decision: `PASS_CANDIDATE_BASELINE_162_SIGNAL_INTEGRATION`

## Summary

The replay128 underutilized-field survivor audit found `14` deployable representatives. Signal-vector registry reclustering held out `1` high-correlation duplicate and queued `13` provisional-new representatives.

This integration step placed the frozen `149` registry and the `13` queued representatives into one sampled signal-vector collision audit.

Result:

- existing registry: `149`
- queued representatives: `13`
- accepted new signal clusters: `13`
- rejected or review-required queued representatives: `0`
- candidate registry count: `162`
- queued edges above review threshold: `0`
- queued edges above high-correlation duplicate threshold: `0`
- zero vector count: `0`

## Promotion Interpretation

This is now strong enough to treat the `13` representatives as candidate new deployable signal clusters for the data-feature workspace.

The official baseline is not overwritten in-place. Instead, a candidate registry is written:

- `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json`

This keeps the mature `149` baseline intact while making the `162` candidate baseline available for review, book-readiness checks, and future official promotion.

## Accepted New By Source Lane

- `cn_research_feature_layer_v2`: `7`
- `cn_underutilized_field_feature_layer`: `4`
- `cn_flow_liquidity_feature_layer`: `2`

## Accepted New By Factor Lane

- `fundamental_x_activity`: `4`
- `fundamental_risk_inverse`: `3`
- `fundamental_quality`: `2`
- `fundamental_size_residual`: `2`
- `fundamental_x_flow`: `2`

## Held Out

The following survivor remains held out as a known/duplicate signal cluster:

- `cluster_070`
- factor lane: `capacity_residual_activity`
- nearest registry entry: `registry_147`
- sampled signal-vector correlation: `0.835079`

## Confirmed

- new data-feature layers generated replay-surviving deployable representatives;
- `13 / 14` deployable representatives remain distinct from the frozen `149` registry under sampled signal-vector integration;
- no accepted new representative collided internally with another queued representative;
- no canonical duplicate exists in the candidate registry;
- the candidate registry contains `162` representatives.

## Not Confirmed

- production readiness;
- minute execution / slippage / true capacity;
- book-level marginal value;
- official baseline mutation without explicit promotion.

## Next Gate

Use `cn_underutilized_field_candidate_162_registry_20260601.json` as the review target for:

1. book-readiness filtering of the `13` new representatives;
2. source-family concentration and turnover/cost stress;
3. optional official promotion record if the user wants to freeze `162` as the next discovery baseline.

## Artifacts

- `reports/cn_underutilized_field_global_cluster_integration_20260601/CN_UNDERUTILIZED_FIELD_GLOBAL_CLUSTER_INTEGRATION_2026-06-01.md`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/cn_underutilized_field_global_cluster_integration.json`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/global_integration_rows.csv`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/accepted_new_rows.csv`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/rejected_or_review_rows.csv`
- `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json`
