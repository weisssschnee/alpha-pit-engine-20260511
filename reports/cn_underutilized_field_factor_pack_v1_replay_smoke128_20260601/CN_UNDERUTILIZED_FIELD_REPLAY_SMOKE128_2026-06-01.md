# CN Underutilized Field Replay Smoke Gate

decision: `PASS_REPLAY_SMOKE_EXECUTION_GATE`
algorithmic_decision: `PASS_REPLAY_SMOKE_HAS_DEPLOYABLE_SIGNAL`

## Counts

- source_unique_rows: 215
- frozen_queue_rows: 128
- forbidden_field_hit_count: 0
- selected_factor_lane_count: 23

## Replay Summary

- audit_count: 128
- deployable_clusters: 14
- top_cluster_share: 0.047619
- output_root: runtime\cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601\replay\aa

## Source Attribution

- strict_row_count: 128
- raw_pass_count: 12
- portfolio_replay_pass_count: 42
- cost_survive_count: 27
- unique_signal_clusters_raw_pass: 9
- top_signal_cluster_id: cluster_063
- top_signal_cluster_share: 0.25

## Raw Pass By Factor Lane

- event_x_seal_flow: 1
- event_x_theme: 3
- flow_impulse: 1
- fundamental_risk_inverse: 3
- fundamental_size_residual: 2
- fundamental_x_activity: 1
- limit_seal_flow: 1

## Boundary

- This is a frozen replay smoke gate, not a promotion-grade official matrix.
- Candidate generation and selector queue are frozen before replay.
- No replay/deployable/final-cluster labels are allowed in selection.
