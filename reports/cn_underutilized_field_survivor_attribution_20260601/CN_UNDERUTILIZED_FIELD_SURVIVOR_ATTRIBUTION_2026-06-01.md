# CN Underutilized Field Survivor Attribution

decision: `PASS_SURVIVOR_ATTRIBUTION_READY_FOR_REGISTRY_REVIEW`

## Counts

- audited: 128
- survivor_rows: 54
- raw_non_gap_pass: 42
- deployable_rows: 14
- deployable_unique_clusters: 14
- deployable_cluster_representatives: 14
- registry_rows: 149
- registry_exact_match_reps: 0
- registry_skeleton_match_reps: 2
- registry_high_symbolic_similarity_reps: 2

## Top Cluster

- signal_cluster_id: `cluster_021`
- raw-pass share: `0.047619047619047616`

## Source Lane Table

- cn_flow_liquidity_feature_layer: audited=47, raw=10, cost=6, deployable_clusters=2
- cn_research_feature_layer_v2: audited=25, raw=21, cost=7, deployable_clusters=7
- cn_underutilized_field_feature_layer: audited=50, raw=11, cost=9, deployable_clusters=5
- event_derived_feature_layer: audited=6, raw=0, cost=5, deployable_clusters=0

## Factor Lane Table

- capacity_normalized_flow: audited=4, raw=0, cost=1, deployable_clusters=0
- capacity_residual_activity: audited=7, raw=1, cost=3, deployable_clusters=1
- capacity_residual_flow: audited=1, raw=0, cost=1, deployable_clusters=0
- event_x_seal_flow: audited=7, raw=0, cost=1, deployable_clusters=0
- event_x_theme: audited=6, raw=0, cost=5, deployable_clusters=0
- flow_impulse: audited=6, raw=1, cost=2, deployable_clusters=0
- flow_relative_activity: audited=7, raw=1, cost=0, deployable_clusters=0
- fundamental_capacity_value: audited=2, raw=2, cost=0, deployable_clusters=0
- fundamental_quality: audited=7, raw=4, cost=2, deployable_clusters=2
- fundamental_risk_inverse: audited=7, raw=7, cost=3, deployable_clusters=3
- fundamental_size_residual: audited=4, raw=3, cost=2, deployable_clusters=2
- fundamental_x_activity: audited=7, raw=7, cost=4, deployable_clusters=4
- fundamental_x_event: audited=7, raw=7, cost=0, deployable_clusters=0
- fundamental_x_flow: audited=7, raw=6, cost=2, deployable_clusters=2
- limit_seal_flow: audited=7, raw=0, cost=1, deployable_clusters=0
- price_flow_divergence: audited=7, raw=3, cost=0, deployable_clusters=0

## Registry Review

- Registry comparison is symbolic/proxy only; this is not a fresh signal-vector recluster.
- exact representative matches: `0`
- skeleton representative matches: `2`
- high symbolic similarity representatives: `2`

## Boundary

- This is posthoc attribution over frozen replay128 rows.
- It does not change selection, replay, registry, or official baseline.
