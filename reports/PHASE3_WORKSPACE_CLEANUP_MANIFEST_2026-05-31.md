# Phase3 Workspace Cleanup Manifest

Date: 2026-05-31

Decision: `KEEP_CHAIN_ASSETS_ARCHIVE_ONEOFFS`

## Scope

This cleanup preserves the mature-chain implementation, final Phase3AB diagnostic outputs, run plans, and decision records. It archives interrupted, superseded, or one-off operational artifacts outside the Git worktree.

## Preserved In Worktree

Core implementation:

- `app.py`
- `src/our_system_phase2/runtime/phase3aa_run_mature_chain.py`
- `src/our_system_phase2/runtime/phase3aa_run_cached_mature_pool.py`
- `src/our_system_phase2/runtime/phase3aa_apply_mature_g2_selector.py`
- `src/our_system_phase2/runtime/phase3aa_enrich_shared_candidate_pool.py`
- `src/our_system_phase2/runtime/phase3aa_smoke_from_shared_selection.py`
- `src/our_system_phase2/runtime/phase3aa_asset_preflight.py`
- `src/our_system_phase2/runtime/phase3aa_cached_result_audit.py`
- `src/our_system_phase2/runtime/phase3ab_launch_large_search.py`
- `src/our_system_phase2/runtime/phase3ab_large_search_aggregate.py`
- `src/our_system_phase2/runtime/phase3ab_candidate_deep_validation.py`
- `src/our_system_phase2/runtime/phase3ab_deep_validation_compare.py`
- `src/our_system_phase2/runtime/phase3ab_r3_challenger_audit.py`
- `src/our_system_phase2/runtime/phase3ab_challenger_family_audit.py`

Run plans:

- `runtime/run_plans/phase3aa_mature_chain_event_g2_run_plan.json`
- `runtime/run_plans/phase3ab_large_daily_search_run_plan_20260529.json`
- `runtime/run_plans/phase3ab_deep_validation_run_plan_20260530.json`

Final reports:

- `reports/PHASE3AA_MATURE_CHAIN_EVENT_CANARY_2026-05-29.md`
- `reports/PHASE3Z46_49_EVENT_ALPHA_DIAGNOSTIC_DECISION_2026-05-29.md`
- `reports/phase3aa_asset_preflight_20260529/`
- `reports/phase3ab_large_search_aggregate_retry_20260530/`
- `reports/phase3ab_candidate_deep_validation_20260530_top80/`
- `reports/phase3ab_deep_validation_compare_20260530/`
- `reports/phase3ab_r3_challenger_audit_v3_official_gate_20260530/`
- `reports/phase3ab_challenger_family_audit_20260530/`
- `reports/phase3_event_alpha_validation_20260529/`
- `reports/phase3z46_reward_lane_dry_audit_20260529/`
- `reports/phase3z47_event_study_20260529_retry/`
- `reports/phase3z48_event_veto_gate_audit_20260529_retry/`
- `reports/phase3z49_event_long_selection_overlap_20260529_retry/`

## Archived Outside Worktree

Archive root:

- `G:\Project_V7_Rotation\workspace_archives\phase3_cleanup_20260531`

Archive manifest:

- `G:\Project_V7_Rotation\workspace_archives\phase3_cleanup_20260531\archive_manifest.csv`

Archived categories:

- superseded smoke reports
- failed or interrupted local R3 challenger outputs
- wrong-incumbent R3 challenger output
- retry-superseded Phase3AB aggregate
- one-off company-machine launcher/status/collection scripts

## Preserved Decisions

Phase3AB final status:

```text
HOLD_PHASE3AB_R3_CHALLENGER_DIAGNOSTIC_ONLY
```

Rationale:

- 9 recent/R3 challenger candidates remain diagnostic only.
- All 9 fail X0/R3 marginal overlay promotion.
- Pairwise R3 candidate correlation is too high for a new independent book.
- Same-family expansion should not continue without a marginal-aware reward redesign.

Official X0/R3 status:

```text
read_only_no_change
```

## Verification Required After Cleanup

- `python -m py_compile app.py` and key Phase3AA/AB runtime modules
- `pytest tests/test_event_derived_features.py -q`
- `app.py list` includes Phase3AA/AB routes

