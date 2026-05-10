# Alpha PIT Engine Export

This repository is a compact export of the Phase2 A-share alpha discovery work that is under our direct control.

It contains:

- Phase2 alpha search, validation, proof-suite, ledger-policy, and A-share state modules under `src/our_system_phase2`.
- The focused Phase2 runtime/test coverage in `tests/test_phase2_v21_runtime.py`.
- Recent proof and bias-audit reports under `reports/`.
- Company-PC proof launch/check artifacts under `runtime/next_stage_artifacts/`.
- Local TDX/TDXGP data-build scripts under `scripts/`.

It intentionally excludes:

- Raw market data files: `*.parquet`, `*.csv`, `*.db`, `*.sqlite`.
- Long-running shard outputs and search ledgers not needed for code review.
- Local credentials, caches, virtualenvs, and machine-specific IDE state.

## Current Research State

The latest true-limit validation uses `TDXGP GPJYVALUE(15)` as the preferred close-locked limit-up/down source:

- `value1 == 2`: close locked limit-up.
- `value1 == -2`: close locked limit-down.
- `rt_change_pct>=9.8` / `<=-9.8` remains only a fallback.

The current algorithm-level conclusion is `HOLD_RESEARCH`: UCB/reward memory has not yet proven superior to baseline under strict/replay validation. See:

- `reports/PHASE2_TDXGP_LIMIT_STATUS_AUDIT_2026-05-11.md`
- `reports/PHASE2_TDXGP_LIMIT_P0_P3_RESULTS_2026-05-11.md`

## Quick Checks

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_phase2_v21_runtime.py -k "tdxgp_limit_status or limit_state_masks or prepare_market_panel" -q
```
