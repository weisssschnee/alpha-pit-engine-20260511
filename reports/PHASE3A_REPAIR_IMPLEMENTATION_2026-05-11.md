# Phase3A Repair Implementation - 2026-05-11

## Objective

Move the next experiment from raw pass optimization to deployable unique alpha discovery.

Primary KPI:

- `cost/turnover deployable unique clusters / audited`

Secondary KPIs:

- `unique return-corr clusters / audited`
- `new clusters not covered by R0 / audited`
- `raw non-gap replay pass / audited`

Raw pass is diagnostic only.

## Implemented

- Added Phase3A service:
  `src/our_system_phase2/services/stock_pit_phase3_repair.py`
- Added runtime:
  `src/our_system_phase2/runtime/stock_pit_phase3_repair.py`
- Added medium launcher:
  `launch_phase3A_repair_medium_local_20260511.ps1`
- Added CEM elite duplicate downweight:
  `fast_reward / sqrt(structural_cluster_count)`
- Added future strict-row metadata passthrough:
  `phase3_budget_bucket`, `repair_policy`, parent metadata, replay decile, quarantine lane.
- Added `selection_pool_type` to R0 and replay-aware slice selection.

## Phase3A Design

Audit budget split:

- R0/CEM-led with cluster quota: 60%
- AST failure-aware repair: 20%
- replay-aware residual/calibration: 10%
- novelty/quarantine diagnostic: 10%

Cluster quota:

- max audited per return-corr cluster per seed: 4
- max audited per AST cluster per seed: 3
- raw pass credit per return-corr cluster: capped conceptually by unique-cluster KPI

AST repair policies:

- `duplicate_escape`
- `operator_sanitize`

Replay-aware residual:

- 40% top-decile exploit
- 60% score-decile calibration

Quarantine:

- non-gap forced, RX, typed random, unreached no longer compete as normal alpha lanes.
- They enter only diagnostic/hard-gated or repair-source roles.

## Smoke

Root:

`runtime\next_stage_artifacts\phase3A-repair-smoke2-local-20260511`

Parameters:

- candidate budget: 8
- strict audit budget: 16
- recent quarter windows: 1
- warmup days: 30

Smoke result:

- primary deployable unique clusters: 6 / 16
- unique return-corr clusters: 10 / 16
- raw non-gap replay pass: 14 / 16
- top cluster raw pass share: 0.214286
- R0/CEM-led bucket: 10 audited, 5 deployable clusters
- AST repair bucket: 3 audited, 2 deployable clusters
- replay-aware residual bucket: 2 audited, 0 deployable clusters

Smoke decision:

- wiring PASS
- not promotion evidence

## Verification

```text
G:\PythonProject\.venv\Scripts\python.exe -m py_compile src\our_system_phase2\services\stock_pit_phase3_repair.py src\our_system_phase2\runtime\stock_pit_phase3_repair.py src\our_system_phase2\runtime\stock_pit_phase3_repair_audit.py src\our_system_phase2\services\stock_pit_true_limit_search_bakeoff_v2.py src\our_system_phase2\services\stock_pit_proof_suite.py
G:\PythonProject\.venv\Scripts\python.exe -m pytest tests\test_candidate_feature_builder.py tests\test_stock_pit_replay_ranker.py -q
git diff --check -- src\our_system_phase2\services\stock_pit_phase3_repair.py src\our_system_phase2\runtime\stock_pit_phase3_repair.py src\our_system_phase2\runtime\stock_pit_phase3_repair_audit.py src\our_system_phase2\services\stock_pit_true_limit_search_bakeoff_v2.py src\our_system_phase2\services\stock_pit_proof_suite.py launch_phase3A_repair_medium_local_20260511.ps1
```

Results:

- py_compile: OK
- tests: 10 passed
- diff check: OK

## Next Run

Launcher:

`launch_phase3A_repair_medium_local_20260511.ps1`

Medium parameters:

- seeds: 1, 2, 3
- candidate budget: 64
- strict audit budget: 64 per seed
- KPI: deployable unique clusters per audited
