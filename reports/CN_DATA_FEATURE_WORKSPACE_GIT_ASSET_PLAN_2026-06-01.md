# CN Data Feature Workspace Git Asset Plan - 2026-06-01

## Scope

This plan separates the current data-feature workspace into:

- assets that should be reviewed for Git staging,
- local runtime outputs that should remain outside Git,
- historical artifacts that should not be deleted without a separate review,
- archived stale outputs that are already moved out of the active runtime tree.

No files were staged, committed, pushed, deleted, or moved by this plan.

## Workspace State

- branch: `feature/data-feature-workspace-20260531`
- head: `c47d107`
- cleanup policy: non-destructive archive only
- key artifact manifest: `runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json`
- key artifact missing count: `0`
- cleanup archive report: `reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.md`

## Stage As Code

These files define reusable chain logic or app routes and should be reviewed together:

- `.gitignore`
- `app.py`
- `src/our_system_phase2/services/candidate_pool_priority.py`
- `src/our_system_phase2/services/event_derived_features.py`
- `src/our_system_phase2/services/field_encoder.py`
- `src/our_system_phase2/services/phase3e_selectors.py`
- `src/our_system_phase2/services/phase3g_signal_vector_store.py`
- `src/our_system_phase2/services/phase3g_vector_selector.py`
- `src/our_system_phase2/services/real_market_validation.py`
- `src/our_system_phase2/services/stock_pit_proof_suite.py`
- `tests/test_event_derived_features.py`

New runtime entrypoints that should be reviewed as reusable tooling:

- `src/our_system_phase2/runtime/cn_build_augmented_signal_panel.py`
- `src/our_system_phase2/runtime/cn_build_research_signal_panel_v2.py`
- `src/our_system_phase2/runtime/cn_controlled_data_smoke.py`
- `src/our_system_phase2/runtime/cn_event_derived_feature_smoke.py`
- `src/our_system_phase2/runtime/cn_factor_pack_shared_pool_preflight.py`
- `src/our_system_phase2/runtime/cn_field_factor_pack.py`
- `src/our_system_phase2/runtime/cn_field_utilization_audit.py`
- `src/our_system_phase2/runtime/cn_flow_liquidity_factor_pack_v1.py`
- `src/our_system_phase2/runtime/cn_fundamental_controlled_smoke.py`
- `src/our_system_phase2/runtime/cn_fundamental_pit_feature_panel.py`
- `src/our_system_phase2/runtime/cn_research_factor_pack_v2.py`
- `src/our_system_phase2/runtime/cn_signal_vector_event_field_smoke.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_book_readiness_audit.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_batched_selector_smoke.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_factor_pack_v1.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_family_smoke.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_global_cluster_integration.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_promote_162_baseline.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_registry_recluster.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_registry_review_queue.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_replay_smoke_gate.py`
- `src/our_system_phase2/runtime/cn_underutilized_field_survivor_attribution.py`
- `src/our_system_phase2/runtime/cn_workspace_cleanup_archive.py`
- `src/our_system_phase2/runtime/cn_workspace_key_artifact_manifest.py`
- `src/our_system_phase2/runtime/phase3aa_apply_mature_g2_selector.py`
- `src/our_system_phase2/runtime/phase3aa_enrich_shared_candidate_pool.py`
- `scripts/stage_cn_data_feature_workspace_20260601.ps1`

## Stage As Decision Records

These are small decision records that explain the current data-feature line and should be included if the code is committed:

