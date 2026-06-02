# CN Data Feature Workspace Key Artifacts

manifest_id: `cn_data_feature_workspace_key_artifacts_20260601`

## Cleanup Policy

- mode: non_destructive_key_artifact_manifest
- reason: key reports and runtime artifacts are still active downstream inputs
- delete_policy: do_not_delete_or_move_key_artifacts_without_new_manifest
- archive_policy: only archive obvious temporary logs after source/result paths are no longer referenced

## Keep Directories

- `reports/cn_*_20260531`
- `reports/cn_*_20260601`
- `runtime/factor_packs`
- `runtime/field_registry`
- `runtime/datasets`
- `runtime/fundamental_features`
- `runtime/cn_research_factor_pack_v2_*`
- `runtime/cn_flow_liquidity_factor_pack_v1_*`
- `runtime/cn_underutilized_field_factor_pack_v1_*`
- `reports/cn_underutilized_field_*`
- `runtime/run_plans`

## Key Artifacts

| exists | bytes | path |
|---:|---:|---|
| True | 3600 | `reports/CN_DATA_FEATURE_WORKSPACE_ACCEPTANCE_2026-05-31.md` |
| True | 2192 | `reports/cn_field_utilization_audit_20260531/CN_FIELD_UTILIZATION_AUDIT_2026-05-31.md` |
| True | 730 | `reports/cn_flow_liquidity_factor_pack_v1_20260601/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_2026-06-01.md` |
| True | 1445 | `reports/cn_flow_liquidity_factor_pack_v1_preflight_20260601/CN_FACTOR_PACK_SHARED_POOL_PREFLIGHT_2026-05-31.md` |
| True | 4594 | `reports/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_PREFLIGHT_DECISION_2026-06-01.md` |
| True | 1752 | `reports/cn_underutilized_field_factor_pack_v1_20260601/CN_UNDERUTILIZED_FIELD_FACTOR_PACK_V1_2026-06-01.md` |
| True | 1608 | `reports/cn_underutilized_field_factor_pack_v1_preflight_20260601/CN_FACTOR_PACK_SHARED_POOL_PREFLIGHT_2026-05-31.md` |
| True | 1848 | `reports/cn_underutilized_field_family_smoke_20260601/CN_UNDERUTILIZED_FIELD_FAMILY_SMOKE_2026-06-01.md` |
| True | 1745 | `reports/cn_underutilized_field_factor_pack_v1_selector128_20260601/CN_UNDERUTILIZED_FIELD_SELECTOR128_SMOKE_DECISION_2026-06-01.md` |
| True | 1350 | `reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/CN_UNDERUTILIZED_FIELD_BATCHED_SELECTOR256_2026-06-01.md` |
| True | 20670 | `reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/cn_underutilized_field_batched_selector256.json` |
| True | 442691 | `reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/cn_underutilized_field_batched_selector256_selected_unique.csv` |
| True | 2241 | `reports/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE_DECISION_2026-06-01.md` |
| True | 1118 | `reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE48_2026-06-01.md` |
| True | 4328 | `reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/cn_underutilized_field_replay_smoke48.json` |
| True | 2819 | `reports/CN_UNDERUTILIZED_FIELD_REPLAY128_DECISION_2026-06-01.md` |
| True | 1178 | `reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE128_2026-06-01.md` |
| True | 8384 | `reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/cn_underutilized_field_replay_smoke128.json` |
| True | 3108 | `reports/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_DECISION_2026-06-01.md` |
| True | 2477 | `reports/cn_underutilized_field_survivor_attribution_20260601/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_2026-06-01.md` |
| True | 14084 | `reports/cn_underutilized_field_survivor_attribution_20260601/cn_underutilized_field_survivor_attribution.json` |
| True | 460 | `reports/cn_underutilized_field_survivor_attribution_20260601/by_source_lane.csv` |
| True | 1454 | `reports/cn_underutilized_field_survivor_attribution_20260601/by_factor_lane.csv` |
| True | 87747 | `reports/cn_underutilized_field_survivor_attribution_20260601/survivor_rows.csv` |
| True | 24084 | `reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv` |
| True | 3721 | `reports/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_DECISION_2026-06-01.md` |
| True | 4795 | `reports/cn_underutilized_field_registry_recluster_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_2026-06-01.md` |
| True | 2863 | `reports/cn_underutilized_field_registry_recluster_20260601/cn_underutilized_field_registry_recluster.json` |
| True | 8409 | `reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv` |
| True | 10452 | `reports/cn_underutilized_field_registry_recluster_20260601/recluster_top3_registry_matches.csv` |
| True | 2 | `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_signal_corr_pairs.csv` |
| True | 562 | `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_components.csv` |
| True | 1155 | `reports/cn_underutilized_field_registry_review_queue_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_REVIEW_QUEUE_2026-06-01.md` |
| True | 21590 | `reports/cn_underutilized_field_registry_review_queue_20260601/cn_underutilized_field_registry_review_queue.json` |
| True | 9520 | `reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_queue.csv` |
| True | 378 | `reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_holdouts.csv` |
| True | 21590 | `runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json` |
| True | 3506 | `reports/CN_UNDERUTILIZED_FIELD_CANDIDATE_162_DECISION_2026-06-01.md` |
| True | 1660 | `reports/cn_underutilized_field_global_cluster_integration_20260601/CN_UNDERUTILIZED_FIELD_GLOBAL_CLUSTER_INTEGRATION_2026-06-01.md` |
| True | 2329 | `reports/cn_underutilized_field_global_cluster_integration_20260601/cn_underutilized_field_global_cluster_integration.json` |
| True | 61270 | `reports/cn_underutilized_field_global_cluster_integration_20260601/global_integration_rows.csv` |
| True | 6789 | `reports/cn_underutilized_field_global_cluster_integration_20260601/accepted_new_rows.csv` |
| True | 2 | `reports/cn_underutilized_field_global_cluster_integration_20260601/rejected_or_review_rows.csv` |
| True | 2 | `reports/cn_underutilized_field_global_cluster_integration_20260601/queued_pair_review_edges.csv` |
| True | 178694 | `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json` |
| True | 1235 | `reports/CN_UNDERUTILIZED_FIELD_DISCOVERY_BASELINE_162_PROMOTION_2026-06-01.md` |
| True | 179582 | `runtime/baselines/cn_discovery_baseline_162_20260601.json` |
| True | 107 | `runtime/baselines/cn_discovery_baseline_162_20260601.sha256` |
| True | 3451 | `reports/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_DECISION_2026-06-01.md` |
| True | 3138 | `reports/cn_underutilized_field_book_readiness_20260601/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_2026-06-01.md` |
| True | 9734 | `reports/cn_underutilized_field_book_readiness_20260601/cn_underutilized_field_book_readiness.json` |
| True | 7779 | `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_rows.csv` |
| True | 25161 | `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json` |
| True | 2 | `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_errors.csv` |
| True | 3331 | `reports/CN_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_DECISION_2026-06-01.md` |
| True | 3307 | `reports/cn_research_factor_pack_v2_replay_smoke64_20260531/CN_RESEARCH_FACTOR_PACK_V2_REPLAY_SMOKE64_2026-05-31.md` |
| True | 127881361 | `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet` |
| True | 1493966 | `runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json` |
| True | 603259 | `runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json` |
| True | 685758 | `runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json` |
| True | 449785 | `runtime/field_registry/cn_fundamental_field_registry_v1_20260531.json` |
| True | 6320677 | `runtime/cn_research_factor_pack_v2_phase3aa_preflight_20260531/shared_candidate_pool_event_fund_enriched.json` |
| True | 7073739 | `runtime/cn_flow_liquidity_factor_pack_v1_phase3aa_preflight_20260601/shared_candidate_pool_event_fund_flow_enriched.json` |
| True | 7573316 | `runtime/cn_underutilized_field_factor_pack_v1_phase3aa_smoke_20260601/shared_candidate_pool_event_fund_flow_underutilized_enriched.json` |
| True | 4981 | `runtime/cn_underutilized_field_factor_pack_v1_selector128_20260601/selector_safe_v1/aa/phase3_selection_only_report.json` |
| True | 599755 | `runtime/cn_underutilized_field_factor_pack_v1_selector128_20260601/selector_safe_v1/aa/phase3e_selector_audit.csv` |
| True | 5004 | `runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/event_seal_flow/aa/phase3_selection_only_report.json` |
| True | 5089 | `runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/pure_flow_price/aa/phase3_selection_only_report.json` |
| True | 5096 | `runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/capacity_liquidity_cost/aa/phase3_selection_only_report.json` |
| True | 5093 | `runtime/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/selectors/fund_theme_activity/aa/phase3_selection_only_report.json` |
| True | 287167 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/selection/aa/phase3_strict_selection_inputs.json` |
| True | 100157 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/selection/frozen_replay_smoke_queue.csv` |
| True | 36126 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/replay/aa/phase3_repair_report.json` |
| True | 182214 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/replay/aa/phase3_strict_rows.json` |
| True | 764443 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/selection/aa/phase3_strict_selection_inputs.json` |
| True | 264124 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/selection/frozen_replay_smoke_queue.csv` |
| True | 55445 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_repair_report.json` |
| True | 489870 | `runtime/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/replay/aa/phase3_strict_rows.json` |
| True | 587502 | `runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector/aa/phase3_strict_selection_inputs.json` |
| True | 39910 | `runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa/phase3_repair_report.json` |
| True | 213030 | `runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa/phase3_strict_rows.json` |
