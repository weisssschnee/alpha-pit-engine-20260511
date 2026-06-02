# CN Data Feature Workspace Precommit Staging Plan - 2026-06-01

## Decision

Do not use `git add .` for this workspace.

The active working tree contains code, decision records, heavy runtime outputs, archived stale outputs, and historical research artifacts. The correct staging method is an explicit whitelist.

## Whitelist

Canonical whitelist:

- `runtime/manifests/cn_data_feature_workspace_git_stage_whitelist_20260601.txt`

Dry-run staging helper:

- `scripts/stage_cn_data_feature_workspace_20260601.ps1`

The helper is dry-run by default. It only stages when called with `-Execute`.

## Dry Run

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage_cn_data_feature_workspace_20260601.ps1
```

Expected behavior:

- validates the asset plan JSON,
- checks all whitelist paths exist,
- prints the exact stage list,
- does not modify Git index.

## Execute

Only after review:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stage_cn_data_feature_workspace_20260601.ps1 -Execute
git diff --cached --stat
```

## Include

The whitelist includes:

- mature-chain code changes,
- new app routes and runtime entrypoints,
- event-derived feature tests,
- compact decision records,
- survivor-attribution replay evidence for the 128-audited underutilized-field smoke,
- signal-vector registry-recluster evidence for the deployable survivor representatives,
- baseline-safe registry review queue for the provisional-new representatives,
- candidate `162` integrated registry and promotion-boundary decision record,
- promoted discovery-only baseline `162` with stable hash,
- book-readiness audit and shortlist for the `13` new discovery clusters,
- factor pack JSON metadata,
- field registry JSON,
- workspace key artifact manifest,
- run plan metadata,
- cleanup and asset-index reports.

## Exclude

The whitelist excludes by default:

- `archive/`,
- heavy Parquet datasets,
- selector audit CSV payloads,
- strict/replay row payloads,
- signal-vector cache,
- shared candidate pool runtime outputs,
- historical Phase3 report trees that are not part of the current data-feature workspace.

## Current Validation

Before creating this plan:

- key artifact manifest check returned zero missing artifacts,
- code compilation for key new runtime scripts passed,
- `tests/test_event_derived_features.py` passed with `PYTHONPATH=src`,
- the Git asset plan JSON parsed successfully.

## Remaining Review

Before a commit:

1. Review `git diff` for tracked code changes.
2. Decide whether old Phase3AA/Phase3AB runtime scripts should be included in this branch or left for a separate mature-chain commit.
3. Execute the staging helper only after the whitelist is accepted.
