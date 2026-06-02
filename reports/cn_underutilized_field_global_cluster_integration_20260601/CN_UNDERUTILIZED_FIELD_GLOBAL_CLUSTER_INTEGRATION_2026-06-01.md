# CN Underutilized Field Global Cluster Integration - 2026-06-01

decision: `PASS_CANDIDATE_BASELINE_162_SIGNAL_INTEGRATION`

## Scope

global signal-vector integration of frozen 149 registry plus 13 provisional-new underutilized-field representatives

## Counts

- existing_registry: `149`
- queued_new: `13`
- accepted_new_signal_clusters: `13`
- rejected_or_review_queued: `0`
- candidate_registry_count: `162`
- candidate_baseline_if_promoted: `162`
- queued_edges_ge_review_threshold: `0`
- queued_edges_ge_high_threshold: `0`
- zero_vector_count: `0`

## Accepted New By Source Lane

- cn_flow_liquidity_feature_layer: `2`
- cn_research_feature_layer_v2: `7`
- cn_underutilized_field_feature_layer: `4`

## Accepted New By Factor Lane

- fundamental_quality: `2`
- fundamental_risk_inverse: `3`
- fundamental_size_residual: `2`
- fundamental_x_activity: `4`
- fundamental_x_flow: `2`

## Boundary

This creates a candidate 162 registry. It does not overwrite the official 149 baseline.

## Outputs

- candidate_registry: `runtime\registry_review\cn_underutilized_field_candidate_162_registry_20260601.json`
- global_integration_rows_csv: `reports\cn_underutilized_field_global_cluster_integration_20260601\global_integration_rows.csv`
- accepted_new_rows_csv: `reports\cn_underutilized_field_global_cluster_integration_20260601\accepted_new_rows.csv`
- rejected_or_review_rows_csv: `reports\cn_underutilized_field_global_cluster_integration_20260601\rejected_or_review_rows.csv`
- queued_pair_review_edges_csv: `reports\cn_underutilized_field_global_cluster_integration_20260601\queued_pair_review_edges.csv`
