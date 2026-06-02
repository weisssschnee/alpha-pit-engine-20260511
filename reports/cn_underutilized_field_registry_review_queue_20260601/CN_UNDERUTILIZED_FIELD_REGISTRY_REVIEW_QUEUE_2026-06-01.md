# CN Underutilized Field Registry Review Queue - 2026-06-01

decision: `PASS_REGISTRY_REVIEW_QUEUE_READY`

## Scope

candidate registry-review queue for replay128 underutilized-field provisional-new signal-space representatives; does not mutate official baseline

## Counts

- recluster_rows: `14`
- queued_provisional_new: `13`
- known_duplicate_holdout: `1`
- review_band_holdout: `0`
- queue_canonical_hits_in_registry: `0`
- queue_internal_duplicate_canonical_count: `0`
- candidate_discovery_baseline_if_all_queue_survives: `162`

## Queue By Source Lane

- cn_flow_liquidity_feature_layer: `2`
- cn_research_feature_layer_v2: `7`
- cn_underutilized_field_feature_layer: `4`

## Queue By Factor Lane

- fundamental_quality: `2`
- fundamental_risk_inverse: `3`
- fundamental_size_residual: `2`
- fundamental_x_activity: `4`
- fundamental_x_flow: `2`

## Holdouts

- `cluster_070` `known_or_duplicate_signal_cluster` corr=`0.835079` nearest=`registry_147` factor=`capacity_residual_activity`

## Boundary

This queue is not an official baseline update. It is an input to the next global-cluster integration gate.
