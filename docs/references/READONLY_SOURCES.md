# Readonly Sources

This repository may read from the following sources, but must not modify or absorb them into the active code layer.

## 1. AlphaCFG Official Source

- role: `official baseline source`
- mode: `read-only`
- local snapshot: `G:\Project_V7_Rotation\_work\alphacfg_official_snapshot_20260420`
- gate evidence: `G:\Project_V7_Rotation\reports\repro\alphacfg\source_snapshot.md`
- purpose:
  - official object boundaries
  - official benchmark protocol reference
  - grammar-aware search reference implementation

## 2. Local AlphaCFG-Style Candidate Baseline Freeze

- role: `local execution baseline`
- mode: `read-only`
- freeze evidence: `G:\Project_V7_Rotation\reports\repro\alphacfg\local_candidate_baseline_freeze.md`
- selected summary: `G:\Project_V7_Rotation\_work\alphacfg_local_rich_run_deeper_seed11\summary.json`
- wider-window evaluation: `G:\Project_V7_Rotation\_work\alphacfg_rich_pool_eval.json`
- purpose:
  - provide an existing baseline result that Our System can ingest
  - provide candidate expressions, weights, and evaluation evidence

## 3. A5 Archive Recovered Source

- role: `historical recovered source`
- mode: `read-only`
- archive code path: `G:\Project_V7_Archive_20260412\alpha_factory_backup_20260412\alphagpt_a5`
- archive reports path: `G:\Project_V7_Archive_20260412\alpha_factory_backup_20260412\reports\alphagpt_a5`
- gate evidence: `G:\Project_V7_Rotation\reports\repro\a5\integration_readiness.md`
- purpose:
  - historical implementation evidence
  - tests, reports, and interface reference

## Explicit Prohibitions

This repository must not:

- modify the AlphaCFG snapshot
- copy AlphaCFG code into Our System as the main implementation layer
- restore A5 into mainline
- copy the archived A5 package into this source tree

