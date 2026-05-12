# Phase2 Replay-Aware Slice Integration - 2026-05-11

## Experiment Record

- date: 2026-05-11
- experiment_id: 20260511_replay_aware_slice_integration_001
- objective: integrate replay-aware selector into true-limit bakeoff as a capped strict/replay slice while preserving R0 as the main control decision.
- status: completed smoke, medium launcher prepared
- mode: research
- decision: HOLD_RESEARCH. This is selector plumbing and smoke validation, not alpha promotion.

## Implementation

- Added optional CLI args to true-limit bakeoff:
  - `--replay-ranker-model-dir`
  - `--replay-aware-slice-n-per-variant`
- Default behavior is unchanged: replay-aware slice is disabled unless explicitly requested.
- Main bakeoff decision now uses `main_table_scope = r0_control_only`.
- Extra ranker-selected candidates are tagged:
  - `selection_policy = replay_aware_shadow_slice`
  - `strict_selection_role = replay_aware_shadow_slice_*`
- Pure RL remains diagnostic only and does not control main search.

## Smoke Validation

Command:

```text
$env:PYTHONPATH='src'; G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.stock_pit_true_limit_search_bakeoff_v2 --output-root runtime\next_stage_artifacts\phase2-true-limit-replayaware-smoke2-local-20260511 --candidate-budget 4 --target-window-count 3 --max-window 13 --beam-width 4 --max-beam-records 32 --strict-top-n-per-variant 1 --stratified-random-n-per-variant 0 --replay-ranker-model-dir data\models --replay-aware-slice-n-per-variant 1 --recent-quarter-window-count 1 --recent-warmup-days 30 --seed replayaware_smoke2_20260511
```

Smoke result:

- status: completed
- R0 selected: 8
- replay-aware selected: 8
- strict rows: 16
- policy counts: R0 control 8, replay-aware shadow slice 8
- replay-aware role counts: 8 `replay_aware_shadow_slice_exploit_ranker_top`
- replay-aware slice replay pass total: 8
- replay-aware slice non-gap replay pass total: 6

Important caveat:

- The smoke is deliberately tiny and uses only one recent-quarter window. It validates wiring and timestamp/tradability plumbing, not commercial signal strength.

## Prepared Medium Run

Launcher:

```text
launch_phase2_true_limit_replayaware_slice_medium_local_20260511.ps1
```

Default medium parameters:

- seeds: 1, 2, 3
- candidate budget: 64 per lane per seed
- strict: top4 + stratified random2 per lane
- replay-aware slice: 2 per lane
- evaluator: TDXGP true-limit, after-open, T+1, 10bps
- decision table: R0 control only
- slice table: replay-aware candidates only

## Bias Audit

- Factor: not a single tradable factor; this is selector/ranker integration.
- Frequency and horizon: daily, next 1d replay, after-open signal, T+1 execution.
- Cost model: 10bps inherited from true-limit bakeoff.
- Replay vs discovery: replay-aware slice is a selector experiment over generated candidates.
- Look-ahead guard: ranker scorer uses only pre-replay candidate features and persisted previous replay ranker models.
- Decision: HOLD_RESEARCH.

## Verification

```text
G:\PythonProject\.venv\Scripts\python.exe -m pytest tests\test_candidate_feature_builder.py tests\test_stock_pit_replay_ranker.py -q
G:\PythonProject\.venv\Scripts\python.exe -m py_compile src\our_system_phase2\services\stock_pit_replay_ranker.py src\our_system_phase2\services\stock_pit_true_limit_search_bakeoff_v2.py src\our_system_phase2\services\stock_pit_proof_suite.py src\our_system_phase2\runtime\stock_pit_true_limit_search_bakeoff_v2.py
git diff --check -- src\our_system_phase2\services\stock_pit_replay_ranker.py src\our_system_phase2\services\stock_pit_true_limit_search_bakeoff_v2.py src\our_system_phase2\services\stock_pit_proof_suite.py src\our_system_phase2\runtime\stock_pit_true_limit_search_bakeoff_v2.py tests\test_stock_pit_replay_ranker.py launch_phase2_true_limit_replayaware_slice_medium_local_20260511.ps1
```

Results:

- tests: 10 passed
- py_compile: OK
- diff check: OK
