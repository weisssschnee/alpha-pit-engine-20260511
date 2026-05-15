# Phase3H Selector-Only Dry Run Status

Date: 2026-05-15

## Decision

Decision: `HOLD_SELECTOR_ONLY_DRYRUN_EXECUTION`.

Implementation status:

- H0/H1/H2/H3 arm routing implemented.
- H2 has a distinct `signal_vector_turnover_calibrated_proxy` selector profile.
- H3 records `DUAL_BASELINE_ACCEPTED`, discovery baseline `134`, and selector vector baseline `122`.
- Selector-only dry-run audit tooling implemented.

Execution status:

- A local 4-arm selector-only dry run was attempted.
- Command shape: `stock_pit_phase3_repair --selection-only --ablation-arm Phase3H_* --seed 33 --candidate-budget 64 --strict-audit-budget 64`.
- The run was stopped after the shell timeout and subsequent progress inspection.
- Progress reached `ast_repair_ledger_built` for all four arms.
- No `phase3e_selector_audit.csv` was produced before stop.

## Finding

The current runner's `--selection-only` mode is not a lightweight selector-only path. It still performs the expensive candidate/stage1 generation path before freezing strict inputs.

This means:

- H0-H3 smoke preparation is blocked by engineering runtime, not by selector semantics.
- Running four arms independently repeats the same expensive candidate generation.
- Continuing this exact local path wastes compute.

## Required Fix Before Reattempt

Use one of these paths:

1. Shared candidate pool / cache path:
   - Generate candidate pools once.
   - Apply H0/H1/H2/H3 selectors against the same frozen pre-replay candidate pool.
   - Then run `phase3h_selector_only_dryrun_audit.py`.

2. Company-machine long detached path:
   - Launch H0/H1/H2/H3 as detached tasks.
   - Use status/progress files as success markers.
   - Still prefer shared candidate cache to avoid repeated work.

## Current Next Action

Do not run Phase3H smoke yet.

Next engineering step:

- Add or reuse a shared candidate-pool cache for Phase3H selector dry run, or run the existing heavy path on the company machine with a long timeout and explicit progress watcher.