- `reports/CN_DATA_FEATURE_WORKSPACE_ACCEPTANCE_2026-05-31.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_KEY_ARTIFACTS_2026-06-01.md`
- `reports/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_PREFLIGHT_DECISION_2026-06-01.md`
- `reports/CN_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_DECISION_2026-06-01.md`
- `reports/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE48_2026-06-01.md`
- `reports/cn_underutilized_field_factor_pack_v1_replay_smoke48_20260601/cn_underutilized_field_replay_smoke48.json`
- `reports/CN_UNDERUTILIZED_FIELD_REPLAY128_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE128_2026-06-01.md`
- `reports/cn_underutilized_field_factor_pack_v1_replay_smoke128_20260601/cn_underutilized_field_replay_smoke128.json`
- `reports/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_survivor_attribution_20260601/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_2026-06-01.md`
- `reports/cn_underutilized_field_survivor_attribution_20260601/cn_underutilized_field_survivor_attribution.json`
- `reports/cn_underutilized_field_survivor_attribution_20260601/by_source_lane.csv`
- `reports/cn_underutilized_field_survivor_attribution_20260601/by_factor_lane.csv`
- `reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv`
- `reports/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_registry_recluster_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_2026-06-01.md`
- `reports/cn_underutilized_field_registry_recluster_20260601/cn_underutilized_field_registry_recluster.json`
- `reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/recluster_top3_registry_matches.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_signal_corr_pairs.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_components.csv`
- `reports/cn_underutilized_field_registry_review_queue_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_REVIEW_QUEUE_2026-06-01.md`
- `reports/cn_underutilized_field_registry_review_queue_20260601/cn_underutilized_field_registry_review_queue.json`
- `reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_queue.csv`
- `reports/cn_underutilized_field_registry_review_queue_20260601/registry_review_holdouts.csv`
- `runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json`
- `reports/CN_UNDERUTILIZED_FIELD_CANDIDATE_162_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/CN_UNDERUTILIZED_FIELD_GLOBAL_CLUSTER_INTEGRATION_2026-06-01.md`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/cn_underutilized_field_global_cluster_integration.json`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/global_integration_rows.csv`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/accepted_new_rows.csv`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/rejected_or_review_rows.csv`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/queued_pair_review_edges.csv`
- `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json`
- `reports/CN_UNDERUTILIZED_FIELD_DISCOVERY_BASELINE_162_PROMOTION_2026-06-01.md`
- `runtime/baselines/cn_discovery_baseline_162_20260601.json`
- `runtime/baselines/cn_discovery_baseline_162_20260601.sha256`
- `reports/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_DECISION_2026-06-01.md`
- `reports/cn_underutilized_field_book_readiness_20260601/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_2026-06-01.md`
- `reports/cn_underutilized_field_book_readiness_20260601/cn_underutilized_field_book_readiness.json`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_rows.csv`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_errors.csv`
- `reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.md`
- `reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.json`
- `reports/CN_DATA_FEATURE_WORKSPACE_GIT_ASSET_PLAN_2026-06-01.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_INDEX_2026-06-01.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_PRECOMMIT_STAGING_PLAN_2026-06-01.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_CLEANUP_HANDOFF_2026-06-01.md`

## Stage As Current Evidence Directories

These directories contain current reports from the 2026-05-31 to 2026-06-01 data/feature work. They are small enough to review, but CSV/Parquet payloads may be ignored by `.gitignore` and should not be forced unless intentionally selected.

- `reports/cn_field_utilization_audit_20260531/`
- `reports/cn_flow_liquidity_factor_pack_v1_20260601/`
- `reports/cn_flow_liquidity_factor_pack_v1_preflight_20260601/`
- `reports/cn_underutilized_field_factor_pack_v1_20260601/`
- `reports/cn_underutilized_field_factor_pack_v1_preflight_20260601/`
- `reports/cn_underutilized_field_family_smoke_20260601/`
- `reports/cn_underutilized_field_factor_pack_v1_selector128_20260601/`
- `reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/`
- `reports/cn_underutilized_field_survivor_attribution_20260601/`
- `reports/cn_underutilized_field_registry_recluster_20260601/`
- `reports/cn_underutilized_field_registry_review_queue_20260601/`
- `reports/cn_underutilized_field_global_cluster_integration_20260601/`
- `reports/cn_underutilized_field_book_readiness_20260601/`
- `reports/cn_research_factor_pack_v2_replay_smoke64_20260531/`

## Stage As Metadata

These are small metadata files that make the feature line reproducible:

- `runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json`
- `runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json`
- `runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json`
- `runtime/field_registry/cn_fundamental_field_registry_v1_20260531.json`
- `runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json`
- `runtime/manifests/cn_data_feature_workspace_git_asset_plan_20260601.json`
- `runtime/manifests/cn_data_feature_workspace_git_stage_whitelist_20260601.txt`
- `runtime/run_plans/cn_data_feature_workspace_run_plan_20260531.json`

## Keep Local, Do Not Stage By Default

These are runtime products or heavy evidence payloads. They should remain local unless a specific artifact is needed for a review package.

- `runtime/datasets/`
- `runtime/fundamental_features/`
- `runtime/phase3g_signal_vectors/`
- `runtime/cn_research_factor_pack_v2_*`
- `runtime/cn_flow_liquidity_factor_pack_v1_*`
- `runtime/cn_underutilized_field_factor_pack_v1_*`
- selector audit CSV files
- shared candidate pool JSON files
- strict/replay row payloads

## Historical, Review Before Staging

These directories predate the current data-feature workspace and should be treated as historical context, not current deliverables:

- `reports/phase3*_20260517*`
- `reports/phase3z45b_*`
- `reports/phase3z46_*`
- `reports/phase3z47_*`
- `reports/phase3z48_*`
- `reports/phase3z49_*`
- `reports/phase3ab_*`
- `runtime/registries/`
- `runtime/baselines/`
- `runtime/phase3p_locked_daily_forward/`

## Archived

Stale runtime outputs were moved under:

- `archive/workspace_cleanup_20260601/`

`archive/` is ignored and should not be staged.

## Current Decision

The workspace is now clean enough for code review, but not clean enough for a blind `git add .`.

Recommended next Git action, if requested:

1. Stage code and compact decision records first.
2. Stage JSON metadata deliberately.
3. Keep runtime payloads local.
4. Do not stage archive or heavy replay artifacts.
