# CN Data Feature Workspace Cleanup Handoff - 2026-06-01

## Status

Cleanup and asset organization are complete for the current data-feature workspace.

No Git staging, commit, push, or destructive deletion was performed during the final handoff.

## Workspace

- branch: `feature/data-feature-workspace-20260531`
- head: `c47d107`
- active whitelist paths: `48`
- current Git status entries: `106`
- modified tracked files: `11`
- untracked entries: `95`
- archive ignored by Git: `true`

The status count is expected because the workspace still contains many local reports and runtime artifacts. The important point is that staging is now controlled by an explicit whitelist rather than `git add .`.

## Key Files Added For Governance

- `reports/CN_DATA_FEATURE_WORKSPACE_GIT_ASSET_PLAN_2026-06-01.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_INDEX_2026-06-01.md`
- `reports/CN_DATA_FEATURE_WORKSPACE_PRECOMMIT_STAGING_PLAN_2026-06-01.md`
- `runtime/manifests/cn_data_feature_workspace_git_asset_plan_20260601.json`
- `runtime/manifests/cn_data_feature_workspace_git_stage_whitelist_20260601.txt`
- `scripts/stage_cn_data_feature_workspace_20260601.ps1`

## Validation

Latest validation results:

- key artifact check: `missing_key_artifacts = []`
- asset whitelist count: `48`
- asset whitelist missing paths: `0`
- full py_compile over whitelisted Python code: `pass`
- event-derived feature tests: `8 passed`
- staging helper dry run: `pass`
- Git index after dry run: empty staged diff

Test command used:

```powershell
$env:PYTHONPATH='src'
G:\PythonProject\.venv\Scripts\python.exe -m pytest tests\test_event_derived_features.py -q
```

## Preserved Current Results

Current feature-system proof objects remain in place:

- flow/liquidity factor pack: `runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json`
- underutilized field factor pack: `runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json`
- current system decision: `reports/CN_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_DECISION_2026-06-01.md`
- batched selector256 report: `reports/cn_underutilized_field_factor_pack_v1_batched_selector256_20260601/CN_UNDERUTILIZED_FIELD_BATCHED_SELECTOR256_2026-06-01.md`
- frozen replay smoke48 decision: `reports/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE_DECISION_2026-06-01.md`
- frozen replay smoke128 decision: `reports/CN_UNDERUTILIZED_FIELD_REPLAY128_DECISION_2026-06-01.md`
- survivor attribution decision: `reports/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_DECISION_2026-06-01.md`
- registry recluster decision: `reports/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_DECISION_2026-06-01.md`
- registry review queue: `runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json`
- candidate 162 registry: `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json`
- candidate 162 decision: `reports/CN_UNDERUTILIZED_FIELD_CANDIDATE_162_DECISION_2026-06-01.md`
- promoted discovery baseline 162: `runtime/baselines/cn_discovery_baseline_162_20260601.json`
- promoted discovery baseline 162 hash: `runtime/baselines/cn_discovery_baseline_162_20260601.sha256`
- new-cluster book-readiness decision: `reports/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_DECISION_2026-06-01.md`
- key artifact manifest: `runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json`

## Staging Rule

Do not use:

```powershell
git add .
```

Use dry run first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage_cn_data_feature_workspace_20260601.ps1
```

Execute only after review:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage_cn_data_feature_workspace_20260601.ps1 -Execute
git diff --cached --stat
```

## Local-Only Assets

These remain local by default:

- heavy datasets,
- shared candidate pools,
- selector audit CSVs,
- replay/strict row payloads,
- signal-vector runtime cache,
- archived stale runtime directories,
- historical Phase3 report trees not part of the current data-feature workspace.

## Next Technical Gate

Completed:

1. Attribute replay128 survivors by source lane, factor lane, formula skeleton, and field family.
2. Recluster replay128 survivors against the current discovery registry.

Next research gate:

1. Promote only the `13` provisional-new signal-space representatives into a registry review queue.
2. Run full global clustering before changing the official discovery baseline.
3. Use the candidate `162` registry for book-readiness review or explicit promotion.
4. Run book-level marginal audit for the `6` core book-readiness candidates.
5. Decide whether to replay the remaining unique selected rows or launch a larger shared-pool search.
