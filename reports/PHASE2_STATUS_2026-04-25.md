# Phase2 Status - 2026-04-25

## Executive State

Active work is Phase2 generation/runtime, despite the historical worktree name
`our_system_phase1_repo`.

Latest validated artifact:

- `runtime/next_stage_artifacts/phase2-budget-77cb6c38b3`
- final selected run: `phase2-df54168c41`
- selected budget: `3`

The current validated result is not a tradable-alpha claim. It is a prototype
search-system result showing that the Phase2 runtime can preserve non-score
exploration while passing the retained-yield floor under the current synthetic
evaluator.

## What Changed In The Last Work Wave

Nine fixes were landed after session recovery:

1. Generated field tokens are now registry-safe.
   - Commit: `c693659 Guard Phase2 generated field tokens`
   - Removed nonce/id suffixes from executable field names.
   - Added `canonical_field_name()` in the field encoder.
   - Regression test checks generated and archive-aware synthesis expressions
     only use registered raw, alias, or derived fields.

2. Target-aware pre-screen is now dominance-aware for occupied cells.
   - Commit: `f67f87d Skip non-dominating prescreen candidates`
   - Existing archive dominance rules were not relaxed.
   - Pre-screen now predicts whether an existing-cell candidate can beat the
     incumbent dominance tuple before spending evaluator budget.
   - Score lane remains excluded from this pre-screen to protect non-score
     exploration.

3. Score lane now refreshes saturated parents without reintroducing duplicate
   or non-dominating score candidates.
   - Score lane still does not participate in target-aware non-score
     pre-screen.
   - When the current score parents only lead to already-seen or predicted
     non-dominating occupied-cell variation, parent selection rotates to score
     frontier parents with productive unseen variation.
   - Score variation candidate pools now skip predictions that cannot open a
     new cell or dominate the predicted incumbent cell.

4. Saturated uncertainty and bridge lanes now have coverage-refresh synthesis.
   - Coverage refresh targets missing behavior cells during high-budget
     continuations after lane stall or occupied-cell pressure.
   - Score lane remains outside this non-score refresh path.
   - The first explicit target-cell probes cover observed reachable bottlenecks:
     `high_momentum|high_size|transition|high_vol|mean_revert` and
     `low_momentum|high_size|stable|high_vol|trend`.
   - Target selection prioritizes behavior cells with explicit probes before
     falling back to the broader 32-cell grid.

5. Coverage refresh now has parent-aware reachability survey and seed insertion.
   - Missing target cells are surveyed through explicit probes, archive-aware
     synthesis, parent-directed variation, and behavior-guided crossover before
     budget is spent.
   - Exact reachable expressions are inserted at the front of the refresh pool
     as `reachability_seed` candidates.
   - Hard-stopping unreachable targets was tested and was worse; the current
     runtime keeps a fallback path because parent variation can still open
     incidental cells even when the target cell itself is not exactly reachable.

6. Late-probe coverage refresh now delays high-vol stable probes until lane
   stall.
   - Late probes cover high-vol stable mean-reversion cells and
     `high_momentum|low_size|stable|high_vol|trend`.
   - These probes are not used for pure occupied-cell pressure; they are
     released only after zero-new or zero-retention lane evidence.
   - A stable low-vol mean-reversion probe expansion was tested and rejected
     because it reduced the long continuation from three passing steps to two.

7. Real-edge claim boundaries are now explicit in runtime artifacts.
   - `edge_reality_gate_report` now declares `evidence_tier =
     synthetic_proxy_only`.
   - The report marks its role as candidate triage only, not real edge
     evidence.
   - `phase2_execution_report` carries `real_edge_cannot_claim` and
     `real_edge_required_validation`.
   - Required validation before any real-edge claim now includes leakage-checked
     real market data, transaction cost/slippage/capacity backtest, quarterly
     3-month purged walk-forward OOS, factor/crowding audit, and forward paper
     or shadow live validation.

8. A real-market data contract is now wired into Phase2 reports.
   - Selected dataset:
     `G:\Project_V7_Rotation\scripts\data\tdx_sector_data_p3_enhanced.csv`.
   - Dataset kind: OHLCV cross-section panel CSV.
   - Full scan: 1,607,969 rows, 579 codes, 2005-06-07 through 2026-02-04.
   - Required columns present with zero missing values:
     `date`, `open`, `high`, `low`, `close`, `amount`, `volume`, `code`.
   - Target columns present with zero missing values:
     `return_1d`, `return_5d`, `return_20d`.
   - Validation period policy is quarterly 3-month windows; do not default to
     long rolling windows for IC, backtest, or Sortino checks.
   - Runtime reports now distinguish `real_market_data_contract` from
     `real_market_data_consumed_by_runtime`; the contract is available, but
     the synthetic search runtime still does not consume real market data.

9. A standalone real-market validation path now exists for candidate smoke
   checks.
   - Module: `src/our_system_phase2/services/real_market_validation.py`.
   - It evaluates supported expression trees on the selected real OHLCV panel,
     then reports quarterly 3-month rank IC, top-bottom spread, and Sortino.
   - It supports runtime field aliases such as `$volt`, `$pldn`, `$arat`,
     `$mbrd`, and `$vrat`; missing `vwap`, `ret`, `amtm`, and
     `turnover_rate` are derived from OHLCV/amount/volume.
   - Two-argument `Corr` and `Cov` are interpreted as 20-day rolling
     per-instrument relation operators for this smoke-validation path.
   - This is validation instrumentation, not an automatic alpha promotion
     gate yet.

## Budget Comparison

Source:
`runtime/next_stage_artifacts/phase2-budget-77cb6c38b3/budget_profile_comparison.json`

| budget | all runs pass | retained yield | non-score retained ratio | blockers |
| --- | --- | ---: | ---: | --- |
| 1 | false | 0.318182 | 0.714286 | not_all_runs_pass, avg_retained_yield_below_floor |
| 2 | true | 0.368421 | 0.571429 | avg_retained_yield_below_floor |
| 3 | true | 0.659574 | 0.838710 | none |

Selection result: `best_budget = 3`.

## Budget 3 Lane Diagnostics

Source:
`runtime/next_stage_artifacts/phase2-budget-77cb6c38b3/phase2-flow-43bc4e02e1/phase2-df54168c41/generation_efficiency_audit.json`

| lane | generated | retained | new cells | retained yield | status |
| --- | ---: | ---: | ---: | ---: | --- |
| score_frontier | 12 | 5 | 3 | 0.416667 | eligible_for_scaling |
| novelty_frontier | 15 | 11 | 7 | 0.733333 | eligible_for_scaling |
| uncertainty_frontier | 10 | 9 | 6 | 0.900000 | eligible_for_scaling |
| bridge_frontier | 10 | 6 | 4 | 0.600000 | eligible_for_scaling |

All lanes are now above the retained-yield floor of `0.4`.

## Pre-Screen Behavior

Source:
`runtime/next_stage_artifacts/phase2-budget-77cb6c38b3/phase2-flow-43bc4e02e1/phase2-df54168c41/round_report.json`

| lane | events | selected | skipped | rejected |
| --- | ---: | ---: | ---: | ---: |
| novelty_frontier | 14 | 13 | 42 | 20 |
| uncertainty_frontier | 18 | 10 | 36 | 6 |
| bridge_frontier | 18 | 10 | 77 | 11 |

Score lane does not participate in target-aware pre-screen. This is intentional:
score-frontier candidates can dominate retained yield and crowd out non-score
exploration if allowed into the same high-budget pre-screen mechanism.

Dominance-aware skipping is now the main efficiency lever for high-budget
non-score lanes. It avoids spending evaluation budget on candidates predicted
to land in an occupied cell without beating the incumbent archive record.

## Current Interpretation

The latest Phase2 state supports this narrower claim:

- registry-safe generation is enforced by tests
- high-budget pre-screen protects non-score exploration
- budget 3 is currently the best profile
- retained yield is above floor after dominance-aware pre-screening
- bridge and uncertainty lanes no longer drag the aggregate yield below floor

The latest state does not support these broader claims:

- production alpha quality
- tradable net edge
- benchmark superiority over AlphaCFG
- stable result under real market data
- latent-first or neural search superiority

## Recommended Next Step

Continuation check has now been run from the selected budget-3 run root after
score parent refresh and score-cell dominance gating:

- `runtime/next_stage_artifacts/phase2-flow-79958ebd28`
- input previous run root:
  `runtime/next_stage_artifacts/phase2-budget-77cb6c38b3/phase2-flow-43bc4e02e1/phase2-df54168c41`

This continuation includes the score-lane duplicate fallback fix plus the
productive parent-refresh mechanism. Score lane no longer re-evaluates
already-seen variation candidate ids when its proposal pool is exhausted, and
it avoids score variation candidates predicted to be non-dominating in occupied
cells.

Continuation summary:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-cd32946b25 | 4 | 0.815789 | 0.580645 | true |
| 2 | phase2-ac3e560de8 | 2 | 0.781250 | 0.560000 | true |

Continuation lane diagnostics show all lanes above the retained-yield floor:

| run id | score yield | novelty yield | uncertainty yield | bridge yield |
| --- | ---: | ---: | ---: | ---: |
| phase2-cd32946b25 | 1.000000 | 0.555556 | 0.666667 | 0.900000 |
| phase2-ac3e560de8 | 1.000000 | 0.545455 | 0.666667 | 0.857143 |

Score parent refresh events were observed in both continuation runs:

| run id | refresh event count | score variation ids | duplicate score variation ids |
| --- | ---: | ---: | ---: |
| phase2-cd32946b25 | 5 | 15 | 0 |
| phase2-ac3e560de8 | 6 | 18 | 0 |

## Longer Continuation Check

Pre-refresh source:
`runtime/next_stage_artifacts/phase2-flow-28f53eac57`

Input previous root:
`runtime/next_stage_artifacts/phase2-flow-79958ebd28/phase2-ac3e560de8`

Command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --previous-run-root 'runtime\next_stage_artifacts\phase2-flow-79958ebd28\phase2-ac3e560de8' --flow-length 4 --rounds 6 --per-lane-budget 3
```

Pre-refresh longer continuation result:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-04767fd2e0 | 3 | 0.523810 | 0.818182 | true |
| 2 | phase2-3c50e2d1dc | 0 | 0.400000 | 1.000000 | false |
| 3 | phase2-b9d6ad64d9 | 0 | 0.357143 | 1.000000 | false |
| 4 | phase2-4eb843e334 | 0 | 0.357143 | 1.000000 | false |

Lane diagnostics:

| run id | score yield | novelty yield | uncertainty yield | bridge yield | below-floor lanes |
| --- | ---: | ---: | ---: | ---: | --- |
| phase2-04767fd2e0 | 1.000000 | 0.500000 | 0.000000 | 0.571429 | uncertainty_frontier |
| phase2-3c50e2d1dc | n/a | 0.500000 | 0.000000 | 0.333333 | uncertainty_frontier, bridge_frontier |
| phase2-b9d6ad64d9 | n/a | 0.500000 | 0.000000 | 0.000000 | uncertainty_frontier, bridge_frontier |
| phase2-4eb843e334 | n/a | 0.500000 | 0.000000 | 0.000000 | uncertainty_frontier, bridge_frontier |

M4 failed from the second continuation onward because coverage gain fell to
`0.0`, blocking any superiority-over-random-search claim. Archive growth also
stalled at `0` from the second continuation onward.

Score variation duplicate checks remained clean:

| run id | score variation ids | unique score variation ids | duplicate groups |
| --- | ---: | ---: | ---: |
| phase2-04767fd2e0 | 10 | 10 | 0 |
| phase2-3c50e2d1dc | 9 | 9 | 0 |
| phase2-b9d6ad64d9 | 8 | 8 | 0 |
| phase2-4eb843e334 | 8 | 8 | 0 |

Interpretation:

- score-cell dominance gating fixed the duplicate / non-dominating score
  candidate waste observed in shorter continuations
- the longer run does not support scaling the current search policy as-is
- non-score retained ratio reaching `1.0` in failed runs is not evidence of
  healthy exploration; it reflects score lane non-retention while archive
  growth and M4 coverage gain stall
- the next bottleneck was coverage refresh for uncertainty and bridge lanes
  after the archive saturates, not further tightening score or non-score
  filters

## Coverage Refresh Check

Latest source:
`runtime/next_stage_artifacts/phase2-flow-36ae2db1fd`

Input previous root:
`runtime/next_stage_artifacts/phase2-flow-79958ebd28/phase2-ac3e560de8`

Command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --previous-run-root 'runtime\next_stage_artifacts\phase2-flow-79958ebd28\phase2-ac3e560de8' --flow-length 4 --rounds 6 --per-lane-budget 3
```

Coverage-refresh continuation result:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-d1ee1212ad | 5 | 0.849057 | 0.755556 | true |
| 2 | phase2-f128356cb7 | 3 | 0.627451 | 0.500000 | true |
| 3 | phase2-2f3e8198cf | 0 | 0.650000 | 0.692308 | false |
| 4 | phase2-74054d9bb9 | 0 | 0.400000 | 1.000000 | false |

Lane diagnostics:

| run id | novelty yield/new cells | uncertainty yield/new cells | bridge yield/new cells | score yield/new cells | below-floor lanes |
| --- | ---: | ---: | ---: | ---: | --- |
| phase2-d1ee1212ad | 0.500000 / 2 | 0.944444 / 4 | 0.857143 / 5 | 1.000000 / 0 | none |
| phase2-f128356cb7 | 0.250000 / 0 | 0.571429 / 3 | 0.461538 / 0 | 1.000000 / 0 | novelty_frontier |
| phase2-2f3e8198cf | 0.500000 / 0 | 0.428571 / 0 | 0.647059 / 0 | 1.000000 / 0 | none |
| phase2-74054d9bb9 | 0.200000 / 0 | 0.000000 / 0 | 0.562500 / 0 | n/a | novelty_frontier, uncertainty_frontier |

M4 diagnostics:

| run id | M4 status | coverage gain | quality noninferiority |
| --- | --- | ---: | ---: |
| phase2-d1ee1212ad | PASS | 5.0 | 0.638715 |
| phase2-f128356cb7 | PASS | 3.0 | 0.674632 |
| phase2-2f3e8198cf | FAIL | 0.0 | 0.660892 |
| phase2-74054d9bb9 | FAIL | 0.0 | 0.656035 |

Coverage-refresh events show the mechanism is active and useful early, but
still runs out of reachable new cells:

| run id | refresh events | predicted new-cell sum | dominant later targets |
| --- | ---: | ---: | --- |
| phase2-d1ee1212ad | 37 | 8 | transition/high-vol/mean-revert, stable/high-vol/trend |
| phase2-f128356cb7 | 32 | 3 | stable/high-vol/mean-revert, transition/low-vol/mean-revert |
| phase2-2f3e8198cf | 35 | 0 | high-momentum stable/high-vol/mean-revert cells |
| phase2-74054d9bb9 | 32 | 0 | high-momentum stable/high-vol/mean-revert cells |

Interpretation:

- coverage refresh materially improves the first half of longer continuation:
  archive growth changes from `[3, 0, 0, 0]` pre-refresh to `[5, 3, 0, 0]`
- M4 now passes for the first two continuation steps, but still fails after the
  reachable explicit probes are exhausted
- the remaining bottleneck is behavior-cell reachability under the current
  expression grammar/surrogate fingerprint, especially high-momentum stable
  high-vol mean-reversion cells
- this still does not support scaling or superiority claims; it narrows the next
  engineering target from generic coverage refresh to reachable-cell modeling

## Parent-Aware Reachability Check

Strict reachability gating artifact:
`runtime/next_stage_artifacts/phase2-flow-40feeafc56`

Parent-aware reachability seed artifact:
`runtime/next_stage_artifacts/phase2-flow-f0e61040a5`

Input previous root:
`runtime/next_stage_artifacts/phase2-flow-79958ebd28/phase2-ac3e560de8`

Command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --previous-run-root 'runtime\next_stage_artifacts\phase2-flow-79958ebd28\phase2-ac3e560de8' --flow-length 4 --rounds 6 --per-lane-budget 3
```

Strict gating result:

- archive growth reverted to `[3, 0, 0, 0]`
- only the first continuation step passed all gates
- conclusion: exact reachability should inform targeting, but should not hard
  disable coverage refresh when parent variation can still produce incidental
  new cells

Parent-aware seed continuation result:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-555216c9fd | 3 | 0.823529 | 0.761905 | true |
| 2 | phase2-de355597cd | 2 | 0.638298 | 0.533333 | true |
| 3 | phase2-88a9d0b54c | 2 | 0.666667 | 0.642857 | true |
| 4 | phase2-bffba08829 | 0 | 0.555556 | 0.900000 | false |

Lane diagnostics:

| run id | novelty yield/new cells | uncertainty yield/new cells | bridge yield/new cells | score yield/new cells | below-floor lanes |
| --- | ---: | ---: | ---: | ---: | --- |
| phase2-555216c9fd | 0.583333 / 1 | 0.888889 / 2 | 0.818182 / 4 | 1.000000 / 2 | none |
| phase2-de355597cd | 0.166667 / 0 | 0.333333 / 1 | 0.666667 / 4 | 1.000000 / 0 | novelty_frontier, uncertainty_frontier |
| phase2-88a9d0b54c | 0.333333 / 1 | 0.555556 / 0 | 0.647059 / 4 | 1.000000 / 0 | novelty_frontier |
| phase2-bffba08829 | 0.000000 / 0 | 0.200000 / 0 | 0.727273 / 0 | 1.000000 / 0 | novelty_frontier, uncertainty_frontier |

M4 diagnostics:

| run id | M4 status | coverage gain | quality noninferiority |
| --- | --- | ---: | ---: |
| phase2-555216c9fd | PASS | 3.0 | 0.646059 |
| phase2-de355597cd | PASS | 2.0 | 0.666333 |
| phase2-88a9d0b54c | PASS | 2.0 | 0.663741 |
| phase2-bffba08829 | FAIL | 0.0 | 0.648384 |

Coverage-refresh diagnostics:

| run id | refresh events | predicted new-cell sum | seed events | reachability status mix |
| --- | ---: | ---: | ---: | --- |
| phase2-555216c9fd | 36 | 8 | 6 | exact_reachable: 6; no_exact_reachable_fallback: 30 |
| phase2-de355597cd | 34 | 2 | 2 | exact_reachable: 2; no_exact_reachable_fallback: 32 |
| phase2-88a9d0b54c | 32 | 1 | 3 | exact_reachable: 3; no_exact_reachable_fallback: 29 |
| phase2-bffba08829 | 35 | 0 | 0 | no_exact_reachable_fallback: 35 |

Interpretation:

- parent-aware reachability seed improves the long continuation from two M4
  passes to three M4 passes
- the fourth continuation still fails because all refresh events are fallback
  events with zero predicted new cells
- the final bottleneck is concentrated in high-momentum stable high-vol
  mean-reversion behavior cells under the current expression grammar and
  surrogate fingerprint
- more pre-screen tightening is unlikely to solve the last failure; the next
  useful work is either expanding the reachable expression family for those
  cells or teaching the refresh target model to route away from them when the
  survey shows no exact seed
- this remains a synthetic evaluator/search-runtime result, not a production
  alpha or real-market superiority claim

## Late-Probe Reachability Check

Current retained late-probe artifact:
`runtime/next_stage_artifacts/phase2-flow-5667ea92d1`

Input previous root:
`runtime/next_stage_artifacts/phase2-flow-79958ebd28/phase2-ac3e560de8`

Command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --previous-run-root 'runtime\next_stage_artifacts\phase2-flow-79958ebd28\phase2-ac3e560de8' --flow-length 4 --rounds 6 --per-lane-budget 3
```

What changed:

- high-vol stable mean-reversion probes are now treated as late probes
- late probes are withheld during pure occupied-cell pressure and only released
  after lane zero-new or zero-retention stall
- an additional late probe covers
  `high_momentum|low_size|stable|high_vol|trend`
- score lane remains outside target-aware non-score pre-screen and outside
  coverage refresh

Long continuation result:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-d8c82d8704 | 8 | 0.833333 | 0.777778 | true |
| 2 | phase2-5c73153bf9 | 1 | 0.769231 | 0.750000 | true |
| 3 | phase2-2a41807d3e | 1 | 0.611111 | 0.954545 | true |
| 4 | phase2-31fe55fd43 | 0 | 0.575000 | 1.000000 | false |

M4 diagnostics:

| run id | M4 status | coverage gain | quality noninferiority |
| --- | --- | ---: | ---: |
| phase2-d8c82d8704 | PASS | 8.0 | 0.632879 |
| phase2-5c73153bf9 | PASS | 1.0 | 0.636083 |
| phase2-2a41807d3e | PASS | 1.0 | 0.634939 |
| phase2-31fe55fd43 | FAIL | 0.0 | 0.629103 |

Coverage-refresh diagnostics:

| run id | refresh events | predicted new-cell sum | reachability status mix | dominant targets |
| --- | ---: | ---: | --- | --- |
| phase2-d8c82d8704 | 36 | 19 | exact_reachable: 15; no_exact_reachable_fallback: 21 | transition/low-vol mean-revert, high-size high-vol trend, high-size high-vol mean-revert |
| phase2-5c73153bf9 | 35 | 0 | no_exact_reachable_fallback: 35 | high-size high-vol trend, low-momentum high-size high-vol mean-revert |
| phase2-2a41807d3e | 34 | 1 | no_exact_reachable_fallback: 34 | high-size stable low-vol mean-revert, high-size high-vol trend |
| phase2-31fe55fd43 | 32 | 0 | no_exact_reachable_fallback: 32 | high-size stable low-vol mean-revert |

Rejected variant:

- `runtime/next_stage_artifacts/phase2-flow-d6174fcba1` added stable low-vol
  mean-reversion late probes
- it increased early archive growth to `[8, 4, 0, 0]` but reduced all-gate
  passing continuations from three to two
- that change was not retained; it appears to over-consume remaining easy
  cells and suppress useful later coverage-refresh events

Interpretation:

- current late probes improve total retained coverage over the previous
  parent-aware seed run while preserving three all-gate passing continuation
  steps
- the fourth step still fails M4 with coverage gain 0.0
- adding more exact probes can improve early yield but can also shorten useful
  continuation depth
- the next useful change should be a routing/budget policy for exhausted
  no-exact-reachable fallbacks, not another broad probe expansion
- this remains a synthetic evaluator/search-runtime result, not a production
  alpha or real-market superiority claim

## Rejected Fallback-Exhaustion Check

Two fallback-exhaustion variants were tested after the retained late-probe flow.
Neither is retained.

Input previous root:
`runtime/next_stage_artifacts/phase2-flow-79958ebd28/phase2-ac3e560de8`

Command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --previous-run-root 'runtime\next_stage_artifacts\phase2-flow-79958ebd28\phase2-ac3e560de8' --flow-length 4 --rounds 6 --per-lane-budget 3
```

Rejected variant A:

- artifact: `runtime/next_stage_artifacts/phase2-flow-7c51cf51af`
- policy: count repeated `no_exact_reachable_fallback` + zero predicted-new
  events, then skip exhausted target cells once all available missing targets
  are exhausted
- result: archive growth `[8, 1, 0, 0]`; only the first two continuation steps
  passed all gates
- diagnosis: exhaustion events were recorded, but the runtime kept rotating to
  the next missing target, so the budget never actually shifted to from-scratch
  synthesis

Rejected variant B:

- artifact: `runtime/next_stage_artifacts/phase2-flow-166dfc7354`
- policy: immediately route the current allocation to from-scratch synthesis
  when a target reaches the repeated fallback-exhaustion threshold
- result: archive growth `[8, 1, 0, 0]`; only the first two continuation steps
  passed all gates
- diagnostics: from-scratch generation did trigger (`6, 5, 6, 7` generated
  from-scratch candidates across the four runs), but it produced zero new cells
  in steps 3 and 4 and lowered retained yield versus the retained late-probe
  flow

Interpretation:

- the retained flow remains `phase2-flow-5667ea92d1` with growth `[8, 1, 1, 0]`
  and three all-gate passing continuation steps
- generic from-scratch routing is not enough once coverage refresh is trapped
  in no-exact-reachable fallback cells
- the next improvement should be a more specific bridge/reachability repair,
  not a broad fallback-exhaustion budget shift
- this remains a synthetic evaluator/search-runtime result, not a production
  alpha or real-market superiority claim

## Real-Market Validation Smoke

Dataset:
`G:\Project_V7_Rotation\scripts\data\tdx_sector_data_p3_enhanced.csv`

Validation policy:

- use quarterly 3-month windows for IC/backtest/Sortino checks
- treat runtime synthetic metrics as search diagnostics only
- do not promote any candidate to real edge without leakage, cost/slippage,
  capacity, factor exposure, crowding, and forward shadow validation

Full-panel smoke expression:
`CSRank(Mom($close,20))`

- rows after signal/target filtering: 1,595,813
- quarterly windows: 83
- mean window rank IC: 0.017566
- mean window Sortino: 0.699478
- recent windows:
  - 2025Q3 rank IC 0.053502, long-short Sortino 2.717137
  - 2025Q4 rank IC -0.005817, long-short Sortino -1.224505
  - 2026Q1 rank IC 0.018629, long-short Sortino -0.462941

Retained-candidate smoke expression:
`Cov(CSRank($open), Corr(Cov(Std($ret,20),Cov($low,$pldn)), Abs($pldn)))`

- source candidate: retained Phase2 expression from
  `phase2-flow-5667ea92d1/phase2-d8c82d8704`
- rows after signal/target filtering: 1,588,866
- quarterly windows: 83
- mean window rank IC: 0.004426
- mean window Sortino: 0.523251
- recent windows:
  - 2025Q3 rank IC -0.010992, long-short Sortino 0.383884
  - 2025Q4 rank IC 0.036755, long-short Sortino 5.864007
  - 2026Q1 rank IC -0.043099, long-short Sortino -2.233191

Interpretation:

- the real-data validation path works on the selected 464MB V7 panel and can
  evaluate at least a subset of retained Phase2 expressions
- the retained candidate smoke is weak and unstable; it does not justify a
  real-edge claim
- the right next research step is to batch-evaluate retained candidates by
  quarter and reject anything without stable 3-month OOS behavior before any
  transaction-cost or factor-exposure work

Batch retained-candidate smoke:

- report: `reports/PHASE2_REAL_MARKET_BATCH_SMOKE_2026-04-25.json`
- source ledger:
  `runtime/next_stage_artifacts/phase2-flow-5667ea92d1/phase2-d8c82d8704/candidate_ledger.json`
- retained candidates requested: 8
- evaluated candidates: 8
- unsupported expressions: 0
- passed real-market smoke: 0
- best candidate by mean quarterly rank IC:
  - `v2cand-342aa4c73bd5`
  - mean window rank IC: 0.004426
  - recent 4-quarter mean rank IC: -0.000771
  - flags: `weak_mean_rank_ic_below_0_01`,
    `non_positive_recent_mean_rank_ic`
- second candidate:
  - `v2cand-7e88fa27659c`
  - mean window rank IC: -0.000768
  - recent 4-quarter mean rank IC: -0.002157
  - flags: `weak_mean_rank_ic_below_0_01`,
    `non_positive_recent_mean_rank_ic`,
    `recent_positive_quarter_ratio_below_0_5`
- remaining six candidates produced zero usable signal/target rows under the
  current real-panel expression interpretation and were flagged as
  `no_valid_quarterly_rank_ic`

Batch interpretation:

- the first retained batch does not contain real-market edge evidence
- synthetic retained yield is therefore not sufficient as an edge proxy
- the next useful batch should either scan more retained candidates or add a
  pre-filter that demotes expressions producing zero usable real-panel signal
  before expensive validation

Follow-up on the apparent 0.01 recent-window IC candidate:

- fast recent-window candidate: `v2cand-77971a52c245`
- recent 3-month fast-screen rank IC: 0.010446
- full-history confirmation report:
  `reports/PHASE2_REAL_MARKET_FULL_HISTORY_v2cand-77971a52c245_2026-04-25.json`
- full-history rows after signal/target filtering: 1,008,503
- full-history quarterly windows: 83
- full-history mean window rank IC: 0.000419
- full-history mean window Sortino: 0.198863
- recent full-history windows:
  - 2025Q1 rank IC -0.008182
  - 2025Q2 rank IC -0.012476
  - 2025Q3 rank IC -0.017024
  - 2025Q4 rank IC 0.000752
  - 2026Q1 rank IC -0.002586

Interpretation:

- a 0.01 IC in a single recent 3-month window is worth promoting to
  confirmation, but it is not a real-edge claim by itself
- this candidate failed full-history quarterly confirmation, so the recent
  signal is likely unstable or regime-local rather than a robust edge
- fast screening should label such candidates as `needs_full_history_review`,
  not as final passes

Forward-shadow handling:

- full-history failure does not prove the signal will be useless over the next
  3 months
- `v2cand-77971a52c245` is therefore moved to a regime-local forward shadow
  watchlist rather than deleted outright
- watchlist report:
  `reports/PHASE2_FORWARD_SHADOW_WATCHLIST_v2cand-77971a52c245_2026-04-25.json`
- as-of date: 2026-02-04
- instrument count with valid latest signal: 273
- unique signal values: 2
- fixed side count: 55 long-watch / 55 short-watch
- interpretation: the expression is a coarse binary `Sign(...)` style signal,
  so it should be monitored as a group-spread regime-local hypothesis, not as a
  fine-grained cross-sectional ranking factor
- promotion condition for the next 3 months: forward shadow spread and IC must
  remain positive after transaction-cost/slippage/capacity and factor/crowding
  checks; no capital-readiness claim before that

Skill-governed candidate review:

- review file:
  `reports/PHASE2_CANDIDATE_REVIEW_v2cand-77971a52c245_2026-04-25.md`
- applied review rules:
  `candidate_factor_review`, `quant_backtest_bias_audit`,
  `experiment_budget_and_reproducibility`, and `alpha_cross_review_loop`
- gatekeeper decision: `HOLD_RESEARCH`
- reason:
  recent IC is meaningful enough for forward shadow, but full-history weakness,
  binary signal granularity, missing costs/turnover, missing formal execution
  alignment, missing factor/crowding audit, and missing future outcome block
  KEEP or promotion
- next state:
  regime-local forward shadow, not deletion and not promotion

Validation-cost triage:

- report:
  `reports/PHASE2_VALIDATION_COST_TRIAGE_2026-04-25.json`
- source ledger:
  `runtime/next_stage_artifacts/phase2-flow-5667ea92d1/phase2-d8c82d8704/candidate_ledger.json`
- retained candidates scanned: 65
- lane counts:
  - `cheap_fast_path`: 0
  - `moderate_fast_path`: 0
  - `slow_relation_path`: 18
  - `very_slow_nested_relation_path`: 47
- validation roles:
  - `cross_sectional_rank_validation`: 60
  - `group_spread_regime_shadow`: 5
- cheapest retained candidate:
  - `v2cand-342aa4c73bd5`
  - estimated validation cost score: 49.42
  - relation operators: 4
  - rolling operators: 5
- `v2cand-77971a52c245`:
  - lane: `slow_relation_path`
  - role: `group_spread_regime_shadow`
  - estimated validation cost score: 83.9
  - relation operators: 6
  - rolling operators: 9

Interpretation:

- the current retained pool has no genuinely cheap real-validation candidates
- the earlier poor throughput is therefore not just an implementation bug; it
  reflects a generator/search bias toward nested relation expressions
- next search improvement should add a real-validation budget lane that emits
  cheap or moderate expressions before spending evaluator budget on deep
  `Corr/Cov` compositions
- very slow nested relation candidates should be sampled or forward-shadowed
  until the evaluator has vectorized relation-subtree caching

Real-validation budget seed search:

- generated ledger:
  `reports/PHASE2_REAL_VALIDATION_BUDGET_SEED_LEDGER_2026-04-25.json`
- fast-screen report:
  `reports/PHASE2_REAL_VALIDATION_BUDGET_FAST_SCREEN_2026-04-25.json`
- screened candidates: 106
- elapsed time: 49.952 seconds
- promoted to full-history review from recent 3-month IC >= 0.01: 67
- top recent-window candidates were cheap volatility/amount formulas rather
  than nested retained relation formulas

Top 5 full-history confirmation:

- report:
  `reports/PHASE2_REAL_VALIDATION_BUDGET_TOP5_FULL_HISTORY_2026-04-25.json`
- candidates checked: 5
- one candidate survived full-history confirmation:
  - `cheap-080`: `CSRank(Std($amount,60))`
  - recent 3-month IC: 0.034896
  - full-history mean quarterly IC: 0.019231
  - full-history mean Sortino: 0.182147

Amount/liquidity family confirmation:

- report:
  `reports/PHASE2_AMOUNT_FAMILY_FULL_HISTORY_2026-04-25.json`
- review file:
  `reports/PHASE2_CANDIDATE_REVIEW_amount_family_2026-04-25.md`
- primary forward shadow watchlist:
  `reports/PHASE2_FORWARD_SHADOW_WATCHLIST_cheap-079_amount_mean60_2026-04-25.json`
- full-history family results:
  - `cheap-079` / `CSRank(Mean($amount,60))`: full-history mean IC 0.023344,
    recent 8-quarter mean IC 0.027398, recent 8-quarter positive ratio 1.0
  - `cheap-073` / `CSRank(Mean($amount,10))`: full-history mean IC 0.022625,
    recent 8-quarter mean IC 0.024036, recent 8-quarter positive ratio 1.0
  - `cheap-076` / `CSRank(Mean($amount,20))`: full-history mean IC 0.022459,
    recent 8-quarter mean IC 0.025328, recent 8-quarter positive ratio 1.0
  - `cheap-070` / `CSRank(Mean($amount,5))`: full-history mean IC 0.021477,
    recent 8-quarter mean IC 0.023108, recent 8-quarter positive ratio 1.0
  - `cheap-080` / `CSRank(Std($amount,60))`: full-history mean IC 0.019231,
    recent 8-quarter mean IC 0.024369, recent 8-quarter positive ratio 1.0
- primary watchlist properties:
  - as-of date: 2026-02-04
  - valid instruments: 561
  - unique signal values: 540
  - fixed side count: 113 long-watch / 113 short-watch

Interpretation:

- the amount family is the first serious real-data positive cheap-path family
  found in this work wave
- this is still `HOLD_RESEARCH`, not a live-trading or KEEP conclusion,
  because it may be a liquidity/size/sector-attention exposure and lacks
  costs, turnover, capacity, and factor/crowding audits
- the result strongly supports adding a real-validation budget lane to future
  search: cheap interpretable primitives found better real-data evidence in
  under a minute than the retained nested relation pool did in much longer
  validation runs

Amount Mean60 strict audit:

- report:
  `reports/PHASE2_AMOUNT_MEAN60_STRICT_AUDIT_2026-04-25.json`
- horizon-methodology correction:
  the existing strict-audit artifact was produced with an explicit legacy
  horizon set, `1d/5d/20d`. The strict-audit default is now parameterized from
  the shared operator prior, `WINDOW_PRIOR = (2, 5, 10, 20, 60)`, and reports
  its `horizon_policy`.
- parameterized rerun report:
  `reports/PHASE2_AMOUNT_MEAN60_STRICT_AUDIT_PARAMETERIZED_HORIZONS_2026-04-25.json`
- parameterized horizon policy:
  `feature_algebra_window_prior`
- parameterized horizons:
  `2d/5d/10d/20d/60d`
- parameterized rerun summary:
  - 2d mean quarterly IC: 0.019408; positive-window ratio: 0.674699;
    cost-adjusted spread: -0.000214
  - 5d mean quarterly IC: 0.016243; positive-window ratio: 0.590361;
    cost-adjusted spread: -0.000736
  - 10d mean quarterly IC: 0.014326; positive-window ratio: 0.554217;
    cost-adjusted spread: -0.001526
  - 20d mean quarterly IC: 0.013500; positive-window ratio: 0.554217;
    cost-adjusted spread: -0.002762
  - 60d mean quarterly IC: 0.012343; positive-window ratio: 0.560976;
    cost-adjusted spread: -0.006949
- parameterized gatekeeper decision:
  `HOLD_RESEARCH`
- expression:
  `CSRank(Mean($amount,60))`
- cost model:
  10 bps one-way turnover smoke
- horizons:
  - 1d mean quarterly IC: 0.023344; positive-window ratio: 0.771084
  - 5d mean quarterly IC: 0.016243; positive-window ratio: 0.590361
  - 20d mean quarterly IC: 0.013500; positive-window ratio: 0.554217
- mean cost-adjusted window spread:
  - 1d: -0.000076
  - 5d: -0.000736
  - 20d: -0.002762
- mean one-way bucket turnover:
  - 1d: 0.006500
  - 5d: 0.006489
  - 20d: 0.006473
- exposure:
  - amount mean daily rank corr: 0.973640
  - volume mean daily rank corr: 0.924865
  - close mean daily rank corr: 0.136784
  - turnover_rate mean daily rank corr: 0.062396
- gatekeeper decision: `HOLD_RESEARCH`
- blockers:
  - non-positive cost-adjusted primary spread under the current long-high /
    short-low convention
  - very high amount/volume exposure
  - sector neutralization not run
  - capacity model not run
  - survivorship/universe policy not promotion-grade

Strict audit interpretation:

- the amount family has real IC evidence across 1d/5d/20d, but the tradable
  direction and spread economics are not yet clean
- high amount and volume exposure means this is likely a liquidity/size/crowding
  primitive unless residualized evidence survives
- next action should be directionality and neutralization audit, not KEEP

Amount Mean60 inverted direction check:

- report:
  `reports/PHASE2_AMOUNT_MEAN60_INVERTED_STRICT_AUDIT_2026-04-25.json`
- expression:
  `Neg(CSRank(Mean($amount,60)))`
- horizons:
  - 1d mean quarterly IC: -0.023344; cost-adjusted spread: 0.000064
  - 5d mean quarterly IC: -0.016243; cost-adjusted spread: 0.000723
  - 20d mean quarterly IC: -0.013500; cost-adjusted spread: 0.002749
- interpretation:
  - inverting the factor makes rank IC negative, as expected
  - but it makes the simple long-short tail spread positive
  - this means rank IC and tail portfolio economics disagree for this family
  - the next audit must inspect bucket/quantile return curves and not rely on
    one scalar IC or a single top-bottom convention

Amount Mean60 bucket curve:

- report:
  `reports/PHASE2_AMOUNT_MEAN60_BUCKET_CURVE_2026-04-25.json`
- full-history bucket result:
  - 1d high-minus-low bucket return: -0.000073
  - 5d high-minus-low bucket return: -0.000967
  - 20d high-minus-low bucket return: -0.004520
- full-history low-minus-high result:
  - 1d: 0.000073
  - 5d: 0.000967
  - 20d: 0.004520
- recent 8-quarter bucket result:
  - 1d high-minus-low: 0.000160
  - 5d high-minus-low: 0.000463
  - 20d high-minus-low: -0.000198
- interpretation:
  - full history favors low-amount over high-amount tails, especially at 5d
    and 20d horizons
  - recent 8 quarters partially reverse at 1d and 5d
  - therefore the amount family is horizon/regime dependent; it should not be
    treated as a stable one-direction rank factor without regime conditioning

Updated next engineering target:

- local CFG baseline search-efficiency review:
  `reports/PHASE2_CFG_BASELINE_SEARCH_EFFICIENCY_REVIEW_2026-04-25.md`
- comparison verdict:
  Phase2 has surpassed the local CFG candidate baseline on same-contract
  Phase2 proxy metrics and search-control instrumentation, but not on the CFG
  native local 20-day IC objective and not on real tradable-edge evidence.
- skill strengthening and CFG real-market comparison:
  `reports/PHASE2_SKILL_STRENGTHENING_CFG_COMPARISON_2026-04-25.md`
- evaluator strengthening:
  real-market validation now supports CFG-style `WMA`, `Med`, `Kurt`, `Skew`,
  and explicit-window `Corr/Cov`, allowing the frozen CFG pool to be evaluated
  rather than rejected as unsupported grammar.
- CFG real-market fast screen:
  `reports/PHASE2_CFG_BASELINE_REAL_FAST_SCREEN_2026-04-25.json`
- CFG pool result under Phase2 real-market fast screen:
  10/10 supported, 1/10 promoted to full-history review.
- CFG top full-history check:
  `cfg-seed11-007` had full-history mean quarterly IC -0.003750 but positive
  mean Sortino 0.535804, so it is preserved as a tail-economics shadow rather
  than deleted.
- CFG shadow watchlist:
  `reports/PHASE2_FORWARD_SHADOW_WATCHLIST_cfg-seed11-007_2026-04-25.json`
- preserve the current rule that score lane does not participate in the
  target-aware non-score pre-screen
- keep score duplicate and score-cell dominance gating in place
- keep coverage-refresh target-cell probes and parent-aware seed insertion, but
  treat them as a bounded reachability scaffold rather than a complete 32-cell
  solution
- preserve fallback refresh for no-exact-reachable targets, but stop allowing it
  to dominate long continuations when the survey repeatedly reports zero
  predicted new cells
- keep the retained late probes for high-vol stable mean-reversion and
  high-momentum low-size high-vol trend cells
- do not retain the stable low-vol mean-reversion probe expansion without a
  routing change, because the long-run check regressed to two passing steps
- do not retain generic fallback-exhaustion routing; both tested variants
  regressed to two passing continuation steps
- next target is a targeted bridge/reachability repair for no-exact-reachable
  fallback cells: either generate bridge seeds that predict the missing cell
  exactly before spending evaluation budget, or make the target model demote
  repeatedly unreachable cells in favor of cells with observed exact probes

2026-04-26 A5 real-parameterized lane update:

- review:
  `reports/PHASE2_A5_REAL_PARAMETERIZED_SEARCH_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/a5_parameterized_lane.py`
- evaluator extension:
  real-market validation now supports `ZScore(expr)` and `Mul(left, right)`.
- parameter policy:
  `depends_on_registered_window_prior = false`
- parameter source:
  `real_data_calendar_scales_plus_a5_archive_observed_scales`
- inferred windows:
  `1/2/3/4/5/6/7/8/9/10/11/12/13/14/15/16/17/18/19/20/21/22/23/27/39/45/57/60/83/120/174/240/252`
- interpretation:
  this lane is not the old fixed `WINDOW_PRIOR` sweep. It infers candidate
  scales from the real panel calendar and from locally archived A5 formula
  evidence, then expands primitive families across real observed scales.

A5 real-parameterized fast screen:

- ledger:
  `reports/PHASE2_A5_REAL_PARAMETERIZED_LEDGER_2026-04-26.json`
- fast-screen report:
  `reports/PHASE2_A5_REAL_PARAMETERIZED_FAST_SCREEN_2026-04-26.json`
- candidates generated: 180
- evaluated: 180
- unsupported: 0
- elapsed: 62.388 seconds
- promoted to full-history review: 52
- top recent-window candidate:
  `a5-real-param-0161`
- top recent-window expression:
  `CSRank(Div(Sub($open,Delay($close,9)),Delay($close,9)))`
- top recent-window mean IC:
  `0.039913`
- important caveat:
  recent-window strength alone is not promotion evidence. It is only a search
  budget allocation signal.

A5 real-parameterized full-history top-family check:

- top-family ledger:
  `reports/PHASE2_A5_REAL_PARAMETERIZED_TOP_FAMILY_LEDGER_2026-04-26.json`
- full-history report:
  `reports/PHASE2_A5_REAL_PARAMETERIZED_TOP_FAMILY_FULL_HISTORY_2026-04-26.json`
- candidates checked: 5
- elapsed: 88.338 seconds
- unsupported: 0
- strongest full-history family representative:
  `a5-real-param-0053`
- expression:
  `CSRank(Div(Sub($close,Mean($close,3)),Mean($close,3)))`
- family:
  `a5_dev_ma`
- recent-window IC:
  `0.020371`
- full-history mean quarterly IC:
  `0.026340`
- full-history mean Sortino:
  `1.950278`
- recent 8-quarter mean IC:
  `0.006096`
- recent 8-quarter positive-window ratio:
  `0.75`
- interpretation:
  the recent winner `a5_gap(9)` is not the full-history winner. The stronger
  research lead is `a5_dev_ma(3)`, which means the search system needs
  family-level promotion rather than naive top-recent sorting.

A5 `dev_ma3` strict audit:

- report:
  `reports/PHASE2_A5_DEVMA3_STRICT_AUDIT_2026-04-26.json`
- forward shadow:
  `reports/PHASE2_FORWARD_SHADOW_WATCHLIST_a5-real-param-0053_2026-04-26.json`
- gatekeeper decision:
  `HOLD_RESEARCH`
- 2d:
  mean IC `0.023906`; positive-window ratio `0.761905`;
  cost-adjusted spread `0.000591`; one-way turnover `0.568977`
- 5d:
  mean IC `0.014740`; positive-window ratio `0.666667`;
  cost-adjusted spread `0.000652`; one-way turnover `0.568914`
- 10d:
  mean IC `0.026901`; positive-window ratio `0.714286`;
  cost-adjusted spread `0.002683`; one-way turnover `0.568655`
- 20d:
  mean IC `0.030127`; positive-window ratio `0.797619`;
  cost-adjusted spread `0.005548`; one-way turnover `0.568590`
- 60d:
  mean IC `0.012694`; positive-window ratio `0.566265`;
  cost-adjusted spread `0.014719`; one-way turnover `0.569104`
- exposure:
  amount rank corr `0.080158`; volume rank corr `0.074447`;
  close rank corr `0.026466`; turnover-rate rank corr `0.309362`
- blockers:
  sector neutralization not run; capacity model not run;
  survivorship/universe policy not promotion-grade.
- interpretation:
  compared with the amount family, this candidate removes the two worst
  blockers: non-positive cost-adjusted spread and extreme amount/volume
  self-exposure. It is the strongest real-market research candidate found in
  this work wave, but it is still not a KEEP/live signal.

Next search-algorithm strengthening target:

- keep the A5 real-parameterized lane as a first-class lane.
- add family-first budget allocation: first search across primitive families,
  then expand the winning family/scale neighborhood.
- deduplicate early scale twins such as `CSRank(x)` and `ZScore(x)` unless
  tail-spread behavior diverges.
- add a feature-store/DAG cache for repeated subexpressions such as
  `Mean($close,3)`, `Delay($close,9)`, `CSRank(...)`, and horizon labels.
- promote by a composite of recent IC, full-history stability, cost-adjusted
  spread, exposure cleanliness, and family novelty, not by one scalar score.
- use shadow queues instead of deletion:
  recent-only winners go to regime-local shadow, tail-economics winners go to
  tail shadow, and exposure-heavy winners go to residualization queue.
- next concrete audit:
  sector-neutralized and turnover-rate-residualized strict audit for
  `a5-real-param-0053`.

2026-04-26 Phase2 Search Core v2 continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V2_REVIEW_2026-04-26.md`
- plan artifact:
  `reports/PHASE2_SEARCH_CORE_V2_PLAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v2.py`
- purpose:
  return to the Phase2 search-system mainline and turn A5 real-parameterized
  evidence into a family-first next-run planner.
- policy:
  no KEEP/live claim; recent screen allocates budget only; full-history selects
  family representatives; strict audit discovers blockers before keep review.
- scale-twin result:
  180 fast-screen candidates collapsed to 90 after direct `CSRank(x)` /
  `ZScore(x)` deduplication, preserving inverted direction separately.
- family budget result:
  - `a5_dev_ma`: `audit_expand`; best `a5-real-param-0053`; full IC `0.026340`
  - `a5_momentum`: `regime_probe`; best `a5-real-param-0165`;
    full IC `0.014662`
  - `a5_volatility`: `regime_probe`; best `a5-real-param-0157`;
    full IC `0.002522`
  - `a5_gap`: `regime_probe`; best `a5-real-param-0161`;
    recent IC `0.039913`, full IC `0.007526`
  - `a5_amihud`: `watch`; best `a5-real-param-0110`; full IC `0.018332`
- shadow queues:
  - regime-local shadow count: 6
  - tail-economics shadow count: 2
  - residualization queue count: 1
- residualization queue:
  `a5-real-param-0053`, due turnover-rate exposure and missing neutralization /
  capacity checks.
- feature-store precompute targets:
  `Delay($close,9)`, `Mean($close,3)`, `Mom($close,9)`, `Std($ret,8)`,
  plus `2d/5d/10d/20d/60d` horizon labels.
- next audits:
  sector-neutralized strict audit; turnover-rate-residualized strict audit;
  capacity/liquidity sensitivity; survivorship/universe policy review.

2026-04-26 Phase2 Search Core v3 conditional-edge continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V3_CONDITIONAL_EDGE_REVIEW_2026-04-26.md`
- conditional-edge plan:
  `reports/PHASE2_SEARCH_CORE_V3_CONDITIONAL_EDGE_PLAN_2026-04-26.json`
- activation gate dataset:
  `reports/PHASE2_SEARCH_CORE_V3_ACTIVATION_GATE_DATASET_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v3.py`
- objective correction:
  cross-regime stability is now a fragility diagnostic, not the only search
  objective. Phase2 should search for both broad edges and identifiable
  regime-specialist edges.
- paper-informed principles:
  hierarchical quality-diversity search; multi-dimensional evaluation beyond
  single IC; dynamic/conditional factor use; grammar or memory guided
  redundancy reduction.
- real A5 v3 candidate counts:
  full-history after scale-twin dedupe `5`; fast after scale-twin dedupe `90`;
  specialist candidates `2`; broad candidates `3`; watch candidates `0`.
- v3 family allocation:
  - `a5_volatility`: `broad_audit_search`; best `a5-real-param-0157`
  - `a5_gap`: `specialist_gate_search`; best `a5-real-param-0161`
  - `a5_momentum`: `broad_audit_search`; best `a5-real-param-0165`
  - `a5_amihud`: `specialist_gate_search`; best `a5-real-param-0110`
  - `a5_dev_ma`: `broad_audit_search`; best `a5-real-param-0053`
- important interpretation:
  `a5_gap(9)` is no longer treated as a failed all-weather factor. It is a
  regime-specialist candidate with activation windows, and the next job is to
  learn a gate for when to deploy or expand it.
- activation gate dataset:
  5 candidates x 84 quarterly windows = 420 rows; 20 activated rows.
- gate features:
  market return state; cross-sectional volatility state; breadth state;
  liquidity amount state; liquidity volume state; mean instrument count.
- next computational target:
  train a lightweight activation gate, score conditional utility after gate
  costs, then allocate formula expansion budget using family UCB plus
  quality-diversity bonus.

2026-04-26 Phase2 Search Core v4 mathematical-search continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V4_MATH_REVIEW_2026-04-26.md`
- math plan:
  `reports/PHASE2_SEARCH_CORE_V4_MATH_PLAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v4.py`
- objective:
  move beyond engineering controls and put candidates into a mathematical
  multi-objective search space.
- objective vector:
  edge strength; activation-pattern novelty; gate separability in market-state
  space; low fragility.
- selection:
  Pareto front plus softmax expansion weights.
- real A5 v4 result:
  5 candidates in; 4 candidates on Pareto front.
- Pareto front and expansion weights:
  - `a5-real-param-0165` / `a5_momentum9`: math value `0.621809`;
    expansion weight `0.287191`
  - `a5-real-param-0161` / `a5_gap9`: math value `0.604952`;
    expansion weight `0.261517`
  - `a5-real-param-0157` / `a5_volatility8`: math value `0.598617`;
    expansion weight `0.252473`
  - `a5-real-param-0053` / `a5_dev_ma3`: math value `0.555613`;
    expansion weight `0.198819`
- interpretation:
  v4 shifts the next search frontier away from a single full-history anchor.
  It keeps `dev_ma3`, but the stronger mathematical expansion budget is now
  `momentum9`, `gap9`, and `volatility8`.
- next mathematical upgrade:
  Bayesian posterior over objective vectors, expected hypervolume improvement,
  kernelized factor-manifold novelty, and conditional utility after learned
  activation gates.

2026-04-26 Phase2 Search Core v5 expected-hypervolume continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V5_EHI_REVIEW_2026-04-26.md`
- EHI plan:
  `reports/PHASE2_SEARCH_CORE_V5_EHI_PLAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v5.py`
- objective:
  move from static Pareto ranking to active mathematical search.
- method:
  use the v4 objective vector as posterior mean, build a diagonal objective
  uncertainty model from active-window count and fragility, sample candidate
  neighborhood improvements, and estimate expected hypervolume improvement.
- current frontier hypervolume:
  `0.14224836`
- real A5 EHI ranking:
  - `a5-real-param-0157` / `a5_volatility8`: EHI `0.01427748`;
    positive improvement probability `0.91875`; expansion weight `0.296090`
  - `a5-real-param-0165` / `a5_momentum9`: EHI `0.01029555`;
    positive improvement probability `0.85625`; expansion weight `0.227057`
  - `a5-real-param-0161` / `a5_gap9`: EHI `0.00748549`;
    positive improvement probability `0.73750`; expansion weight `0.188268`
  - `a5-real-param-0053` / `a5_dev_ma3`: EHI `0.00453853`;
    positive improvement probability `0.79375`; expansion weight `0.154686`
  - `a5-real-param-0110` / `a5_amihud6`: EHI `0.00237382`;
    positive improvement probability `0.57500`; expansion weight `0.133899`
- interpretation:
  v4 static Pareto favored momentum/gap/vol/dev_ma. v5 active search says the
  next formula-neighborhood expansion should favor volatility8 first, then
  momentum9 and gap9. This is a mathematical search shift, not an audit rule.
- next mathematical target:
  learn correlated objective posteriors from actual formula-neighborhood
  samples, then allocate by expected hypervolume improvement plus mutation
  radius.

2026-04-26 Phase2 Search Core v6 correlated-posterior continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V6_CORRELATED_EHI_REVIEW_2026-04-26.md`
- correlated EHI plan:
  `reports/PHASE2_SEARCH_CORE_V6_CORRELATED_EHI_PLAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v6.py`
- objective:
  replace v5 independent objective uncertainty with correlated posterior
  structure estimated from real formula-neighborhood samples.
- method:
  derive family-level proxy objective covariance from A5 fast-screen samples,
  blend it with v5 diagonal objective uncertainty, and adjust expected
  hypervolume improvement by family mutation radius.
- real A5 neighborhood:
  5 families; 36 fast-screen samples per family.
- current frontier hypervolume:
  `0.14224836`
- correlated EHI ranking:
  - `a5-real-param-0157` / `a5_volatility8`: correlated EHI `0.02892503`;
    radius-adjusted EHI `0.03821135`; expansion weight `0.383414`
  - `a5-real-param-0165` / `a5_momentum9`: correlated EHI `0.02875053`;
    radius-adjusted EHI `0.03529373`; expansion weight `0.315641`
  - `a5-real-param-0161` / `a5_gap9`: correlated EHI `0.01963436`;
    radius-adjusted EHI `0.02491510`; expansion weight `0.158016`
  - `a5-real-param-0053` / `a5_dev_ma3`: correlated EHI `0.01411652`;
    radius-adjusted EHI `0.01540969`; expansion weight `0.083848`
  - `a5-real-param-0110` / `a5_amihud6`: correlated EHI `0.00752460`;
    radius-adjusted EHI `0.01015821`; expansion weight `0.059081`
- interpretation:
  `dev_ma3` remains the audit anchor, but it should not dominate the next
  formula-expansion wave. The next compute budget should go primarily to
  `volatility8`, `momentum9`, and `gap9` neighborhoods.
- next mathematical target:
  generate real local formula-neighborhood samples around those top three
  families, compute actual v4 objective vectors for them, then estimate
  covariance from real objectives rather than fast-screen proxy metrics.

2026-04-26 Phase2 Search Core v7 actual-neighborhood continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V7_ACTUAL_NEIGHBORHOOD_REVIEW_2026-04-26.md`
- local neighborhood ledger:
  `reports/PHASE2_SEARCH_CORE_V7_LOCAL_NEIGHBORHOOD_LEDGER_2026-04-26.json`
- full-history validation:
  `reports/PHASE2_SEARCH_CORE_V7_LOCAL_NEIGHBORHOOD_FULL_HISTORY_2026-04-26.json`
- local activation gate dataset:
  `reports/PHASE2_SEARCH_CORE_V7_LOCAL_ACTIVATION_GATE_DATASET_2026-04-26.json`
- actual objective covariance plan:
  `reports/PHASE2_SEARCH_CORE_V7_ACTUAL_OBJECTIVE_COVARIANCE_PLAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v7.py`
- objective:
  replace v6 fast-screen proxy covariance with actual local formula samples and
  real full-history validation.
- local sample generation:
  from v6 top neighborhoods `volatility8`, `momentum9`, and `gap9`; six
  window-neighborhood samples per family; 18 formulas total.
- full-history validation result:
  elapsed `284.583` seconds; evaluated `18`; unsupported `0`; passed smoke `7`.
- top full-history IC samples:
  - `v7-local-0012` / `CSRank(Mom($close,14))`: full IC `0.019787`;
    recent IC `0.014000`; Sortino `0.708256`
  - `v7-local-0011` / `CSRank(Mom($close,11))`: full IC `0.017372`;
    recent IC `0.013336`; Sortino `0.903895`
  - `v7-local-0010` / `CSRank(Mom($close,10))`: full IC `0.015191`;
    recent IC `0.015451`; Sortino `0.775491`
  - `v7-local-0018` / `gap14`: full IC `0.014896`;
    recent IC `0.014996`; Sortino `0.556650`
- actual objective covariance summary:
  - `a5_gap`: best `v7-local-0016` / gap10; math value `0.562121`;
    actual mutation radius `0.097035`
  - `a5_momentum`: best `v7-local-0011` / momentum11; math value `0.549025`;
    actual mutation radius `0.248450`
  - `a5_volatility`: best `v7-local-0001`; math value `0.517299`;
    actual mutation radius `0.010590`
- interpretation:
  v6 favored volatility8 first from proxy covariance, but v7 actual local
  samples show gap10/gap11 are the strongest actual objective profiles and
  momentum has the widest useful local radius. Volatility still matters, but
  pure window-neighborhood changes are too narrow.
- next mathematical target:
  feed v7 actual covariance back into correlated EHI and generate second-wave
  samples around gap10/gap11, momentum11/momentum14, and structural volatility
  variants rather than only volatility window shifts.

2026-04-26 Phase2 Search Core v8 natural-parameter continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V8_NATURAL_PARAMETER_REVIEW_2026-04-26.md`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V8_NATURAL_PARAMETER_PROPOSAL_LEDGER_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/search_core_v8.py`
- objective:
  correct the v7 sampling shape so parameter values are generated from the
  actual objective posterior, not from a hand-picked local grid.
- method:
  infer family-level parameter posteriors from v7 actual objective profiles
  using softmax weights over `math_search_value`, then generate windows from
  posterior mean, posterior spread, weighted quantiles, and actual best window.
- key correction:
  gap10/gap11 and momentum11 are now natural posterior outputs. They are not
  treated as fixed offsets from a registered anchor.
- posterior summary:
  - `a5_gap`: mean `9.688769`; std `1.656135`; q20/q50/q80 `8/10/11`;
    best window `10`; best value `0.562121`
  - `a5_momentum`: mean `9.373476`; std `1.689378`; q20/q50/q80 `8/9/11`;
    best window `11`; best value `0.549025`
  - `a5_volatility`: mean `8.520816`; std `1.969232`; q20/q50/q80 `7/8/10`;
    best window `6`; best value `0.517299`
- generated proposal ledger:
  `61` formulas across posterior windows and structural variants:
  - `a5_gap`: `20` formulas; windows `7,8,10,11,12`
  - `a5_momentum`: `18` formulas; windows `7,8,9,11,12`
  - `a5_volatility`: `23` formulas; windows `6,7,8,9,10,11`
- interpretation:
  this is a mathematical search upgrade. v8 moves from fixed local
  neighborhood sampling to posterior-geometry-driven parameter generation.
  The next expensive step should validate this 61-formula ledger on a
  three-month-cycle budget before expanding the space again.
- next mathematical target:
  validate v8 proposals, update the posterior with actual objective profiles,
  then add non-window continuous transforms such as scale, interaction
  strength, and family mixing weights as learned parameters.

2026-04-26 Phase2 Search Core v8 real-validation continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V8_REAL_VALIDATION_REVIEW_2026-04-26.md`
- recent fast screen:
  `reports/PHASE2_SEARCH_CORE_V8_REAL_FAST_SCREEN_2026-04-26.json`
- promoted full-history ledger:
  `reports/PHASE2_SEARCH_CORE_V8_PROMOTED_FULL_HISTORY_LEDGER_2026-04-26.json`
- promoted full-history validation:
  `reports/PHASE2_SEARCH_CORE_V8_PROMOTED_FULL_HISTORY_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V8_FULL_HISTORY_PASSED_LEDGER_2026-04-26.json`
- rank-quotient proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V8_RANK_QUOTIENT_PROPOSAL_LEDGER_2026-04-26.json`
- validation result:
  recent three-month fast screen evaluated `61` formulas in `31.525` seconds;
  unsupported `0`; promoted `26` to full-history review.
- full-history result:
  evaluated `26` promoted formulas in `411.095` seconds; unsupported `0`;
  quarterly-smoke passed `10`.
- strongest full-history passes:
  - `v8-natural-0035` / `CSRank(Mom($close,12))`: IC `0.019339`;
    Sortino `0.832050`
  - `v8-natural-0031` / `CSRank(Mom($close,11))`: IC `0.017372`;
    Sortino `0.903895`
  - `v8-natural-0028` / `CSRank(Mom($close,9))`: IC `0.014662`;
    Sortino `0.770180`
  - `v8-natural-0017` / gap12: IC `0.013637`; Sortino `0.638010`
  - `v8-natural-0013` / gap11: IC `0.010964`; Sortino `0.600823`
- family read:
  `a5_momentum` passed `6/6` promoted candidates; `a5_gap` passed `4/8`;
  `a5_volatility` passed `0/12` despite strong recent fast-screen IC.
- proposal-kind read:
  `posterior_window` and `zscore_scale` produced all full-history passes.
  Structural interactions underperformed in this batch.
- search-efficiency read:
  v7 full-history local neighborhood produced `7/18` passes in `284.583`
  seconds. v8 promoted full-history produced `10/26` passes in `411.095`
  seconds. Raw full-history hit/sec is similar, but v8 diagnosed the useful
  region faster and exposed representation duplicates.
- mathematical correction:
  for rank-based validation, outer `CSRank(x)` and `ZScore(x)` are monotone
  equivalent. The new rank-quotient ledger reduces `61` formulas to `45`,
  dropping `16` duplicate representation twins before future expensive review.
- next mathematical target:
  run the next wave on quotient classes only, update posterior mass toward
  momentum `9/11/12` and gap `11/12`, keep volatility in a conditional
  recent/regime lane, and replace binary interaction templates with learned
  continuous interaction weights.

2026-04-26 Phase2 Search Core v9 bounded multi-cycle correction:

- review:
  `reports/PHASE2_SEARCH_CORE_V9_BOUNDED_MULTI_CYCLE_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v9.py`
- bounded validation implementation:
  `src/our_system_phase2/services/real_market_validation.py`
- protocol correction:
  multi-cycle validation now means a bounded number of three-month quarterly
  windows, not full-history. The new validation switch is
  `recent_quarter_window_count=N`.
- interrupted run:
  the attempted v9 full-history validation was stopped and produced no output
  artifact. It should not be used as evidence.
- v9 posterior:
  `reports/PHASE2_SEARCH_CORE_V9_RANK_QUOTIENT_POSTERIOR_2026-04-26.json`
- v9 proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V9_CONTINUOUS_PROPOSAL_LEDGER_2026-04-26.json`
- v9 recent 4Q bounded validation:
  `reports/PHASE2_SEARCH_CORE_V9_RECENT_4Q_MULTI_CYCLE_2026-04-26.json`
- v9 recent 4Q passed ledger:
  `reports/PHASE2_SEARCH_CORE_V9_RECENT_4Q_PASSED_LEDGER_2026-04-26.json`
- bounded validation result:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; loaded
  `148,881` rows; evaluated `40`; unsupported `0`; passed `34`; elapsed
  `70.452` seconds.
- v9 posterior mass:
  `a5_momentum` `0.557026`; `a5_gap` `0.327180`; `a5_volatility` `0.115794`.
- v9 ledger shape:
  `9` quotient broad posterior-window formulas, `27` continuous momentum-gap
  mix formulas, and `4` volatility recent-shadow formulas.
- strongest bounded 4Q candidates:
  - `v9-continuous-0005` / gap9: IC `0.026492`; Sortino `1.003509`
  - `v9-continuous-0006` / gap10: IC `0.024463`; Sortino `0.795227`
  - `v9-continuous-0038` / volatility10 shadow: IC `0.024457`;
    Sortino `2.117429`
  - `v9-continuous-0037` / volatility11 shadow: IC `0.024321`;
    Sortino `2.104872`
  - `v9-continuous-0013` / momentum10-gap9 mix: IC `0.022458`;
    Sortino `0.664948`
  - `v9-continuous-0010` / momentum9-gap9 mix: IC `0.022417`;
    Sortino `1.317083`
- continuous mix read:
  top 8 mix candidates average momentum weight `0.534` and gap weight `0.466`;
  useful windows concentrate at momentum `9/10` and gap `9/10`.
- next mathematical target:
  build v10 around quotient-space continuous local search near momentum weight
  `0.50-0.58`, gap weight `0.42-0.50`, windows momentum `9/10`, gap `9/10`;
  keep volatility10/11 in a recent/regime shadow lane.

2026-04-26 Phase2 tradability-filter correction:

- implementation:
  `src/our_system_phase2/services/real_market_validation.py`
- principle:
  IC and spread validation must not reward impossible trades. The validator now
  excludes limit-up, limit-down, and suspended rows from rank IC; excludes
  limit-up rows from long bucket selection; and excludes limit-down rows from
  short bucket selection.
- field policy:
  use explicit `is_limit_up` / `is_limit_down` or equivalent fields when
  present. If explicit limit fields are absent but `rt_change_pct` is present,
  use conservative fallback `rt_change_pct>=9.8` and `rt_change_pct<=-9.8`.
- tradability-filtered v9 report:
  `reports/PHASE2_SEARCH_CORE_V9_RECENT_4Q_MULTI_CYCLE_TRADABLE_2026-04-26.json`
- tradability-filtered passed ledger:
  `reports/PHASE2_SEARCH_CORE_V9_RECENT_4Q_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- result:
  recent 4Q bounded validation with tradability filtering evaluated `40`,
  unsupported `0`, passed `34`, elapsed `163.099` seconds.
- data note:
  current CSV has `rt_change_pct` but no explicit `is_limit_up/is_limit_down`.
  The run therefore used the conservative percentage-change fallback.
- impact:
  first candidate excluded `14` limit-up rows and `25` limit-down rows from
  the IC universe. The largest absolute IC change versus pre-filtered v9 4Q was
  about `0.000079`, so this batch is not materially driven by untradable limit
  rows.
- strongest tradability-filtered candidates:
  - `v9-continuous-0005` / gap9: IC `0.026451`; Sortino `0.990517`
  - `v9-continuous-0038` / volatility10 shadow: IC `0.024444`;
    Sortino `2.094823`
  - `v9-continuous-0006` / gap10: IC `0.024384`; Sortino `0.772730`
  - `v9-continuous-0013` / momentum10-gap9 mix: IC `0.022415`;
    Sortino `0.645039`
- next mathematical target:
  all future bounded multi-cycle validation must use tradability-filtered IC.
  v10 should use the tradability-filtered passed ledger as its input, not the
  earlier unfiltered v9 report.

2026-04-26 Phase2 Search Core v10 local continuous continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V10_LOCAL_CONTINUOUS_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v10.py`
- local surface:
  `reports/PHASE2_SEARCH_CORE_V10_LOCAL_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V10_LOCAL_CONTINUOUS_LEDGER_2026-04-26.json`
- tradability-filtered bounded validation:
  `reports/PHASE2_SEARCH_CORE_V10_RECENT_4Q_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V10_RECENT_4Q_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- input rule:
  v10 used only the v9 tradability-filtered recent 4Q report as input.
- local surface inference:
  from `27` v9 mix samples, inferred local momentum-weight mean `0.536120`
  and std `0.072214`; generated weight grid
  `0.392,0.421,0.449,0.466,0.478,0.507,0.536,0.565,0.594,0.623,0.652,0.681`.
- generated ledger:
  `56` quotient candidates: `48` local continuous mix, `4` local anchors,
  `4` recent volatility shadow.
- validation result:
  recent 4Q tradability-filtered validation evaluated `56`; unsupported `0`;
  passed `56`; elapsed `271.102` seconds.
- best overall:
  - `v10-local-0049` / gap9 anchor: IC `0.026451`; Sortino `0.990517`
  - `v10-local-0050` / volatility10 shadow: IC `0.024444`;
    Sortino `2.094823`
  - `v10-local-0052` / gap10 anchor: IC `0.024384`; Sortino `0.772730`
- best new mix:
  - `v10-local-0001` / momentum9-gap9 with weights `0.392/0.608`:
    IC `0.023149`; Sortino `1.258412`
  - `v10-local-0013` / momentum10-gap9 with weights `0.392/0.608`:
    IC `0.023114`; Sortino `0.639495`
- comparison:
  v9 tradable 4Q best mix IC was `0.022415`; v10 best mix IC is `0.023149`.
  v10 did not beat pure gap9, but it improved the continuous mix surface.
- interpretation:
  the best mix sits at the lower boundary of the v10 momentum-weight grid.
  The surface wants more gap dominance, not more momentum dominance.
- next mathematical target:
  build v11 around momentum weight below `0.392` and gap weight above `0.608`,
  centered on momentum windows `9/10` and gap window `9`; keep gap9/gap10 as
  anchors and volatility10/11 as recent-regime shadow references.

2026-04-26 Phase2 execution-bias audit correction:

- audit:
  `reports/PHASE2_EXECUTION_BIAS_AUDIT_2026-04-26.md`
- scan:
  `reports/PHASE2_SEARCH_EXECUTION_BIAS_SCAN_2026-04-26.json`
- implementation:
  `src/our_system_phase2/services/real_market_validation.py`
- correction:
  daily-bar validation now defaults to `execution_lag_days=1`: signal date `t`,
  execute on `t+1`, and 1-day label is `t+1 close -> t+2 close`.
- tradability correction:
  entry/exit day limit states are used, not signal-day limit states. Long side
  cannot buy execution-day limit-up or exit exit-day limit-down; short side
  cannot sell execution-day limit-down or cover exit-day limit-up.
- search scan:
  `661` recent search records use daily price fields; `421` are gap/open
  sensitive. Old same-day IC for these records is not execution-valid evidence.
- T+1 bounded revalidation:
  `reports/PHASE2_SEARCH_CORE_V10_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- T+1 passed ledger:
  `reports/PHASE2_SEARCH_CORE_V10_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- T+1 result:
  evaluated `56`; unsupported `0`; passed `42`; elapsed `187.027` seconds.
- key finding:
  the old gap-dominant conclusion was overstated. Gap9 drops from IC `0.026451`
  to `0.015569`; gap10 drops from `0.024384` to `0.002386` and fails smoke.
  Momentum9 becomes the strongest T+1 candidate with IC `0.023730`.
- best T+1 mix:
  momentum9-gap9 with weights `0.681/0.319`: IC `0.021476`; this means the
  valid mix surface shifts momentum-heavy after execution alignment.
- minute data search:
  found local US minute files `G:\tdxmock\vipdoc\ds\minline\74#QQQ.lc1` and
  `74#TQQQ.lc1`, with parser
  `G:\Project_V7_Rotation\us_nextgen\scripts\run_us_parse_qqq_minute_regime.py`.
  A-share `sh/sz/bj/minline` directories exist but no `.lc1/.lc5` A-share
  minute files were found.
- next mathematical target:
  discard no-lag v10 posterior direction. Build v11 only from
  `PHASE2_SEARCH_CORE_V10_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`,
  centered on momentum9, volatility10 shadow, and momentum-heavy gap mixes.

2026-04-26 Phase2 Search Core v11 T+1 momentum-heavy continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V11_TPLUS1_MOMENTUM_HEAVY_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v11.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V11_TPLUS1_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V11_TPLUS1_MOMENTUM_HEAVY_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V11_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V11_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- tests:
  added v11 surface/ledger tests and a T+1 tradability alignment regression
  test in `tests/test_phase2_v21_runtime.py`.
- input rule:
  v11 used the T+1 tradability-filtered v10 report only. Pre-T+1 and no-lag
  v8-v10 reports remain stale for execution-valid conclusions.
- local surface inference:
  from `48` T+1 v10 mix samples, best mix was `v10-local-0012`
  momentum9-gap9 with weights `0.681/0.319`; this was the upper edge of the
  seen momentum-weight range `[0.392,0.681]`, so v11 extended the local surface
  to weights `0.681,0.711,0.741,0.771,0.800,0.830,0.860,0.890,0.920`.
- generated ledger:
  `37` formulas: momentum-heavy mixes for the top local pairs, momentum/gap
  anchors, and volatility shadow anchors.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `37`; unsupported `0`; passed `34`; elapsed `101.204` seconds.
- strongest candidates:
  - `v11-tplus1-0029` / momentum8 anchor: IC `0.026995`; Sortino `1.373838`
  - `v11-tplus1-0030` / momentum9 anchor: IC `0.023730`; Sortino `0.533329`
  - `v11-tplus1-0009` / momentum9-gap9 weights `0.920/0.080`:
    IC `0.023179`; Sortino `0.468069`
  - `v11-tplus1-0008` / momentum9-gap9 weights `0.890/0.110`:
    IC `0.022991`; Sortino `0.442338`
- key mathematical read:
  under valid T+1 execution, the surface is no longer gap-dominant. Momentum8
  beats the old momentum9 anchor, and the best mix keeps only a small gap
  residual. The momentum9-gap9 mix curve improved monotonically as momentum
  weight increased from `0.681` to `0.920`.
- next mathematical target:
  build v12 around momentum windows `7/8/9`, test pure momentum8 versus
  momentum8-gap9 with gap residual weight `0.00-0.12`, and keep volatility as
  a shadow lane unless it wins under the same T+1 tradable protocol.

2026-04-26 Phase2 Search Core v12 natural residual continuation:

- review:
  `reports/PHASE2_SEARCH_CORE_V12_TPLUS1_RESIDUAL_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v12.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V12_TPLUS1_RESIDUAL_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V12_TPLUS1_RESIDUAL_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V12_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V12_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- natural parameterization:
  inferred from v11 results, not legacy fixed windows. Top momentum anchor was
  window `8`; generated momentum neighborhood `7,8,9`, gap windows `9,10`, and
  residual gap weights `0.00,0.04,0.08,0.12,0.16`.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `32`; unsupported `0`; passed `32`; elapsed `88.094` seconds.
- strongest candidates:
  - `v12-tplus1-0002` / momentum8 anchor: IC `0.026995`; Sortino `1.373838`
  - `v12-tplus1-0012` / momentum8-gap9 weights `0.960/0.040`:
    IC `0.026476`; Sortino `1.280234`
  - `v12-tplus1-0016` / momentum8-gap10 weights `0.960/0.040`:
    IC `0.026099`; Sortino `1.258464`
  - `v12-tplus1-0013` / momentum8-gap9 weights `0.920/0.080`:
    IC `0.026021`; Sortino `1.277134`
- key mathematical read:
  the local optimum is at or very near pure momentum8. Small gap residuals
  remain viable but monotonically reduce IC as their weight increases on the
  momentum8-gap9 and momentum8-gap10 curves.
- next mathematical target:
  build v13 around second-order transforms of momentum8: smoothed momentum,
  acceleration, and rank-normalized momentum slope. Only test gap residuals
  below `0.04` if they preserve T+1 execution semantics.

2026-04-26 Phase2 Search Core v13 direct higher-order formula search:

- review:
  `reports/PHASE2_SEARCH_CORE_V13_HIGHER_ORDER_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v13.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V13_TPLUS1_HIGHER_ORDER_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V13_TPLUS1_HIGHER_ORDER_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V13_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V13_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- implementation note:
  `real_market_validation.py` now preserves higher-order metadata fields such
  as `short_window`, `long_window`, `smoothing_window`, `slope_lag`, and
  `volatility_window` in batch validation output.
- direct high-order search space:
  generated `60` formulas around the v12 momentum8 center: smoothed momentum,
  WMA price momentum, short-long acceleration, momentum slope, momentum
  curvature, volatility-normalized momentum, and skew/kurtosis shadows.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `60`; unsupported `0`; passed `36`; elapsed `150.364` seconds.
- strongest candidates:
  - `v13-tplus1-0041` / momentum9 curvature lag1:
    IC `0.040604`; Sortino `0.923118`
  - `v13-tplus1-0053` / momentum9 divided by volatility8:
    IC `0.040082`; Sortino `0.591879`
  - `v13-tplus1-0052` / momentum9 divided by volatility7:
    IC `0.038967`; Sortino `0.523602`
  - `v13-tplus1-0049` / momentum8 divided by volatility7:
    IC `0.037053`; Sortino `1.561447`
  - `v13-tplus1-0050` / momentum8 divided by volatility8:
    IC `0.036368`; Sortino `1.635274`
- best formula:
  `CSRank(Sub(Sub(Mom($close,9),Delay(Mom($close,9),1)),Sub(Delay(Mom($close,9),1),Delay(Mom($close,9),2))))`
- key mathematical read:
  direct higher-order mathematical search did improve the frontier. Curvature
  and volatility-normalized momentum beat pure momentum8; short-minus-long
  acceleration did not. Skew was weak, while kurtosis survived only as a shadow.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for curvature and volatility-normalized momentum
  families, but still not a production edge claim until cost/slippage/exposure
  and forward shadow checks are run.
- next mathematical target:
  build v14 around two manifolds: momentum curvature windows `8/9/10` with
  lags `1/2`, and volatility-normalized momentum with numerator windows
  `8/9/10` and denominator windows `6/7/8/9`.

2026-04-26 Phase2 Search Core v14 curvature / vol-normalized manifold:

- review:
  `reports/PHASE2_SEARCH_CORE_V14_CURVATURE_VOLNORM_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v14.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V14_TPLUS1_CURVATURE_VOLNORM_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V14_TPLUS1_CURVATURE_VOLNORM_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V14_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V14_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- implementation note:
  `real_market_validation.py` now preserves v14 metadata fields including
  `base_transform`, `numerator_window`, `denominator_window`, and
  `denominator_family`.
- search space:
  `54` formulas: `30` curvature-manifold formulas and `24`
  vol-normalized momentum formulas. Curvature tested raw, mean-smoothed signal,
  and WMA-smoothed price paths. Vol-normalized momentum tested `Std($ret,w)`
  and `Mean(Abs($ret),w)` denominators.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `54`; unsupported `0`; passed `35`; elapsed `136.241` seconds.
- strongest candidates:
  - `v14-tplus1-0040` / `CSRank(Div(Mom($close,9),Mean(Abs($ret),6)))`:
    IC `0.041605`; Sortino `0.685857`
  - `v14-tplus1-0039` / momentum9 divided by `Std($ret,6)`:
    IC `0.040861`; Sortino `0.595028`
  - `v14-tplus1-0011` / raw momentum9 curvature lag1:
    IC `0.040604`; Sortino `0.923118`
  - `v14-tplus1-0032` / momentum8 divided by `Mean(Abs($ret),6)`:
    IC `0.040080`; Sortino `1.629599`
- key mathematical read:
  robust risk-normalized momentum is now the leading surface. The
  `Mean(Abs($ret),6)` denominator slightly beats raw curvature and std
  denominators, while momentum8 robust normalization has lower IC but much
  stronger Sortino.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for robust vol-normalized momentum and raw curvature, but
  still not a production edge claim until cost/slippage/exposure and forward
  shadow checks are run.
- next mathematical target:
  build v15 around robust denominator topology: numerator windows `8/9/10`,
  denominator windows `5/6/7`, and denominator forms mean absolute return,
  median absolute return, WMA absolute return, and any representable downside
  proxy.

2026-04-26 Phase2 Search Core v15 robust denominator topology:

- review:
  `reports/PHASE2_SEARCH_CORE_V15_ROBUST_DENOMINATOR_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v15.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V15_TPLUS1_ROBUST_DENOMINATOR_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V15_TPLUS1_ROBUST_DENOMINATOR_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V15_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- passed ledger:
  `reports/PHASE2_SEARCH_CORE_V15_RECENT_4Q_TPLUS1_TRADABLE_PASSED_LEDGER_2026-04-26.json`
- search space:
  `63` formulas: numerator windows `8/9/10`, denominator windows `5/6/7`,
  and denominator families `mean_abs_ret`, `med_abs_ret`, `wma_abs_ret`,
  `mean_downside_abs_ret`, `med_downside_abs_ret`,
  `wma_downside_abs_ret`, and `std_ret`.
- downside proxy:
  `Div(Sub(Abs($ret),$ret),2)`, which is zero for non-negative returns and
  absolute downside move for negative returns.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `63`; unsupported `0`; passed `63`; elapsed `162.416` seconds.
- strongest candidates:
  - `v15-tplus1-0005` /
    `CSRank(Div(Mom($close,8),Med(Div(Sub(Abs($ret),$ret),2),5)))`:
    IC `0.046668`; Sortino `1.667614`
  - `v15-tplus1-0019` / momentum8 divided by median downside abs return7:
    IC `0.046301`; Sortino `1.856272`
  - `v15-tplus1-0029` / momentum9 divided by mean absolute return6:
    IC `0.041605`; Sortino `0.685857`
  - `v15-tplus1-0038` / momentum9 divided by WMA absolute return7:
    IC `0.041162`; Sortino `0.666670`
  - `v15-tplus1-0008` / momentum8 divided by mean absolute return6:
    IC `0.040080`; Sortino `1.629599`
- key mathematical read:
  median downside normalization is the highest-IC path, but it is regime-spiky:
  `v15-tplus1-0005` has 2026Q1 IC `0.157186` and 2025Q4 IC `-0.018941`.
  Mean absolute return normalization is less explosive but positive in all four
  quarters for `v15-tplus1-0029`.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for mean/WMA absolute return denominators. `HOLD_RESEARCH`
  for median downside denominators until stricter quarter-floor and forward
  shadow checks are run.
- next mathematical target:
  build v16 with a quarter-floor objective: stable path refines mean/WMA
  absolute-return denominators near windows `5/6/7`, while spiky median-downside
  candidates require explicit regime-conditional handling before promotion.

2026-04-26 Phase2 Search Core v16 quarter-floor denominator search:

- review:
  `reports/PHASE2_SEARCH_CORE_V16_QUARTER_FLOOR_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v16.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V16_TPLUS1_QUARTER_FLOOR_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V16_TPLUS1_QUARTER_FLOOR_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V16_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- stable passed ledger:
  `reports/PHASE2_SEARCH_CORE_V16_RECENT_4Q_TPLUS1_STABLE_PASSED_LEDGER_2026-04-26.json`
- spiky audit ledger:
  `reports/PHASE2_SEARCH_CORE_V16_RECENT_4Q_TPLUS1_SPIKY_AUDIT_LEDGER_2026-04-26.json`
- quarter-floor objective:
  records minimum quarterly IC, negative-quarter count, positive-quarter ratio,
  quarterly IC std, concentration ratio, floor pass/fail, and floor score.
  Stable promotion requires no negative quarterly IC.
- v15 surface read:
  `63` candidates; `34` quarter-floor stable; `29` spiky.
- generated ledger:
  `51` formulas: `45` stable quarter-floor candidates and `6` median-downside
  regime-conditional audit candidates.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `51`; unsupported `0`; passed `51`; elapsed `131.596` seconds.
- strongest stable candidates:
  - `v16-tplus1-0018` / `CSRank(Div(Mom($close,9),Std($ret,4)))`:
    IC `0.042127`; Sortino `0.623533`; min quarterly IC `0.015910`
  - `v16-tplus1-0022` / momentum9 divided by mean abs return6:
    IC `0.041605`; Sortino `0.685857`; min quarterly IC `0.011351`
  - `v16-tplus1-0026` / momentum9 divided by WMA abs return7:
    IC `0.041162`; Sortino `0.666670`; min quarterly IC `0.008221`
- spiky audit:
  median downside candidate `v16-tplus1-0050` still has high mean IC
  `0.046668`, but fails the quarter floor with 2025Q4 IC `-0.018941` and
  2026Q1 IC `0.157186`; it stays in audit, not stable promotion.
- key mathematical read:
  once quarter-floor is enforced, the stable frontier is robust risk-normalized
  momentum, led by momentum9 divided by short-window volatility. The
  median-downside denominator is a conditional/regime hypothesis, not a stable
  general alpha yet.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for stable quarter-floor track. `HOLD_RESEARCH` for
  spiky median-downside audit track.
- next mathematical target:
  build v17 around stable quarter-floor refinement: numerator windows `8/9`,
  denominator windows `3/4/5/6/7/8`, denominator families `std_ret`,
  `mean_abs_ret`, and `wma_abs_ret`, with quarter-floor score as the primary
  ranking objective.

2026-04-26 Phase2 Search Core v17 stable denominator refinement:

- review:
  `reports/PHASE2_SEARCH_CORE_V17_STABLE_DENOMINATOR_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v17.py`
- surface:
  `reports/PHASE2_SEARCH_CORE_V17_TPLUS1_STABLE_DENOMINATOR_SURFACE_2026-04-26.json`
- proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V17_TPLUS1_STABLE_DENOMINATOR_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V17_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- stable passed ledger:
  `reports/PHASE2_SEARCH_CORE_V17_RECENT_4Q_TPLUS1_STABLE_PASSED_LEDGER_2026-04-26.json`
- search space:
  `36` stable formulas: numerator windows `8/9`, denominator windows
  `3/4/5/6/7/8`, denominator families `std_ret`, `mean_abs_ret`, and
  `wma_abs_ret`. Median downside audit lane was deliberately excluded.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit tradability filtering; no full-history run.
- validation result:
  evaluated `36`; unsupported `0`; passed smoke `36`; quarter-floor passed
  `36`; elapsed `146.067` seconds.
- strongest by quarter-floor score:
  - `v17-tplus1-0002` / `CSRank(Div(Mom($close,8),Mean(Abs($ret),3)))`:
    IC `0.043011`; Sortino `1.932296`; min quarterly IC `0.015441`;
    floor score `0.045374`
  - `v17-tplus1-0020` / momentum9 divided by mean abs return3:
    IC `0.043049`; Sortino `0.846763`; min quarterly IC `0.010191`;
    floor score `0.044936`
  - `v17-tplus1-0022` / momentum9 divided by std return4:
    IC `0.042127`; Sortino `0.623533`; min quarterly IC `0.015910`;
    floor score `0.044137`
- key mathematical read:
  stable frontier moved from denominator windows `4/6/7` toward short robust
  denominators, especially `Mean(Abs($ret),3)`. The best mean-IC candidate is
  momentum9/mean-abs3, but the best quarter-floor candidate is
  momentum8/mean-abs3 because of stronger Sortino and quarter floor.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for stable risk-normalized momentum family; still needs
  turnover/cost and forward shadow checks before any production edge claim.
- next mathematical target:
  build v18 around `Mom8 / Mean(Abs($ret),3)`, testing light smoothing of
  numerator/denominator and denominator windows `2/3/4`, with turnover/cost
  shadow added before stronger keep-list promotion.

2026-04-26 Phase2 Search Core v18 light smoothing and tradable cost shadow:

- review:
  `reports/PHASE2_SEARCH_CORE_V18_LIGHT_SMOOTHING_REVIEW_2026-04-26.md`
- implementation:
  `src/our_system_phase2/services/search_core_v18.py`
- full proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V18_TPLUS1_LIGHT_SMOOTHING_LEDGER_2026-04-26.json`
- compact validation ledger:
  `reports/PHASE2_SEARCH_CORE_V18_TPLUS1_COMPACT_VALIDATION_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V18_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- stable passed ledger:
  `reports/PHASE2_SEARCH_CORE_V18_RECENT_4Q_TPLUS1_STABLE_PASSED_LEDGER_2026-04-26.json`
- tradable turnover/cost shadow:
  `reports/PHASE2_SEARCH_CORE_V18_TPLUS1_TRADABLE_TURNOVER_COST_SHADOW_2026-04-26.json`
- search space:
  `330` generated formulas; compact validation ran `78` formulas using raw
  baselines plus single-side smoothing window `2`, excluding double-smoothing
  crosses.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit limit-up/down and suspension filtering; no full-history run.
- validation result:
  evaluated `78`; unsupported `0`; passed smoke `78`; quarter-floor passed
  `72`; elapsed `466.589` seconds.
- strongest by quarter-floor score:
  - `v18-tplus1-0002` /
    `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`:
    IC `0.046947`; Sortino `2.120522`; min quarterly IC `0.018110`;
    floor score `0.049015`
  - `v18-tplus1-0167` / momentum9 divided by same smoothed denominator:
    IC `0.047444`; Sortino `0.874450`; min quarterly IC `0.012248`;
    floor score `0.048929`
- cost-shadow read:
  with `10 bps` cost and tradability-filtered long/short pools, `v18-tplus1-0002`
  has cost-adjusted spread `0.001098` and one-way turnover `0.341827`, beating
  the v17 stable baseline spread `0.001043`. `v18-tplus1-0167` has the highest
  IC but weaker cost-adjusted spread `0.000510`, so it is an IC reference rather
  than the preferred trading candidate.
- key mathematical read:
  the useful move was denominator-side light smoothing near effective horizon
  `2`, not numerator smoothing. The stable center is now
  `Mom8 / Mean(Mean(Abs($ret),2),2)`.
- candidate review decision:
  `ALLOW_KEEP_REVIEW` for `v18-tplus1-0002`; no production edge claim yet.
- next mathematical target:
  search continuous/fractional denominator kernels around effective horizon
  `2..4`, then residualize new A5 neighbors against the v18 center so the
  system stops spending budget on near-duplicate risk-normalized momentum.

2026-04-27 Phase2 Search Core v19 continuous kernel and residual audit:

- review:
  `reports/PHASE2_SEARCH_CORE_V19_CONTINUOUS_KERNEL_REVIEW_2026-04-27.md`
- implementation:
  `src/our_system_phase2/services/search_core_v19.py`
- evaluator enhancement:
  `CSResidual(y,x)` added to `real_market_validation.py` for daily
  cross-sectional residualization against a known center signal.
- full proposal ledger:
  `reports/PHASE2_SEARCH_CORE_V19_TPLUS1_CONTINUOUS_KERNEL_LEDGER_2026-04-26.json`
- compact validation ledger:
  `reports/PHASE2_SEARCH_CORE_V19_TPLUS1_COMPACT_VALIDATION_LEDGER_2026-04-26.json`
- bounded T+1 tradable validation:
  `reports/PHASE2_SEARCH_CORE_V19_RECENT_4Q_TPLUS1_TRADABLE_2026-04-26.json`
- stable passed ledger:
  `reports/PHASE2_SEARCH_CORE_V19_RECENT_4Q_TPLUS1_STABLE_PASSED_LEDGER_2026-04-26.json`
- tradable turnover/cost shadow:
  `reports/PHASE2_SEARCH_CORE_V19_TPLUS1_TRADABLE_TURNOVER_COST_SHADOW_2026-04-26.json`
- search space:
  `40` generated formulas; compact validation ran `24`: continuous weighted
  denominator kernels around the v18 center plus `CSResidual(candidate,
  v18_center)` variants.
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit limit-up/down and suspension filtering; no full-history run.
- validation result:
  evaluated `24`; unsupported `0`; passed smoke `19`; quarter-floor passed
  `14`.
- strongest overall:
  the top quarter-floor candidate is still the v18 center replayed as
  `v19-tplus1-0001`:
  `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`, IC `0.046947`,
  Sortino `2.120522`, min quarterly IC `0.018110`, floor score `0.049015`.
- best new continuous-kernel candidate:
  `v19-tplus1-0011` /
  `CSRank(Div(Mom($close,8),Add(Mul(0.7,Mean(Mean(Abs($ret),2),2)),Mul(0.3,Std($ret,3)))))`:
  IC `0.046827`, Sortino `2.056740`, min quarterly IC `0.017397`, floor score
  `0.048794`.
- best mean-IC candidate:
  `v19-tplus1-0031` / momentum9 over the same 70/30 mean-abs/std kernel:
  IC `0.047471`, but Sortino only `0.720355` and cost-adjusted spread only
  `0.000398`.
- residual audit:
  raw candidates: `14/14` quarter-floor pass, mean IC `0.046268`;
  residualized candidates: `0/10` quarter-floor pass, mean IC `0.002031`.
  This is evidence that the current A5 edge is concentrated in the v18
  risk-normalized momentum manifold rather than a separable residual component.
- cost-shadow read:
  `v19-tplus1-0011` has cost-adjusted spread `0.001014` and one-way turnover
  `0.339845`, below v18 center's `0.001098`; `v19-tplus1-0031` has
  cost-adjusted spread `0.000398`. v19 does not supersede v18.
- candidate review decision:
  `HOLD_RESEARCH` for new v19 kernels; keep `v18-tplus1-0002` as the active
  stable center.
- next mathematical target:
  stop local A5 denominator nudging unless it adds orthogonal mechanism or cost
  advantage. Move to activation/conditional geometry for when the v18 center
  should be on/off, or search a different family that remains positive after
  residualization against v18.

2026-04-27 Phase2 Search Core v20 v18 activation geometry:

- review:
  `reports/PHASE2_SEARCH_CORE_V20_ACTIVATION_GEOMETRY_REVIEW_2026-04-27.md`
- implementation:
  `src/our_system_phase2/services/search_core_v20.py`
- same-sample activation geometry:
  `reports/PHASE2_SEARCH_CORE_V20_V18_ACTIVATION_GEOMETRY_2026-04-27.json`
- two-half activation holdout:
  `reports/PHASE2_SEARCH_CORE_V20_V18_ACTIVATION_HOLDOUT_2026-04-27.json`
- center expression:
  `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit limit-up/down and suspension filtering; no full-history run.
- same-sample baseline:
  daily IC `0.038614`; cost-adjusted spread `0.000809`; one-way turnover
  `0.342772`.
- strongest same-sample gate:
  `ret_dispersion_le_q30`, active `63` days, active IC `0.062503`,
  active cost-adjusted spread `0.002164`, inactive spread `0.000216`, lift over
  baseline `0.001355`, min quarter IC `0.019311`.
- two-half holdout:
  train windows `2025Q2/2025Q3`; test windows `2025Q4/2026Q1`.
  Train baseline IC `0.040178`, cost-adjusted spread `0.000908`.
  Test baseline IC `0.036181`, cost-adjusted spread `0.000655`.
- surviving holdout gate:
  `ret_dispersion_change_5_le_q30`, test active `19` days, test IC `0.122615`,
  test cost-adjusted spread `0.002885`, lift over test baseline `0.002230`.
  Only `1` train-selected gate passed holdout, so this is a strong hypothesis
  but still a small-sample result.
- key mathematical read:
  the v18 center appears materially stronger in low or contracting
  cross-sectional dispersion states. This is a better next edge direction than
  further local A5 denominator tweaks.
- candidate review decision:
  `HOLD_RESEARCH` as an activation hypothesis; not a production trading gate.
- next mathematical target:
  v21 should run rolling activation splits around dispersion contraction, then
  search for orthogonal residual families inside the active state.

2026-04-27 Phase2 Search Core v21 rolling activation search:

- review:
  `reports/PHASE2_SEARCH_CORE_V21_ROLLING_ACTIVATION_SEARCH_REVIEW_2026-04-27.md`
- implementation:
  `src/our_system_phase2/services/search_core_v20.py`
  (activation-search module; v21 rolling search was consolidated here to avoid
  one-file-per-experiment growth)
- rolling activation report:
  `reports/PHASE2_SEARCH_CORE_V21_ROLLING_ACTIVATION_SEARCH_2026-04-27.json`
- center expression:
  `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit limit-up/down and suspension filtering; no full-history run.
- rolling search design:
  `8` rolling/expanding train-to-next-quarter tests. Gate thresholds are fitted
  on train split only and applied to the next test quarter.
- full recent-4Q baseline:
  daily IC `0.038614`, cost-adjusted spread `0.000809`, one-way turnover
  `0.342772`.
- highest pass-count gate:
  `equal_weight_ret_ge_q70`, selected in `7` splits, passed `5`, pass ratio
  `0.714286`, mean test lift `0.000947`, total test active days `107`, mean
  test IC `0.052981`. This is a market-strength activation hypothesis.
- strongest recurring lift gate:
  `ret_dispersion_le_q50`, selected in `6` splits, passed `3`, mean test lift
  `0.003110`, min test lift `0.000230`, total test active days `78`, mean test
  IC `0.097980`. It supports the low-dispersion hypothesis but has uneven
  active-day coverage.
- v20 survivor:
  `ret_dispersion_change_5_le_q30`, selected in `6`, passed `3`, mean test lift
  `0.000880`, total active days `61`, mean test IC `0.100095`, but with one
  negative test lift.
- key mathematical read:
  activation is now more promising than local A5 formula search. Two conditional
  mechanisms are emerging: broad-market strength and low/contracting
  cross-sectional dispersion. Neither is production-ready.
- candidate review decision:
  `HOLD_RESEARCH` for both activation hypotheses. They should become v22
  gated-v18 ledger candidates with train-only thresholds, not fixed hindsight
  rules.
- next mathematical target:
  v22 should compare ungated v18 against train-threshold-gated v18 for market
  strength and low-dispersion gates, measuring active-day coverage,
  cost-adjusted spread, turnover, and quarter behavior.

2026-04-27 Phase2 Search Core v22 gated v18 combo search:

- review:
  `reports/PHASE2_SEARCH_CORE_V22_GATED_V18_COMBO_SEARCH_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V22_GATED_V18_COMBO_SEARCH_2026-04-27.json`
- implementation:
  reused `src/our_system_phase2/services/search_core_v20.py` activation dataset,
  split, and metric utilities. No new `search_core_v22.py` module was created.
- center expression:
  `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`
- validation protocol:
  recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1 execution;
  entry/exit limit-up/down and suspension filtering; no full-history run.
- combo-search design:
  `22` market-state gate templates over `8` rolling/expanding train-to-next
  quarter tests. Each template fits thresholds on the train split only and then
  applies those thresholds to the next test quarter.
- full recent-4Q baseline:
  daily IC `0.038614`, cost-adjusted spread `0.000809`, one-way turnover
  `0.342772`.
- strongest coverage/robustness combo:
  `eqret70_or_contract30`
  (`equal_weight_ret_ge_q70 OR ret_dispersion_change_5_le_q30`) was selected in
  `8/8` splits and passed `8/8` sample-out tests. Mean test lift was
  `0.000555`, minimum test lift `0.000119`, total test active days `188`, and
  mean test active IC `0.064067`.
- strongest cleaner-but-narrower combo:
  `eqret70_or_signal50`
  (`equal_weight_ret_ge_q70 OR signal_dispersion_le_q50`) was selected in `5`
  splits and passed `5/5`, with mean test lift `0.001804`, minimum test lift
  `0.000810`, total test active days `108`, and mean test active IC `0.095376`.
- high-purity but too sample-thin read:
  `lowret50_and_contract30` had mean test lift `0.004250` and minimum test lift
  `0.002540`, but only `33` total active test days and minimum split active
  days `1`; do not promote without a coverage constraint.
- key mathematical read:
  broad-market strength and dispersion contraction are complementary activation
  mechanisms. The best OR combo improved robustness over either leg alone, but
  this is still an activation overlay on v18, not a newly discovered standalone
  alpha formula.
- candidate review decision:
  `HOLD_RESEARCH_ACTIVATION_COMBOS`. The next step should be continuous
  activation weighting, not another fixed Boolean gate.
- next mathematical target:
  build a train-fitted continuous activation score from market-strength and
  low/contracting-dispersion state variables, then compare weighted v18 exposure
  against ungated v18 and the best Boolean gates under the same T+1/tradability
  protocol.

2026-04-27 Phase2 Search Core v23 continuous activation shadow:

- review:
  `reports/PHASE2_SEARCH_CORE_V23_CONTINUOUS_ACTIVATION_SHADOW_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V23_CONTINUOUS_ACTIVATION_SHADOW_2026-04-27.json`
- implementation:
  reused `src/our_system_phase2/services/search_core_v20.py` utilities. No new
  search-core module was created.
- method:
  daily market-strength / dispersion-contraction / low-ret-dispersion /
  low-signal-dispersion components were converted to train-window empirical
  percentiles. A small nonnegative simplex grid and gamma grid generated
  continuous exposure weights.
- caveat:
  this is a daily aggregate exposure shadow. It scales v18 daily long-short
  returns and existing stock-level cost shadow, but does not yet charge extra
  costs for changing the gross exposure multiplier.
- validation protocol:
  same recent `4` quarterly cycles from `2025-04-01` to `2026-02-04`; T+1
  execution; entry/exit limit-up/down and suspension filtering; no full-history
  run.
- best continuous activation:
  strength-only percentile exposure with gamma `1.5` was selected and passed in
  `8/8` splits. Mean unit-exposure test lift was `0.000555`, minimum unit lift
  `0.000117`, mean weighted IC `0.057574`, mean exposure `0.394088`, total
  effective test days `145.074753`.
- important limitation:
  the best continuous activations have negative calendar-day lift versus
  full-exposure v18, because they intentionally reduce average exposure. This
  makes them useful as capital/risk allocation overlays, not as immediate proof
  of higher standalone strategy return.
- comparison to v22:
  continuous weighting matches the robustness of the best Boolean combo on unit
  lift, but does not dominate it. v22 `eqret70_or_contract30` remains the best
  simple activation candidate for coverage and interpretability.
- candidate review decision:
  `HOLD_RESEARCH_CONTINUOUS_ACTIVATION`. Continue only after adding
  exposure-change turnover cost and comparing calendar-return, unit-exposure
  return, and drawdown consistently.
- next mathematical target:
  move from aggregate shadow to a stock-level tradable portfolio simulation for
  v18 plus the best activation overlay, with exposure-change costs and
  liquidity/coverage constraints.

2026-04-27 Phase2 Search Core v24 stock-level activation shadow:

- review:
  `reports/PHASE2_SEARCH_CORE_V24_STOCK_LEVEL_ACTIVATION_SHADOW_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V24_STOCK_LEVEL_ACTIVATION_SHADOW_2026-04-27.json`
- implementation:
  reused existing real-market validation and `search_core_v20.py` utilities. No
  new search-core module was created.
- compared:
  ungated v18, v22 `eqret70_or_contract30`, and v23 continuous strength gamma
  `1.5`.
- stock-level protocol:
  daily equal-weight top/bottom 20% portfolios from tradable long/short pools;
  signal at `t`, entry at `t+1` close, exit at `t+2` close; long side excludes
  entry limit-up / entry suspension / exit limit-down / exit suspension; short
  side excludes entry limit-down / entry suspension / exit limit-up / exit
  suspension.
- cost model:
  signed position-delta turnover times `10 bps`, including entering/exiting
  gated exposure.
- full-period descriptive read:
  ungated v18 mean calendar net `0.000459`, unit net `0.000459`, mean turnover
  `0.691683`, Sortino `1.405564`, compounded net `0.092434`.
- v22 Boolean activation full-period descriptive read:
  active ratio `0.497585`, calendar net `0.000455`, unit net `0.000914`, mean
  turnover `0.617474`, Sortino `2.011558`, compounded net `0.094672`.
- rolling test summary:
  v22 Boolean activation passed calendar return in only `3/8` splits and unit
  return in only `2/8` splits versus ungated v18. Mean calendar lift was
  `-0.000238`; mean unit lift was `-0.000061`; turnover delta was `-0.020713`.
- continuous strength gamma `1.5`:
  calendar pass `3/8`, unit pass `5/8`, mean calendar lift `-0.000365`, mean
  unit lift `-0.000041`, turnover delta `-0.188064`, mean exposure `0.394088`.
- key mathematical read:
  the earlier activation lift partly came from daily aggregate metrics that did
  not fully charge exposure entry/exit costs. At stock-level with position-delta
  costs, activation is better interpreted as risk-budget/capital-allocation
  research, not free return alpha.
- candidate review decision:
  `HOLD_RESEARCH_STOCK_LEVEL_SHADOW`. Do not promote the activation overlay as a
  production trading rule.
- next mathematical target:
  search for a genuinely orthogonal stock-selection formula inside the v22
  active state, residualized against v18, with stock-level costs in the first
  screen.

2026-04-27 Phase2 Search Core v25 active-state residual stock screen:

- review:
  `reports/PHASE2_SEARCH_CORE_V25_ACTIVE_STATE_RESIDUAL_STOCK_SCREEN_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V25_ACTIVE_STATE_RESIDUAL_STOCK_SCREEN_2026-04-27.json`
- implementation:
  reused existing real-market validation and `search_core_v20.py` utilities. No
  new search-core module was created.
- active-state protocol:
  only evaluate stocks on v22 active days:
  `equal_weight_ret_ge_q70 OR ret_dispersion_change_5_le_q30`, with thresholds
  fitted on each train split only.
- candidates:
  `22` gap, momentum, reversal, moving-average deviation, volatility,
  amount/liquidity candidates, each residualized against v18 via
  `CSResidual(candidate, v18_center)`, plus v18 active as the baseline.
- execution/cost:
  same stock-level top/bottom 20%, T+1/T+2, long/short tradability filters, and
  signed position-delta `10 bps` cost as v24.
- result:
  no residual candidate earned discovery credit. The top-ranked residual by pass
  count, `reversal5_resid_v18`, had calendar pass `4/8` and unit pass `4/8`, but
  mean calendar lift `-0.000486`, mean unit lift `-0.000839`, mean net calendar
  `-0.000114`, and mean unit net `-0.000289`.
- next best residual reads:
  `gap1_resid_v18` had positive mean net calendar `0.000039` and mean unit net
  `0.000053`, but only `2/8` calendar and unit pass counts, with negative mean
  lift versus v18 active. `volume_ratio_5_20_resid_v18` had `3/8` pass counts
  but negative mean net and negative lift.
- key mathematical read:
  local price/volume residuals inside the active state do not provide a robust
  second mechanism after tradability and costs. This strengthens the view that
  the current exploitable signal is concentrated in the v18 manifold, while v22
  is mostly a risk-budget overlay.
- candidate review decision:
  `NO_RESIDUAL_STOCK_EDGE_PROMOTED`.
- next mathematical target:
  stop searching local A5-style price/volume residuals around v18. Move to a
  genuinely different information source or operator class, while keeping
  stock-level tradability and position-delta costs in the first screen.

2026-04-27 Enhanced real-market field enablement:

- implementation:
  `src/our_system_phase2/services/real_market_validation.py` now loads enhanced
  CSV columns when present: `sector`, target-return columns, RPS fields,
  `money_flow`, `f9_quantile_250d`, `crowding`, `overnight`, `low_20`,
  `high_20`, `price_pos`, and enhanced RPS fields.
- field semantics:
  `src/our_system_phase2/services/field_encoder.py` now registers enhanced
  fields so future candidate fingerprints do not silently collapse unknown
  fields back toward `close`.
- reason:
  prior real-market validation only loaded OHLCV plus tradability columns, even
  though the local CSV contained richer features. This likely contributed to the
  search being trapped around the v18 OHLCV momentum manifold.
- leakage guard:
  target-return columns are loadable for contracts/audits, but v26 candidate
  design deliberately avoided `return_1d`, `return_5d`, and `return_20d` because
  their timestamp semantics are ambiguous for alpha inputs.
- direct verification:
  `CSRank(Add($money_flow,Sub($rps_score,$crowding)))` evaluates on the recent
  real panel with `148881/148881` non-null signal rows, and `money_flow`,
  `rps_score`, and `crowding` are loaded from the CSV.

2026-04-27 Phase2 Search Core v26 enhanced-field stock screen:

- review:
  `reports/PHASE2_SEARCH_CORE_V26_ENHANCED_FIELD_STOCK_SCREEN_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V26_ENHANCED_FIELD_STOCK_SCREEN_2026-04-27.json`
- implementation:
  reused existing real-market validation and stock-level shadow utilities. No
  new search-core module was created.
- candidates:
  `31` standalone or simple interaction candidates from RPS, RPS slope, money
  flow, crowding/f9, overnight, price position, and residual forms against v18
  or crowding.
- protocol:
  stock-level equal-weight top/bottom 20%; T+1/T+2 execution; long/short
  tradability filters; signed position-delta `10 bps` cost; recent `4` quarters;
  no full-history run.
- redundancy audit:
  `f9_quantile_250d` and `crowding` are identical in this panel for the tested
  period: correlation `1.0`, mean absolute difference `0.0`.
- best descriptive candidate:
  `crowding_resid_v18_neg` had full-period compounded net `0.186132`, mean net
  calendar `0.000858`, and Sortino `3.950494`, but rolling performance did not
  beat v18: calendar pass `3/8`, mean calendar lift `-0.000482`, min lift
  `-0.002189`.
- other reads:
  `rps_resid_v18` and low-crowding variants reduced turnover, but their rolling
  mean lifts versus v18 remained negative.
- candidate review decision:
  `HOLD_RESEARCH_ENHANCED_FIELDS`; no standalone enhanced-field selector is
  production-ready.
- next target:
  use enhanced fields as market-state variables or run concentration diagnostics
  on descriptive winners, rather than promoting standalone selectors.

2026-04-27 Phase2 Search Core v27 enhanced-state activation shadow:

- review:
  `reports/PHASE2_SEARCH_CORE_V27_ENHANCED_STATE_ACTIVATION_SHADOW_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V27_ENHANCED_STATE_ACTIVATION_SHADOW_2026-04-27.json`
- design:
  daily cross-sectional aggregates of RPS, money flow, crowding, overnight,
  price position, and enhanced RPS fields were tested as train-quantile state
  gates for the v18 stock-level portfolio.
- strongest broad read:
  `crowding_dispersion_le_q70` had calendar pass `5/8`, mean calendar lift
  `0.000129`, min lift `0.0`, mean unit lift `0.000123`, active ratio
  `0.511174`, and turnover delta `-0.250697`.
- strongest unit-quality reads:
  `rps_score_mean_le_q70` and `money_flow_mean_change_5_le_q30` had unit pass
  `8/8`, with mean unit lifts `0.000736` and `0.001671` respectively, but both
  still had negative mean calendar lift after exposure costs.
- candidate review decision:
  `NO_ENHANCED_STATE_GATE_PROMOTED` from v27 alone, because ranking gates by all
  split outcomes is not sufficient evidence. Proceed to train-selected holdout.

2026-04-27 Phase2 Search Core v28 enhanced-state holdout selection:

- review:
  `reports/PHASE2_SEARCH_CORE_V28_ENHANCED_STATE_HOLDOUT_SELECTION_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V28_ENHANCED_STATE_HOLDOUT_SELECTION_2026-04-27.json`
- design:
  focused v27 gates were required to beat ungated v18 on train calendar net and
  train unit net before being evaluated on the next quarter.
- best train-selected combo:
  `crowd70_or_price50` selected in `3` splits and passed `2`, pass ratio
  `0.666667`, mean test calendar lift `0.000256`, min lift `0.0`, mean test
  unit lift `0.000411`, active ratio `0.466667`.
- single-gate read:
  `crowding_dispersion_le_q70` selected in only `2` splits and had `0` strict
  test passes under the train-selection definition, but selected-test mean
  calendar lift was `0.000168` with min `0.0`.
- key mathematical read:
  enhanced fields opened a new state-space axis, but simple Boolean gates are
  still too sample-thin for production. The most useful clue is not a deployable
  rule; it is that crowding/RPS state may explain v18 quality changes.
- candidate review decision:
  `HOLD_RESEARCH_CROWDING_STATE`.
- next target:
  audit `crowding_dispersion_le_q70`, `crowd70_or_price50`, and
  `crowding_resid_v18_neg` by quarter, sector, and concentration; if the edge is
  not one cluster/interval, test sector-neutral stock-level variants.

2026-04-27 Phase2 Search Core v29 crowding sector concentration audit:

- review:
  `reports/PHASE2_SEARCH_CORE_V29_CROWDING_SECTOR_CONCENTRATION_AUDIT_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V29_CROWDING_SECTOR_CONCENTRATION_AUDIT_2026-04-27.json`
- implementation:
  reused existing validation utilities and reconstructed stock-level holdings.
  No new search-core module was created.
- audited modes:
  ungated v18, v18 with `crowding_dispersion_le_q70`, v18 with
  `crowd70_or_price50`, and standalone `crowding_resid_v18_neg`.
- descriptive result:
  `crowding_resid_v18_neg` beat v18 over the recent 4Q descriptive window:
  calendar lift `0.000399`, unit lift `0.000399`, Sortino lift `2.544930`, and
  turnover delta `-0.074501`.
- quarter read:
  `crowding_resid_v18_neg` was strong in `2025Q2` and `2025Q4`, weak in
  `2025Q3`, and failed versus v18 in `2026Q1`.
- concentration read:
  no gross sector concentration flag was triggered, but this was later found to
  be limited by the meaning of the available `sector` field.
- decision:
  `HOLD_RESEARCH_SECTOR_AUDIT`. Continue with sector-neutral and
  quarter-exclusion sensitivity before any promotion.

2026-04-27 Phase2 Search Core v30 sector-neutral crowding audit:

- review:
  `reports/PHASE2_SEARCH_CORE_V30_SECTOR_NEUTRAL_CROWDING_AUDIT_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V30_SECTOR_NEUTRAL_CROWDING_AUDIT_2026-04-27.json`
- attempted method:
  equal sector budget, within-sector top/bottom 20%, zero net sector exposure
  per sector when both sides are tradable.
- data reality:
  the available `sector` field is not a usable industry-neutralization key in
  this panel. Recent window has `574` codes and `574` distinct `sector` values;
  every date-sector group has size `1`, so no within-sector long/short portfolio
  can be formed.
- corrected decision:
  `BLOCKED_BY_SECTOR_FIELD_GRANULARITY`. v30 cannot decide whether the crowding
  residual survives true industry neutralization. A real industry taxonomy is
  required before making sector-neutral claims.

2026-04-27 Phase2 Search Core v31 crowding quarter-exclusion sensitivity:

- review:
  `reports/PHASE2_SEARCH_CORE_V31_CROWDING_QUARTER_EXCLUSION_REVIEW_2026-04-27.md`
- report:
  `reports/PHASE2_SEARCH_CORE_V31_CROWDING_QUARTER_EXCLUSION_2026-04-27.json`
- compared:
  v18 versus `crowding_resid_v18_neg` using the stock-level T+1/T+2 tradable
  top/bottom 20% protocol and signed position-delta `10 bps` cost.
- full recent-4Q result:
  calendar lift `0.000399`, Sortino lift `2.544930`, turnover delta `-0.074501`.
- exclusion result:
  excluding `2025Q2` reduces the lift to `-0.000020`, with Sortino lift
  `-0.007184`. Excluding `2025Q3`, `2025Q4`, or `2026Q1` remains positive.
- quarter attribution:
  `2025Q2` lift `0.001428`; `2025Q3` lift `-0.000426`; `2025Q4` lift
  `0.001186`; `2026Q1` lift `-0.002195`.
- flags:
  `edge_does_not_survive_excluding_2025Q2` and
  `quarter_pass_count_below_3_of_4`.
- decision:
  `NO_PROMOTION_QUARTER_INSTABILITY`. The crowding residual is mathematically
  interesting but not robust enough for promotion, commercial use, or signal
  sale. Keep it as a research clue for enhanced-field search.
- next target:
  search enhanced fields with quarter-exclusion robustness as a first-class
  filter, and find/build a real industry taxonomy before sector-neutral claims.

2026-04-27 Search infrastructure consolidation decision:

- issue:
  previous research iterations created many `search_core_vN.py` files. This was
  useful for preserving exploratory lineage, but it is no longer the right
  engineering pattern now that the project has stable search/validation
  components.
- stable runtime/search entry points:
  - `src/our_system_phase2/runtime/prototype_run.py`
  - `src/our_system_phase2/runtime/generation_run.py`
  - `src/our_system_phase2/services/real_market_validation.py`
  - `src/our_system_phase2/services/search_core_v20.py` for activation/on-off
    searches around the current v18 center
- policy going forward:
  do not create a new large `search_core_v22.py`, `search_core_v23.py`, etc. for
  every experiment. New work should extend existing stable modules unless it is
  a genuinely separate subsystem.
- artifact policy:
  reports may remain per experiment because they are immutable research
  evidence, but implementation code should be consolidated.
- immediate consolidation already applied:
  v21 rolling activation search was merged into `search_core_v20.py`; no
  separate `search_core_v21.py` implementation remains.

2026-04-27 Local industry mapping inventory:

- review:
  `reports/PHASE2_LOCAL_INDUSTRY_MAPPING_INVENTORY_2026-04-27.md`
- found real stock-level PIT industry mapping:
  `G:/Project_V7_Rotation/_work/news_labeling_20260320/mapping/stock_sector_mapping_pit_jq.parquet`
- mapping stats:
  `1,255,369` rows, `5,209` stocks, `54` sector codes, date range
  `2025-03-03` to `2026-02-27`, source `jq_monthly_snapshot`,
  latest Unknown ratio `0.039547`.
- related usable assets:
  `stock_sector_mapping_pit.parquet`,
  `stock_sector_mapping_pit_history.parquet`,
  `stock_sector_mapping_scd2_jq.parquet`,
  `mapping_snapshot_20260221.parquet`,
  `futu_tdx_sector_mapping.csv`, `sector_metadata.csv`, and
  `sector_codes.csv`.
- important correction:
  current enhanced validation data lives at
  `G:/Project_V7_Rotation/scripts/data/tdx_sector_data_p3_enhanced.csv` and is
  a board/sector-index panel with `579` codes and `579` sector names. Its
  `sector` column is the board name, not a true industry-neutralization key.
- decision:
  use `stock_sector_mapping_pit_jq.parquet` only with a stock-level
  feature/label panel joined by `(trade_date, stock_code)`. Do not make
  stock-level sector-neutral claims from the current board-index panel.
- next target:
  locate or rebuild the matching stock-level feature/label panel, then rerun
  crowding/residual validation under true PIT industry neutrality.
- follow-up search:
  the historical inventory paths
  `alpha_factory/data/features/p15_layered_features.parquet`,
  `alpha_factory/data/features/p25_incremental_features.parquet`, and
  `alpha_factory/data/labels/labels_daily_fixed.parquet` were not found in the
  active local project tree. The only `alpha_factory` directory found is the
  A5 recovered worktree, which contains A5 algorithm/formula assets rather than
  the old p15/p25 stock panel.

2026-04-27 Stock-level validation slice rebuild:

- slice review:
  `reports/PHASE2_STOCK_LEVEL_VALIDATION_SLICE_REVIEW_2026-04-27.md`
- slice report:
  `reports/PHASE2_STOCK_LEVEL_VALIDATION_SLICE_2026-04-27.json`
- generated stock-level datasets:
  - `G:/Project_V7_Rotation/scripts/data/phase2_stock_validation_slice_2026-04-27.csv.gz`
  - `G:/Project_V7_Rotation/scripts/data/phase2_stock_validation_slice_2026-04-27.parquet`
- source:
  local TDX day files from `G:/hsjday/sh/lday` and `G:/hsjday/sz/lday`.
- universe:
  first pass uses stock-like `sh6`, `sz0`, and `sz3` files. BJ files are
  excluded because the current PIT industry mapping is SH/SZ-oriented.
- date reality:
  latest local TDX stock day-file date is `2026-02-04`. The rebuilt recent
  three-month evaluation window is therefore `2025-11-04` to `2026-02-04`,
  with warmup starting `2025-08-06`.
- slice stats:
  `5,980` stock files scanned, `679,556` panel rows, `5,549` panel stocks,
  `123` panel dates. Evaluation window has `359,871` rows, `358,672` actual
  traded rows, `1,199` suspended placeholder rows, `65` dates, and `5,545`
  actually traded stocks.
- PIT industry mapping:
  joined from
  `G:/Project_V7_Rotation/_work/news_labeling_20260320/mapping/stock_sector_mapping_pit_jq.parquet`
  by `(date, code)`. Evaluation actual Unknown sector ratio is `0.096885`.
- tradability controls:
  missing rows inside the local market calendar are represented as `susp=1`
  placeholders with forward-filled OHLC only to keep shift-based execution
  blocking conservative. Limit-up/limit-down flags are inferred from
  close-to-close daily return `>= +/-9.8%`; ST 5% limits are not identified in
  this first pass.

2026-04-27 Stock-level representative candidate replay:

- review:
  `reports/PHASE2_STOCK_LEVEL_REVALIDATION_REPRESENTATIVE_CANDIDATES_2026-04-27.md`
- report:
  `reports/PHASE2_STOCK_LEVEL_REVALIDATION_REPRESENTATIVE_CANDIDATES_2026-04-27.json`
- protocol:
  stock-level recent 3-month replay, horizon `1d`, signal at `t`, entry at
  `t+1` close, exit at `t+2` close, top/bottom `20%`, inferred limit and
  suspension blocking.
- result summary:
  - `CSRank($overnight)` / gap proxy: mean IC `0.005331`, mean Sortino
    `6.547624`.
  - v18 compact center
    `CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))`: mean IC
    `0.002179`, mean Sortino `3.336540`.
  - v18 mean-abs3 variant: mean IC `0.001660`, mean Sortino `3.176987`.
  - `CSRank(Mom($close,8))`: mean IC `-0.018742`, mean Sortino `3.105480`.
  - `CSRank(Mean($amount,60))`: mean IC `-0.018812`, mean Sortino `1.295987`.
  - `CSRank(Std($ret,10))`: mean IC `-0.068054`, mean Sortino `1.595932`.
- important correction:
  the old board-level winners do not automatically transfer to stock-level
  evidence. Momentum/amount/volatility families are weak or negative by
  stock-level IC in this first replay. Overnight/gap remains a weak research
  clue, not a promotion candidate.

2026-04-27 Stock-level industry-neutral sensitivity:

- review:
  `reports/PHASE2_STOCK_LEVEL_INDUSTRY_NEUTRAL_SENSITIVITY_2026-04-27.md`
- report:
  `reports/PHASE2_STOCK_LEVEL_INDUSTRY_NEUTRAL_SENSITIVITY_2026-04-27.json`
- method:
  audit-only sensitivity using PIT industry `sector`, excluding `Unknown`,
  requiring at least `20` stocks per sector per day. Metrics are daily
  within-sector residual rank IC and equal-sector long/short spread.
- result summary:
  - `CSRank($overnight)`: neutral IC `0.002629`, equal-sector Sortino
    `8.613215`.
  - v18 compact center: neutral IC `-0.002548`, equal-sector Sortino
    `4.947859`.
  - v18 mean-abs3 variant: neutral IC `-0.002624`, equal-sector Sortino
    `4.706499`.
  - `CSRank(Mom($close,8))`: neutral IC `-0.023349`.
  - `CSRank(Mean($amount,60))`: neutral IC `-0.040279`.
  - `CSRank(Std($ret,10))`: neutral IC `-0.070172`.
- decision:
  `STOCK_LEVEL_REPLAY_RESETS_PROMOTION_STATUS`. All prior stock-level promotion
  language from board-panel validation is invalid. Board-level results remain
  useful only for board/sector rotation research. Stock-level research should
  continue from the rebuilt slice and expand to broader windows before any
  commercial or signal-sale claim.

2026-04-27 Stock-level leakage audit and correction:

- audit:
  `reports/PHASE2_STOCK_LEVEL_LEAKAGE_AUDIT_2026-04-27.md`
- corrected replay:
  `reports/PHASE2_STOCK_LEVEL_REVALIDATION_ENTRY_ONLY_CORRECTED_2026-04-27.md`
- corrected industry-neutral sensitivity:
  `reports/PHASE2_STOCK_LEVEL_INDUSTRY_NEUTRAL_ENTRY_ONLY_CORRECTED_2026-04-27.md`
- finding:
  the user's concern was correct. The first stock-level replay had an
  execution-validation leakage: exit-day limit-up / limit-down / suspended
  states were used to drop rows from IC and long/short spread evaluation. This
  is ex-post information relative to signal date `t`.
- diagnostic:
  a datewise-shuffled random signal produced positive spread and absurd Sortino
  under the old protocol, confirming the row filter itself created economics.
  An intentional leaked forward-return rank produced IC `1.0`, as expected.
- code correction:
  `src/our_system_phase2/services/real_market_validation.py` now uses
  entry-only tradability for IC/spread inclusion. Long side blocks only `t+1`
  limit-up or suspended; bottom/short side blocks only `t+1` limit-down or
  suspended. Exit-day limit states are still reported but no longer delete
  outcomes.
- corrected representative replay:
  - v18 compact center: mean IC `0.006374`, mean Sortino `0.324238`.
  - v18 mean-abs3 variant: mean IC `0.005895`, mean Sortino `0.264476`.
  - `CSRank($overnight)`: mean IC `0.003510`, mean Sortino `-0.886493`.
  - `CSRank(Mom($close,8))`: mean IC `-0.011839`, mean Sortino `-0.493752`.
  - `CSRank(Mean($amount,60))`: mean IC `-0.014839`, mean Sortino `-0.400865`.
  - `CSRank(Std($ret,10))`: mean IC `-0.053633`, mean Sortino `-0.681898`.
- corrected industry-neutral read:
  v18 compact center and mean-abs3 keep tiny neutral IC around `0.00179`, but
  equal-sector Sortino is negative. Overnight neutral IC falls to `0.000391`
  with negative equal-sector Sortino.
- superseded:
  the earlier stock-level replay and industry-neutral reports from this date
  are superseded for spread/Sortino and promotion purposes.
- decision:
  `FAIL_OLD_PROTOCOL_HOLD_RESEARCH_CORRECTED_PROTOCOL`. No representative
  stock-level candidate is promotion-ready after the leakage correction.

2026-04-27 Stock-level signal timestamp audit and feature-lag replay:

- user correction:
  the user identified a second, separate leakage risk after the entry-only
  fix. A rank such as `CSRank($close)` or a formula using same-day close/ret is
  not available at the current day's open. For an open-decision protocol, the
  decision-date signal must use the raw expression from `t-1`.
- code correction:
  `src/our_system_phase2/services/real_market_validation.py` now exposes
  `feature_lag_days`. `feature_lag_days=1` means decision date `t` uses the raw
  expression value computed from `t-1`; `feature_lag_days=0` is only valid for
  close-after-close / after-EOD decision semantics.
- representative lagged replay:
  `reports/PHASE2_STOCK_LEVEL_REVALIDATION_FEATURE_LAG1_2026-04-27.md`
- representative lagged results:
  - `CSRank($overnight)`: mean IC `0.015735`, mean Sortino `0.187486`.
  - v18 mean-abs3 variant: mean IC `0.006937`, mean Sortino `0.660667`.
  - v18 compact center: mean IC `0.006611`, mean Sortino `0.629252`.
  - `CSRank(Mean($amount,60))`: mean IC `-0.011589`, mean Sortino `-0.284954`.
  - `CSRank(Mom($close,8))`: mean IC `-0.016640`, mean Sortino `-0.526462`.
  - `CSRank(Std($ret,10))`: mean IC `-0.052610`, mean Sortino `-0.749229`.
- existing ledger recheck:
  `reports/PHASE2_STOCK_LEVEL_EXISTING_LEDGER_RECHECK_FEATURE_LAG1_2026-04-27.md`
- ledger recheck read:
  - v19 retained ledger: `14/14` evaluated, `0` promoted; best IC `0.007128`,
    Sortino `0.688995`.
  - v18 retained ledger: `72/72` evaluated, only `3` pass the current fast
    screen but all have insufficient quarterly windows. Best is
    `v18-tplus1-0091` /
    `CSRank(Div(Mean(Mom($close,8),2),WMA(Abs($ret),3)))` with IC `0.010423`
    and Sortino `1.003796`.
  - A5 parameterized ledger: `180/180` evaluated. Inverse-volatility variants
    show high rank IC around `0.05` but negative Sortino under this spread
    construction. The cleaner positive-Sortino A5 clue is anti-momentum, for
    example `Neg(CSRank(Mom($close,4)))` with IC `0.033245` and Sortino
    `0.650420`, still only recent-window research evidence.
- decision:
  previous unlagged stock-level reports are superseded for open-decision
  interpretation. No existing stock-level candidate is commercial/promotion
  ready. Next work should deepen A5 inverse-vol/anti-momentum diagnostics under
  PIT industry, ST-aware limits, costs, turnover, and explicit open/close
  execution assumptions before any new search expansion.
- verification:
  added a focused unit test proving `feature_lag_days=1` uses each stock's
  prior-day signal for the decision date. The synthetic panel is intentionally
  constructed so unlagged same-day rank has IC near `-1`, while the lagged
  signal has IC near `+1`.
  `py_compile` OK, `unittest -k feature_lag` OK, `unittest -k
  real_market_validation` ran `14` tests OK, and `git diff --check` OK with
  CRLF warnings only.

2026-04-27 Stock-level true trading-clock refinement:

- user correction:
  the user was right that whole-expression `feature_lag_days=1` is too blunt
  for every open-decision use case. Some data is available after the opening
  print, especially `open_t` and open-derived gap/overnight fields. The stricter
  rule is timestamp-specific, not formula-wide.
- code correction:
  `src/our_system_phase2/services/real_market_validation.py` now exposes
  `signal_clock`:
  - `after_close`: raw daily bar fields are available before the next session.
  - `pre_open`: current-day daily bar fields, including `open_t`, are not
    available for opening-auction submission.
  - `after_open`: current-day `open` / `overnight` are available after the
    opening print, while full-day `high/low/close/amount/volume/ret` style
    fields use prior-day availability.
- evaluator correction:
  explicit `Delay($field,k)` is not double-shifted under `after_open`; raw field
  children use `max(k, required_field_lag)`. This matters for A5 gap formulas
  such as `Div(Sub($open,Delay($close,1)),Delay($close,1))`.
- representative after-open replay:
  `reports/PHASE2_STOCK_LEVEL_REVALIDATION_AFTER_OPEN_CLOCK_2026-04-27.md`
- representative after-open results:
  - `CSRank($overnight)`: mean IC `0.003510`, mean Sortino `-0.886493`.
  - v18 mean-abs3: mean IC `0.010039`, mean Sortino `0.956750`.
  - v18 compact center: mean IC `0.006611`, mean Sortino `0.629252`.
  - `CSRank($open)`: mean IC `0.000943`, mean Sortino `0.078252`.
  - `CSRank(Mom($close,8))`: mean IC `-0.016640`, mean Sortino `-0.526462`.
- existing ledger after-open recheck:
  `reports/PHASE2_STOCK_LEVEL_EXISTING_LEDGER_RECHECK_AFTER_OPEN_CLOCK_2026-04-27.md`
- ledger after-open read:
  - v19 retained ledger: `14/14` evaluated, `0` promoted; best IC `0.007128`.
  - v18 retained ledger: `72/72` evaluated, `3` pass current fast-screen but
    still have insufficient quarterly windows; best IC `0.010423`, Sortino
    `1.003796`.
  - A5 parameterized ledger: `180/180` evaluated, `62` pass current fast-screen
    but all remain research-only due the short recent window. Highest IC remains
    inverse-vol around `0.0515` with negative Sortino. The better positive
    spread clues are gap/anti-momentum: `a5-real-param-0082` /
    `Neg(CSRank(Div(Sub($open,Delay($close,5)),Delay($close,5))))` has IC
    `0.033718` and Sortino `0.691953`; `a5-real-param-0066` /
    `Neg(CSRank(Mom($close,4)))` has IC `0.033245` and Sortino `0.650420`.
- verification:
  added tests proving `after_open` shifts full-day close fields, keeps
  current-day open, `pre_open` lags open, and explicit `Delay($close,1)` is not
  double-shifted. `py_compile` OK, `unittest -k after_open` ran `3` tests OK,
  and `unittest -k real_market_validation` ran `17` tests OK.
- decision:
  use `signal_clock=after_open` as the preferred open-decision replay only when
  the decision is made after the opening print and execution is not assumed at
  that same opening print. For opening-auction submission, use `pre_open`.
  Current daily data still cannot validate same-open or intraday post-open fill
  quality; that requires minute/tick data.

2026-04-27 A-share adapter architecture correction:

- user correction:
  the user objected that a candidate-count cap can look like a hard search-space
  limit and conflict with the system's unlimited-space goal. The user also
  pointed out that A-share constraints must be global, not specific to gap
  formulas.
- code correction:
  added `src/our_system_phase2/services/ashare_search_adapter.py` as an
  independent market adapter. It does not modify the portable core search
  system. The adapter uses training-style scheduling:
  `start_round`, `round_count`, and `candidates_per_family_per_round`.
  Candidate count is an output of the schedule, not a search-space cap.
- search semantics:
  the existing core runtime already has `rounds`, `round_index`, and
  `per_lane_budget`. `seed_source` means where the run starts from
  (`bootstrap_cold_start`, `phase1_seed`, continuation, etc.). `seed_key` is a
  deterministic generation context used by from-scratch/template generation; it
  is not an ML training sample and not a space boundary.
- constraint semantics:
  `ashare_constraints_apply_to_all_candidates = true` is attached at ledger and
  record level. Limit-up/down, suspension, T+1, signal-clock availability, and
  no exit-day outcome deletion apply to every candidate family. Gap is only one
  expression family; it does not receive a special constraint regime.
- field timestamp reminder:
  some fields can carry implicit future leakage depending on `signal_clock`.
  The adapter only recommends the validation clock. The validator must still
  enforce field-level availability: `pre_open` cannot use current `open`;
  `after_open` can use current `open/overnight` but full-day bar fields must be
  as-of prior day; `after_close` can use the full daily bar only for later
  execution.
- verification:
  `py_compile` OK for the A-share adapter and tests. `unittest -k ashare` ran
  `2` tests OK. `git diff --check` OK with CRLF warnings only.

2026-04-27 A-share adapter targeted round-0 search:

- ledger:
  `reports/PHASE2_ASHARE_ADAPTER_TARGETED_LEDGER_2026-04-27.json`
- validation report:
  `reports/PHASE2_ASHARE_ADAPTER_TARGETED_RECHECK_AFTER_OPEN_2026-04-27.md`
- schedule:
  `start_round=0`, `round_count=6`,
  `candidates_per_family_per_round=8`. This produced `130` candidates from a
  current parameter-slice space of `506` possible candidates. Candidate count is
  the result of the round schedule, not a hard space cap.
- family coverage:
  - `ashare_gap_reversal`: `36` evaluated, `20` routed to fast full-history
    review.
  - `ashare_short_term_anti_momentum`: `46` evaluated, `44` routed.
  - `ashare_vol_normalized_gap_reversal`: `48` evaluated, `29` routed.
- top recent-window candidates:
  - `ashare-adapter-0046` /
    `Neg(CSRank(Div(Sub($open,Delay($close,5)),Delay($close,5))))`: IC
    `0.033718`, Sortino `0.691953`.
  - `ashare-adapter-0011` / `Neg(CSRank(Mom($close,4)))`: IC `0.033245`,
    Sortino `0.650420`.
  - `ashare-adapter-0064` /
    `Neg(CSRank(Div(Div(Sub($open,Delay($close,2)),Delay($close,2)),Mean(Abs($ret),4))))`:
    IC `0.032888`, Sortino `1.997910`.
- read:
  the adapter is structurally doing what it should: preserving core portability,
  applying A-share constraints globally, and concentrating validation budget on
  families already supported by the corrected after-open stock replay. However,
  `93/130` fast-screen routed candidates are not promotion evidence because the
  screen is still recent three-month evidence only. Next step is to full-history
  / multi-window validate the top family representatives under the same
  `signal_clock=after_open`, PIT industry, ST-aware limit, cost, and turnover
  protocol.

2026-04-27 A-share top candidate long-only diagnostic:

- report:
  `reports/PHASE2_ASHARE_TOP_CANDIDATE_LONG_ONLY_DIAGNOSTIC_2026-04-27.md`
- reason:
  the user correctly challenged that IC around `0.03` may still be weak and
  that inverted signals can be meaningless if the economics come mostly from
  the short/avoid leg. The diagnostic splits top long leg, bottom leg, universe
  return, top excess, spread, hit rate, drawdown, and decile bucket curve under
  `signal_clock=after_open` and entry-only tradability.
- result:
  - `gap5_inverted`: mean IC `0.027679`, but top excess only `0.000137` with
    top-excess hit rate `0.444444`. This is weak for A-share long-only use.
  - `mom4_inverted`: mean IC `0.027632`, top excess `0.000178`, hit rate
    `0.476190`. Also weak as a standalone long-only signal.
  - `gap2_vol4_inverted`:
    `Neg(CSRank(Div(Div(Sub($open,Delay($close,2)),Delay($close,2)),Mean(Abs($ret),4))))`
    has mean IC `0.026191`, top excess `0.000724`, top-excess Sortino
    `3.256008`, top-excess max drawdown `-0.010166`, and a much cleaner
    low-to-high signal bucket curve. This looks less like pure short-leg alpha
    and more like a candidate long-only research clue.
- decision:
  do not treat all inverted signals as equally meaningful. Plain gap reversal
  and plain anti-momentum remain weak/avoidance-like. The next serious branch
  should focus on vol-normalized gap reversal, then test it across more
  windows, costs, turnover, PIT industry, and stricter ST/limit handling.

2026-04-27 A-share adapter external-benchmark alignment correction:

- user correction:
  the user objected that the new A-share targeted method looked like it was
  locking interactions and reducing the formula space to a few single-field
  stacks. That objection is valid. A5 is our own failed/partly failed prior
  work and should not be treated as an external benchmark. The useful external
  references are CFG, AlphaForge, and AlphaGPT-style systems, where broad
  expression generation, interaction discovery, and parameter exploration live
  in the grammar/tree/program search layer. A market adapter should not define
  the search grammar.
- local external-reference read:
  - CFG remains valuable as a complex-expression generator: the local snapshot
    exposes unary, binary, rolling, and paired-rolling operator actions plus
    MCTS/self-play.
  - AlphaGPT/AlphaForge-style evidence should be interpreted as tree/program
    generation and subtree/parameter mutation, not as a fixed A-share formula
    family list.
  - A5 can only be used as an internal postmortem/replay source, not as a
    competitor target.
  - The existing Phase2 core already has interaction generation through
    natural-parameter ledgers, residual surfaces, bridge/crossover, and
    variation logic.
- code correction:
  `src/our_system_phase2/services/ashare_search_adapter.py` is now explicitly
  a market-contract and evaluation adapter, not a formula generator. It records:
  `does_not_define_formula_space = true`, formula generation owner as
  `portable_core_search_or_external_generators_cfg_a5_alphagpt`, and an
  interaction policy that the adapter never locks formula interactions.
- semantic correction:
  `build_ashare_targeted_search_ledger` is demoted to a diagnostic seed lane.
  It is preserved only for reproducible probes around gap/anti-momentum clues;
  it is not the primary search generator and should not be used to judge the
  breadth of our search space.
- main path:
  generate candidates using core Phase2 / CFG / AlphaForge / AlphaGPT-style
  ledgers,
  then run `annotate_ledger_for_ashare(...)` and validate under A-share clock,
  T+1, limit-up/down, suspension, PIT industry, cost, turnover, and leakage
  rules.

2026-04-27 A-share generated-then-checked validation closure:

- user correction:
  the user challenged whether the implementation truly performs generation
  first and A-share checking second. The challenge was valid: the adapter wrote
  `recommended_validation_kwargs`, but `batch_validate_candidate_ledger` still
  required the caller to pass `signal_clock` and lag settings explicitly.
- code correction:
  `batch_validate_candidate_ledger` now reads a ledger's
  `recommended_validation_kwargs` by default. Explicit function arguments still
  override ledger defaults.
- implication:
  the intended main path is now represented in code: external/core generator
  produces a ledger, `annotate_ledger_for_ashare` adds market-contract metadata,
  and batch validation consumes those defaults before evaluating expressions.
- efficiency read:
  field timestamp and tradability constraints are mostly cheap rule/metadata
  gates compared with the expensive part: expression evaluation, rolling
  operations, cross-sectional ranks, repeated panel loading, and repeated
  subexpression recomputation. Once field availability is encoded at the field
  schema / AST level, leakage checks should not be a major source of search
  inefficiency.

2026-04-27 External formula-generator review and non-A5 replay:

- report:
  `reports/PHASE2_EXTERNAL_FORMULA_GENERATOR_REVIEW_2026-04-27.md`
- external references:
  AlphaForge, AlphaGen, AutoAlpha, and AlphaCFG. A5 is treated only as internal
  postmortem/replay material, not as an external benchmark.
- replay protocol:
  generator ledger -> `annotate_ledger_for_ashare(signal_clock=after_open)` ->
  `batch_validate_candidate_ledger` consumes ledger defaults -> stock-level
  recent three-month fast screen on
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_validation_slice_2026-04-27.csv.gz`.
- CFG external reference pool:
  `10/10` evaluated, `0` unsupported, `0` routed to full-history review. Best
  candidate `cfg-seed11-001` has recent IC `0.005269`, Sortino `1.340627`, and
  remains `watchlist_weak_positive_recent_ic`.
- Phase2 core V8 rank-quotient top20:
  `20/20` evaluated, `0` unsupported, `0` routed. Best candidate
  `v8-natural-0024` /
  `CSRank(Sub(Mom($close,4),Mom($close,17)))` has recent IC `0.008788` and
  Sortino `-1.055777`.
- read:
  the adapter/validation path is working, but neither CFG frozen pool nor core
  V8 top20 is strong under corrected A-share stock-level replay. The next
  target is a formula-generator policy upgrade: grammar frontier, semantic
  quotient, quality-diversity allocation, and pool-aware reward. Do not continue
  expanding hard-coded A-share formula families.

2026-04-27 External formula generation policy layer:

- status:
  deprecated as a side-path after user correction. The implementation and test
  were removed from the active Phase2 code path so the project does not drift
  away from the native archive/lane/surrogate/coverage-refresh runtime.
- artifacts:
  - `reports/PHASE2_EXTERNAL_FORMULA_GENERATION_POLICY_LEDGER_2026-04-27.json`
  - `reports/PHASE2_EXTERNAL_FORMULA_GENERATION_POLICY_ASHARE_ADAPTED_LEDGER_2026-04-27.json`
- actual plan:
  `55` source records from CFG plus core V8, `0` rank-validation semantic
  duplicates under current quotient, `24` scheduled records, `10` buckets.
- role:
  historical side experiment only. Do not use it as the next engineering path.
  The active generator upgrade is Phase2-native AST expansion inside
  `variation.py` and `prototype_run.py`.

2026-04-27 Phase2-native generator correction:

- user correction:
  the user correctly pushed back that Phase2 should not be replaced by an
  external formula-policy layer. Phase2's core remains the archive/lane/
  surrogate/coverage-refresh/gate runtime.
- implementation:
  added `phase2_native_ast_expansion(...)` inside
  `src/our_system_phase2/services/variation.py`.
- integration:
  `src/our_system_phase2/runtime/prototype_run.py` now adds
  `phase2_native_ast_expansion` candidates inside `_coverage_refresh_candidate_pool`.
  These candidates still flow through the existing target-aware pre-screen,
  archive update, behavior-cell accounting, and gates.
- method:
  this is not CFG/AlphaForge/AlphaGPT reuse and not an A-share adapter path.
  It uses Phase2's own archive subtrees, target behavior, target-aware fields,
  archive-observed windows, structural skeleton novelty, and surrogate
  fingerprint distance to synthesize stronger candidate formulas when a lane
  needs coverage refresh.
- tests:
  added a direct native-AST test and extended the coverage-refresh pool test to
  require native-AST candidates. Both pass.
- read:
 external methods remain inspiration only. The active generator upgrade is now
 back inside Phase2's native search loop.

2026-04-27 Phase2-native continuation validation:

- previous-root tested:
  `runtime/next_stage_artifacts/phase2-flow-5667ea92d1/phase2-2a41807d3e`.
  This was chosen because the next old continuation in that flow had stalled
  at M4 with zero coverage gain.
- first native-AST smoke continuation:
  `runtime/next_stage_artifacts/phase2-native-ast-continuation-20260427/phase2-a86172ac30`.
  Coverage refresh fired `31` times and produced `279` native-AST pool
  candidates, but `predicted_new_cell_count` stayed `0`; archive growth was
  `0` and M4 still failed. Diagnosis: the generator was active, but target
  field selection was too one-dimensional for missing behavior cells such as
  `low_momentum|high_size|stable|low_vol|mean_revert`.
- correction:
  `_fields_for_target(...)` now composes fields across all behavior axes
  instead of returning the first matching branch, and reachability survey now
  includes Phase2-native AST proposals. Coverage-refresh events also record
  selected refresh sources for auditability.
- corrected continuation:
  `runtime/next_stage_artifacts/phase2-native-ast-continuation-v3-20260427/phase2-8c7c324b74`.
  Result: `archive_growth=2`, `total_new_behavior_cells=3`,
  `avg_generated_per_round=3.666667`, `retained_yield=0.636364`,
  `non_score_retained_ratio=1.0`, and M1-M6 all pass.
- source read:
  selected new-cell candidates came from Phase2 coverage-refresh
  archive-synthesis/reachability seeds after the target-field correction, not
  directly from `phase2_native_ast_expansion` in this replay. Native AST still
  contributed `27` pool candidates and `5` predicted-new-cell pool hits in the
  corrected run, but it was not the selected source. Treat this as a native
  Phase2 search-efficiency improvement, not as evidence of real-market edge.
- next target:
  run a bounded multi-step continuation from the corrected path before any
  large-scale search. Watch bridge-frontier starvation: in the corrected run
  bridge generated `4`, retained `0`, so scaling is not yet allowed by the
  lane-yield guard even though milestone gates passed.

2026-04-27 Bounded post-correction continuation:

- artifact:
  `runtime/next_stage_artifacts/phase2-native-ast-bounded-continuation-20260427/phase2-flow-876c84e1c0`.
- input previous root:
  `runtime/next_stage_artifacts/phase2-native-ast-continuation-v3-20260427/phase2-8c7c324b74`.
- result:

| sequence | run id | archive growth | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | phase2-bd7b805e69 | 0 | 0.400000 | 1.000000 | false |
| 2 | phase2-150db14df6 | 0 | 0.421053 | 1.000000 | false |
| 3 | phase2-714a712f85 | 0 | 0.421053 | 0.875000 | false |

- M4:
  all three steps failed M4 with `coverage_gain=0.0`; quality
  noninferiority stayed positive (`0.631043`, `0.635419`, `0.636850`).
- coverage-refresh read:
  no coverage-refresh events fired in the bounded continuation because the
  corrected replay had already occupied all `32` coarse behavior cells.
- conclusion:
  do not start large-scale search yet. The current bottleneck is no longer
  candidate count or target-field choice; it is the finite coarse behavior
  grid. Once all 32 cells are occupied, "new cell" coverage is exhausted and
  M4 cannot represent continued progress. The next Phase2-native math upgrade
  should be hierarchical/adaptive behavior-cell refinement or within-cell
  dominance-frontier search, so the search space remains effectively unbounded
  after the coarse grid saturates.

2026-04-27 Adaptive behavior-cell refinement:

- implementation:
  added deterministic `adaptive_archive_cell` metadata derived from the
  existing behavioral fingerprint. The original coarse `archive_cell` is
  unchanged, so old Phase2 cell semantics remain intact.
- archive behavior:
  `PrototypeArchive` still keeps `cell_index` as the coarse incumbent map, but
  now also tracks `refined_cell_index`. A candidate in an occupied coarse cell
  can be retained if it opens a new adaptive refined cell; dominance replacement
  still controls the coarse incumbent.
- search behavior:
  target-aware pre-screen, score-lane productive-parent checks, and
  coverage-refresh pool ranking now treat adaptive refined cells as valid
  new-cell opportunities. This prevents the saturated 32-cell grid from
  blocking continued Phase2-native exploration.
- tests:
  added tests for refined-cell retention and deterministic adaptive-cell
  assignment. Targeted adaptive/archive/coverage-refresh/score-parent tests
  pass.
- bounded replay artifact:
  `runtime/next_stage_artifacts/phase2-adaptive-cell-bounded-continuation-20260427/phase2-flow-336ed281d3`.
- input previous root:
  `runtime/next_stage_artifacts/phase2-native-ast-continuation-v3-20260427/phase2-8c7c324b74`.
- result:

| sequence | run id | archive growth | new adaptive cells | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | phase2-f572016492 | 36 | 37 | 0.764706 | 0.846154 | true |
| 2 | phase2-55d4c28173 | 27 | 32 | 0.816327 | 0.850000 | true |
| 3 | phase2-b5369ee8aa | 24 | 27 | 0.595745 | 0.928571 | true |

- M4:
  coverage gain recovered from `0.0/0.0/0.0` before adaptive refinement to
  `37.0/32.0/27.0`, with positive quality noninferiority throughout
  (`0.591819`, `0.560901`, `0.537449`).
- warning:
  the third adaptive run has score-frontier retained yield below floor
  (`2/12 = 0.166667`), while novelty, uncertainty, and bridge remain healthy.
  This does not block the milestone gates, but the next scale-up should monitor
  score-lane waste and avoid spending extra budget there.
- interpretation:
  the finite coarse-grid bottleneck is fixed for synthetic Phase2 search
  runtime. This is a search-efficiency and unbounded-space improvement, not a
  real-market edge claim. The next reasonable step is a limited larger pilot,
  followed by corrected A-share real-data replay only for retained candidates.

2026-04-27 Adaptive behavior-cell scale pilot:

- experiment id:
  `20260427_phase2_adaptive_cell_scale_pilot_001`.
- objective:
  test whether adaptive refined cells keep Phase2-native exploration alive for
  more than the three-step bounded replay before starting any larger search.
- mode:
  light controlled scale pilot, synthetic Phase2 runtime only.
- input previous root:
  `runtime/next_stage_artifacts/phase2-adaptive-cell-bounded-continuation-20260427/phase2-flow-336ed281d3/phase2-b5369ee8aa`.
- command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --output-root runtime\next_stage_artifacts\phase2-adaptive-cell-scale-pilot-20260427 --previous-run-root runtime\next_stage_artifacts\phase2-adaptive-cell-bounded-continuation-20260427\phase2-flow-336ed281d3\phase2-b5369ee8aa --flow-length 5 --rounds 6 --per-lane-budget 3
```

- artifact:
  `runtime/next_stage_artifacts/phase2-adaptive-cell-scale-pilot-20260427/phase2-flow-51216fe097`.
- result:

| sequence | run id | archive growth | new adaptive cells | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | phase2-00fbf71b7f | 10 | 12 | 0.589744 | 0.782609 | true |
| 2 | phase2-84f6cc525d | 5 | 6 | 0.413793 | 0.833333 | true |
| 3 | phase2-740e0e10c0 | 4 | 5 | 0.303030 | 1.000000 | true |
| 4 | phase2-2ee4e25f3c | 4 | 5 | 0.433333 | 0.846154 | true |
| 5 | phase2-ff0e51b43d | 5 | 6 | 0.333333 | 0.833333 | true |

- M4:

| run id | coverage gain | adaptive coverage | quality noninferiority |
| --- | ---: | ---: | ---: |
| phase2-00fbf71b7f | 12.0 | 0.791139 | 0.545085 |
| phase2-84f6cc525d | 6.0 | 0.772152 | 0.538841 |
| phase2-740e0e10c0 | 5.0 | 0.742515 | 0.532659 |
| phase2-2ee4e25f3c | 5.0 | 0.750000 | 0.542467 |
| phase2-ff0e51b43d | 6.0 | 0.719101 | 0.539696 |

- lane diagnostics:

| run id | score yield/new cells | novelty yield | uncertainty yield | bridge yield | below-floor lanes |
| --- | ---: | ---: | ---: | ---: | --- |
| phase2-00fbf71b7f | 0.500000 / 0 | 0.888889 | 0.500000 | 0.500000 | none |
| phase2-84f6cc525d | 1.000000 / 0 | 0.600000 | 0.250000 | 0.222222 | uncertainty_frontier, bridge_frontier |
| phase2-740e0e10c0 | 0.000000 / 0 | 0.500000 | 0.272727 | 0.300000 | uncertainty_frontier, bridge_frontier, score_frontier |
| phase2-2ee4e25f3c | 0.333333 / 0 | 0.571429 | 0.375000 | 0.444444 | score_frontier, uncertainty_frontier |
| phase2-ff0e51b43d | 0.250000 / 0 | 0.500000 | 0.250000 | 0.300000 | score_frontier, uncertainty_frontier, bridge_frontier |

- interpretation:
  adaptive refined cells pass the five-step pilot and keep producing new
  behavior coverage after the old 32-cell grid was exhausted. However, retained
  yield trends down and score contributes zero new adaptive cells throughout
  the pilot. This means the next larger search should not simply multiply
  budget. The next search-runtime upgrade should add saturation-aware budget
  reallocation: shrink or skip lanes with repeated below-floor yield and zero
  new adaptive cells, and redirect budget toward lanes still opening adaptive
  coverage.
- decision:
  `HOLD_RESEARCH` for real edge claims; `PROMOTE_RUNTIME_UPGRADE` for adaptive
  behavior-cell refinement.
- next action:
  implement adaptive saturation-aware lane budget reallocation, then rerun a
  controlled continuation before any high-budget search or real-market replay.

2026-04-27 Adaptive saturation-aware budget reallocation:

- experiment id:
  `20260427_phase2_adaptive_budget_reallocation_pilot_001`.
- implementation:
  generalized high-budget continuation quality control from novelty/bridge
  only to all Phase2 lanes. A lane now sheds budget when its latest retained
  yield is below lane threshold and it opens zero adaptive cells. Recovered
  slots avoid immediately flowing back into suppressed lanes. Score lane can
  relax its absolute floor to `1` after repeated zero-adaptive-cell saturation,
  but this is local to A/B continuation scheduling and does not remove the
  score frontier from the system.
- tests:
  high-budget quality-control tests pass, including a new saturated-score-lane
  test. Adaptive refined-cell tests still pass.
- input previous root:
  `runtime/next_stage_artifacts/phase2-adaptive-cell-scale-pilot-20260427/phase2-flow-51216fe097/phase2-ff0e51b43d`.
- command:

```powershell
$env:PYTHONPATH='G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.generation_run --output-root runtime\next_stage_artifacts\phase2-adaptive-budget-reallocation-pilot-20260427 --previous-run-root runtime\next_stage_artifacts\phase2-adaptive-cell-scale-pilot-20260427\phase2-flow-51216fe097\phase2-ff0e51b43d --flow-length 5 --rounds 6 --per-lane-budget 3
```

- artifact:
  `runtime/next_stage_artifacts/phase2-adaptive-budget-reallocation-pilot-20260427/phase2-flow-6968910605`.
- result:

| sequence | run id | archive growth | new adaptive cells | retained yield | non-score retained ratio | all gates pass |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | phase2-132416c5ca | 3 | 3 | 0.321429 | 0.777778 | true |
| 2 | phase2-69acb607d6 | 3 | 4 | 0.392857 | 0.818182 | true |
| 3 | phase2-11df179e8e | 3 | 3 | 0.111111 | 1.000000 | true |
| 4 | phase2-82872a41a8 | 2 | 3 | 0.366667 | 0.818182 | true |
| 5 | phase2-6590f6184e | 3 | 3 | 0.111111 | 1.000000 | true |

- M4:

| run id | adaptive coverage | quality noninferiority |
| --- | ---: | ---: |
| phase2-132416c5ca | 0.731429 | 0.540199 |
| phase2-69acb607d6 | 0.724719 | 0.540525 |
| phase2-11df179e8e | 0.682540 | 0.540898 |
| phase2-82872a41a8 | 0.704301 | 0.541240 |
| phase2-6590f6184e | 0.670103 | 0.541668 |

- quality-control activity:
  every run triggered saturation-aware budget control. Suppressed lanes included
  uncertainty/novelty/bridge in earlier steps and score in the most saturated
  steps (`phase2-11df179e8e`, `phase2-6590f6184e`).
- interpretation:
  this is a continuation-safety improvement, not proof of stronger alpha
  search. Starting from the already-saturated scale-pilot tail, the system still
  kept all five continuation runs passing and opened adaptive cells each time,
  but retained yield is now low. The correct next decision is not to launch an
  unbounded high-budget run yet; it is to add an explicit stop/escalate rule:
  continue only while adaptive cells are opening at acceptable cost, otherwise
  switch to real-data replay of retained candidates or a new math-search
  operator family.

2026-04-27 Continuation stop/escalate decision gate:

- implementation:
  generation-flow summaries now include `continuation_scale_decision`, built
  from all-gate status, retained-yield trend, adaptive new-cell yield, and
  recent zero-new-cell behavior. It is advisory and auditable: it does not
  claim real edge and does not mutate archive retention.
- decision labels:
  `CONTINUE_CONTROLLED_SYNTHETIC_SEARCH`,
  `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`,
  `HOLD_SYNTHETIC_SCALE_IMPROVE_EFFICIENCY`,
  `ESCALATE_OPERATOR_FAMILY`, and `STOP_FIX_RUNTIME_GATES`.
- real-edge guard:
  the decision gate always sets `real_edge_claim_allowed=false`; promotion
  still requires timestamp-aligned features, A-share T+1 execution alignment,
  limit-up/down entry/exit tradability filters, costs/slippage/turnover/capacity
  checks, and quarterly 3-month walk-forward replay.
- tests:
  added direct decision tests for low-yield replay routing and healthy
  controlled continuation. Existing budget-profile comparison still passes.
- retroactive read on the latest reallocation pilot:
  `phase2-adaptive-budget-reallocation-pilot-20260427/phase2-flow-6968910605`
  resolves to `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`.
- diagnostic:
  average archive growth `2.8`, average retained yield `0.260635`, average
  adaptive new-cell yield `0.103333`, all runs pass `true`, recent yield below
  floor `true`, recent zero adaptive gain `false`.
- conclusion:
  the system is still exploring, but not efficiently enough to justify another
  synthetic scale-up. The next work item should be real-data replay on retained
  candidates under the corrected A-share execution contract, not more blind
  synthetic continuation.

2026-04-27 Adaptive retained real-data replay:

- experiment id:
  `20260427_adaptive_retained_real_replay_001`.
- source:
  `runtime/next_stage_artifacts/phase2-adaptive-budget-reallocation-pilot-20260427/phase2-flow-6968910605/phase2-6590f6184e/candidate_ledger.json`.
- selection:
  picked 12 retained candidates by lowest estimated validation cost from the
  latest adaptive archive tail. This was a pipeline replay subset, not new
  discovery and not a synthetic-IC winner showcase.
- A-share execution contract:
  signal clock `after_open`; current-day `open` is allowed, full-day bar fields
  are lagged to prior day by field-clock policy; execution lag is T+1; entry
  limit-up buys, entry limit-down sells, and suspended rows are blocked; exit
  day limit state is audit-only and not used for signal-day filtering.
- recent one-quarter replay:
  artifact `reports/PHASE2_ADAPTIVE_RETAINED_REAL_REPLAY_2026-04-27.json`.
  Window `2026-01-01` to `2026-02-04`, loaded rows `46752`,
  evaluated `12`, unsupported `0`, passed smoke `0`.
- recent four-quarter replay:
  artifact
  `reports/PHASE2_ADAPTIVE_RETAINED_REAL_REPLAY_RECENT4Q_2026-04-27.json`.
  Window `2025-04-01` to `2026-02-04`, evaluated `12`, unsupported `0`,
  passed smoke `0`.
- best four-quarter replay read:
  `v2cand-770b6568d717`, expression
  `Div(Mean($amount,2),Mean($volume,5))`, mean rank IC `0.002163`,
  Sortino `-0.074092`; flagged `weak_mean_rank_ic_below_0_01` and weak
  positive-ratio evidence. The next candidate was only `0.001093` mean rank IC.
- conclusion:
  synthetic adaptive retained candidates do not currently transfer to a usable
  A-share real-market edge under the corrected clock, T+1, and tradability
  rules. Continue treating Phase2 search as a generator/evaluator system under
  construction. The next math-search upgrade should use real replay feedback to
  change the objective/operator family, not merely keep opening synthetic
  behavior cells.

2026-04-27 Real replay feedback objective:

- implementation:
  added a real-replay feedback objective helper that converts corrected
  A-share replay results into soft search priors. It does not promote
  candidates, does not prune or lock formula space, and does not change archive
  retention.
- artifact:
  `reports/PHASE2_REAL_REPLAY_FEEDBACK_OBJECTIVE_2026-04-27.json`.
- review:
  `reports/PHASE2_REAL_REPLAY_FEEDBACK_OBJECTIVE_REVIEW_2026-04-27.md`.
- source:
  `reports/PHASE2_ADAPTIVE_RETAINED_REAL_REPLAY_RECENT4Q_2026-04-27.json`.
- decision:
  `USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH`.
- metrics:
  evaluated `12`, supported `8`, passed smoke `0`, weak-positive `2`,
  mean rank IC across supported candidates `-0.009802`.
- weak-positive motifs:
  `v2cand-770b6568d717`
  `Div(Mean($amount,2),Mean($volume,5))`, mean rank IC `0.002163`;
  and `v2cand-5c213236a71f`
  `Cov(CSRank($open), Corr(Div(Mean($amount,2),Mean($volume,5)), Abs($pldn)))`,
  mean rank IC `0.001093`.
- demotion read:
  broad `field:$amount` and `field:$volume` groups are still negative on
  average (`-0.009802`), so the feedback must not naively upweight all amount
  or volume formulas. The only watch signal is the local amount/volume quotient
  motif under corrected after-open/T+1 replay.
- next search objective adjustment:
  increase weight on real replay rank IC, positive-window ratio, and
  tradability-filtered top/bottom spread; decrease weight on synthetic IC
  without real replay support and coverage-only growth after retained-yield
  floor breaks; hard-block signal-clock lookahead and impossible limit-up/down
  entry assumptions.
- conclusion:
  next Phase2 search should be real-feedback-guided, not synthetic-coverage-led.
  This is still `HOLD_RESEARCH` for commercial edge.

2026-04-27 Real-feedback-guided search audit pilot:

- implementation:
  wired the real replay feedback objective into generation flow as a soft
  routing prior. It can move one slot from demoted lanes toward weak-positive
  lanes and add a small expression-level pre-screen bonus for local motifs.
  It still does not lock formula space, change archive retention, or allow a
  real-edge claim.
- level0 audit fix:
  selected candidates now carry their real-replay feedback context into the
  evaluator. Positive feedback candidates can trigger a bounded level0 review
  when the raw surrogate gate would reject them, but they still must pass
  later short-window/regime/full-evaluation gates before any retention effect.
- artifact:
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-audit-pilot-20260427/phase2-flow-6002589871`.
- result:
  two-run flow passed all gates. Continuation decision:
  `CONTINUE_CONTROLLED_SYNTHETIC_SEARCH`.
- M3 before/after read:
  the earlier feedback-guided pilot failed M3 with level0 rejection rates
  `0.857143` and `0.904762`. After carrying feedback into bounded level0
  audit, the same-scale pilot passed M3 with rejection rates `0.52381` and
  `0.571429`, false-negative rate `0.0`, and full-evaluation ratio `0.0`.
- feedback usage:
  run `phase2-1efff4d85a` had 3 lane-transfer events, 11 feedback-scored
  selected candidates, and 7 level0 feedback-review events. Run
  `phase2-2be9a55c02` had 4 lane-transfer events, 13 feedback-scored selected
  candidates, and 7 level0 feedback-review events.
- generation efficiency:
  archive growth stayed at `3` per run; retained yield was `0.47619` then
  `0.333333`; adaptive new-cell yield was `0.190476` in both runs.
- interpretation:
  this fixes a search-mechanics bug: real replay feedback was previously used
  for candidate selection but then discarded by the evaluator funnel. The fix
  makes feedback auditable in the funnel without converting weak real replay
  evidence into a promotion rule. It is a readiness step for the next bounded
  search, not evidence of commercial tradable alpha.

2026-04-27 Real-feedback-guided continuation and replay:

- continuation artifact:
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-continuation-20260427/phase2-flow-83a2ff2508`.
- continuation result:
  three continuation runs all passed gates, but the flow-level decision moved
  back to `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`.
- continuation diagnostics:
  archive growth trend `[0, 3, 0]`, retained-yield trend
  `[0.315789, 0.277778, 0.315789]`, average retained yield `0.303119`,
  average adaptive new-cell yield `0.109162`. Recent retained yield stayed
  below the `0.4` floor, so more synthetic budget is not justified.
- funnel diagnostics:
  M3 passed in all three runs. Level0 rejection rates were `0.631579`,
  `0.5`, and `0.631579`; real-feedback level0 review events were `6`, `7`,
  and `6`; full-evaluation ratio remained `0.0`.
- real replay artifact:
  `reports/PHASE2_REAL_FEEDBACK_CONTINUATION_REAL_REPLAY_2026-04-27.json`.
- selected replay ledger:
  `reports/PHASE2_REAL_FEEDBACK_CONTINUATION_REAL_REPLAY_LEDGER_2026-04-27.json`.
- replay review:
  `reports/PHASE2_REAL_FEEDBACK_CONTINUATION_REAL_REPLAY_REVIEW_2026-04-27.md`.
- replay contract:
  latest retained generated candidates, 12 lowest estimated validation-cost
  samples, after-open signal clock, T+1 execution, field-clock lag policy, and
  limit-up/down entry tradability filters over recent four 3-month windows.
- replay result:
  evaluated `12`, unsupported `0`, passed smoke `0`, promoted to full-history
  review `0`.
- best replay read:
  `v2cand-770b6568d717`, expression
  `Div(Mean($amount,2),Mean($volume,5))`, mean window rank IC `0.002163`,
  recent mean rank IC `0.002163`; flags:
  `weak_mean_rank_ic_below_0_01`,
  `recent_positive_quarter_ratio_below_0_5`.
- conclusion:
  the real-feedback wiring improved search mechanics and funnel calibration,
  but did not discover a new real A-share edge. The next productive step is
  not more same-family continuation; it is a math/operator-family upgrade or
  objective redesign that creates new real-data hypotheses before another
  bounded synthetic run.

2026-04-28 Expanded feedback-guided search sample:

- rationale:
  sample size was plausibly too small, so one more bounded search was run with
  a wider but still controlled budget. This remains research sampling, not
  commercial edge evidence.
- artifact:
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-expanded-search-20260428/phase2-flow-41f350aba7`.
- settings:
  previous root
  `phase2-real-feedback-guided-continuation-20260427/phase2-flow-83a2ff2508/phase2-e45497060b`;
  `flow-length=3`, `rounds=6`, `per-lane-budget=4`, real replay feedback
  objective enabled.
- synthetic search result:
  all runs passed gates. Generated candidates per run were `44`, `35`, and
  `42`; retained-yield trend was `[0.295455, 0.4, 0.238095]`; adaptive
  new-cell yields were approximately `0.227273`, `0.142857`, and `0.166667`.
  The flow decision still resolved to `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`
  because average retained yield was only `0.311183`.
- M3/funnel read:
  level0 rejection rates were `0.431818`, `0.457143`, and `0.5`; false
  negative rate stayed `0.0`; full-evaluation ratio stayed `0.0`; feedback
  level0 review events were `8`, `7`, and `8`.
- expanded replay selection:
  retained candidate pool before/after expression dedupe was `516` / `167`.
  The previous 12 replayed expressions were excluded, then 24 low validation
  cost candidates were selected.
- replay artifact:
  `reports/PHASE2_REAL_FEEDBACK_EXPANDED_SEARCH_REAL_REPLAY_2026-04-28.json`.
- selected replay ledger:
  `reports/PHASE2_REAL_FEEDBACK_EXPANDED_SEARCH_REAL_REPLAY_LEDGER_2026-04-28.json`.
- replay review:
  `reports/PHASE2_REAL_FEEDBACK_EXPANDED_SEARCH_REAL_REPLAY_REVIEW_2026-04-28.md`.
- replay result:
  selected `24`, evaluated `24`, unsupported `0`, passed smoke `0`, promoted
  to full-history review `0`, positive mean-rank-IC count `3`.
- best replay read:
  `v2cand-342aa4c73bd5`, expression
  `Cov(CSRank($open), Corr(Cov(Std($ret,20),Cov($low,$pldn)), Abs($pldn)))`,
  mean window rank IC `0.005528`, recent positive quarter ratio `0.75`,
  mean window Sortino `1.448504`; still blocked by
  `weak_mean_rank_ic_below_0_01`.
- interpretation:
  expanding the sample did improve the best observed real replay score and
  found a different local structure, but it still did not cross the smoke
  threshold. The next sensible branch is to mine the new weak-positive
  structure family (`CSRank($open)` interacting with ret/low/pldn covariance)
  or redesign the operator family, not promote anything.

2026-04-28 Deep feedback-guided sample:

- rationale:
  the 12/24 candidate real replays were too small to rule out the line. A
  deeper but still bounded sample was run before abandoning same-family search.
- experiment record:
  `reports/PHASE2_EXPERIMENT_RECORD_DEEP_SAMPLE_2026-04-28.md`.
- search artifact:
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-deep-sample-20260428/phase2-flow-311d09cfd0`.
- settings:
  previous root
  `phase2-real-feedback-guided-expanded-search-20260428/phase2-flow-41f350aba7/phase2-4a6d18305a`;
  `flow-length=6`, `rounds=10`, `per-lane-budget=5`, real replay feedback
  objective enabled.
- synthetic search result:
  all six runs passed gates. Generated candidates per run were
  `83`, `95`, `62`, `86`, `53`, and `83` for total `462`. Retained-yield
  trend fell from `0.216867` to `0.060241`; archive-growth trend was
  `[7, 7, 5, 3, 3, 1]`; average retained yield was `0.145581`; average
  new-cell yield was `0.067247`. The continuation decision stayed
  `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`.
- replay selection:
  retained pool before/after expression dedupe was `979` / `163`, after
  excluding `36` previously replayed expressions. Selected `64` low validation
  cost retained expressions for recent four-quarter replay.
- replay artifact:
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_REAL_REPLAY_2026-04-28.json`.
- selected replay ledger:
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_REAL_REPLAY_LEDGER_2026-04-28.json`.
- replay review:
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_REAL_REPLAY_REVIEW_2026-04-28.md`.
- replay result:
  evaluated `64`, unsupported `0`, passed smoke `2`, positive mean-rank-IC
  count `6`.
- best smoke-pass candidate:
  `v2cand-d09a583f942a`,
  `Cov(Corr(CSRank(Sign(CSRank(Div(Sub(Corr(Abs(Div(Mean($amount,2),Mean($volume,5))), Log(Abs($mbrd))), Mean(Corr(Abs(Div(Mean($amount,2),Mean($volume,5))), Log(Abs($mbrd))),20)), Std(Corr(Abs(Div(Mean($amount,2),Mean($volume,5))), Log(Abs($mbrd))),20))))), $vrat), Sign($amtm))`,
  mean window rank IC `0.013515`, positive quarter ratio `1.0`, Sortino
  `1.563898`.
- second smoke-pass candidate:
  `v2cand-d6f7431bf3cc`, mean window rank IC `0.010869`, positive quarter
  ratio `1.0`, Sortino `0.488397`.
- strict top2 audit:
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_TOP2_STRICT_AUDIT_2026-04-28.json`;
  review
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_TOP2_STRICT_AUDIT_REVIEW_2026-04-28.md`.
- strict audit read:
  both candidates remain `HOLD_RESEARCH` because sector neutralization,
  capacity model, and promotion-grade survivorship/universe policy are not
  run. However, neither was killed by the 10bps turnover cost shadow. The best
  candidate kept mean rank IC `0.013515`, mean cost-adjusted window spread
  `0.000256`, mean one-way turnover `0.161911`, amount exposure `0.07642`,
  and volume exposure `0.072604`. The second kept mean rank IC `0.010869`,
  mean cost-adjusted spread `0.000056`, turnover `0.10718`, amount exposure
  `0.000278`, and volume exposure `0.012678`.
- conclusion:
  the user's objection was correct: sample size was too small to dismiss this
  line. The deeper sample found two research-grade smoke-pass candidates. They
  are not commercial edges yet, but this now justifies a focused family study
  around the normalized amount/volume-mbrd interaction gated through
  CSRank/Sign/Cov with `vrat`, `amtm`, `open`, and `pldn`, plus industry
  neutralization and capacity checks.

2026-04-28 Scale-up feedback-guided search:

- rationale:
  user requested further depth because AlphaGPT-style official runs can use
  much larger step budgets. A larger but still bounded Phase2 continuation was
  run to test whether the deep-sample pass rate improves with more search.
- experiment record:
  `reports/PHASE2_EXPERIMENT_RECORD_SCALEUP_2026-04-28.md`.
- search artifact:
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-scaleup-20260428/phase2-flow-ff635e6af9`.
- settings:
  previous root
  `phase2-real-feedback-guided-deep-sample-20260428/phase2-flow-311d09cfd0/phase2-53b79255bd`;
  `flow-length=10`, `rounds=12`, `per-lane-budget=6`, real replay feedback
  objective enabled.
- synthetic search result:
  all ten runs passed gates. Total generated candidates `1069`. Retained-yield
  trend stayed low:
  `[0.160494, 0.101562, 0.155844, 0.092308, 0.093333, 0.078571, 0.197183, 0.089655, 0.117647, 0.080292]`.
  Average retained yield `0.116689`, average new-cell yield `0.049654`.
  Continuation decision remained `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`.
- replay selection:
  retained pool before/after expression dedupe was `1175` / `135` after
  excluding continuation, expanded, and deep-sample replay expressions. This
  high duplication rate is an important search-efficiency warning.
- replay artifact:
  `reports/PHASE2_REAL_FEEDBACK_SCALEUP_REAL_REPLAY_2026-04-28.json`.
- selected replay ledger:
  `reports/PHASE2_REAL_FEEDBACK_SCALEUP_REAL_REPLAY_LEDGER_2026-04-28.json`.
- replay review:
  `reports/PHASE2_REAL_FEEDBACK_SCALEUP_REAL_REPLAY_REVIEW_2026-04-28.md`.
- replay result:
  selected `128`, evaluated `128`, unsupported `0`, passed smoke `0`,
  positive mean-rank-IC count `9`.
- best new replay read:
  `v2cand-ab4462fe082e`, mean window rank IC `0.002717`, positive quarter
  ratio `0.75`, Sortino `1.171518`; still blocked by
  `weak_mean_rank_ic_below_0_01`.
- interpretation:
  scale-up did not find additional smoke-pass expressions beyond the two found
  in the previous deep sample. The larger continuation generated many
  candidates, but after excluding already tested expressions only `135` unique
  retained expressions remained, and the best new IC fell back to `0.002717`.
 This suggests the current generator is saturating/repeating rather than
 compounding edge discovery. The two deep-sample pass candidates remain the
 main research leads; the next efficiency improvement should focus on
 family-specific search and diversity/novelty control, not simply more of the
 same continuation.

2026-04-28 Feature lag sensitivity audit:

- rationale:
  user raised a valid concern that the weak scale-up result could come from
  mistaken `+1` / `-1` feature timestamp handling rather than a genuinely weak
  search line.
- code fix:
  `evaluate_panel_expression` now includes the field-lag policy in expression
  cache keys. This prevents mixed `after_open` / `pre_open` / `after_close`
  diagnostics from reusing a cached signal computed under a different timestamp
  policy. Normal single-policy batch replay was not the main risk, but the
  sensitivity audit needed this separation.
- audit artifact:
  `reports/PHASE2_FEATURE_LAG_SENSITIVITY_TOP2_2026-04-28.json`; review
  `reports/PHASE2_FEATURE_LAG_SENSITIVITY_TOP2_2026-04-28.md`.
- test window:
  recent four 3-month windows, `2025-04-01` to `2026-02-04`, 90 trading-day
  warmup.
- default policy checked:
  `signal_clock=after_open`, `feature_lag_days=0`, `execution_lag_days=1`.
  Current-day `open` is allowed; full-day bar fields and aliases such as
  `amount`, `volume`, `vwap`/`mbrd`, `turnover_rate`/`vrat`, and `amtm` are
  field-lagged to the prior day.
- result for `v2cand-d09a583f942a`:
  default IC `0.013515`; whole-expression extra lag IC `0.015409`;
  `pre_open` IC `0.013515`; `after_close` IC `0.018618`; same-day close-entry
  diagnostic IC `0.007442`. Strict cost-adjusted spread under default stayed
  `0.000256`; extra-lag stayed positive at `0.000365`.
- result for `v2cand-d6f7431bf3cc`:
  default IC `0.010869`; whole-expression extra lag IC `0.013306`;
  `pre_open` IC `0.011402`; `after_close` IC `0.015590`; same-day close-entry
  diagnostic IC `0.009547`. Strict cost-adjusted spread under default stayed
  `0.000056`; extra-lag stayed positive at `0.000108`.
- interpretation:
  the top candidates are not being killed by an accidental whole-expression
  `+1`; adding that lag slightly improves both, which suggests a slow-moving
  structure rather than over-lag damage. However, `after_close` is stronger
  than `after_open`, so same-day full daily bar information can materially
  inflate these formulas if used under the wrong signal clock. For A-share
  open-decision replay, keep field-level timestamp control and do not allow
  raw same-day full-bar fields. The remaining open question is not primarily
  feature lag, but execution modeling: the current default uses next-day close
  entry, while a realistic after-open strategy may need a separate same-day
  tradable close/VWAP entry model rather than bluntly switching all validation
  to `execution_lag_days=0`.
- tests:
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k expression_cache_separates_field_lag_policies`
  OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k after_open_clock`
  ran 3 tests OK.

2026-04-28 Feature lag sensitivity top12 extension:

- artifact:
  `reports/PHASE2_FEATURE_LAG_SENSITIVITY_TOP12_2026-04-28.json`; review
  `reports/PHASE2_FEATURE_LAG_SENSITIVITY_TOP12_2026-04-28.md`.
- sample:
  top 12 candidates by default `after_open`, `execution_lag_days=1` mean
  rank IC from
  `reports/PHASE2_REAL_FEEDBACK_DEEP_SAMPLE_REAL_REPLAY_2026-04-28.json`.
- aggregate result:
  extra whole-expression lag mean delta was `+0.000792`, positive in `9/12`.
  `after_close` mean delta was `-0.000180`, positive in `4/12`.
  same-day close-entry diagnostic mean delta was `-0.000985`, positive in
  `4/12`.
- readout:
  the weak scale-up result is not explained by accidental over-lagging of
  features. Across the top deep-sample candidates, adding an extra
  whole-expression lag is more often helpful than harmful. The current
 `after_open` field-level lag policy therefore remains reasonable for open
 decision replay. The deeper problem is still search saturation / formula
 family quality, plus the need for a more realistic execution-price model
 before commercial-grade claims.

2026-04-28 Three-dimensional pre-screen strengthening:

- rationale:
  the existing system already has result-space diversity (`behavioral_cell` and
  adaptive archive cells), target-space diversity (coverage refresh), and
  generation-space diversity (Phase2-native AST expansion/crossover). The
  missing layer was selection-space diversity before expensive evaluation:
  candidates were still mostly ranked by scalar pre-screen score.
- code change:
  `_target_aware_pre_screen` now adds a soft three-dimensional search profile
  to non-score candidate ranking. The profile measures structural skeleton
  novelty, distinct field count, field-axis coverage, operator-family coverage,
  and relation-plus-temporal interaction. This is a soft bonus, not a hard
  constraint, so it does not lock or shrink the expression space.
- test:
  added a tie-break test proving a multi-field/multi-axis candidate beats a
  single-field stack when target distance and surrogate quality are tied.
  Related target-aware pre-screen tests still pass.
- smoke flow:
  `runtime/next_stage_artifacts/phase2-three-dimensional-pre-screen-smoke-20260428/phase2-flow-5dab0184f3`.
  It continued from
  `runtime/next_stage_artifacts/phase2-real-feedback-guided-scaleup-20260428/phase2-flow-ff635e6af9/phase2-2c98f55fa9`
  with `flow-length=2`, `rounds=6`, `per-lane-budget=4`, and the existing real
  replay feedback objective.
- synthetic result:
  both runs passed gates, but retained yield stayed weak: `0.161290` then
  `0.121212`; archive growth was `4` then `1`. The continuation decision
  remains `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY`.
- profile sanity:
  the selected pre-screen candidates were genuinely richer: selected events had
  average three-dimensional score around `0.197`, average distinct fields about
  `5.1`, and average field-axis count about `2.8-2.9`.
- real replay sample:
  because full replay of all generated candidates timed out, a bounded current
  generated sample was replayed:
  `reports/PHASE2_THREE_DIMENSIONAL_PRE_SCREEN_SMOKE_REAL_REPLAY_SAMPLE_2026-04-28.json`;
  review
  `reports/PHASE2_THREE_DIMENSIONAL_PRE_SCREEN_SMOKE_REAL_REPLAY_SAMPLE_2026-04-28.md`.
  It selected current-run generated ids only, max 16, using retained/rich
  three-dimensional profiles while avoiding obviously expensive expressions
  unless retained. Evaluated `13`, passed smoke `0`, positive mean IC `2`, best
  IC `0.001093` (`v2cand-5c213236a71f`).
- interpretation:
  the new layer improves geometric richness of selected candidates, but by
  itself does not produce stronger real-market replay. Several retained rich
  formulas also yielded `None` metrics because expression complexity produced
  too many NaNs/insufficient valid quarterly observations. The next search
  improvement should therefore combine the 3D selection bonus with an
  availability/density penalty and a bounded-complexity grammar, not simply
  raise depth.

2026-04-28 Three-dimensional density penalty follow-up:

- code change:
  the three-dimensional search profile now includes expression length, operator
  count, relation-operator count, temporal-operator count, max operator depth,
  and an `availability_density_penalty`. The penalty is soft and only reduces
  pre-screen score for expressions likely to create sparse/NaN-heavy real
  validation panels.
- tests:
  added a test proving a compact multi-axis expression beats a deeply nested
  NaN-prone expression under equal surrogate quality and target distance.
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k target_aware_pre_screen`
  ran 7 tests OK.
- smoke artifact:
  `runtime/next_stage_artifacts/phase2-three-dimensional-density-penalty-smoke-20260428/phase2-a68eb64a72`.
  It continued from
  `runtime/next_stage_artifacts/phase2-three-dimensional-pre-screen-smoke-20260428/phase2-flow-5dab0184f3/phase2-de159551d3`.
- synthetic result:
  archive growth `1`, retained yield `0.162162`, total generated `37`, retained
  `6`, new behavior cells `1`. This improved retained yield versus the prior
  smoke run's second step (`0.121212`) but still remains below the scale floor.
  Bridge lane had zero retention, so more depth is not yet justified.
- selected profile read:
  selected candidates still remained rich: average distinct fields `5.19`,
  average field axes `2.857`, average 3D score `0.176571`; average density
  penalty was `0.031143`, max `0.14`.
- bounded real replay:
  `reports/PHASE2_THREE_DIMENSIONAL_DENSITY_PENALTY_REAL_REPLAY_SAMPLE_2026-04-28.json`;
  review
  `reports/PHASE2_THREE_DIMENSIONAL_DENSITY_PENALTY_REAL_REPLAY_SAMPLE_2026-04-28.md`.
  Current generated unique expressions `34`, selected `13`, evaluated `13`,
  passed smoke `1`, positive mean IC `3`, best IC `0.010869`.
- important caveat:
  the smoke-pass candidate was `v2cand-d6f7431bf3cc`, already known from the
  earlier deep-sample replay. This means the strengthened search can recover a
  known valid-ish local family, but it has not yet shown new-edge discovery.
- next action:
  do not jump straight to 20k depth. First add family-level novelty pressure
  against already-replayed winners (`d09a583f942a` and `d6f7431bf3cc`) while
  keeping the density penalty. Then run a medium search and replay only
  low-cost, unique, non-duplicate family representatives.

2026-04-28 Family novelty / seen fallback / saturated-positive feedback:

- family novelty pressure:
  `_target_aware_pre_screen` now computes a structural family signature and a
  soft `family_saturation_penalty` from retained archive family counts. This
  is deliberately local/soft: it discourages crowded families without banning
  their neighborhoods or shrinking the infinite formula space.
- family novelty smoke:
  `runtime/next_stage_artifacts/phase2-family-novelty-pressure-smoke-20260428/phase2-146f9eee89`
  continued from the density-penalty run. Synthetic retained yield weakened to
  `0.060606`, archive growth `1`, generated `33`, retained `2`, and new cells
  `1`. Family signatures were more diverse, but the known replay winner
  `v2cand-d6f7431bf3cc` still appeared, so local family pressure alone is not
  enough.
- seen-candidate fallback guard:
  high-budget continuation fallback now avoids reusing already-seen candidates
  when the candidate pool is empty. Smoke artifact:
  `runtime/next_stage_artifacts/phase2-seen-fallback-guard-smoke-20260428/phase2-28fa901c6c`.
  Current generated count `37`, unique current generated count `33`, duplicate
  count `4`, retained yield `0.135135`, archive growth `1`. The known
  `d6f7431bf3cc` appeared only once in the current generated set instead of
  being repeatedly reintroduced by fallback.
- seen fallback real replay sample:
  `reports/PHASE2_SEEN_FALLBACK_GUARD_REAL_REPLAY_SAMPLE_2026-04-28.json`;
  review
  `reports/PHASE2_SEEN_FALLBACK_GUARD_REAL_REPLAY_SAMPLE_2026-04-28.md`.
  Evaluated `13`, passed smoke `1`, positive mean IC `3`, best IC `0.010869`.
  The pass was still the already-known `v2cand-d6f7431bf3cc`, not a new edge.
- saturated-positive feedback code change:
  `build_real_replay_feedback_objective` now exposes
  `saturated_positive_candidates` for replay-passed candidates. The pre-screen
  feedback score applies a negative exact-match prior via
  `saturated_positive_exact:<candidate_id>`, so an already-passed formula is no
  longer treated as a weak-positive motif to chase again. This is a repeat
  suppression mechanism, not a formula-family ban.
- saturated-positive smoke:
  objective artifact
  `reports/PHASE2_SEEN_FALLBACK_GUARD_FEEDBACK_OBJECTIVE_2026-04-28.json`
  marked `v2cand-d6f7431bf3cc` as saturated. Continuation artifact:
  `runtime/next_stage_artifacts/phase2-saturated-positive-feedback-smoke-20260428/phase2-980d91be24`.
  Current generated count `35`, current unique ids `33`, duplicate count `2`,
  and current `d6f7431bf3cc` count `0`. Synthetic retained yield `0.114286`,
  archive growth `3`, retained `4`, new behavior cells `3`.
- saturated-positive profile sanity:
  target-aware pre-screen selected candidates remained geometrically rich:
  average distinct fields `5.286`, average field axes `3.000`, average operator
  families `4.238`, average 3D score `0.170667`. The added repeat suppression
  did not collapse search back into single-field stacks.
- saturated-positive real replay sample:
  `reports/PHASE2_SATURATED_POSITIVE_FEEDBACK_REAL_REPLAY_SAMPLE_2026-04-28.json`;
  review
  `reports/PHASE2_SATURATED_POSITIVE_FEEDBACK_REAL_REPLAY_SAMPLE_2026-04-28.md`.
  Sample policy: current-run unique records, retained first, then low-cost
  non-retained fill to `13`. Evaluated `13`, unsupported `0`, passed smoke `0`,
  positive mean IC `0`, best mean window rank IC `-0.001817`. Feedback decision
  from this replay is `REJECT_CURRENT_SYNTHETIC_MOTIFS_FOR_REAL_REPLAY`.
- interpretation:
  the latest fixes improve search hygiene: richer geometry is preserved,
  density is controlled, exact repeat winners are suppressed, and duplicate
  current generation falls. But the post-suppression current sample found no
  new real replay support. The next large task should not be blind depth.
  Recommended next move: change the mathematical generation prior toward
  genuinely different interaction mechanisms, especially state-conditioned
  cross-field operators and residualized/local-rank constructions, while
  keeping the A-share timestamp/tradability adapter and replaying bounded
  representative samples every cycle.
- tests:
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k real_replay_feedback`
  ran 6 tests OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k target_aware_pre_screen`
  ran 9 tests OK; `py_compile` OK for the touched runtime, validation, and
  test modules.

2026-04-28 Residual/state-conditioned mathematical prior:

- rationale:
  after saturated-positive suppression, the current generated sample had no
  new real replay support. The next move was therefore a mathematical prior
  shift, not more blind depth. The chosen mechanism family was
  cross-sectional residual interaction gated by state/transition proxies:
  `CSResidual(...) * Sign(CSResidual(...))`, plus local-rank residual pairs.
- code change:
  `phase2_native_ast_expansion` now emits and prioritizes three mechanism
  kinds: `cs_residual_state_gate`, `residual_local_rank_gate`, and
  `local_rank_residual_pair`. `directed_variation` also gets one compact
  `CSResidual` edit for novelty, uncertainty, and bridge lanes. The surrogate
  structural feature extractor now recognizes `add`, `mul`, `zscore`, and
  `csresidual`, and treats `CSResidual` as a pair operator. This remains inside
  the existing searcher; no new large search file was added.
- tests:
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k feature_algebra_is_connected`
  OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k phase2_native_ast_expansion`
  ran 2 tests OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k target_aware_pre_screen`
  ran 9 tests OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k real_market_validation_accepts_cross_sectional_residual`
  OK; `py_compile` OK for touched variation/surrogate/test modules.
- smoke artifact:
  `runtime/next_stage_artifacts/phase2-residual-state-prior-smoke-20260428/phase2-5784639918`.
  It continued from
  `runtime/next_stage_artifacts/phase2-saturated-positive-feedback-smoke-20260428/phase2-980d91be24`
  using `reports/PHASE2_SEEN_FALLBACK_GUARD_FEEDBACK_OBJECTIVE_2026-04-28.json`.
- synthetic readout:
  current generated `50`, unique current ids `50`, duplicate current ids `0`,
  current `d6f7431bf3cc` count `0`, retained `12`, archive growth `9`,
  retained yield `0.24`, new behavior cells `10`. Current `CSResidual`
  candidates `22`; retained `CSResidual` candidates `9`. This is the first
  recent smoke where the new mathematical family actually dominated retained
  candidates instead of merely rediscovering `d6f`.
- bounded after-open replay:
  sample ledger
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_SAMPLE_LEDGER_2026-04-28.json`;
  replay
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_REAL_REPLAY_SAMPLE_AFTER_OPEN_2026-04-28.json`;
  review
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_REAL_REPLAY_SAMPLE_AFTER_OPEN_2026-04-28.md`.
  Policy: current-run unique records, retained first, residual-first, then
  low-cost fill to `16`. Replay used `signal_clock=after_open`,
  `execution_lag_days=1`, `feature_lag_days=0`, recent four 3-month windows,
  and the tradability filter. Evaluated `16`, unsupported `0`, smoke pass `3`,
  positive IC `8`, best mean window rank IC `0.015887`.
- new smoke-pass candidates:
  `v2cand-6b5b53c336ac`:
  `CSRank(Mul(CSResidual(Cov(Div(Mean($amount,2),Mean($volume,5)), Log(Abs($volt))),$mbrd),Sign(CSResidual($arat,$pldn))))`,
  mean IC `0.015887`;
  `v2cand-f54b89b324c8`:
  `CSRank(Mul(CSResidual(Div(Mean($amount,2),Mean($volume,5)),$mbrd),Sign(CSResidual($arat,$pldn))))`,
  mean IC `0.011876`;
  `v2cand-c0b2d60f0275`:
  `CSRank(Mul(CSResidual(Cov(Corr(Div(Mean($amount,2),Mean($volume,5)), $vrat), Sign($amtm)),$mbrd),Sign(CSResidual($arat,$pldn))))`,
  mean IC `0.011096`.
- strict top3 audit:
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_TOP3_STRICT_AUDIT_AFTER_OPEN_2026-04-28.json`;
  review
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_TOP3_STRICT_AUDIT_AFTER_OPEN_2026-04-28.md`.
  All three remain `HOLD_RESEARCH`, not KEEP. Primary-horizon ICs were
  `0.018078`, `0.011437`, and `0.018299`, all with positive-window ratio
  `1.0`. Cost-adjusted primary spread was negative for
  `v2cand-6b5b53c336ac` (`-0.001299`) but positive for
  `v2cand-f54b89b324c8` (`0.000247`) and `v2cand-c0b2d60f0275`
  (`0.000522`). Remaining blockers: sector neutralization not run, capacity
  model not run, and survivorship/universe policy not promotion grade.
- feedback objective:
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_FEEDBACK_OBJECTIVE_2026-04-28.json`
  marks the three pass candidates as saturated positives and records five weak
  positives. Future searches should use this objective to avoid simply
  re-emitting the same three formulas.
- interpretation:
  this is the first clear evidence in the current workstream that changing the
  mathematical generation mechanism, rather than increasing depth, can produce
  new A-share-valid replay candidates under after-open/T+1/tradability rules.
  It is still research-grade only. The next high-value task is not commercial
  promotion; it is sector/industry exposure neutralization or residual exposure
  audit for the residual-state family, followed by another bounded generation
  cycle using the new feedback objective.
- experiment record:
  `reports/PHASE2_EXPERIMENT_RECORD_RESIDUAL_STATE_PRIOR_2026-04-28.md`.

2026-04-28 Residual/state panel exposure audit and feedback continuation:

- code change:
  `real_market_validation` now has
  `audit_expression_panel_exposure_neutrality`. It compares raw tradability
  metrics, daily cross-sectional residualization against available controls
  (`amount`, `volume`, `turnover_rate`, `crowding`, `rps_score`,
  `money_flow`), and group-demeaned metrics if the requested group column has
  enough instruments per group. This is an audit/probe only; it does not
  promote candidates.
- tests:
  added synthetic tests for both a viable multi-code sector grouping and a
  one-code-per-sector panel. `python -m unittest discover -s tests -p
  test_phase2_v21_runtime.py -k panel_exposure_neutrality_probe` ran 2 tests
  OK; `py_compile` OK.
- panel reality confirmed:
  the current enhanced validation panel has effectively one `sector` label per
  board code. In the top3 exposure audit it reported `574` unique groups with
  median codes/group `1.0`, so true sector/industry-neutral claims remain
  blocked on this panel. This matches
  `reports/PHASE2_LOCAL_INDUSTRY_MAPPING_INVENTORY_2026-04-27.md`.
- audit artifacts:
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_TOP3_PANEL_EXPOSURE_AUDIT_2026-04-28.json`;
  review
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_TOP3_PANEL_EXPOSURE_AUDIT_2026-04-28.md`.
- top3 exposure readout:
  `v2cand-6b5b53c336ac` raw IC `0.018078`, exposure-residualized IC
  `0.017197`, delta `-0.000881`; top control exposure only `0.034477`
  (`rps_score`). `v2cand-c0b2d60f0275` raw IC `0.018299`,
  residualized IC `0.017254`, delta `-0.001045`; top control exposure
  `0.089920` (`volume`). These two look reasonably robust to this board-panel
  exposure residualization probe.
- weaker member:
  `v2cand-f54b89b324c8` raw IC `0.011437`, residualized IC `0.004038`,
  delta `-0.007399`; it also had high turnover-rate exposure `0.351781`.
  Treat this candidate as a weaker liquidity/turnover-exposed member of the
  family until a stock-level PIT industry/capacity audit says otherwise.
- feedback continuation:
  a short run using
  `reports/PHASE2_RESIDUAL_STATE_PRIOR_FEEDBACK_OBJECTIVE_2026-04-28.json`
  produced
  `runtime/next_stage_artifacts/phase2-residual-state-feedback-continuation-20260428/phase2-60acfe9acb`.
  Current generated `40`, unique `39`, duplicates `1`, retained `13`,
  retained yield `0.325`, new cells `3`, residual candidates `11`, retained
  residual candidates `3`. It did not regenerate the new top3 pass candidates,
  but old `v2cand-d6f7431bf3cc` reappeared because the residual-only feedback
  objective did not include older saturated positives.
- continuation replay:
  after excluding known saturated candidates
  (`d6f7431bf3cc`, `6b5b53c336ac`, `f54b89b324c8`, `c0b2d60f0275`), the
  bounded current sample replayed `16`, unsupported `0`, smoke pass `0`,
  positive IC `4`, best IC `0.004379`.
  Artifacts:
  `reports/PHASE2_RESIDUAL_STATE_FEEDBACK_CONTINUATION_SAMPLE_LEDGER_2026-04-28.json`,
  `reports/PHASE2_RESIDUAL_STATE_FEEDBACK_CONTINUATION_REAL_REPLAY_AFTER_OPEN_2026-04-28.json`,
  and
  `reports/PHASE2_RESIDUAL_STATE_FEEDBACK_CONTINUATION_REAL_REPLAY_AFTER_OPEN_2026-04-28.md`.
- merged feedback objective:
  created
  `reports/PHASE2_MERGED_SATURATED_FEEDBACK_OBJECTIVE_2026-04-28.json`,
  combining old `d6f7431bf3cc` and the three residual-state pass candidates
  as saturated positives. Use this for the next search to avoid reintroducing
  old winners.
- interpretation:
  the residual-state prior produced real replay hits, and two of the three top
  hits survive the available board-panel exposure residualization probe.
  However, exact continuation around the same family did not immediately find
  a fresh pass once known winners were excluded. The next mathematical upgrade
  should branch from the robust two (`6b5b...`, `c0b...`) into alternative
  state gates or non-liquidity denominators, while the engineering validation
  target remains a true stock-level panel joined to
  `stock_sector_mapping_pit_jq.parquet`.

2026-04-28 Non-liquidity state gate branch:

- code change:
  `phase2_native_ast_expansion` now includes two higher-priority mechanism
  kinds: `non_liquidity_state_gate` and `orthogonal_state_spread_gate`.
  Directed variation also gets compact non-liquidity state edits using
  `price_pos`, `crowding`, `rps_score`, and `money_flow`. These fields remain
  subject to the existing `after_open` field-lag policy in real replay, so
  same-day full-bar leakage is not introduced.
- first smoke:
  `runtime/next_stage_artifacts/phase2-non-liquidity-state-gate-smoke-20260428/phase2-746528d9a5`
  did not actually expose the new state fields in current candidates
  (`nonliquidity_state_count=0`). Diagnosis: the templates existed but were
  displaced by older residual templates under small-budget sorting.
- sorting fix:
  added explicit `MECHANISM_KIND_PRIORITY` and direct non-liquidity state
  edits. Tests:
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k feature_algebra_is_connected`
  OK; `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k phase2_native_ast_expansion`
  ran 2 tests OK; `py_compile` OK.
- second smoke:
  `runtime/next_stage_artifacts/phase2-non-liquidity-state-gate-smoke2-20260428/phase2-5bc17621d0`
  continued from the residual-state feedback run using
  `reports/PHASE2_MERGED_SATURATED_FEEDBACK_OBJECTIVE_2026-04-28.json`.
  Current generated `47`, unique `47`, duplicate `0`, retained `12`, archive
  growth `12`, retained yield `0.255319`, new cells `12`, residual candidates
  `20`, retained residual candidates `11`. The new state fields entered:
  non-liquidity state candidates `8`, retained `8`.
- caveat:
  despite the merged feedback objective, exact saturated candidates
  `v2cand-c0b2d60f0275` and `v2cand-d6f7431bf3cc` still appeared. The current
  saturated-positive feedback is a soft penalty, not a hard block. For future
  efficiency, add a high-budget exact saturated hard skip before evaluation,
  while keeping family neighborhoods open.
- replay sample:
  sample ledger
  `reports/PHASE2_NON_LIQUIDITY_STATE_GATE_SAMPLE_LEDGER_2026-04-28.json`;
  real replay
  `reports/PHASE2_NON_LIQUIDITY_STATE_GATE_REAL_REPLAY_AFTER_OPEN_2026-04-28.json`;
  review
  `reports/PHASE2_NON_LIQUIDITY_STATE_GATE_REAL_REPLAY_AFTER_OPEN_2026-04-28.md`.
  The sample excluded the four known saturated ids and prioritized retained
  non-liquidity-state candidates. Evaluated `16`, unsupported `0`, smoke pass
  `0`, positive IC `4`, best IC `0.004379`.
- readout:
  the best candidate remained an older liquidity/residual weak positive
  (`v2cand-c5b17b081ea2`, IC `0.004379`). The direct non-liquidity state gate
  `v2cand-9ac7412e2622`
  (`Corr(CSResidual(CSRank($open),CSRank($price_pos)),Sign(CSResidual($rps_score,$crowding)))`)
  was positive but weak at IC `0.001124`; the compact pure state-spread
  `v2cand-519547def34b`
  (`CSRank(Mul(CSResidual($price_pos,$crowding),Sign(CSResidual($rps_score,$money_flow))))`)
  was near zero at IC `0.000089`.
- interpretation:
  non-liquidity state gates are now actually reachable by the searcher, but
  this branch did not discover a fresh real replay pass in the first bounded
  sample. The evidence still favors the residual-state family with liquidity
  denominator plus transition residual gate (`6b5b...` and `c0b...`) over pure
  non-liquidity state spread gates. Next engineering fix: hard skip exact
  saturated candidates during high-budget continuation. Next math direction:
  keep `CSResidual(...,$mbrd) * Sign(CSResidual($arat,$pldn))` as the useful
  scaffold, but vary the left residual numerator more intelligently rather
  than replacing the scaffold wholesale.

2026-04-28 Exact saturated hard skip:

- code change:
  high-budget continuation now hard-skips exact saturated positive candidates
  before final evaluation, with a target-aware pre-screen record when the
  candidate is encountered inside the non-score candidate pool. This is exact
  id/expression blocking only; it does not block the family, skeleton, fields,
  or nearby expressions, preserving the open search space.
- tests:
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k saturated`
  OK, `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k target_aware_pre_screen`
  OK, `py_compile` OK.
- smoke:
  `runtime/next_stage_artifacts/phase2-saturated-hard-skip-smoke-20260428/phase2-248d574ee8`
  continued from `phase2-5bc17621d0` with the merged saturated objective.
  Efficiency audit: generated `36`, retained `14`, archive growth `5`,
  retained yield `0.388889`, new cells `7`.
- hard-skip verification:
  the smoke recorded `1` exact saturated evaluation skip
  (`v2cand-d6f7431bf3cc`). Comparing the new ledger to the previous run's
  ledger shows the current-run new records contain `0` saturated ids. The old
  saturated ids still appear in the combined ledger only because the run is a
  continuation seeded from the prior archive.
- next:
  with exact repeats removed, the next useful search should scale the
  residual-state scaffold branch, not the weak pure non-liquidity state-spread
  branch. Use bounded 3-month real replay samples and keep after-open/T+1 and
  limit-up/limit-down tradability filters active.

2026-04-28 Residual-state hard-skip scale run:

- run:
  `runtime/next_stage_artifacts/phase2-residual-state-hardskip-scale-20260428/phase2-82f35a9dd3`
  continued from the hard-skip smoke with the merged saturated objective.
- synthetic search efficiency:
  generated `275`, retained `36`, archive growth `23`, retained yield
  `0.130909`, new cells `28`, non-score generated `244`, non-score retained
  `35`. Current-run ledger delta contained `0` exact saturated ids. Final
  saturated evaluation skips `5`.
- structure:
  current-run residual candidates `94`, non-liquidity state candidates `74`,
  and the sampled current-run records were all multi-field. However, many
  high synthetic IC candidates became very deep nested rank/rolling stacks;
  that is a search-efficiency warning, not evidence of real edge.
- bounded replay:
  sample ledger
  `reports/PHASE2_RESIDUAL_STATE_HARDSKIP_SCALE_REAL_REPLAY_LEDGER_2026-04-28.json`;
  replay
  `reports/PHASE2_RESIDUAL_STATE_HARDSKIP_SCALE_REAL_REPLAY_2026-04-28.json`;
  review
  `reports/PHASE2_RESIDUAL_STATE_HARDSKIP_SCALE_REAL_REPLAY_REVIEW_2026-04-28.md`.
  Evaluated `24`, unsupported `0`, smoke pass `0`, positive IC `7`.
- strict top3:
  `reports/PHASE2_RESIDUAL_STATE_HARDSKIP_SCALE_TOP3_STRICT_AUDIT_2026-04-28.json`.
  Best follow-up was `v2cand-47518afbe4d2`: horizon-2 strict IC `0.010958`,
  cost-adjusted spread `0.000508`, one-way turnover `0.102644`, decision
  `HOLD_RESEARCH`. The next two were weaker and cost-adjusted spread negative.
- interpretation:
  exact-repeat efficiency is fixed, and the scaled run did surface one weak
  follow-up worth watching, but no commercial-grade candidate emerged. Next
  mathematical search should add a soft depth-growth penalty and emphasize
  simpler residual/state compositions, especially variants of the earlier
  robust `CSResidual(...,$mbrd) * Sign(CSResidual($arat,$pldn))` scaffold,
  instead of allowing score-like nested operator towers to dominate.

2026-04-28 Operator-tower soft penalty:

- code change:
  `_three_dimensional_search_profile` now records `operator_tower_penalty`,
  `dominant_wrapper_operator`, and `dominant_wrapper_count`. The penalty is
  soft and only reduces target-aware pre-screen rank for repeated wrapper
  towers (`CSRank`, `Rank`, `ZScore`, `Sign`, `Abs`, `Log`) plus very high
  operator count/depth. It does not ban deep formulas.
- tests:
  `py_compile` OK and
  `python -m unittest discover -s tests -p test_phase2_v21_runtime.py -k target_aware_pre_screen`
  ran `10` tests OK.
- smoke:
  `runtime/next_stage_artifacts/phase2-depth-penalty-smoke-20260428/phase2-b205a2f89b`.
  Generated `38`, retained `11`, archive growth `2`, retained yield
  `0.289474`, new cells `3`, final exact saturated skips `1`.
- readout:
  target-aware pre-screen events now expose tower diagnostics. In the smoke,
  extreme nested candidates reached the max soft penalty and were mostly
  skipped by pre-screen efficiency gates; some moderately complex selected
  candidates still pass, so the infinite/deep search space remains reachable.
  Next larger run should use this penalty before another replay sample.

2026-04-28 Depth-penalty medium replay:

- run:
  `runtime/next_stage_artifacts/phase2-depth-penalty-medium-20260428/phase2-cfb8b3c39f`
  continued from the depth-penalty smoke.
- search efficiency:
  generated `136`, retained `8`, archive growth `6`, retained yield
  `0.058824`, new cells `6`. True new unique ids vs previous depth-penalty
  smoke: `82`; true new retained ids: `2`; exact saturated hits among new ids:
  `0`.
- structure:
  true new residual candidates `22`, non-liquidity-state candidates `12`.
  Average new depth `21.085`, max depth `42`, average new operator count
  `36.744`. This confirms the first tower penalty is not enough; deep
  score-like continuations still consume too much search mass.
- replay artifacts:
  sample ledger
  `reports/PHASE2_DEPTH_PENALTY_MEDIUM_REAL_REPLAY_LEDGER_2026-04-28.json`;
  replay
  `reports/PHASE2_DEPTH_PENALTY_MEDIUM_REAL_REPLAY_2026-04-28.json`;
  review
  `reports/PHASE2_DEPTH_PENALTY_MEDIUM_REAL_REPLAY_REVIEW_2026-04-28.md`;
  strict audit
  `reports/PHASE2_DEPTH_PENALTY_MEDIUM_TOP2_STRICT_AUDIT_2026-04-28.json`.
- real replay:
  selected `24`, evaluated `24`, unsupported `0`, smoke pass `0`, positive IC
  `2`. Best replay candidates were `v2cand-c5b17b081ea2` with recent mean IC
  `0.004379` and `v2cand-7b96babe5058` with `0.003217`.
- strict audit:
  both are `HOLD_RESEARCH`. `c5b...` strict horizon-2 IC `0.002767`,
  cost-adjusted spread `0.001099`, turnover `0.153481`; `7b96...` strict
  horizon-2 IC `0.002714`, cost-adjusted spread `0.000782`, turnover
  `0.113527`.
- interpretation:
  the medium run did not produce a fresh pass. Exact-repeat blocking works,
  but the search still needs stronger mathematical allocation away from
  wrapper towers and toward compact residual/state activation surfaces.

2026-04-28 Score-tower guard rejected:

- attempted change:
  briefly tested a stricter score-lane entry guard for extreme wrapper towers
  in already-occupied adaptive cells.
- smoke:
  `runtime/next_stage_artifacts/phase2-score-tower-guard-smoke-20260428/phase2-bf47002df5`.
  Generated `31`, retained `8`, retained yield `0.258065`, but true new unique
  ids vs the previous medium run were only `1`, new cells `0`, and funnel
  calibration was `FAIL`.
- decision:
  rejected and reverted the stricter score-lane guard. It was too hard and
  risked reducing open-space exploration. Keep the softer
  `operator_tower_penalty` diagnostics/ranking pressure only.
- implication:
  the next improvement should be generative/math-side, not a score-lane hard
  entry filter. Better options: compact residual/state template expansion,
  activation-surface sampling, and parent selection that prefers low-depth
  productive parents without banning deep descendants.

2026-04-28 Competitor generator method review:

- scope:
  read-only review; no Phase2 searcher code changed.
- report:
  `reports/PHASE2_COMPETITOR_GENERATOR_METHOD_REVIEW_2026-04-28.md`.
- imbue AlphaGPT read:
  local `G:\Project_V7_Rotation\external_refs\AlphaGPT-main` is not an
  unbounded formula-tree searcher. It uses a compact token/operator language,
  `MAX_FORMULA_LEN = 12`, StackVM arity execution, invalid/constant penalties,
  and an execution-aware reward with liquidity, slippage/fees, turnover,
  drawdown penalty, and activity floor.
- CFG read:
  local AlphaCFG-style baseline uses `expr_len_limit = 10`, MCTS, replay
  buffer, and a final pool of 10 formulas. Its native local objective is strong
  but A-share after-open/T+1/tradability replay is weak. The transferable
  lesson is grammar/size-controlled tree search plus semantic redundancy, not
  direct formula reuse.
- AlphaForge read:
  main lesson is factor zoo plus dynamic combination; standalone formula IC is
  not the right terminal objective.
- decision:
  `HOLD_MAIN_SEARCHER`. Do not continue patching the current searcher with
  ad-hoc hard guards. Next work should be a sidecar generator gap matrix and
  candidate scheduler spec over existing ledgers, then evaluate whether that
  improves replay hit-rate before touching the main searcher again.

2026-04-28 CFG+ optimization design:

- report:
  `reports/PHASE2_CFG_PLUS_OPTIMIZATION_DESIGN_2026-04-28.md`.
- scope:
  design only; no main searcher code changed.
- goal:
  improve beyond plain CFG rather than merely copying it. The proposed CFG+
  sidecar combines typed financial grammar, semantic quotient classes,
  cost-aware UCT, early real-replay posterior value, pool marginal
  contribution, conditional activation value, and A-share tradability context.
- key distinction:
  plain CFG solves syntax/tree legality and search efficiency; CFG+ adds
  market-clock semantics, execution-aware reward, pool usefulness, and
  specialist activation. This directly targets the latest failure mode where
  synthetic archive reward was fooled by wrapper towers.
- decision:
  `BUILD_CFG_PLUS_SIDECAR`, not `PATCH_MAIN_SEARCHER`. Next concrete work
  should be Stage 0 method matrix plus Stage 1 read-only scheduler over
  existing ledgers before any new generator code.

2026-04-28 CFG+ Stage 0/1 specification:

- method matrix:
  `reports/PHASE2_CFG_PLUS_METHOD_MATRIX_2026-04-28.md`.
  It compares Phase2 current search, local CFG baseline, imbue AlphaGPT,
  AlphaForge, and CFG+ across formula space, size control, validity,
  redundancy, reward, market rules, pool awareness, conditional edge, and
  failure modes.
- sidecar scheduler spec:
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULER_SPEC_2026-04-28.md`.
  It defines a read-only scheduler over existing ledgers with semantic
  quotient keys, mechanism buckets, cost score, wrapper-tower score, A-share
  clock risk, known replay status, scheduler score, budget allocation, and
  acceptance tests.
- checked ledger compatibility:
  representative ledgers already expose enough fields for Stage 1 scheduling:
  CFG pool, depth-penalty medium replay sample, residual-state hardskip sample,
  V8 rank-quotient proposals, and V18 light-smoothing surface.
- boundary:
  Stage 1 is not a generator and not a main searcher patch. It may only read
  existing ledgers and write a scheduled replay ledger/report. It must not edit
  `prototype_run.py`, `variation.py`, or retention logic.
- next:
  if approved, implement the read-only scheduler artifact and compare it
  against naive retained-first and synthetic-IC-top schedules under the same
  bounded replay budget.

2026-04-28 CFG+ sidecar schedule and replay:

- artifacts:
  schedule ledger
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_2026-04-28.json`;
  schedule review
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_REVIEW_2026-04-28.md`;
  real replay
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_REAL_REPLAY_2026-04-28.json`;
  replay review
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_REAL_REPLAY_REVIEW_2026-04-28.md`.
- implementation boundary:
  main searcher code was not modified. The sidecar only read existing ledgers
  and produced a bounded replay schedule.
- schedule quality:
  input pool `432`, scheduled `24`, represented `5` mechanism buckets, max
  semantic-family duplicate count `2`, wrapper-tower-risk count `0`,
  saturated ids excluded `11`. Average expression cost was `17.857917` versus
  source-order naive retained-first `25.892083`.
- replay contract:
  after-open signal clock, field-level lag policy, feature lag `0`, execution
  lag `1`, recent `4` quarterly windows with `60` warmup days, entry
  limit-up/down and suspension aware through the A-share adapter.
- replay result:
  evaluated `24`, unsupported `0`, smoke pass `12`, positive recent IC `22`,
  average recent IC `0.016262`.
- source split:
  compact V18 light-smoothing candidates: `7/7` pass, average recent IC
  `0.035802`; compact V8 rank-quotient candidates: `5/6` pass, average recent
  IC `0.016646`; CFG external reference: `0/2` pass; residual-state recent
  branch: `0/8` pass; recent failed depth-penalty sample: `0/1` pass.
- interpretation:
  the CFG+ scheduler improved replay triage versus the latest blind
  residual/depth continuations, but the pass set mostly came from compact
  V18/V8 lineage rather than newly complex residual/state trees. This supports
  CFG+-style allocation around compact typed kernels first, with residual and
  limit-state interaction as conditional specialists. It is not a commercial
  edge claim yet.
- next:
  compare the sidecar schedule against naive retained-first and synthetic-IC-top
  schedules under the identical budget, then run strict cost/exposure review on
  the `12` smoke-pass rows before any new large search.

2026-04-28 CFG+ sidecar same-budget comparison:

- artifacts:
  comparison summary
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_COMPARISON_2026-04-28.json`;
  comparison review
  `reports/PHASE2_CFG_PLUS_SIDECAR_SCHEDULE_COMPARISON_2026-04-28.md`;
  control ledgers/replays:
  `reports/PHASE2_CFG_PLUS_COMPARISON_NAIVE_RETAINED_FIRST_LEDGER_2026-04-28.json`,
  `reports/PHASE2_CFG_PLUS_COMPARISON_NAIVE_RETAINED_FIRST_REAL_REPLAY_2026-04-28.json`,
  `reports/PHASE2_CFG_PLUS_COMPARISON_SYNTHETIC_SCORE_TOP_LEDGER_2026-04-28.json`,
  `reports/PHASE2_CFG_PLUS_COMPARISON_SYNTHETIC_SCORE_TOP_REAL_REPLAY_2026-04-28.json`.
- common replay budget:
  `24` candidates, after-open signal clock, field-level lag policy, feature lag
  `0`, execution lag `1`, recent `4` quarterly windows, warmup `60`, A-share
  entry tradability aware.
- result:
  naive retained-first: `1/24` smoke pass, `3/24` positive recent IC, average
  recent IC `0.000055`.
  Synthetic-score-top: `3/24` smoke pass, `9/24` positive recent IC, average
  recent IC `-0.010642`.
  CFG+ sidecar: `12/24` smoke pass, `22/24` positive recent IC, average recent
  IC `0.016262`.
- interpretation:
  CFG+ scheduling is materially better at spending the replay budget than both
  source-order selection and synthetic-proxy selection. The remaining issue is
  not schedule triage but generator direction: the productive candidates are
  still compact V18/V8 price-return kernels, while residual/limit-state complex
  trees mostly remain weak positives or failures.
- next:
  run strict cost/exposure/capacity-style review on the `12` sidecar pass rows.
  Then design the actual CFG+ generator around compact typed kernels plus
  conditional residual/limit-state specialists, instead of another blind
  depth-scale continuation.

2026-04-28 CFG+ sidecar top12 strict audit:

- artifacts:
  strict audit
  `reports/PHASE2_CFG_PLUS_SIDECAR_TOP12_STRICT_AUDIT_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_SIDECAR_TOP12_STRICT_AUDIT_REVIEW_2026-04-28.md`.
- scope:
  top `12` smoke-pass rows from the CFG+ sidecar schedule replay; horizons
  `(1, 2, 5)`, after-open signal clock, feature lag `0`, recent `4`
  quarterly windows, warmup `60`, cost shadow `10` bps.
- result:
  all `12` remain `HOLD_RESEARCH`; `0/12` are promotion-grade KEEP. However,
  `9/12` retain positive H1 cost-adjusted window spread under the current
  cost shadow.
- best H1 strict rows:
  `v8-natural-0043` H1 IC `0.013225`, cost-adjusted spread `0.000917`,
  one-way turnover `0.186523`;
  `v8-natural-0039` H1 IC `0.011234`, cost-adjusted spread `0.000765`,
  turnover `0.216297`;
  `v8-natural-0021` H1 IC `0.025425`, cost-adjusted spread `0.000617`,
  turnover `0.280427`;
  `v18-tplus1-0031` H1 IC `0.044421`, cost-adjusted spread `0.000568`,
  turnover `0.387193`;
  `v18-tplus1-0001` H1 IC `0.042306`, cost-adjusted spread `0.000566`,
  turnover `0.377609`.
- blockers:
  common blockers are `sector_neutralization_not_run`,
  `capacity_model_not_run`, and
  `survivorship_and_universe_policy_not_promotion_grade`; three candidates
  also have `non_positive_cost_adjusted_primary_spread`.
- interpretation:
  strict audit confirms this is a real research lead, not yet a deployable
  edge. The signal mass worth further mathematical search is compact V18/V8
  kernel structure with cost-aware smoothing/quotient behavior. Residual and
  limit-state formulas should be reintroduced as controlled conditional
  specialists after neutralization/capacity checks, not as the next blind
  search center.

2026-04-28 CFG+ compact-kernel novel generation:

- artifacts:
  generated pool
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_GENERATED_LEDGER_2026-04-28.json`;
  novel replay schedule
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_NOVEL_SCHEDULE_LEDGER_2026-04-28.json`;
  replay
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_NOVEL_REAL_REPLAY_2026-04-28.json`;
  strict audit
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_NOVEL_TOP12_STRICT_AUDIT_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_NOVEL_REPLAY_REVIEW_2026-04-28.md`.
- implementation boundary:
  report-only sidecar generation; no main searcher code changed.
- generation:
  created `967` compact typed candidates around strict-audit survivor windows.
  Excluded exact expressions already present in prior V8/V18/sidecar ledgers,
  leaving `900` novel expressions. Scheduled `64` novel candidates with average
  expression cost `11.1412`.
- parameterization:
  parameters were derived from strict-audit survivor neighborhoods: numerator
  windows around `6-8`, denominator windows around `2-5`, and nearby natural
  extrapolations. This is not a fixed 1/5/20 grid.
- replay result:
  evaluated `64`, unsupported `0`, smoke pass `38`, positive recent IC `45`,
  average recent IC `0.012957`.
- family readout:
  `smoothed_momentum_vol_norm` passed `10/10`, average recent IC `0.046273`;
  `vol_normalized_momentum` passed `14/14`, average recent IC `0.034350`;
  `volatility_term_structure` passed `5/8`, average recent IC `0.010682`;
  `typed_cross` families failed (`momentum_vol_cross` `0/8`,
  `gap_momentum_cross` `0/6`) and should not receive more budget unchanged.
- top new pocket:
  `CSRank(Div(Mean(Mom($close,7),2),WMA(Abs($ret),2)))` recent IC `0.052298`;
  `CSRank(Div(Mean(Mom($close,7),2),Mean(Abs($ret),2)))` recent IC `0.051702`;
  related denominator windows `2-4` all passed.
- strict audit:
  top `12` novel smoke-pass rows all remain `HOLD_RESEARCH`, but `12/12`
  retain positive H1 cost-adjusted spread under `10` bps cost shadow. Best H1
  strict rows include:
  `cfgplus-compact-novel-0015` H1 IC `0.050577`, cost spread `0.000914`,
  turnover `0.311915`;
  `cfgplus-compact-novel-0022` H1 IC `0.051702`, cost spread `0.000908`,
  turnover `0.342411`;
  `cfgplus-compact-novel-0018` H1 IC `0.052298`, cost spread `0.000896`,
  turnover `0.366143`;
  `cfgplus-compact-novel-0013` H1 IC `0.041029`, cost spread `0.001083`,
  turnover `0.414970`.
- interpretation:
  this is the first strong evidence that CFG+ generation, not just scheduling,
  can improve the search. The mathematical improvement is numerator smoothing
  and compact vol-normalized momentum around the discovered survivor surface.
  It is still not commercial-grade because sector/exposure neutralization,
  capacity, and promotion-grade universe policy remain unresolved.
- next:
  allocate the next bounded search to `cost_cooling_numerator_mean` and compact
  vol-normalized momentum around `n=6-8`, `d=2-5`; run exposure-neutrality and
  capacity-style checks before increasing depth or reintroducing residual/limit
  specialists.

2026-04-28 CFG+ compact-kernel exposure neutrality probe:

- artifacts:
  exposure probe
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_TOP8_EXPOSURE_NEUTRALITY_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_COMPACT_KERNEL_TOP8_EXPOSURE_NEUTRALITY_REVIEW_2026-04-28.md`.
- scope:
  top `8` strict-audit novel compact-kernel candidates, all from the
  `smoothed_momentum_vol_norm` pocket.
- controls:
  available panel controls `amount`, `volume`, `turnover_rate`, `crowding`,
  `rps_score`, and `money_flow`; after-open/T+1/recent-4Q/warmup-60 contract.
- result:
  `0/8` materially weakened after available exposure residualization. Raw IC to
  residualized IC examples:
  `cfgplus-compact-novel-0018` `0.052298 -> 0.049023`;
  `cfgplus-compact-novel-0022` `0.051702 -> 0.049290`;
  `cfgplus-compact-novel-0015` `0.050577 -> 0.048479`;
  `cfgplus-compact-novel-0017` improved `0.045306 -> 0.047421`.
- caveat:
  true group/industry neutralization is not available on the current panel, so
  blockers remain `true_group_neutralization_not_available_on_current_panel`,
  `stock_level_pit_industry_join_not_run`, `capacity_model_not_run`, and
  `survivorship_and_universe_policy_not_promotion_grade`.
- interpretation:
  the new compact pocket does not appear to be merely a simple liquidity/style
  exposure artifact under available controls. It is now a stronger research
  lead, but still not KEEP/commercial-grade until stock-level PIT industry join
  and capacity tests are done.

2026-04-28 CFG+ pocket2 focused search:

- artifacts:
  generated pool
  `reports/PHASE2_CFG_PLUS_POCKET2_FOCUSED_GENERATED_LEDGER_2026-04-28.json`;
  replay schedule
  `reports/PHASE2_CFG_PLUS_POCKET2_FOCUSED_SCHEDULE_LEDGER_2026-04-28.json`;
  real replay
  `reports/PHASE2_CFG_PLUS_POCKET2_FOCUSED_REAL_REPLAY_2026-04-28.json`;
  strict audit
  `reports/PHASE2_CFG_PLUS_POCKET2_TOP12_STRICT_AUDIT_2026-04-28.json`;
  exposure probe
  `reports/PHASE2_CFG_PLUS_POCKET2_TOP8_EXPOSURE_NEUTRALITY_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_POCKET2_FOCUSED_REPLAY_REVIEW_2026-04-28.md`.
- implementation boundary:
  report-only sidecar generation; no main searcher code changed.
- generation:
  focused around
  `Mean(Mom(close,7),2) / Mean|WMA(Abs(ret),2-4)`.
  Generated `4056` candidates after excluding prior exact expressions, then
  scheduled `96` with average expression cost `16.4587`.
- replay:
  after-open/T+1/recent-4Q/warmup-60/tradability-aware replay evaluated `96`,
  unsupported `0`, smoke pass `84`, positive recent IC `88`, average recent IC
  `0.036187`.
- family readout:
  `smoothed_momentum_vol_norm_pocket2`: `64/64` pass, average IC `0.041403`;
  `open_momentum_vol_norm_probe`: `8/8` pass, average IC `0.039064`;
  `additive_gap_state_probe`: `6/6` pass, average IC `0.038509`;
  `additive_vol_state_probe`: `6/6` pass, average IC `0.047914`;
  `relative_smoothed_momentum_vol_norm`: `0/12` pass, average IC `-0.000576`.
- best replay rows:
  `cfgplus-pocket2-sched-0087`
  `CSRank(Add(Div(Mean(Mom($close,7),2),WMA(Abs($ret),4)),ZScore(Div(Std($ret,4),Mean(Abs($ret),4)))))`
  recent IC `0.052934`;
  `cfgplus-pocket2-sched-0085`
  `CSRank(Add(Div(Mean(Mom($close,7),2),WMA(Abs($ret),3)),ZScore(Div(Std($ret,3),Mean(Abs($ret),3)))))`
  recent IC `0.052811`;
  `cfgplus-pocket2-sched-0012`
  `CSRank(Div(Mom(Mean($close,2),7),WMA(Abs($ret),3)))`
  recent IC `0.050590`.
- strict audit:
  top `12` all remain `HOLD_RESEARCH`, but `12/12` retain positive H1
  cost-adjusted spread. H1 cost-adjusted spread range among top12:
  `0.000673` to `0.001110`; H1 turnover roughly `0.294302` to `0.397787`.
- exposure probe:
  top `8` residualized against available panel controls. `1/8` had material IC
  weakening (`cfgplus-pocket2-sched-0087`, `0.052934 -> 0.047300`,
  delta `-0.005634`); the others remained strong, generally around
  residualized IC `0.046-0.049`. True group/industry neutralization is still
  not available on the current panel.
- interpretation:
  formula-generation efficiency is now clearly improved; the remaining
  bottleneck is promotion-grade validation. Next work should prioritize PIT
  industry join, neutralized replay, capacity/slippage stress, and forward
  shadow. For generation allocation, keep mass on focused denominator sweep and
  additive vol-state probes; drop the relative short-long family for now.

2026-04-28 CFG+ pocket2 stock PIT and small-capacity probe:

- artifacts:
  stock PIT top8 ledger
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_TOP8_LEDGER_2026-04-28.json`;
  strict/neutral stock audit
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_TOP8_STRICT_NEUTRAL_2026-04-28.json`;
  small-capacity probe
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_TOP8_SMALL_CAPACITY_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_CAPACITY_REVIEW_2026-04-28.md`.
- data:
  used `G:/Project_V7_Rotation/scripts/data/phase2_stock_validation_slice_2026-04-27.csv.gz`.
  This slice is stock-level and already joined to local PIT JQ/SW-L1-style
  mapping from `stock_sector_mapping_pit_jq.parquet`.
- scope:
  top `8` pocket2 board-level winners; latest stock-level quarter plus warmup.
  This is a bounded recent-quarter reality probe, not a full promotion audit.
- result:
  board-level IC around `0.048-0.053` shrank to stock-level H1 IC around
  `0.031-0.034`, but did not disappear. All top8 kept positive H1
  cost-adjusted spread. Group-neutral IC remained around `0.030-0.033`.
- examples:
  `cfgplus-pocket2-sched-0087`: board IC `0.052934`, stock IC `0.034397`,
  residualized IC `0.041337`, group-neutral IC `0.031511`, cost spread
  `0.002192`, turnover `0.328181`.
  `cfgplus-pocket2-sched-0085`: board IC `0.052811`, stock IC `0.034396`,
  residualized IC `0.041035`, group-neutral IC `0.032535`, cost spread
  `0.002269`, turnover `0.353777`.
- small-capacity read:
  top long bucket has roughly `1080` names per day; median p10 per-stock
  entry-day amount is about `50m` CNY and p01 is about `25m` CNY across the
  audited rows. For diversified `1-10m` CNY style deployment, raw liquidity
  capacity is unlikely to be the first bottleneck. Turnover/cost discipline is
  the main implementation issue.
- caveat:
  existing neutral-audit helper still emits the generic blocker
  `stock_level_pit_industry_join_not_run`, but for this specific stock slice
  PIT `sector` is present and group-neutral metrics were computed. Remaining
  true blockers are short sample length, approximate ST-limit handling,
  survivorship/universe policy, and lack of forward shadow.

2026-04-28 CFG+ pocket2 stock PIT rebalance throttle:

- artifacts:
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_TOP8_REBALANCE_THROTTLE_2026-04-28.json`;
  `reports/PHASE2_CFG_PLUS_POCKET2_STOCK_PIT_REBALANCE_THROTTLE_REVIEW_2026-04-28.md`.
- scope:
  execution overlay only, no searcher/core-generation changes. Same stock PIT
  slice, after-open signal, T+1 execution, H1 forward return, top/bottom 20%,
  10bps one-way cost. Tested 1/2/3/5-day rebalance; first basket entry counts
  as 100% one-way turnover.
- result:
  2-day rebalance dominated daily rebalance for all top8 candidates on net
  long-short mean after cost. Best row:
  `cfgplus-pocket2-sched-0085` at 2-day rebalance, net long-short mean
  `0.002704`, LS Sortino `1.826447`, average one-way turnover `0.292588`,
  net long mean `0.004019`, long Sortino `1.713587`, LS max drawdown
  `-0.020032`.
- read:
  the pocket is not purely a high-turnover artifact; modest throttling improved
  the cost-adjusted path. 5-day rebalance weakened materially, so the current
  small-capacity default should be 2-day rebalance, with 3-day kept as a
  lower-churn sensitivity check.

2026-04-28 CFG+ pocket2 commercial/private-fund proof gate:

- artifacts:
  `reports/PHASE2_CFG_PLUS_POCKET2_COMMERCIAL_PROOF_GATE_2026-04-28.json`;
  `reports/PHASE2_CFG_PLUS_POCKET2_COMMERCIAL_PROOF_GATE_2026-04-28.md`.
- standard:
  private-fund-grade proof requires PIT feature/industry/tradability evidence,
  realistic A-share execution constraints, cost stress, turnover/capacity,
  at least `250` daily OOS observations (`750+` preferred), multiple independent
  3-month windows, frozen formula/search policy, and forward shadow or
  broker-like fill simulation.
- result:
  decision is `HOLD_RESEARCH`, not commercial proof. Available stock PIT slice
  only covers `123` unique trading dates from `2025-08-06` to `2026-02-04`.
  Leader remains `cfgplus-pocket2-sched-0085`, but across usable windows it has
  only `1/3` positive 10bps net long-short windows and `1/3` positive
  group-neutral IC windows. Average 10bps net LS is `0.000441`; average IC is
  `0.005098`; average group-neutral IC is `0.005941`.
- leader window detail:
  `2025Q3`: IC `-0.004164`, GN IC `-0.006980`, 10bps net LS `-0.000394`.
  `2025Q4`: IC `-0.014937`, GN IC `-0.010306`, 10bps net LS `-0.000987`.
  `2026Q1_partial`: IC `0.034396`, GN IC `0.035109`, 10bps net LS `0.002704`.
- interpretation:
  recent pocket strength is real under the recent-quarter execution overlay, but
  it is not yet a commercial/private-fund-grade proof. Next work should either
  build a longer stock-level PIT panel and rerun this gate, or freeze the
  candidate and start a forward shadow. Do not describe this as deployable or
  sellable signal evidence yet.

2026-04-28 CFG+ pocket2 regime-conditioned proof probe:

- artifacts:
  `reports/PHASE2_CFG_PLUS_POCKET2_REGIME_CONDITIONED_PROOF_2026-04-28.json`;
  `reports/PHASE2_CFG_PLUS_POCKET2_REGIME_CONDITIONED_PROOF_2026-04-28.md`.
- scope:
  tested only the two current leaders, `cfgplus-pocket2-sched-0085` and
  `cfgplus-pocket2-sched-0087`, under 2-day rebalance and 10bps one-way cost.
  Regime variables are timestamp-safe: prior-close market aggregates are shifted
  one trading day; current open-gap aggregates are used only under after-open
  signal timing.
- baseline:
  over `112` usable path days, the unconditional 2-day net long-short path is
  essentially flat/negative: `0085` net LS `-0.000004`, GN IC `-0.000870`;
  `0087` net LS `-0.000039`, GN IC `-0.003180`.
- conditional hypotheses:
  common positive pair conditions exist but remain small-sample/post-hoc. The
  cleanest broad condition is
  `open_gap_mean_state=open_gap_up & open_gap_breadth_state=open_breadth_strong`:
  `35` days, average net LS `0.001088`, average GN IC `0.024699` across 0085/0087.
  A prior-close-only alternative is
  `prior_market_ret_state=prior_ret_mid & prior_breadth_state=prior_breadth_mid`:
  `29` days, average net LS `0.001272`, average GN IC `0.020790`.
  A more selective calm-state hypothesis is
  `prior_breadth_state=prior_breadth_mid & prior_vol_state=prior_vol_calm`:
  `21` days, average net LS `0.002695`, average GN IC `0.037916`.
- decision:
  `REGIME_HYPOTHESIS_ONLY`; this does not upgrade pocket2 to commercial proof.
  The valid next step is to pre-register one or two simple regime gates and test
  them on longer PIT stock data or forward shadow. Do not keep mining more
  conditions on the same `123`-day slice as if it were OOS.

2026-04-28 CFG+ pocket2 frozen regime pre-registration:

- artifacts:
  frozen spec
  `reports/PHASE2_CFG_PLUS_POCKET2_FROZEN_REGIME_SPEC_2026-04-28.json`;
  development-slice replay
  `reports/PHASE2_CFG_PLUS_POCKET2_FROZEN_REGIME_REPLAY_2026-04-28.json`;
  review
  `reports/PHASE2_CFG_PLUS_POCKET2_FROZEN_REGIME_REPLAY_2026-04-28.md`.
- status:
  `PRE_REGISTERED_FOR_NEXT_OOS_ONLY`. The gates and thresholds were selected on
  the `2025-08-06..2026-02-04` development slice and must not be refit on any
  future test/forward period.
- frozen gates:
  `gate_open_strength_after_open`:
  `open_gap_mean >= 0.00101475` and
  `open_gap_breadth >= 0.45960181`.
  `gate_prior_mid_close_only`:
  `-0.00251528 <= prior_market_ret <= 0.00725045` and
  `0.37111913 <= prior_breadth <= 0.59905746`.
  `gate_union_open_strength_or_prior_mid` is coverage sensitivity only, not a
  primary gate unless future validation separately passes.
- development replay:
  this replay recomputes the strategy on gated dates only, rather than filtering
  an already-running ungated path. On the same development slice:
  `0085` open-strength gate: `35` return days, net LS `0.001479`, GN IC
  `0.025742`, Sortino `2.013670`; prior-mid gate: `29` return days, net LS
  `0.001613`, GN IC `0.021984`, Sortino `2.112495`.
  `0087` open-strength gate: `35` return days, net LS `0.001623`, GN IC
  `0.023657`, Sortino `2.371796`; prior-mid gate: `29` return days, net LS
  `0.001470`, GN IC `0.019597`, Sortino `2.007435`.
- promotion rule:
  next PIT/OOS/forward validation must use these thresholds exactly. Promotion
  requires at least `250` daily observations, positive 20bps-stressed net
  long-short, positive group-neutral IC, same-sign challenger confirmation, and
  acceptable turnover/drawdown/capacity. This remains non-commercial research
  until those gates pass.

2026-04-28 CFG+ pocket2 frozen regime pre-development holdout:

- artifacts:
  `reports/PHASE2_CFG_PLUS_POCKET2_FROZEN_REGIME_PREDEV_HOLDOUT_2026-04-28.json`;
  `reports/PHASE2_CFG_PLUS_POCKET2_FROZEN_REGIME_PREDEV_HOLDOUT_2026-04-28.md`.
- data:
  rebuilt a longer stock-level panel directly from local TDX day files
  `G:/hsjday/sh/lday` and `G:/hsjday/sz/lday`, joined to PIT JQ/SW-L1 mapping.
  Evaluation window is `2025-03-03..2025-08-05`; warmup/label load window is
  `2024-12-01..2025-08-08`. Scanned `5980` stock files, loaded `920,739` raw
  rows, produced `922,760` panel rows with suspension placeholders, `5533`
  stocks, `168` dates. Evaluation Unknown-sector ratio is `0.097770`.
- status:
  `FAILS_PREDEV_HOLDOUT_FOR_COMMERCIAL_PROOF`. This is not forward OOS because
  formulas/gates were discovered later, but it is disjoint from the
  `2025-08-06..2026-02-04` development slice and uses the frozen thresholds
  without refit.
- key result:
  ungated holdout is only marginal at 10bps and fails cost stress:
  `0085` ungated net LS `0.000216` at 10bps, `-0.000044` at 20bps, GN IC
  `-0.000531`; `0087` ungated net LS `0.000258` at 10bps, `0.000013` at
  20bps, GN IC `-0.001835`.
  Frozen gates do worse: `0085` open-strength net LS `-0.000819`, GN IC
  `-0.005924`; prior-mid net LS `-0.000178`, GN IC `-0.001399`.
  `0087` open-strength net LS `-0.000982`, GN IC `-0.010864`; prior-mid net
  LS `-0.000140`, GN IC `-0.003896`.
- interpretation:
  the 2026Q1 pocket strength is likely time/regime-local, not a currently
  commercializable edge. Do not spend more effort trying to prove this pocket
  on the same family. Either start a frozen-spec forward shadow as a monitoring
  exercise, or return to discovery with a different edge hypothesis and use this
  as a failure case for the promotion gate.

2026-04-28 gate-first event diagnostic smoke:

- artifacts:
  candidate ledger
  `reports/PHASE2_GATE_FIRST_EVENT_DIAGNOSTIC_LEDGER_2026-04-28.json`;
  small-batch replay
  `reports/PHASE2_GATE_FIRST_EVENT_DIAGNOSTIC_REPLAY_SMALL_2026-04-28.json`;
  review
  `reports/PHASE2_GATE_FIRST_EVENT_DIAGNOSTIC_REPLAY_SMALL_2026-04-28.md`.
- scope:
  did not modify core searcher. Built a small gate-first diagnostic lane from
  existing A-share adapter seeds plus safe prior-limit-state event formulas.
  All limit-state formulas use `Delay($is_limit_up,1)` or
  `Delay($is_limit_down,1)`; no current-day full-bar limit flags are used as
  after-open features.
- gate:
  both `2025-03-03..2025-08-05` predev holdout and `2025-08-06..2026-02-04`
  development slice must show positive `20bps` net long-short and positive
  group-neutral IC under 2-day rebalance.
- result:
  `36` candidates evaluated, `0` passed, `0` unsupported. The closest candidate
  was short-term anti-momentum `Neg(CSRank(Mom($close,5)))`: predev net LS
  `-0.000202`, predev GN IC `0.026416`; development net LS `0.000034`,
  development GN IC `0.025716`. Several prior-limit-down event variants had
  positive GN IC in both windows but negative net LS after cost.
- interpretation:
  the gate-first loop is behaving correctly: it blocks IC-only or local-window
  candidates before promotion. The simple prior-limit-state mini-family is not
  enough by itself. Next discovery should expand the mathematical generator
  while keeping this two-split promotion gate, rather than loosening evidence
  thresholds.

2026-04-29 reusable predev stock PIT cache and low-turnover math smoke:

- artifacts:
  predev cache metadata
  `reports/PHASE2_STOCK_PREDEV_HOLDOUT_SLICE_2026-04-29.json`;
  low-turnover candidate ledger
  `reports/PHASE2_GATE_FIRST_LOW_TURNOVER_MATH_LEDGER_2026-04-29.json`;
  small replay
  `reports/PHASE2_GATE_FIRST_LOW_TURNOVER_MATH_REPLAY_SMALL_2026-04-29.json`;
  review
  `reports/PHASE2_GATE_FIRST_LOW_TURNOVER_MATH_REPLAY_SMALL_2026-04-29.md`.
- cache:
  built reusable stock-level predev panel at
  `G:/Project_V7_Rotation/scripts/data/phase2_stock_predev_holdout_slice_2026-04-29.parquet`
  from local TDX day files and PIT JQ/SW-L1 sector mapping. The parquet is
  outside the repo. It contains `922,760` panel rows, `168` dates, `5533`
  stocks; evaluation window `2025-03-03..2025-08-05`, load/warmup window
  `2024-12-01..2025-08-08`; Unknown-sector ratio `0.097770`.
- gate contract:
  did not modify the core searcher. Replayed `16` low-turnover math candidates
  from the `199`-record ledger under after-open semantics: current-day `open`
  can be used, full-day OHLCV/amount/return fields are lagged to prior trading
  day. Signal date `t` enters at `t+1`, H1 label is next one-day
  close-to-close. Long side excludes execution-day limit-up/suspension; short
  side excludes execution-day limit-down/suspension; IC excludes execution-day
  limit-up/down/suspension. Cost is `20bps` one-way by realized bucket turnover.
- result:
  `1/16` candidate cleared the two-split gate. The survivor is
  `gatefirst-lowturn-small-0013`,
  `Neg(CSRank(Div(Mean($volume,13),Mean($volume,55))))`.
  Predev: net LS `0.000068`, GN IC `0.036199`, one-way turnover `0.085539`,
  net Sortino `0.011025`. Development: net LS `0.000038`, GN IC `0.036259`,
  one-way turnover `0.082025`, net Sortino `0.010900`.
- interpretation:
  this is not commercial proof: net edge is tiny after cost, and this is a
  small replay, not a frozen forward run. It is still useful because it shows
  that the stricter gate can produce a non-empty result when the candidate
  targets low-turnover liquidity/crowding structure instead of high-turnover
  price momentum. Next step should expand this family with staged pruning:
  cheap sector-neutral IC/liquidity filters first, then full tradability and
  turnover replay only for survivors. Promotion remains `HOLD_RESEARCH`.

2026-04-29 liquidity/crowding family expansion:

- artifacts:
  `reports/PHASE2_LIQUIDITY_CROWDING_FAMILY_EXPANSION_2026-04-29.json`;
  `reports/PHASE2_LIQUIDITY_CROWDING_FAMILY_EXPANSION_2026-04-29.md`.
- scope:
  focused expansion around the low-turnover survivor, without modifying the
  core searcher. Tested `60` formulas over `volume` and `amount` short/long
  mean ratios, both signs, using after-open semantics with `volume`/`amount`
  shifted to the prior completed trading day.
- correction:
  this run uses the stricter intended `2`-signal-date rebalance cadence with
  `20bps` one-way turnover cost. The preceding small replay used a daily
  cadence; therefore its single pass should be treated as a weak diagnostic
  only, not a promotion result.
- result:
  `0/60` candidates passed the two-split gate. The best rows retained positive
  group-neutral IC in both windows but failed development net spread. Example:
  `Neg(CSRank(Div(Mean($volume,3),Mean($volume,34))))` had predev net LS
  `0.000384`, predev GN IC `0.036748`, but development net LS `-0.000030`,
  development GN IC `0.032938`. The previous shape
  `Neg(CSRank(Div(Mean($volume,13),Mean($volume,55))))` was not a robust
  two-day rebalance survivor.
- interpretation:
  liquidity/crowding has a real-looking IC structure, but not enough standalone
  tradable spread under stricter cost/rebalance assumptions. Keep it as a
  possible context/gating ingredient, not as a standalone edge. The next search
  should combine this low-crowding state with a separate execution alpha or
  event trigger, while keeping the two-split A-share tradability gate.

2026-04-29 overnight long task flow:

- artifacts:
  `reports/PHASE2_OVERNIGHT_LONG_TASK_FLOW_2026-04-29.json`;
  `reports/PHASE2_OVERNIGHT_LONG_TASK_FLOW_2026-04-29.md`;
  runner
  `runtime/next_stage_artifacts/phase2-overnight-long-search-20260429/run_overnight_phase2_search.py`.
- objective:
  run a minimum `5` hour Phase2 three-dimensional formula-space search using
  the existing generation runtime, not a rewritten searcher. Each cycle writes
  independent artifacts and passes its final archive root into the next cycle.
- starting point:
  latest retained archive root
  `runtime/next_stage_artifacts/phase2-score-tower-guard-smoke-20260428/phase2-bf47002df5`;
  real replay feedback objective
  `reports/PHASE2_MERGED_SATURATED_FEEDBACK_OBJECTIVE_2026-04-28.json`.
- parameters:
  `flow_length=2`, `rounds=28`, `per_lane_budget=9`, repeated until minimum
  runtime is reached. The runner exposes a `STOP` file for controlled shutdown
  after the active cycle.
- interpretation:
  this is discovery only. It can widen and deepen the formula-space search, but
  it cannot produce a commercial claim until generated candidates are replayed
  under A-share timestamp, T+1,涨跌停/停牌, turnover/cost, and multi-window gates.

2026-04-29 overnight long search result:

- artifact:
  `reports/PHASE2_OVERNIGHT_LONG_SEARCH_RESULT_2026-04-29.md`.
- status:
  `PARTIAL_SUCCESS_WITH_RUNNER_BUG`. The first cycle completed one valid
  `flow_length=2` generation flow, but the runner then passed the flow root
  instead of the final internal run root as `previous_run_root`; cycles `2..999`
  failed quickly with missing `archive_state.json`. Effective runtime was
  `1.69` hours, not the intended `5+` hours.
- valid search output:
  internal runs `phase2-74692eb2e9` and `phase2-67ea2b1b3d` both passed runtime
  gates. Starting archive had `293` retained records; final archive had `311`.
  There were `20` final-archive additions vs the starting archive. Run-level
  accounting: `726` generated candidates, `45` retained candidates, `18` net
  archive growth, `25` new behavior cells.
- runtime decision:
  the generation flow itself recommended
  `HOLD_SYNTHETIC_SCALE_RUN_REAL_REPLAY` because retained yield stayed below
  floor and new-cell yield was low. This supports converting candidates to
  A-share replay, not blindly continuing synthetic search.
- fix:
  patched the overnight runner to read `multi_run_generation_summary.json` and
  continue from the final internal run root when `flow_length > 1`.

2026-04-29 overnight new retained A-share replay stage1:

- artifacts:
  ledger
  `reports/PHASE2_OVERNIGHT_NEW_RETAINED_A_SHARE_REPLAY_LEDGER_2026-04-29.json`;
  stage1 replay
  `reports/PHASE2_OVERNIGHT_NEW_RETAINED_A_SHARE_REPLAY_STAGE1_2026-04-29.json`;
  review
  `reports/PHASE2_OVERNIGHT_NEW_RETAINED_A_SHARE_REPLAY_STAGE1_2026-04-29.md`.
- scope:
  extracted the `20` final-archive additions from the valid overnight flow and
  stripped rank-equivalent nested outer `CSRank(...)` wrappers. `16/20` were
  stock-PIT compatible after existing field aliases (`mbrd->vwap`,
  `pldn->low`, `arat->amount`, `volt->volume`, `vrat->turnover_rate`).
  `4/20` were unsupported because current stock PIT cache lacks
  `price_pos`, `crowding`, `rps_score`, and/or `money_flow`.
- execution:
  the full `16`-candidate replay timed out after `30` minutes due to very deep
  nested relation towers, so stage1 evaluated the `6` candidates with estimated
  validation cost `<=130` and deferred the `10` very-slow towers. Replay used
  after-open field lagging, T+1 execution, 2-signal-date rebalance, execution
  day limit/suspension filtering, PIT-sector GN IC, and `20bps` one-way
  turnover cost.
- result:
  `0/6` stage1 candidates passed. Best by gate score was
  `v2cand-fdaa15b69106`: predev net LS `-0.000789`, predev GN IC `-0.002573`;
  development net LS `-0.000470`, development GN IC `0.000394`. The next two
  evaluated candidates also had negative predev and development net LS. Three
  Sign-heavy candidates produced no valid daily IC/spread rows under this
  replay contract.
- interpretation:
  the low/medium-cost overnight synthetic leads did not translate into
  tradable stock-level A-share edge. The remaining high-cost towers should not
  be evaluated naively; either build an optimized expression compiler/cache for
  deep relation towers, or route search budget toward A-share-native
  stock-PIT-compatible structures with explicit cost/depth penalties.

2026-04-29 A-share stock PIT soft routing:

- change:
  added an A-share stock-PIT compatibility profile into the existing
  three-dimensional pre-screen score. This is a soft routing prior only, not a
  formula-space lock: unsupported fields and very high estimated validation
  cost receive penalties, while stock-PIT-compatible candidates receive a small
  bonus.
- scope:
  no core generator rewrite. The portable expression space remains intact for
  future non-A-share use; the A-share preference is reported as
  `soft_search_routing_prior_not_formula_space_lock`.
- reason:
  overnight replay showed that unsupported fields (`price_pos`, `crowding`,
  `rps_score`, `money_flow`) and deep relation towers can consume replay budget
  without producing tradable stock-level evidence. The new prior nudges future
  search toward candidates that can be validated under current A-share PIT,
  T+1, limit/suspension, turnover/cost, and multi-window gates.
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "target_aware_pre_screen"`
  passed: `11 passed, 131 deselected`.

2026-04-29 replay-panel-aware soft routing correction and smoke:

- correction:
  the first A-share soft-routing field set was too conservative because it
  treated fields missing from the smaller fast cache as unavailable. The real
  replay panel can evaluate `price_pos`, `crowding`, `rps_score`, and
  `money_flow` under the signal-clock lag contract, so the router now separates
  replay-panel support from fast-cache coverage. Fast-cache misses are
  diagnostic/lightly penalized, not treated as unsupported fields.
- smoke artifact:
  `runtime/next_stage_artifacts/phase2-ashare-replay-panel-soft-routing-smoke-20260429/phase2-16af7ed4bd`.
  Generated `42`, retained `10`, retained yield `0.238095`, archive growth
  `5`, new behavior cells `7`.
- routing readout:
  `31` target-aware pre-screen events and `112` profiled candidate items.
  All `26` selected profiled candidates were replay-panel supported; selected
  candidates still included optional fields when proper replay support existed.
- real replay:
  new-retained ledger
  `reports/PHASE2_ASHARE_REPLAY_PANEL_SOFT_ROUTING_SMOKE_NEW_RETAINED_LEDGER_2026-04-29.json`;
  replay report
  `reports/PHASE2_ASHARE_REPLAY_PANEL_SOFT_ROUTING_SMOKE_NEW_RETAINED_REAL_REPLAY_4Q_2026-04-29.json`;
  review
  `reports/PHASE2_ASHARE_REPLAY_PANEL_SOFT_ROUTING_SMOKE_REVIEW_2026-04-29.md`.
  Net-new retained candidates: `5`; evaluated `5`; unsupported `0`; passed
  `0`; promoted `0`. Best IC was still negative (`v2cand-01f1717b6d6d`
  mean/recent IC `-0.001844`), so no candidate is commercial or KEEP evidence.
- next target:
  keep the replay-panel-aware router, but do not scale this exact motif family
  blindly. Bias the next search toward compact kernels or event/state gates
  that can survive T+1 tradability and cost-adjusted stock replay.

2026-04-29 CFG+ sidecar pass12 strict stock-PIT audit:

- artifacts:
  default-panel strict audit
  `reports/PHASE2_CFG_PLUS_SIDECAR_PASS12_STRICT20_EXPOSURE_AUDIT_2026-04-29.json`;
  stock-PIT audit
  `reports/PHASE2_CFG_PLUS_SIDECAR_POS8_STOCK_PIT_STRICT20_GN_AUDIT_2026-04-29.json`;
  review
  `reports/PHASE2_CFG_PLUS_SIDECAR_STRICT_STOCK_PIT_AUDIT_REVIEW_2026-04-29.md`.
- setup:
  re-audited the `12` CFG+ sidecar smoke-pass candidates with after-open
  signal clock, validator field lags, T+1 execution, 1d horizon, and `20bps`
  one-way turnover cost. Then moved the `8` default-panel positive-spread
  candidates to the stock PIT slice
  `G:/Project_V7_Rotation/scripts/data/phase2_stock_validation_slice_2026-04-27.csv.gz`,
  which contains PIT `sector` with median `86` codes/group.
- default-panel result:
  `8/12` kept positive 20bps cost-adjusted spread. Top default-panel rows were
  `v8-natural-0043` spread `0.000731`, IC `0.013225`; `v8-natural-0039`
  spread `0.000550`, IC `0.011234`; `v8-natural-0021` spread `0.000338`,
  IC `0.025425`.
- stock-PIT result:
  `0/8` kept positive 20bps cost-adjusted spread. V18 rows retained only tiny
  positive group-neutral IC (`0.002404..0.004560`) but negative stock IC and
  negative net spread. V8 rows had negative stock IC and negative group-neutral
  IC. Best stock-PIT spread was still negative:
  `v18-tplus1-0031` spread `-0.000360`, stock IC `-0.000464`, GN IC
  `0.004368`.
- decision:
  `HOLD_RESEARCH / FAIL_PROMOTION`. The sidecar scheduler remains useful for
  triage, but the sidecar pass12 set is not commercial proof and should not be
  scaled as-is. Next search needs stock-PIT/cost-aware objectives earlier in
  the loop rather than board/default-panel smoke followed by late rejection.

2026-04-29 stock-PIT compact direct search and throttle probe:

- artifacts:
  ledger
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_LEDGER_2026-04-29.json`;
  replay
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_REPLAY_2026-04-29.json`;
  strict top audit
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_TOP_STRICT20_2026-04-29.json`;
  corrected throttle probe
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_TOP10_REBALANCE_THROTTLE_V2_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_REVIEW_2026-04-29.md`.
- search:
  generated `120` low-cost compact candidates directly against the stock PIT
  slice. Families included vol-scaled reversal, smooth momentum over abs-return,
  overnight/open-position, low volume/amount crowding, and shallow interactions.
  Replay evaluated `120`, unsupported `0`, daily-rebalance smoke pass `0`.
- strict daily readout:
  top candidates had positive stock IC and group-neutral IC but failed 20bps
  daily net spread. Examples: `stockpit-compact-65b27be6d609`
  (`Neg(CSRank(Div(Mean($amount,10),Mean($amount,34))))`) had IC `0.030049`,
  GN IC `0.025566`, turnover `0.107358`, but 20bps spread `-0.000159`.
  `stockpit-compact-13a867506b13` had IC `0.028363`, GN IC `0.023890`,
  turnover `0.110928`, spread `-0.000118`.
- throttle probe:
  the first throttle attempt used mismatched tradability column names and was
  discarded. V2 uses `entry_limit_up`, `entry_limit_down`, and
  `entry_suspended`, side counts based on filtered side pools, and charges the
  first entry as `100%` turnover. Under the `1/2/3/5/10` day rebalance grid,
  the top10 all had a positive best-frequency 20bps net spread. Best rows:
  `stockpit-compact-82c9b149ee76` vol-scaled reversal, best freq `5`, net
  `0.000558`, Sortino `0.998406`, turnover `0.170812`;
  `stockpit-compact-65b27be6d609` low-amount crowding, best freq `2`, net
  `0.000486`, Sortino `1.588271`, turnover `0.101929`;
  `stockpit-compact-13a867506b13` low-volume crowding, best freq `3`, net
  `0.000410`, Sortino `1.412950`, turnover `0.096963`.
- decision:
  `HOLD_RESEARCH`. This is the first useful stock-PIT-native pocket after the
  sidecar transfer failure, but the rebalance frequency was selected on the
  same slice. Next step is a frozen holdout test on the pre-development stock
  slice or another disjoint period with the same after-open/T+1/limit/suspension
  and 20bps cost contract.

2026-04-29 stock-PIT compact throttle V3 correction and frozen predev holdout:

- correction:
  the previous throttle V2 probe is superseded. It fixed tradability column
  names but did not pass `after_open` field lags into expression evaluation.
  V3 now calls `evaluate_panel_expression(..., field_lags=signal_clock_report["field_lags"])`,
  so full-day fields are lagged and open-print fields remain available after
  open.
- artifacts:
  V3 validation throttle
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_TOP10_REBALANCE_THROTTLE_V3_2026-04-29.json`;
  frozen predev holdout
  `reports/PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_FROZEN_PREDEV_HOLDOUT_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_FROZEN_PREDEV_HOLDOUT_REVIEW_2026-04-29.md`.
- validation V3:
  on `2025-10-01..2026-02-04`, top10 remained positive after field-lagging.
  Best rows: `stockpit-compact-6e62925db22c` open price-position reversal,
  freq `3`, net `0.000520`, Sortino `1.149372`, turnover `0.243777`;
  `stockpit-compact-a39dde8c8de1` freq `3`, net `0.000426`;
  `stockpit-compact-486021dfbd22` freq `3`, net `0.000396`;
  `stockpit-compact-13a867506b13` low-volume crowding, freq `2`, net
  `0.000352`.
- frozen predev holdout:
  on disjoint pre-development stock PIT slice `2025-03-03..2025-08-05`, using
  each candidate's validation-selected frequency with no holdout tuning,
  `10/10` retained positive 20bps net spread. Best holdout rows:
  `stockpit-compact-65b27be6d609` low-amount crowding, frozen freq `3`, net
  `0.000700`, Sortino `1.608255`, turnover `0.094754`;
  `stockpit-compact-82c9b149ee76` vol-scaled reversal, freq `3`, net
  `0.000647`, Sortino `1.784756`;
  `stockpit-compact-2442a7c29e43` vol-scaled reversal, freq `3`, net
  `0.000639`, Sortino `1.817408`;
  `stockpit-compact-13a867506b13` low-volume crowding, freq `2`, net
  `0.000553`, Sortino `1.221142`.
- decision:
  `HOLD_RESEARCH / PROMISING_RESEARCH_POCKET`. This is the strongest
  stock-PIT-native result so far, but it is not commercial proof because the
  holdout is disjoint/predev rather than chronological forward OOS, and
  production portfolio construction, slippage/capacity, ST/delisting policy,
  sector caps, and forward shadow validation remain open.

2026-04-29 stock-PIT compact top6 ensemble portfolio probe:

- artifacts:
  probe
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_ENSEMBLE_PORTFOLIO_PROBE_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_ENSEMBLE_PORTFOLIO_REVIEW_2026-04-29.md`.
- frozen inputs:
  combined six signals from the strongest families before running the probe:
  low-amount crowding `stockpit-compact-65b27be6d609`, low-volume crowding
  `stockpit-compact-13a867506b13`, vol-scaled reversal
  `stockpit-compact-82c9b149ee76` and `stockpit-compact-2442a7c29e43`, and
  open price-position reversal `stockpit-compact-6e62925db22c` and
  `stockpit-compact-486021dfbd22`.
- construction:
  average component percentile ranks by date; fixed `3`-day rebalance; long
  top `20%` and short bottom `20%`; `20bps` one-way cost on realized turnover;
  rebalance-day limit/suspension filters; simple sector count cap of `20%` per
  side; after-open field lags passed into every component expression.
- result:
  validation slice `2025-10-01..2026-02-04`: `81` days, net LS `0.000539`,
  Sortino `1.591791`, avg turnover `0.205927`, max drawdown `-0.057903`,
  avg long names `1082.963`, avg long sectors `31.370`.
  Predev holdout `2025-03-03..2025-08-05`: `107` days, net LS `0.000925`,
  Sortino `2.090494`, avg turnover `0.208858`, max drawdown `-0.033921`,
  avg long names `1079.402`, avg long sectors `30.935`.
- decision:
  `HOLD_RESEARCH / PROMISING_PORTFOLIO_PROBE`. This is the strongest
  portfolio-like Phase2 result so far, but still not commercial proof. Next
  steps should harden this exact frozen ensemble with chronological forward
  shadow, 10/20/30bps stress, long-only variant, sector exposure reports, and
  capacity/slippage estimates before broadening search.

2026-04-29 stock-PIT compact top6 ensemble stress/capacity:

- artifacts:
  stress/capacity report
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_ENSEMBLE_STRESS_CAPACITY_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_ENSEMBLE_STRESS_CAPACITY_REVIEW_2026-04-29.md`.
- setup:
  same frozen top6 ensemble, same `3`-day rebalance, same after-open field
  lags, T+1 execution, limit/suspension filters, and `20%` count-based sector
  cap. Tested long-short and long-only modes under `10/20/30bps` one-way costs.
  Capacity proxy uses T+1 entry-day amount distribution of selected baskets.
- validation stress:
  long-short net remained positive at `10/20/30bps`: `0.000745`, `0.000539`,
  `0.000333`; Sortino `2.257773`, `1.591791`, `0.970014`. Long-only also
  remained positive through `30bps`: `0.001476`, `0.001270`, `0.001065`.
- predev holdout stress:
  long-short net remained positive at `10/20/30bps`: `0.001134`, `0.000925`,
  `0.000716`; Sortino `2.568594`, `2.090494`, `1.604843`. Long-only also
  remained positive through `30bps`: `0.001522`, `0.001316`, `0.001111`, but
  drawdown was much larger (`~ -0.185..-0.189`) than long-short.
- capacity proxy:
  validation long basket averaged `1082.963` names, long entry amount p10
  `40.67m` CNY and p01 `18.26m`; predev long basket averaged `1079.402`
  names, p10 `37.58m` and p01 `15.20m`. Max sector count weight stayed around
  `13.6..15.4%` after the simple cap.
- decision:
  `HOLD_RESEARCH / STRONG_RESEARCH_POCKET`. The ensemble is robust enough to
  freeze for forward-shadow, but still lacks chronological forward OOS,
  production portfolio construction, order-book slippage/capacity, ST/delisting
  policy, taxes/financing, and execution queue modeling.

2026-04-29 stock-PIT compact top6 reusable report module:

- code:
  added `src/our_system_phase2/services/stock_pit_compact_ensemble.py` as a
  reusable frozen reporter for the current top6 pocket. It does not modify the
  Phase2 searcher or formula space; it only packages the existing stock-PIT
  reproduction contract: after-open signal clock, full-day field lags, T+1
  execution, rebalance-day limit/suspension filters, fixed `3`-day rebalance,
  long/short `20%` baskets, simple sector count cap, and 10/20/30bps cost
  stress.
- artifact:
  reusable report
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_ENSEMBLE_REUSABLE_REPORT_2026-04-29.json`.
  The report intentionally omits daily rows by default so future forward-shadow
  appends are compact and reproducible.
- current reusable-report metrics:
  validation slice `2025-10-01..2026-02-04`: `81` days, 20bps long-short net
  `0.000522`, Sortino `1.509627`, avg turnover `0.205980`. Predev holdout
  `2025-03-03..2025-08-05`: `107` days, 20bps long-short net `0.000902`,
  Sortino `2.057189`, avg turnover `0.208819`.
- note:
  this reusable implementation uses the explicit tradable-pool basket rule as
  the forward protocol. The earlier one-off stress report remains a historical
  run; future append/replay comparisons should use this module to avoid
  hand-script drift.
- tests:
  `py_compile` OK; `unittest -k stock_pit_compact_ensemble` ran `2` tests OK;
  `pytest -q tests/test_phase2_v21_runtime.py -k "after_open or stock_pit_compact_ensemble or ashare"`
  ran `8` tests OK.
- next:
  start the chronological forward-shadow ledger using this reporter before any
  new commercial-grade claim or further expression changes.

2026-04-29 stock-PIT compact top6 Qlib forward-shadow:

- artifacts:
  forward-shadow report
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_FORWARD_SHADOW_QLIB_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_FORWARD_SHADOW_QLIB_REVIEW_2026-04-29.md`.
- data:
  found Qlib rolling A-share data at
  `G:\Project_V7_Rotation\_runtime_home\.qlib\qlib_data\cn_data_rolling`
  with calendar through `2026-04-17`. Built an external parquet panel
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_forward_shadow_qlib_2026-04-29.parquet`
  with `606883` rows, `5519` codes, dates `2025-11-03..2026-04-17`.
  Limit states were derived from Qlib `change` into `rt_change_pct`; sector
  mapping was unavailable, so no sector cap was applied.
- result:
  true chronological forward-shadow window `2026-02-05..2026-04-15`, `43`
  signal days. Long-short net was negative under all costs:
  `10bps -0.001213`, `20bps -0.001430`, `30bps -0.001647`; Sortino
  `-1.562784`, `-1.765264`, `-1.968309`. Long-only was also negative:
  `10bps -0.000892`, `20bps -0.001110`, `30bps -0.001327`.
- decision:
  `FAIL_FORWARD_SHADOW / HOLD_RESEARCH`. This blocks any commercial-grade
  claim for the frozen top6 pocket. It remains useful as a diagnostic failure:
  next work should isolate data-source normalization vs post-2026-02 regime
  decay vs missing sector constraints, rather than tuning the same ensemble
  after seeing the failed forward slice.

2026-04-29 stock-PIT compact top6 regime decay diagnostic:

- artifacts:
  Qlib overlap/forward calibration
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_QLIB_OVERLAP_CALIBRATION_2026-04-29.json`;
  CSV vs Qlib overlap comparison
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_CSV_QLIB_OVERLAP_COMPARISON_2026-04-29.json`;
  CSV validation split
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_CSV_VALIDATION_SPLIT_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_REGIME_DECAY_DIAGNOSTIC_REVIEW_2026-04-29.md`.
- result:
  CSV validation early `2025-10-01..2025-12-12`: LS 20bps net `0.000662`,
  Sortino `1.654605`, while long-only was negative `-0.000302`. CSV validation
  tail `2025-12-15..2026-02-04`: LS 20bps net `-0.001089`, Sortino
  `-1.270395`, while long-only was strong positive `0.002707`. Qlib overlap
  tail agreed directionally: LS negative `-0.000795`, long-only positive
  `0.002482`. Qlib forward-shadow `2026-02-05..2026-04-15`: both LS and
  long-only turned negative (`-0.001430` and `-0.001110` at 20bps).
- interpretation:
  the pocket is not a stable commercial edge. Full-validation positivity hid a
  side/regime split, not a durable all-weather signal. The correct next
  research move is regime/state gating and asymmetric side routing under a
  frozen forward protocol, not retroactively tuning the failed top6 ensemble.

2026-04-29 timestamp-safe side gate attempt on frozen top6:

- artifacts:
  gate report
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_TIMESTAMP_SAFE_SIDE_GATE_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_TOP6_TIMESTAMP_SAFE_SIDE_GATE_REVIEW_2026-04-29.md`.
- setup:
  trained gates only on CSV validation `2025-10-01..2026-02-04`, tested on
  Qlib forward-shadow `2026-02-05..2026-04-15`, cost `20bps`, `440` candidate
  feature/policy combinations. Gate features were timestamp-safe: current-open
  gap aggregates, signal dispersion after after-open field lags, and prior-day
  full-bar market state shifted one trading day. No same-day close/return/limit
  state was used for gate decisions.
- result:
  train-selected gates improved validation but failed forward. Best
  train-selected row `signal_top_bottom_gap_le_q50 + lo_if_gate_else_ls` had
  train net `0.002305` but forward net `-0.001179`. Other top train-selected
  gates also stayed negative forward (`-0.001694`, `-0.001694`, `-0.001179`).
  Forward has post-hoc positive gates such as
  `signal_top_bottom_gap_ge_q80 + lo_if_gate_else_cash` with forward net
  `0.002240`, but its train net was `-0.000402`, so it is only a search hint.
- decision:
  `FAIL_FORWARD_GATE / HOLD_RESEARCH`. Do not rescue the old top6 ensemble with
  one-dimensional gates. Next search should create new timestamp-safe
  side-specific candidates under a pre-registered train/forward protocol.

2026-04-29 stock-PIT compact 120 side-specific forward selection:

- artifacts:
  report
  `reports/PHASE2_STOCK_PIT_COMPACT_120_SIDE_SPECIFIC_FORWARD_2026-04-29.json`;
  review
  `reports/PHASE2_STOCK_PIT_COMPACT_120_SIDE_SPECIFIC_FORWARD_REVIEW_2026-04-29.md`.
- setup:
  evaluated the existing `120` compact direct-search candidates from
  `PHASE2_STOCK_PIT_COMPACT_DIRECT_SEARCH_LEDGER_2026-04-29.json`. Qlib
  forward panel supports `88`; `32` require `$overnight` and were excluded.
  Train selection used CSV validation `2025-10-01..2026-02-04`; forward test
  used Qlib `2026-02-05..2026-04-15`; cost `20bps`; signal/execution/tradability
  used the reusable after-open/T+1 stock-PIT reporter.
- result:
  long-short: top validation-selected candidates all failed forward; best train
  row `stockpit-compact-6e62925db22c` had train net `0.000523` but forward
  `-0.001789`. Forward-positive among top20 train-selected LS candidates:
  `0/20`.
  Long-only: top validation-selected candidates also all failed forward; best
  train row `stockpit-compact-13a867506b13` had train net `0.001552` but
  forward `-0.000729`. Forward-positive among top20 train-selected LO
  candidates: `0/20`.
- diagnostic:
  post-hoc forward-positive candidates exist, mostly raw open-price-position
  direction and short-only diagnostics, but their validation train net was
  negative, so they are not valid promotions.
- decision:
  `FAIL_FORWARD_SELECTION / HOLD_RESEARCH`. The existing compact pool should
  not be mined further for deployable survivors. Next useful work is new
  timestamp-safe side-specific formula generation under the frozen
  validation/forward protocol.

2026-04-29 forward-first large search preparation:

- artifacts:
  generator
  `src/our_system_phase2/services/stock_pit_forward_first_search.py`;
  3000-candidate ledger
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_LARGE_SEARCH_LEDGER_2026-04-29.json`;
  cost report
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_LARGE_SEARCH_COST_REPORT_2026-04-29.json`;
  25-candidate timing dry-run
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_DRYRUN_25_2026-04-29.json`;
  prep review
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_LARGE_SEARCH_PREP_REVIEW_2026-04-29.md`.
- generator:
  added a forward-first, Qlib-compatible, timestamp-safe stock-PIT ledger
  builder. It does not modify the core Phase2 searcher. Windows come from real
  data scales plus local neighborhoods, not fixed registered priors. It avoids
  `$overnight`, uses `after_open`, and relies on the existing evaluator to lag
  full-day fields.
- prepared search space:
  current parameter slice full space `31350`; prepared stage1 ledger `3000`.
  Deterministic round-robin scheduling gives early coverage across
  `cross_axis_interaction_probe` (`1578`), `liquidity_state_probe` (`525`),
  `side_directional_probe` (`372`), and `volatility_normalized_side_probe`
  (`525`). Cost report: `2474` cheap fast-path, `526` moderate fast-path,
  `0` slow relation-path.
- dry-run:
  `25` candidates, elapsed `134.23s`, about `5.369s/candidate`, unsupported
  `0`, smoke pass `0`. The zero smoke pass is not a discovery conclusion:
  stage1 used a recent two-quarter training slice while the smoke flag expects
  more quarterly windows. Use IC/sortino ranking for stage1 triage, then only
  send train-selected candidates to expensive stock-PIT portfolio replay and
  Qlib forward-shadow.
- next:
  run stage1 in resumable shards, preferably `25..50` candidates per shard.
  Estimated time for the prepared `3000` candidates is roughly `4.5` hours at
  the measured rate, before expensive portfolio replay.

2026-04-29 forward-first stage1 shard progress:

- artifacts:
  shard reports
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_000_2026-04-29.json`
  through
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_009_2026-04-29.json`;
  shard ledgers
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_000_LEDGER_2026-04-29.json`
  through
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_009_LEDGER_2026-04-29.json`;
  refreshed summary
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_SUMMARY_2026-04-29.json`;
  forward-blind diversity shortlist
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_500_SHORTLIST_2026-04-29.json`.
- setup:
  evaluated shards `000..009`, `50` candidates each, on CSV validation
  `2025-10-01..2026-02-04`. This is discovery-stage ranking only: no forward
  labels were used. Contract remains `after_open`, field-level lagging for
  full-day bar fields, execution `T+1`, and tradability rows excluded for IC
  where the data exposes limit-up, limit-down, and suspension flags.
- result:
  `500` candidates evaluated, unsupported `0`, smoke pass `0`, elapsed
  `2195.13s`, about `4.390s/candidate`. The zero smoke pass is expected for
  the two-quarter stage1 screen and is not used as the ranking signal.
  Current top IC rows are still concentrated in short-window low-volatility /
  inverse-volatility families:
  `stockpit-ff-224f022784b1` IC `0.058714`, Sortino `0.204251`,
  `Neg(ZScore(Mean(Abs($ret),4)))`;
  `stockpit-ff-5fd225176dfe` IC `0.058714`, Sortino `0.204251`,
  `Neg(CSRank(Mean(Abs($ret),4)))`;
  `stockpit-ff-883eb9929c08` IC `0.057771`, Sortino `-0.200079`,
  `Neg(ZScore(Mean(Abs($ret),7)))`;
  `stockpit-ff-8ef7a8363155` IC `0.057771`, Sortino `-0.200079`,
  `Neg(CSRank(Mean(Abs($ret),7)))`.
  The top Sortino rows are more interaction-like:
  `amount_ratio_x_momentum_curve` Sortino `2.998139` but IC only `0.008404`,
  `volume_ratio_x_momentum_curve` Sortino `2.010555` with IC `0.011763`,
  `turnover_ratio_x_momentum_curve` Sortino `1.794497` but IC only
  `0.000282`, and another `amount_ratio_x_momentum_curve` row has Sortino
  `1.732583` with IC `0.013803`.
- shortlist:
  created a forward-blind `31` candidate diversity shortlist for replay. It
  family-caps IC leaders and Sortino leaders so replay is not monopolized by
  inverse-volatility. Families represented include volatility zscore/rank,
  open-gap zscore/rank, momentum zscore/rank, open-position-vol-scaled,
  momentum-vol-scaled, amount/volume/turnover ratio x momentum-curve,
  amount-ratio x open-position-fast, and amount-ratio x vol-curve.
- interpretation:
  this is a useful discovery signal, not deployable evidence. The next
  promotion gate is still chronological portfolio replay with cost, capacity,
  A-share tradability, and Qlib forward-shadow. Do not infer commercial edge
  from this stage alone.
- next:
  run chronological stock-PIT portfolio replay on the forward-blind 500-candidate
  shortlist with cost, capacity, A-share tradability, and `T+1`; continue shards
  `010+` only if replay does not produce robust forward survivors or if more
  family coverage is needed.

2026-04-29 forward-first 500 shortlist portfolio replay:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_500_SHORTLIST_PORTFOLIO_REPLAY_2026-04-29.json`.
- setup:
  replayed the forward-blind `31` candidate shortlist from the first `500`
  stage1 candidates. Train slice is CSV validation `2025-10-01..2026-02-04`;
  forward shadow is Qlib `2026-02-05..2026-04-15`. Replay used `after_open`,
  field-level lags for full-day fields, execution `T+1`, top/bottom `20%`,
  rebalance frequencies `1/3/5`, costs `10/20/30bps`, and A-share entry
  tradability filters. Forward labels were not used to build the shortlist.
- result:
  `31` candidates x `3` rebalance frequencies x `2` modes produced `186`
  primary rows at `20bps`. `105/186` were train-positive; only `5` of those
  were also forward-positive. The strongest forward survivor is
  `stockpit-ff-ef146fc245b0`, a cross-axis
  `turnover_ratio_x_momentum_curve` residual formula:
  `CSRank(CSResidual(CSRank(Sub(Mom($close,1),Mom($close,6))),CSRank(Div(Mean($turnover_rate,1),Mean($turnover_rate,6)))))`.
  At rebalance `5`, LS `20bps`, it had train net `0.000159`, train Sortino
  `0.390247`, forward net `0.000812`, forward Sortino `1.258979`, forward
  max drawdown `-0.021191`, forward positive-day ratio `0.627907`, and average
  turnover about `0.161902`.
- caveat:
  the survivor is a real research lead but not commercial proof. Train edge is
  thin, forward sample is only `43` days, and the other forward-positive rows
  are very small (`0.000147`, `0.000110`, `0.000107`, `0.000056` net/day).
  Decision remains `HOLD_RESEARCH`.
- next:
  run focused bias/exposure audit on the top survivor and near-survivor family,
  then either use them as weak soft priors for shards `010+` or run a second
  independent forward period if available.

2026-04-29 top survivor focused audit:

- artifacts:
  parquet loader compatibility fix in
  `src/our_system_phase2/services/real_market_validation.py`;
  regression test in `tests/test_phase2_v21_runtime.py`;
  audit report
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_TOP_SURVIVOR_AUDIT_2026-04-29.json`.
- target:
  audited `stockpit-ff-ef146fc245b0`, the best train-selected forward-positive
  replay row from the 500-candidate shortlist. Formula:
  `CSRank(CSResidual(CSRank(Sub(Mom($close,1),Mom($close,6))),CSRank(Div(Mean($turnover_rate,1),Mean($turnover_rate,6)))))`.
- result:
  strict IC remains positive but the strict daily top/bottom cost-adjusted
  spread is negative. CSV train strict IC `0.022619`, cost-adjusted spread
  `-0.000661`, mean one-way turnover `0.354862`; Qlib forward strict IC
  `0.016973`, cost-adjusted spread `-0.001114`, mean one-way turnover
  `0.361765`. Exposure residualization weakens IC materially: CSV residualized
  IC `0.011522` (`-0.011097` delta); Qlib residualized IC `0.007023`
  (`-0.009950` delta). CSV group-neutral IC is still positive at `0.016838`,
  but Qlib forward panel has no usable group column for true group neutral
  replay.
- interpretation:
  the replay survivor is not a promotion candidate. Its best evidence is a
  low-turnover `5`-day rebalance LS shape from the portfolio replay, not a
  robust daily tradable edge. Treat it as a weak research hint for turnover-
  residualized momentum-curve interactions, with explicit turnover throttling,
  not as a commercial signal.
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "parquet_panels or forward_first_large_search or stock_pit_compact_ensemble or after_open"`
  passed: `7 passed, 139 deselected`.
- next:
  continue stage1 shards `010+`, but bias sampling toward cross-axis
  interaction probes and 5-day turnover-throttled payoff shapes; do not let
  inverse-volatility IC leaders monopolize replay budget.

2026-04-29 forward-first stage1 shards 010-011:

- artifacts:
  shard reports
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_010_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_011_2026-04-29.json`;
  shard ledgers
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_010_LEDGER_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_011_LEDGER_2026-04-29.json`;
  refreshed summary
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_SUMMARY_2026-04-29.json`.
- result:
  stage1 total is now `600` candidates over `12` shards, unsupported `0`,
  smoke pass `0`, average `4.441s/candidate`. New IC leaders still mainly add
  more inverse-volatility windows, not a new promotion-quality family. Shard
  `011` added `stockpit-ff-e2efc0b8f91c`
  `Neg(CSRank(Mom($close,11)))` with IC `0.032932` and Sortino `1.513907`,
  consistent with the earlier momentum-zscore replay survivor family.
- interpretation:
  more blind scale is producing coverage but not yet a clearly stronger edge.
  The useful direction remains family-capped replay of non-volatility motifs,
  especially momentum-curve / turnover interaction and longer-window momentum
  reversal, under explicit low-turnover rebalance.
- next:
  either continue shards `012+` for breadth, or build the next replay shortlist
  only from candidates not already represented in the 500-candidate replay.

2026-04-29 forward-first stage1 shards 012-013 and incremental shortlist:

- artifacts:
  shard reports
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_012_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_013_2026-04-29.json`;
  shard ledgers
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_012_LEDGER_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_013_LEDGER_2026-04-29.json`;
  refreshed summary
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_SUMMARY_2026-04-29.json`;
  incremental shortlist
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_700_INCREMENTAL_SHORTLIST_2026-04-29.json`.
- result:
  stage1 total is now `700` candidates over `14` shards, unsupported `0`,
  smoke pass `0`, average `4.487s/candidate`. Shards `012/013` added more
  useful non-volatility motifs: `open_gap_rank`, `momentum_rank`,
  `prior_close_position_rank`, and amount/volume momentum-curve interactions.
  Examples: `stockpit-ff-ba9e1be4f052`
  `Neg(CSRank(Div(Sub($open,Delay($close,12)),Delay($close,12))))` IC
  `0.034285`, Sortino `1.564383`; `stockpit-ff-e2efc0b8f91c`
  `Neg(CSRank(Mom($close,11)))` IC `0.032932`, Sortino `1.513907`;
  `stockpit-ff-9dd7871da730` volume-ratio x momentum-curve IC `0.016019`,
  Sortino `1.666047`.
- shortlist:
  created a forward-blind `29` candidate incremental shortlist. It excludes
  candidates and expressions already in the 500-candidate shortlist, excludes
  inverse-volatility IC leaders, and family-caps the remaining non-volatility
  motifs. Families include volume/amount/turnover ratio x momentum-curve,
  open-gap rank/zscore, momentum rank/zscore, momentum-vol-scaled, amount/volume
  ratio, prior-close-position, volume-ratio x open-position-fast, and
  open-position-vol-scaled.
- next:
  run chronological portfolio replay on this incremental shortlist using the
  same `after_open`, `T+1`, cost, and A-share tradability contract as the
  500-candidate replay.

2026-04-29 forward-first 700 incremental shortlist portfolio replay:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_700_INCREMENTAL_PORTFOLIO_REPLAY_2026-04-29.json`.
- setup:
  replayed the forward-blind `29` candidate incremental shortlist. It excludes
  candidates already in the 500-candidate shortlist and excludes inverse-
  volatility leaders. Train slice is CSV validation `2025-10-01..2026-02-04`;
  forward shadow is Qlib `2026-02-05..2026-04-15`. Replay contract is unchanged:
  `after_open`, field-level lags, execution `T+1`, top/bottom `20%`,
  rebalance frequencies `1/3/5`, cost grid `10/20/30bps`, and A-share entry
  tradability.
- result:
  `29` candidates x `3` rebalance frequencies x `2` modes produced `174`
  primary rows at `20bps`; `116/174` were train-positive, and `26` of those
  were also forward-positive. Strongest row:
  `stockpit-ff-b826a24eb2b1`, `Neg(ZScore(Mom($close,6)))`, rebalance `5`,
  LS `20bps`, train net `0.000033`, train Sortino `0.058148`, forward net
  `0.001021`, forward Sortino `1.446329`, forward max drawdown `-0.025014`,
  forward positive-day ratio `0.627907`, forward average turnover `0.150779`.
  Other top forward-positive rows include amount/volume momentum-curve
  residuals (`0.000746`, `0.000723` forward net) and prior-close-position
  reversal (`0.000648` forward net).
- caveat:
  this is a better search result than the first 500-candidate replay, but still
  not promotion evidence. The train edge is thin for the top row, the forward
  sample is only `43` days, and the common pattern may be a regime-specific
  5-day rebalance effect. Decision remains `HOLD_RESEARCH`.
- next:
  run focused strict/exposure audit on the new top survivor and compare it with
  the earlier turnover-residualized momentum-curve survivor.

2026-04-29 incremental survivor focused audit:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_INCREMENTAL_SURVIVOR_AUDIT_2026-04-29.json`.
- targets:
  audited the top incremental replay survivor
  `stockpit-ff-b826a24eb2b1` / `Neg(ZScore(Mom($close,6)))`, plus the next
  cross-axis survivor `stockpit-ff-9c3c7aeb14a9` / amount-ratio residual
  momentum-curve.
- result:
  both retain positive strict IC in train and Qlib forward, but strict daily
  cost-adjusted top/bottom spread remains negative. For
  `stockpit-ff-b826a24eb2b1`, CSV train strict IC `0.031281`, cost-adjusted
  spread `-0.000306`, mean turnover `0.316188`; Qlib forward strict IC
  `0.020801`, cost-adjusted spread `-0.000637`, mean turnover `0.315443`.
  Residualized IC drops materially: CSV `0.015696` (`-0.015585` delta), Qlib
  `0.008432` (`-0.012369` delta). The amount residual momentum-curve target is
  similar: Qlib strict IC `0.016701`, cost-adjusted spread `-0.001031`, Qlib
  residualized IC `0.008901`.
- interpretation:
  incremental replay found a stronger research pocket than the first 500
  replay, but the pocket is not a daily spread edge. The positive evidence is
  concentrated in `5`-day rebalance portfolio shape with lower turnover, while
  daily strict top/bottom spread is still cost-negative. Treat the motif as
  "low-frequency momentum reversal / prior-position / liquidity-curve routing"
  for further search, not as a deployable signal.
- next:
  continue search with the target explicitly shifted from daily IC leaders to
  low-turnover multi-day payoff shape: generate/replay candidates whose
  expected holding period is `5` days or whose formula naturally throttles
  turnover, while keeping A-share timestamp and tradability constraints.

2026-04-29 forward-first stage1 shards 014-015:

- artifacts:
  shard reports
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_014_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_015_2026-04-29.json`;
  shard ledgers
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_014_LEDGER_2026-04-29.json`
  and
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_015_LEDGER_2026-04-29.json`;
  refreshed summary
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_STAGE1_SHARD_SUMMARY_2026-04-29.json`.
- result:
  stage1 total is now `800` candidates over `16` shards, unsupported `0`,
  smoke pass `0`, average `4.461s/candidate`. New shards mainly extend the
  already observed pocket: `prior_close_position_rank`,
  amount/volume momentum-curve, and `momentum_vol_scaled`. Examples:
  `stockpit-ff-553cba01843c` prior-close-position-rank IC `0.027248`,
  Sortino `1.184246`; `stockpit-ff-2a24540c6f3e` amount-ratio x
  momentum-curve IC `0.016252`, Sortino `1.126282`; `stockpit-ff-86844374cc24`
  momentum-vol-scaled IC `0.027837`, Sortino `1.080723`.
- interpretation:
  the search is no longer discovering a radically new edge class with each
  shard; it is thickening the same low-frequency shape. The practical next
  improvement is not more daily-IC screening alone, but a replay-aware stage1
  objective that scores candidates by `5`-day rebalance net/turnover proxies
  while preserving forward-blind selection.
- next:
  implement or emulate a replay-aware shortlist objective on existing shards
  before spending many more shards on the same daily-IC target.

2026-04-29 replay-aware 800 shortlist and replay:

- artifacts:
  replay-aware shortlist
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_800_SHORTLIST_2026-04-29.json`;
  replay report
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_800_PORTFOLIO_REPLAY_2026-04-29.json`.
- setup:
  built a forward-blind shortlist from the existing `800` stage1 candidates,
  excluding both prior replay shortlists. The score used only train-side
  stage1 metrics plus family priors learned from prior replay outcomes, not
  forward labels: `0.45 * family_replay_prior + 4 * positive_ic +
  0.12 * clipped_positive_sortino + 0.10 * hit_ratio - weak_metric_penalty`.
  It selected `24` unreplayed candidates, family-capped across momentum
  rank/zscore, prior-close-position rank/zscore, amount/volume/turnover
  momentum-curve, and momentum-vol-scaled.
- result:
  replay produced `144` primary rows at `20bps`; `108/144` were train-positive,
  and `24` of those were also forward-positive. The best row is
  `stockpit-ff-e4cbb29e7169` / `Neg(CSRank(Mom($close,6)))`, rebalance `5`,
  LS `20bps`: train net `0.000033`, train Sortino `0.058148`, forward net
  `0.001021`, forward Sortino `1.446329`, forward turnover `0.150779`,
  forward max drawdown `-0.025014`, forward positive-day ratio `0.627907`.
  Other positive rows include `Neg(ZScore(Mom($close,10)))`,
  `Neg(CSRank(Mom($close,10)))`, prior-close-position rank/zscore, and
  amount-ratio x momentum-curve.
- interpretation:
  the replay-aware selector is more efficient than pure daily-IC shard
  expansion for finding the current forward-shadow pocket. However, it is
  trained from prior replay family outcomes, so it is a soft routing prior,
  not independent proof. The persistent weakness is still the same: train net
  for the strongest forward rows is very thin, and the evidence concentrates
  in a short `43`-day Qlib forward period.
- next:
  formalize this as a replay-aware soft prior for search routing, then demand
  a stricter proof gate: at least another independent forward period or a
  rolling walk-forward replay where the `5`-day low-turnover pocket remains
  positive after costs and exposure residualization.

2026-04-29 formal replay-aware shortlist selector:

- artifacts:
  implementation in
  `src/our_system_phase2/services/stock_pit_forward_first_search.py`;
  regression test in `tests/test_phase2_v21_runtime.py`;
  formal reproduction shortlist
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_800_SHORTLIST_FORMAL_2026-04-29.json`;
  next unreplayed shortlist
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_NEXT_800_SHORTLIST_2026-04-29.json`.
- implementation:
  added `infer_replay_aware_family_priors` and
  `build_stock_pit_forward_first_replay_aware_shortlist`. The selector consumes
  stage1 shard reports, prior chronological replay reports, and previous
  shortlists. It uses prior replay only as a family-level soft routing prior,
  excludes previously replayed candidate IDs and expressions, then scores
  unreplayed candidates with:
  `0.45*family_prior + 4*positive_ic + 0.12*clipped_positive_sortino +
  0.10*hit_ratio - weak_metric_penalty`.
- important guardrail:
  the selector does not use candidate-level forward labels for candidates being
  selected. It may use already-completed replay outcomes only to infer
  family-level routing priors. This remains `HOLD_RESEARCH`, not promotion
  evidence.
- result:
  the formal reproduction shortlist selected `24` candidates from the existing
  `800` stage1 pool. The next unreplayed shortlist, excluding the 500, 700, and
  replay-aware-800 prior shortlists, also selected `24` candidates. Family
  priors after all prior replays were strongest for `momentum_rank` (`0.783396`),
  `momentum_zscore` (`0.767324`), `amount_ratio_x_momentum_curve` (`0.693258`),
  `prior_close_position_zscore` (`0.679970`), `prior_close_position_rank`
  (`0.655932`), `volume_ratio_x_momentum_curve` (`0.653123`), and
  `turnover_ratio_x_momentum_curve` (`0.633869`).
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "replay_aware_shortlist or forward_first_large_search or parquet_panels"`
  passed: `3 passed, 144 deselected`.
- next:
  run chronological replay on
  `PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_NEXT_800_SHORTLIST_2026-04-29.json`.

2026-04-29 formal replay-aware next shortlist replay and audit:

- artifacts:
  replay report
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_NEXT_800_PORTFOLIO_REPLAY_2026-04-29.json`;
  survivor audit
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_REPLAY_AWARE_NEXT_SURVIVOR_AUDIT_2026-04-29.json`.
- setup:
  replayed the formal next shortlist, excluding the previous `500`, `700`, and
  replay-aware `800` shortlists. The shortlist was built with the new reusable
  replay-aware selector and prior replay family outcomes as soft routing priors
  only. Replay contract remained `after_open`, field-level lags, execution
  `T+1`, top/bottom `20%`, rebalance frequencies `1/3/5`, cost grid
  `10/20/30bps`, and A-share entry tradability.
- replay result:
  `24` candidates x `3` frequencies x `2` modes produced `144` primary rows at
  `20bps`; `101/144` were train-positive, and `29` of those were also
  forward-positive. Best rows again concentrate at rebalance `5`. Top row:
  `stockpit-ff-605c082f96ee`,
  `Neg(ZScore(Div(Sub($open,Delay($close,7)),Delay($close,7))))`, LS `20bps`,
  train net `0.000179`, train Sortino `0.302366`, forward net `0.000695`,
  forward Sortino `0.939561`, forward turnover `0.149186`, forward max drawdown
  `-0.026140`. Momentum rank `9` and turnover/amount residual momentum-curve
  rows also stayed forward-positive.
- audit result:
  audited the top open-gap survivor and a momentum-rank survivor. Both retain
  positive strict IC in train and Qlib forward, but strict daily cost-adjusted
  spread remains negative. For `stockpit-ff-605c082f96ee`, CSV strict IC
  `0.032061`, Qlib strict IC `0.018250`, but cost-adjusted spreads are
  `-0.000360` and `-0.000891`; residualized IC drops to `0.016688` and
  `0.005300`. For `stockpit-ff-22b7293b4fac`, CSV strict IC `0.029535`, Qlib
  strict IC `0.026299`, cost-adjusted spreads `-0.000858` and `-0.000840`;
  residualized IC `0.016007` and `0.013776`.
- interpretation:
  the replay-aware selector now consistently finds the same research pocket
  across multiple unreplayed batches, which is a real search-efficiency gain.
  It is still not commercial proof. The edge candidate is a low-frequency
  5-day rebalance portfolio-shape motif, not a daily top/bottom spread factor.
- next:
  stop using daily strict spread as the primary discovery objective for this
  branch. The next useful engineering move is a dedicated `5`-day replay proof
  gate with rolling/independent forward periods and exposure residualization
  measured on the same rebalance schedule.

2026-04-29 formal 5-day replay proof gate:

- artifacts:
  implementation in
  `src/our_system_phase2/services/stock_pit_forward_first_search.py`;
  regression test in `tests/test_phase2_v21_runtime.py`;
  proof report
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_FIVE_DAY_PROOF_GATE_2026-04-29.json`.
- setup:
  formalized `build_stock_pit_forward_first_five_day_proof_gate`. It aggregates
  existing chronological replay reports and only evaluates the discovered
  branch under rebalance `5`, cost `20bps`, and train-selected forward outcomes.
  It applies simple proof thresholds: forward net at least `0.0005`, forward
  Sortino at least `0.75`, forward max drawdown no worse than `-0.05`, and
  average turnover no more than `0.20`. It also consumes focused audit reports
  as blockers.
- result:
  across the existing replay reports there are `216` five-day rows, `165`
  train-positive rows, `84` train-positive and forward-positive rows, and `22`
  rows passing the proof thresholds. Qualified families include momentum
  zscore/rank, amount/volume/turnover ratio x momentum-curve, open-gap
  zscore/rank, and prior-close-position zscore/rank. Top row remains
  `stockpit-ff-b826a24eb2b1` / `Neg(ZScore(Mom($close,6)))`: forward net
  `0.001021`, forward Sortino `1.446329`, forward turnover `0.150779`, forward
  max drawdown `-0.025014`.
- decision:
  `HOLD_RESEARCH`. The gate found a coherent 5-day pocket, but it explicitly
  blocks promotion for:
  `independent_forward_period_count_below_2`,
  `qualified_rows_have_thin_train_edge`, and
  `focused_audit_reports_contain_strict_or_exposure_blockers`.
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "five_day_proof_gate or replay_aware_shortlist or forward_first_large_search"`
  passed: `3 passed, 145 deselected`.
- next:
  find or construct a second independent forward period / rolling 5-day
  walk-forward replay. Do not spend promotion effort on daily spread proof for
  this branch; the candidate edge is explicitly a 5-day replay pocket.

2026-04-29 predev independent holdout replay for 5-day proof rows:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_FIVE_DAY_PREDEV_HOLDOUT_REPLAY_2026-04-29.json`.
- setup:
  used local predev holdout panel
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_predev_holdout_slice_2026-04-29.parquet`,
  date range `2024-12-02..2025-08-08`; replay evaluation window
  `2025-01-02..2025-08-08`. Replayed the `22` unique expressions that passed
  the five-day proof gate, using the same `after_open`, `T+1`, top/bottom
  `20%`, rebalance `5`, cost `20bps`, and A-share tradability contract.
- result:
  long-short predev holdout is much weaker than Qlib forward: only `5/22`
  expressions are positive. The surviving LS families are momentum zscore/rank
  and one volume-ratio x momentum-curve row. Best LS rows are
  `Neg(ZScore(Mom($close,10)))` and `Neg(CSRank(Mom($close,10)))`, both predev
  net `0.000231`, Sortino `0.379640`, turnover `0.124048`, max drawdown
  `-0.115516`; `Mom($close,9)` variants have predev net `0.000133`; the
  volume-ratio x momentum-curve row has predev net `0.000109`.
  Long-only is positive for `22/22`, with top predev long-only net around
  `0.001789`, but drawdowns are large (`~ -0.20`), so this is not proof of a
  clean market-neutral edge.
- interpretation:
  the independent backward holdout narrows the pocket sharply. The robust-ish
  sub-pocket is short-term momentum reversal around windows `9..10`, plus a
  weaker volume momentum-curve row. Open-gap and prior-close-position rows that
  looked good in Qlib forward do not survive LS predev holdout. This strengthens
  the warning that the prior forward result contains regime and long-only
  exposure.
- decision:
  still `HOLD_RESEARCH`, closer to `FAIL_PROMOTION` than promotion. The next
  useful search should focus on momentum reversal windows `9..10`, add
  market/long-only exposure controls, and demand LS stability across predev,
  validation, and Qlib forward.

2026-04-29 focused momentum reversal tri-period replay:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_5DAY_TRI_PERIOD_2026-04-29.json`.
- setup:
  replayed a focused grid of inverted momentum reversal formulas:
  `Neg(ZScore(Mom($close,w)))` and `Neg(CSRank(Mom($close,w)))`, windows
  `3..18`, under the same `after_open`, `T+1`, rebalance `5`, cost `20bps`,
  top/bottom `20%`, and A-share entry tradability contract. Tested three
  periods: predev holdout `2025-01-02..2025-08-08`, CSV validation
  `2025-10-01..2026-02-04`, and Qlib forward `2026-02-05..2026-04-15`.
- result:
  `10` LS rows are positive in all three periods. The strongest stable window
  is `8`: both zscore and rank forms have predev net `0.000253`, validation net
  `0.000145`, forward net `0.000400`, mean turnover `0.136950`, max drawdowns
  `-0.090491`, `-0.059036`, `-0.036024`. Window `9` is also positive in all
  three periods: predev `0.000133`, validation `0.000220`, forward `0.000677`,
  mean turnover `0.129379`. Window `10` has strong predev and forward but nearly
  zero validation (`0.000004`), so it is weaker than the raw forward result
  suggested.
- interpretation:
  the cleanest current research pocket is not broad open-gap or prior-position;
  it is short-term momentum reversal around windows `8..9`, with modest but
  tri-period positive LS net at 5-day rebalance. This is materially better
  evidence than the earlier single-forward survivor story, but still not
  commercial-grade: net is small, Sortino is modest, and exposure/residual
  audits are still needed on the exact `8..9` formulas.
- next:
 audit the exact window `8..9` momentum reversal formulas under the focused
  strict/exposure tools, then decide whether to build a small ensemble of
  zscore/rank windows `8..9` and test if it improves stability without adding
  turnover.

2026-04-29 focused momentum reversal 8/9 audit and tiny ensemble:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_8_9_AUDIT_ENSEMBLE_2026-04-29.json`.
- setup:
  audited the representative monotonic forms `Neg(ZScore(Mom($close,8)))`
  and `Neg(ZScore(Mom($close,9)))` across predev holdout, CSV validation, and
  Qlib forward. Rank versions are monotonic-equivalent for top/bottom
  portfolio selection, so the audit focused on zscore forms. The checks used
  `after_open` field lags, `T+1`, 20bps cost, A-share entry tradability, and
  the existing strict/exposure tools. Also replayed a tiny equal-rank ensemble
  of windows `8` and `9` at 5-day rebalance.
- strict/exposure result:
  the formulas have positive daily strict IC in all three slices, but strict
  daily cost-adjusted spread remains negative. Window `8` IC/residualized IC:
  predev `0.034593/0.013845`, validation `0.024427/0.009622`, forward
  `0.010057/-0.003922`. Window `9`: predev `0.031482/0.010868`, validation
  `0.029535/0.014622`, forward `0.026299/0.013110`. Residualized IC deltas are
  materially negative in every slice (`~ -0.013` to `-0.021`), so exposure
  dependence remains a real blocker.
- 8/9 ensemble result:
  the tiny ensemble stayed LS-positive across the three 5-day slices: predev
  net `0.000153`, validation net `0.000180`, forward net `0.000615`, with mean
  turnover around `0.13`. Forward Sortino improved to `0.873582`, but predev
  and validation Sortino remained modest (`0.247205`, `0.374407`) and predev
  max drawdown was still `-0.095027`.
- interpretation:
  this is not a dead branch: the 5-day holding effect is more stable than the
  daily strict spread suggests. But the edge is still small and exposure-heavy.
  Treat it as a research pocket, not a commercial candidate. The next useful
  search should keep the 8/9 reversal center while adding interaction variants
  that may reduce exposure dependence: volatility scaling, amount/volume
  crowding normalization, and compact state gates, all under the same A-share
  timestamp/tradability contract.

2026-04-29 momentum reversal interaction variant tri-period search:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_INTERACTION_VARIANTS_TRI_PERIOD_2026-04-29.json`.
- setup:
  replayed `105` compact variants around reversal windows `7..11` across the
  same predev, CSV validation, and Qlib forward slices. Families covered base
  rank/zscore controls, volatility-scaled reversal, cross-sectional residual
  to volatility, amount/volume crowding gates, residuals to amount/volume
  crowding, and open-position gates. All used `after_open` field lags, `T+1`,
  5-day rebalance, 20bps, top/bottom 20%, and A-share entry tradability.
- result:
  `16/105` candidates were LS-positive in all three periods, with no unsupported
  formulas. The best min-net candidates are still the base controls:
  window `8` min net `0.000145`, mean net `0.000266`, turnover `0.136950`;
  window `9` min net `0.000133`, mean net `0.000343`, turnover `0.129379`.
  The only interaction family that came close was
  `cs_residual_to_volatility`: `mrev-resid-stdret-09-20` had nets
  `0.000125/0.000276/0.000597`, mean net `0.000333`, turnover `0.126975`.
- negative evidence:
  direct volatility scaling, amount/volume crowding gates, residuals to
  amount/volume crowding, and open-position gates produced `0` tri-period
  positive rows in this batch. This argues against simply multiplying the
  8/9 reversal by the earlier compact crowding/open-position pockets.
- interpretation:
  the current best explanation is a narrow short-horizon reversal effect with
  partial volatility-state structure, not a broad multi-factor interaction
  surface. The next search should not blindly deepen every interaction family;
  prioritize volatility-residualized reversal around windows `8..10`, test a
  small base+vol-residual ensemble, and only then consider scaling budget.

2026-04-29 momentum reversal base plus volatility-residual ensemble replay:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_VOLRESID_ENSEMBLES_2026-04-29.json`.
- setup:
  replayed `7` small equal-rank ensembles using base reversal windows `8/9`
  and the best volatility-residual variants
  `Neg(CSRank(CSResidual(Mom($close,w),Std($ret,n))))`. Same three slices,
  same `after_open`/`T+1`/5-day/20bps/A-share tradability contract.
- best result:
  `ens_base9_resid9_20` (`Neg(ZScore(Mom($close,9)))` plus
  `Neg(CSRank(CSResidual(Mom($close,9),Std($ret,20))))`) had the strongest
  balance: predev net `0.000190`, validation `0.000216`, Qlib forward
  `0.000704`, mean net `0.000370`, mean turnover `0.128697`, minimum Sortino
  `0.321679`. It improves on the base `8/9` ensemble min net (`0.000153`) and
  mean net (`0.000316`) while keeping similar turnover.
- caveat:
  the best ensemble's worst max drawdown is still `-0.100543`, and the evidence
  is still from focused post-discovery replay rather than an independent long
  forward paper-trade. Decision remains `HOLD_RESEARCH`; do not promote.
- next:
  the useful path is not generic depth. Freeze this as a tiny candidate pocket
  and run a rolling/periodized proof gate plus exposure-neutral portfolio replay
  for `base9`, `resid9_20`, and `base9+resid9_20`. If that holds, then launch a
  larger search biased toward volatility-residualized short reversal rather
  than broad crowding/open-position interactions.

2026-04-29 momentum reversal periodized proof gate:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_PERIODIZED_PROOF_GATE_2026-04-29.json`.
- setup:
  froze three targets: `base9`, `resid9_20`, and `base9+resid9_20`. Replayed
  raw signal, available exposure-residualized signal against
  `amount/volume/close`, and sector-demeaned signal when the slice had a sector
  column. The gate used calendar quarters as the main 3-month cycle and
  non-overlapping 60-trading-day blocks as a secondary period check. Same
  `after_open`, field-lag, `T+1`, 5-day rebalance, 20bps, and A-share entry
  tradability contract.
- result:
  the raw whole-slice effect still survives, but periodization blocks
  promotion. Best by the gate ranking was `resid9_20` raw: slice nets
  predev `0.000125`, validation `0.000276`, Qlib forward `0.000597`; however
  calendar-quarter min net was `-0.000844` and 60-day-block min net was
  `-0.000798`. The previous best ensemble `base9+resid9_20` raw had higher
  whole-slice mean net (`0.000370`) but worse quarter min net (`-0.001237`).
- exposure result:
  exposure-residualizing against `amount/volume/close` improves or preserves
  the Qlib forward slice, but turns predev negative for all three targets
  (`base9 -0.000049`, `resid9_20 -0.000050`, ensemble `-0.000041`). Sector
  demeaning is also unstable: it helps some predev block ratios but makes the
  validation slice negative.
- interpretation:
  this is a real research pocket but it failed the periodized proof gate. The
  issue is not only average edge; it is state dependence. Do not launch a blind
  large-scale continuation from this pocket. The next useful experiment is a
  state-conditioned gate learned only from predev/validation features and then
  tested on Qlib forward, or a fresh search branch that explicitly optimizes
  period-min net instead of whole-slice mean.

2026-04-29 momentum reversal state-gate experiment:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_STATE_GATE_2026-04-29.json`.
- setup:
  learned simple one-feature market-state thresholds on predev plus CSV
  validation only, then froze and tested on Qlib forward. Candidate targets were
  `base9`, `resid9_20`, and `base9+resid9_20`. State features were after-open
  available or prior-day derived: current open-gap mean/breadth/dispersion,
  prior 1-day and 5-day market return/breadth/dispersion, and prior
  amount/volume ratio means. Search evaluated `240` candidate gates.
- best gate:
  for `base9+resid9_20`, trade only when prior market-wide
  `volume_ratio_mean <= 1.2515794`. Training selected `79/225` days and lifted
  train net from baseline `0.000200` to `0.001912`, with train min period net
  `0.001172` and max drawdown `-0.020946`. On Qlib forward it selected `27/43`
  days and lifted net from `0.000704` to `0.002863`, Sortino from `1.067287`
  to `3.789700`, max drawdown from `-0.040989` to `-0.017826`.
- interpretation:
  this is the first strong evidence that the short-reversal pocket is
  state-conditioned rather than uniformly weak. The economic reading is
  plausible: the 9-day reversal plus volatility-residual ensemble works better
  when prior broad market volume is not in an overheated/crowded expansion
  state. However, this is still a post-discovery threshold selected from 240
  gates and only one Qlib forward slice, so the decision remains
  `HOLD_RESEARCH`.
- next:
  freeze this exact gate (`volume_ratio_mean <= 1.2515794`) and run it on an
  additional independent period or a longer rolling forward shadow. If it
  survives, promote the search objective from whole-slice mean to
  `state_gated_period_min_net` and launch a larger search around state-gated
  short reversal.

2026-04-29 state-gated momentum reversal long-only reality check:

- artifact:
  `reports/PHASE2_STOCK_PIT_FORWARD_FIRST_MOMENTUM_REVERSAL_STATE_GATE_LONG_ONLY_2026-04-29.json`.
- setup:
  because shorting is not currently practical, replayed the current best
  `base9+resid9_20` pocket as a long-only top basket, both baseline and frozen
  state-gated (`volume_ratio_mean <= 1.2515794`). Same `after_open`, field-lag,
  `T+1`, 5-day rebalance, 20bps, top 20%, and A-share long-entry tradability
  contract.
- long-only result:
  baseline long-only was positive but drawdown-heavy. Gating improved all three
  slices: predev net `0.002893`, Sortino `2.118467`, max DD `-0.055951`;
  validation net `0.001343`, Sortino `1.417002`, max DD `-0.028755`; Qlib
  forward net `0.001464`, Sortino `0.937600`, max DD `-0.081760`. Forward
  selected `27/43` days.
- comparison:
  the same gate is much stronger in LS shadow (`0.002863` forward net,
  Sortino `3.789700`, max DD `-0.017826`) than in long-only. For near-term
  deployability, treat this as a long-only alpha sleeve or market-state
  selection prior, not a standalone commercial strategy.
- decision:
  still `HOLD_RESEARCH`. Blockers are post-discovery gate selection, no true
  live/frozen independent forward period, and no benchmark excess-return check.

2026-04-29 next large search definition:

- artifact:
  `reports/PHASE2_NEXT_LARGE_SEARCH_LONG_ONLY_STATE_GATED_SPEC_2026-04-29.json`.
- objective:
  next large search should optimize long-only A-share usability first, with LS
  kept as a research shadow. The primary score becomes forward long-only gated
  net after 20-30bps, drawdown, period-min net, selected-day count, and capacity
  proxy. Whole-slice LS mean is demoted.
- frozen reference:
  keep `base9`, `resid9_20`, `base9+resid9_20`, and
  `volume_ratio_mean <= 1.2515794` as a reference prior, not a hard lock and
  not a forward label.
- budget:
  stage0 sanity `300` candidates, stage1 large `5000`, stage2 portfolio
  shortlist `300`, stage3 frozen-gate replay `50`, stage4 independent forward
  shadow `10`. Search space stays broad but biased toward state-gated
  short-reversal, volatility residualization, open-position reversal,
  low-crowding long-only priors, and separate limit-state branches.

2026-04-29 revised next search objective for small-capital accumulation:

- artifact:
  `reports/PHASE2_NEXT_LARGE_SEARCH_SMALL_CAPITAL_ACCUMULATION_SPEC_2026-04-29.json`.
- correction:
  the next search should not be narrowly framed as institutional `long-only`
  factor discovery. Since shorting is not currently practical and the capital
  base is small, the better objective is a `long-or-cash` / long-biased
  compounding system: trade only when state and signal quality justify it,
  tolerate somewhat higher turnover and lower capacity than an institution,
  but keep strict A-share tradability and cost rules.
- implication:
  the current search has only touched a very thin part of the effectively
  unbounded formula/state/portfolio space. The response should not be blind
  unlimited depth in one family; it should be staged active search: broad cheap
  probes for space coverage, novelty archive to avoid duplicates, then adaptive
  budget allocation to basins that pass realistic portfolio gates.
- proposed budget:
  stage0 broad probe `2000` candidates; stage1 adaptive expansion `20000`
  candidates with budget split across promising basins, novel typed formulas,
  state-gate variants, and limit-state specialists; stage2 long/cash portfolio
  replay `1000`; stage3 frozen OOS `100`; stage4 candidate sleeves `10`.
- branch priorities:
  `state_gated_short_reversal`, `limit_state_prediction`,
  `open_auction_and_gap_state`, `crowding_and_liquidity_contraction`,
  `compact_formula_frontier`, and `portfolio_policy_search`.
- scoring:
  primary score is now risk-adjusted small-capital compounding: long/cash net,
  period-min net, drawdown, selected-day sample quality, cost robustness,
  tradability, novelty/low correlation, with LS only as a research shadow.

2026-04-29 small-capital stage0 shard-0 broad probe:

- artifacts:
  `reports/PHASE2_SMALL_CAPITAL_STAGE0_SHARD0_300_LEDGER_2026-04-29.json` and
  `reports/PHASE2_SMALL_CAPITAL_STAGE0_SHARD0_300_LONG_CASH_2026-04-29.json`.
- setup:
  generated `300` forward-first candidates from the existing searcher schedule
  (`31350` candidates in the current parameter slice), using the CSV validation
  file only for natural window inference and parquet panels for evaluation.
  Trained/screened on predev plus CSV validation, then replayed only the top
  `30` on Qlib forward. Small-capital objective: long/cash top 10%, 5-day
  rebalance, `30bps`, `after_open`, `T+1`, A-share long-entry tradability, and
  fixed prior volume gate `volume_ratio_mean <= 1.2515794`. No Qlib forward
  labels were used for train selection.
- runtime:
  `300/300` evaluated, `0` unsupported, top `30` forward replayed. Elapsed
  about `3155s`.
- result:
  shard-0 did not beat the current reference long-only gate (`0.001464` Qlib
  forward net), but it confirmed the same basin. Top forward gated candidates:
  `Neg(ZScore(Mom($close,10)))` gated net `0.001436`, Sortino `0.831470`,
  max DD `-0.087144`; `Neg(ZScore(Mom($close,9)))` gated net `0.001347`,
  Sortino `0.790973`; inverse open-gap windows `10/11` gated nets
  `0.001206/0.001157`. Prior/open-position zscore families were weaker
  (`~0.0003..0.00076`).
- family signal:
  among top-forward shard results, `momentum_zscore` is best
  (`4/6` top30 positive, best `0.001436`), followed by `open_gap_zscore`
  (`3/5` positive, best `0.001206`), then `prior_close_position_zscore` and
  `open_position_zscore`. Rank-only and ratio-interaction families did not
  survive this long/cash shard.
- interpretation:
  this supports continuing the small-capital search, but the next shard should
  not simply repeat the same schedule. Bias the next expansion toward
  zscore-style short reversal and inverse open-gap around windows `8..12`,
  plus state gates and top-N/quantile policy search. Keep a novelty allocation
  because `300/31350` is still only a very small slice of the scheduled space.

2026-04-29 reversal-long feasibility safety filter:

- artifact:
  `reports/PHASE2_SMALL_CAPITAL_REVERSAL_LONG_SAFETY_FILTER_2026-04-29.json`.
- motivation:
  pure inverse momentum/open-gap formulas are not a deployable short thesis in
  the current setup. For small capital without shorting, the question is
  whether the signal can be converted into a feasible `reversal-long` trade:
  buy oversold names only when they are tradable and not obviously still in a
  breakdown state.
- setup:
  tested top stage0 winners `Neg(ZScore(Mom($close,9/10)))`, inverse open-gap
  `10/11`, and a `mom9+mom10` ensemble under long-only filters. Same
  `after_open`, field-lag, `T+1`, 5-day rebalance, `30bps`, and A-share entry
  tradability. Added safety variants: fixed market volume gate
  `volume_ratio_mean <= 1.2515794`, avoid entry limit-down, avoid signal-day
  severe low opens, and top 5% vs top 10%.
- result:
  safety filtering materially improved deployable long/cash behavior. Best
  row was `mom10_reversal_z` with `volume_gate_top5pct_open_gap_gt_minus5`:
  forward net `0.002294`, Sortino `1.282755`, max DD `-0.081750`, min
  all-slice net `0.000697`. The same signal with top5% and no entry
  limit-down gave forward net `0.002143`. The `mom9+mom10` ensemble with the
  same open-gap safety filter gave forward net `0.002132`, Sortino `1.262254`,
  max DD `-0.075452`.
- interpretation:
  the factor should not be described as "pure inverse" for deployment. It is a
  conditional reversal-long sleeve: buy a small top bucket of oversold names
  only under non-overheated market volume and with falling-knife filters.
  This is closer to small-capital accumulation than the previous top10%
  always-reversal version, but it is still post-discovery and must be frozen
  for independent forward validation.
- next:
  update the next large search scoring to prefer `reversal-long` candidates
  that survive top5/topN, no-entry-limit-down, and signal-day open-gap safety
  filters. Keep LS only as a diagnostic shadow.

2026-04-29 small-capital stage0 shard-1a focused reversal-long:

- artifact:
  `reports/PHASE2_SMALL_CAPITAL_STAGE0_SHARD1A_REVERSAL_LONG_SUMMARY_2026-04-29.json`.
- note:
  the first full shard-1 attempt was too large and timed out after two hours
  before writing a complete report. It was stopped and replaced by this smaller
  focused shard: `38` core zscore/ensemble candidates only, summary output
  only, no daily rows.
- setup:
  candidates covered `Mom` and inverse open-gap zscore windows `6..15`,
  open/prior-position zscore windows `8..12`, and compact ensembles around
  windows `8..11`. Train selection used predev plus CSV validation; Qlib
  forward was used only for the top `20`. Filters were top3/top5/top10 with
  fixed market volume gate `volume_ratio_mean <= 1.2515794`, no entry
  limit-down, and signal-day open-gap safety (`>-5%` or `>-3%`).
- result:
  the focused shard improved the current reversal-long reference. Best forward
  was `Neg(ZScore(Mom($close,10)))` with
  `top3_vgate_no_ld_gap_gt_minus5`: forward net `0.002564`, Sortino
  `1.322893`, max DD `-0.075090`, cum return `0.074585` over `30` active
  forward days. Other strong rows: `Mom(9,10)` ensemble `0.002277`,
  inverse gap `11` with top5/gap>-3 `0.002235`, `Mom(9,10,11)` ensemble
  `0.002205`, and `Mom(9)` `0.002120`.
- interpretation:
  this reinforces that the useful deployable branch is not generic inverse
  ranking but a concentrated, state-gated, falling-knife-filtered
  reversal-long sleeve. The next action should freeze the best filter policy
  (`top3/top5`, no entry limit-down, signal open-gap safety, volume gate) and
  run an independent/frozen forward check or a non-overlapping rolling replay.

2026-04-29 reversal-long portfolio policy grid:

- artifact:
  `reports/PHASE2_SMALL_CAPITAL_REVERSAL_LONG_POLICY_GRID_2026-04-29.json`.
- setup:
  tested whether the mediocre feel was caused by using the wrong portfolio
  policy rather than the wrong formula. Grid searched `24` reversal-long
  targets across `96` policies: rebalance `1/2/3/5`, top `1/2/3/5%`, cost
  `30/50bps`, and signal open-gap safety. Policy was selected on predev plus
  CSV validation only, then replayed frozen on Qlib forward.
- result:
  policy-grid selection did not beat the hand-inspected shard-1a safety
  policy. Best Qlib forward row was inverse gap `11` with
  `reb5_top2_cost30_gapnone`: net `0.002061`, Sortino `0.989735`, max DD
  `-0.086132`. `Mom(9,10)` ensemble with `reb5_top2_cost30_gapnone` had net
  `0.001988`, Sortino `1.171629`, max DD `-0.076144`. Several train-favored
  top1/rebalance2 policies failed badly forward.
- interpretation:
  more aggressive portfolio-policy search is not the next best lever. The
  current best remains `Mom10` reversal-long with `top3`, fixed volume gate,
  no entry limit-down, and signal open-gap `>-5%` from shard-1a (`0.002564`
  forward net, Sortino `1.322893`). Freeze that policy for an independent
  check instead of continuing to tune policy on the same forward slice.

2026-04-30 24h broad-space search launch plan:

- artifact:
  `reports/PHASE2_24H_BROAD_SPACE_SEARCH_PLAN_2026-04-30.md` and
  `reports/PHASE2_24H_BROAD_SPACE_SEARCH_OBJECTIVE_2026-04-30.json`.
- objective:
  start a minimum 24h Phase2 generation run in less-explored spaces instead
  of continuing to tune the current `Mom10` reversal-long basin. Keep the
  reversal-long result as a benchmark only.
- run target:
  `runtime/next_stage_artifacts/phase2-24h-broad-space-search-20260430`.
  The runner writes `overnight_manifest.json`, `heartbeat.json`, per-cycle
  logs, and honors a `STOP` file in that directory.
- search bias:
  move budget toward `novelty_frontier`, `uncertainty_frontier`, and
  `bridge_frontier`; watch open/liquidity/turnover/vwap/volatility transition
  motifs; demote pure score-frontier chasing and repeated policy tuning
  without new formula behavior.
- audit status:
  this is still discovery and remains `HOLD_RESEARCH`. Any winner must later
  pass A-share timestamp, T+1, price-limit, cost, turnover, and frozen-window
  replay checks before it can be treated as real edge.

2026-04-30 24h broad-space search actual launch:

- first attempt:
  `runtime/next_stage_artifacts/phase2-24h-broad-space-search-20260430`.
  It was stopped by `STOP` after `13` failed cycles because the old
  continuation root from the prior overnight manifest did not contain
  `archive_state.json`. The failed evidence was retained.
- active run:
  `runtime/next_stage_artifacts/phase2-24h-broad-space-search-20260430-cold`.
  It was relaunched without `--initial-previous-run-root`, using the same
  broad-space objective, `24` minimum runtime hours, `20000` max cycles,
  `flow_length=3`, `rounds=64`, and `per_lane_budget=12`.
- process:
  active runner process observed as PID `3636`; generation subprocess observed
  under the run root. The first cycle is heavier than the previous short
  overnight cycles, so the heartbeat updates only after a cycle completes.

2026-04-30 landing acceleration patch:

- issue:
  the active 24h cold run proved that broad search can generate real internal
  artifacts, but `flow_length=3` plus full artifact writing made one outer
  cycle run for many hours before manifest checkpoint. The largest observed
  file was a `round_report.json` around `1.2GB`; `candidate_ledger.json` also
  grew large.
- action:
  added an optional `artifact_profile=compact` path to the Phase2 prototype,
  generation runtime, and overnight runner. Default remains `full`, so the
  existing full-audit behavior is preserved.
- compact behavior:
  keep efficiency-critical fields, archive state, retained records, round
  summaries, and generation reports; omit full `round_diagnostics` from
  `round_report.json`; write a retained-only compact candidate ledger. Full
  profile remains required for discarded-space probe runs.
- smoke:
  `python -m our_system_phase2.runtime.generation_run --flow-length 1 --rounds 1 --per-lane-budget 1 --artifact-profile compact`
  passed with compact artifacts. The smoke `round_report.json` was about
  `19KB` and `candidate_ledger.json` about `24KB`.
- next:
  stop the current heavy runner at its next safe cycle boundary, then launch
  compact checkpoint search with `flow_length=1` so each outer cycle lands a
  manifest quickly.

2026-04-30 AlphaGPT and acceleration skill review:

- artifact:
  `reports/PHASE2_ALPHAGPT_ACCELERATION_SKILL_REVIEW_2026-04-30.md`.
- position:
  current Phase2 is not a full RL alpha generator; it is quality-diversity /
  MAP-Elites-style search with frontier routing, surrogate funneling, archive
  continuation, and bandit-like budget allocation. The stronger claim is search
  control and A-share replay discipline, not "faster RL already".
- skill set:
  collected backtest/evaluator acceleration skills (`backtest-expert`,
  `vectorbt_sanity_check`, `quant_backtest_bias_audit`,
  `experiment_budget_and_reproducibility`, data-quality,
  feature-engineering, transaction-cost, walk-forward/overfit/Monte Carlo)
  and RL/search acceleration skills (`reinforcement-learning-trading`,
  `dl_training_diagnostics`, alpha review/candidate/edge orchestration).
- engineering action:
  added and tested a compact artifact regression test:
  `pytest tests/test_phase2_v21_runtime.py -k compact_artifact_profile -q`
  passed with `1 passed, 148 deselected`.

2026-04-30 real replay evaluator duplicate-expression acceleration:

- issue:
  large candidate ledgers can contain repeated expressions under different
  candidate ids / metadata. The evaluator already reused expression Series,
  but still reran the full validation report path for duplicate expressions.
- action:
  added a report-level cache inside `batch_validate_candidate_ledger`, keyed by
  expression plus validation contract (`horizon`, execution lag, signal clock,
  feature lag, quantile, and evaluation date bounds). Duplicate expressions now
  preserve their own candidate metadata while reusing the heavy replay report.
- telemetry:
  batch reports now include `unique_validated_expression_count` and
  `validation_report_cache_hit_count`.
- smoke:
  `pytest tests/test_phase2_v21_runtime.py -k "duplicate_expression_reports or scores_retained_ledger_records or compact_artifact_profile" -q`
  passed with `3 passed, 147 deselected`.
- process note:
  the original full-artifact 24h cold runner was still active with four Python
  processes at last check, and the compact relay was still waiting for its safe
  boundary before launching.

2026-04-30 compact relay launch:

- old runner decision:
  the full-artifact cold runner had a `STOP` file written at `09:08`, no
  manifest/heartbeat movement after startup, no directory update after the
  second internal flow landed at `08:42`, and the active generation child showed
  zero CPU delta over a 10-second check. It was terminated to unblock the
  compact relay.
- compact relay:
  the waiting launcher started the compact runner at `09:32`, using
  `phase2-5998bb450a` as `--initial-previous-run-root`.
- compact command shape:
  `--flow-length 1 --rounds 32 --per-lane-budget 12 --artifact-profile compact`
  with the same broad-space feedback objective and 24h minimum runtime target.
- next monitor:
  verify `phase2-24h-broad-space-search-20260430-compact` lands `cycle_001`
  artifacts and updates `overnight_manifest.json` without recreating giant
  `round_report.json` files.

2026-04-30 future long-run heartbeat hardening:

- action:
  updated the overnight runner script so future launches stream generation
  stdout/stderr directly to per-cycle logs and refresh `heartbeat.json` while
  the generation child is still running.
- purpose:
  avoid long black-box intervals during multi-hour cycles and reduce the risk
  of subprocess stdout/stderr capture becoming an invisible bottleneck.
- verification:
  `python -m py_compile runtime/next_stage_artifacts/phase2-overnight-long-search-20260429/run_overnight_phase2_search.py`
  passed.
- scope note:
  the already-running compact relay loaded the old script before this patch, so
  this hardening applies to the next runner launch rather than the current
  active process.

2026-04-30 cold-run retained candidate quick replay:

- source:
  `phase2-24h-broad-space-search-20260430-cold/cycle_001/phase2-flow-234d31f317/phase2-5998bb450a/candidate_ledger.json`.
- ledger shape:
  `2398` records, `951` retained cumulative records. Retained lanes were
  dominated by non-score search (`bridge_frontier=400`,
  `uncertainty_frontier=241`, `novelty_frontier=210`, `score_frontier=100`).
- quick A-share replay:
  first `80` retained candidates, `after_open`, `T+1`, recent single-quarter
  screen (`2026-01-01` to `2026-02-04`) produced no passed smoke candidates,
  but surfaced `v2cand-01e53be39562` for exact recheck.
- exact recent 4-quarter replay:
  `v2cand-01e53be39562` had mean rank IC `0.020549`, Sortino `2.201842`,
  `4` windows, and no smoke flags over `2025-04-01` to `2026-02-04`.
- full-history caution:
  the same candidate was not full-history stable: full-history quarterly mean
  rank IC was `-0.003035` across `83` windows, with strong positive pockets
  such as `2024Q3` and `2026Q1` but also negative windows. Treat as
  regime-conditional research, not commercial proof.
- small-capital long-only check:
  top `5%` long-only, daily rebalance, `after_open` signal clock, `T+1`
  execution, limit-up/limit-down tradability masks available from
  `rt_change_pct`, `207` trading days. Raw candidate long mean was `0.2445%`
  per day vs tradable-universe equal-weight `0.1811%`; raw excess was
  `0.0633%` per day. After `20bps` turnover cost, excess mean fell to
  `0.0232%` per day with excess Sortino `0.481287`; after `50bps` excess
  turned negative. This is a useful lead, but not yet private-fund-grade proof.

2026-04-30 long-only replay metrics:

- action:
  added long-only metrics to `validate_expression_on_loaded_panel` and
  `batch_validate_candidate_ledger`: per-window `mean_long_return` and
  `long_sortino`, plus summary `mean_window_long_return` and
  `mean_window_long_sortino`.
- reason:
  near-term deployment is long-only/small-capital, so rank IC and long-short
  spread alone can overstate candidates that only work through the short leg.
- smoke:
  `pytest tests/test_phase2_v21_runtime.py -k "scores_retained_ledger_records or duplicate_expression_reports or filters_limit_up_down" -q`
  passed with `3 passed, 147 deselected`.

2026-04-30 continuation speed diagnosis:

- stalled attempts:
  full-archive compact continuation from `phase2-5998bb450a` stalled before
  landing a successful cycle. A distilled attempt with `max_continuation_seeds`
  also timed out before progress markers were added.
- diagnosis:
  the initial seed distillation selected a bridge-frontier parent expression
  with `1,141,933` characters. That is pathological expression bloat, not
  useful "infinite space"; it makes variation/crossover impractical.
- fix:
  added optional continuation seed distillation plus a hard exclusion for
  pathological seed expressions above `2000` characters when enough alternative
  seeds exist. The filter only controls inherited parent seeds and does not
  narrow the generator's formula space.
- observability:
  added `generation_launch_progress.json` and `prototype_progress.json` markers
  for future long runs.
- smoke:
  after filtering pathological seed parents, `rounds=1`,
  `per_lane_budget=2`, `max_continuation_seeds=20`, compact continuation from
  `phase2-5998bb450a` completed within the 120-second probe. It generated `7`,
  retained `7`, created `7` new behavior cells, and retained non-score ratio
  was `0.857143`.

2026-04-30 distilled compact 24h runner:

- launch:
  started
  `runtime/next_stage_artifacts/phase2-24h-broad-space-search-20260430-distilled-compact`
  with `flow_length=1`, `rounds=16`, `per_lane_budget=8`,
  `artifact_profile=compact`, `max_continuation_seeds=160`, and initial root
  `phase2-5998bb450a`.
- first cycle:
  `cycle_001/phase2-e61320f879` completed successfully in `120.021` seconds.
  It generated `343` candidates, retained `195`, grew archive by `141`, created
  `176` new behavior cells, and non-score retained ratio was `0.897436`.
- monitor:
  runner heartbeat moved to `cycle_index=2`; progress showed cycle 2 inside
  round 9 bridge lane shortly after launch. This is the first healthy long-run
  checkpoint after the full-archive stall.

2026-04-30 automated long-only replay shortlist:

- issue:
  generation cycles were landing useful search efficiency metrics, but not an
  automatic A-share long-only replay shortlist. This left too much manual work
  between "retained by search" and "worth strict replay".
- action:
  added `our_system_phase2.services.auto_long_only_replay`, which selects a
  diverse, non-pathological retained subset, runs recent 4-quarter A-share
  `after_open` / `T+1` / top-5% long-only replay, and writes
  `auto_long_only_replay_report.json` under the run root. It always stays
  `HOLD_RESEARCH` and does not allow commercial edge claims.
- runner integration:
  the overnight runner now accepts `--auto-replay-top-k`; future launches can
  run the auto replay after each successful cycle and store the replay summary
  in the manifest.
- current run sidecar:
  because the active 24h runner was launched before this hook existed, a
  sidecar was started from
  `phase2-24h-broad-space-search-20260430-distilled-compact/run_auto_long_only_replay_sidecar.ps1`
  as PID `33100`. It scans completed cycle roots every `300` seconds and fills
  missing auto replay reports with `max_candidates=24`.
- smoke:
  cycle 14 auto replay evaluated `24` selected candidates, had `0`
  unsupported, found `3` `WATCHLIST_LONG_ONLY` candidates and `0`
  `LONG_ONLY_REVIEW` candidates. The best was `v2cand-ab8afeeaaee0` with
 recent-4Q mean long return `0.002816`, long Sortino `2.678541`, and rank IC
 `0.005899`, so it remained watchlist rather than promotion.

2026-04-30 generator/search algorithm upgrade:

- pivot:
  after the automation work, shifted back to the search algorithm itself:
  improve candidate generation quality rather than merely running more loops.
- action:
  added a lightweight generator hygiene layer in the existing Phase2 variation
  core. It canonicalizes equivalent formula spelling, collapses redundant
  idempotent wrappers such as nested `CSRank/Abs/Sign/ZScore`, measures formula
  complexity, skips pathological archive skeleton sources, and projects
  oversized parents to compact field/interaction anchors before variation.
- search-space note:
  this is not a fixed operator/window whitelist. Natural parameters and normal
  AST depth remain open; the filter only blocks pathological expression bloat
  such as repeated wrapper towers and million-character inherited parents that
  waste evaluation budget.
- runtime integration:
  target-aware pre-screen now applies the same canonicalization, dedup, and
  pathological-expression skip before spending surrogate/IC scoring budget.
- smoke:
  `pytest tests/test_phase2_v21_runtime.py -q -k "generator_hygiene or single_step_variation_projects or archive_synthesis_ignores or target_aware_pre_screen or score_lane_candidate_pool or phase2_native_ast_expansion"`
  passed with `16 passed, 140 deselected`.
- generation smoke:
  compact continuation smoke `phase2-b8afdf5aa8` from `phase2-5998bb450a`
  completed `rounds=1`, `per_lane_budget=2`, `max_continuation_seeds=20`.
 It generated `7`, retained `7`, created `7` new behavior cells, and kept
  max expression length at `327` chars across the compact ledger.
- next target:
  use the next large search to compare generated/retained yield, hygiene skip
  count, formula length distribution, and long-only replay leads against the
  current active distilled compact runner.

2026-04-30 local search memory for generator/RL learning:

- issue:
  candidate ledgers recorded per-run results but did not provide a reusable
  search-space memory. This allowed continuation runs to rediscover exact
  formulas and gave future agent/RL policy training no clean production-rule
  outcome table.
- action:
  added `our_system_phase2.services.search_memory`. Each generation/prototype
  run now writes `search_memory.json` with canonical expression keys,
  structural skeleton keys, production-rule keys, duplicate skip events, and a
  local reward proxy for generator-policy learning.
- duplicate policy:
  continuation runs inherit `search_memory.json` when present, otherwise they
  bootstrap memory from the previous run's `candidate_ledger.json`. This is
  chain-local memory, not a global market lock, so the core remains reusable for
  A-share and future US-stock runs.
- reward policy:
  reward is explicitly `local_generator_training_proxy_not_tradable_edge_claim`.
  It combines retained status, novelty, full-evaluation reach, IC proxy, OOS
  stability, coverage, real replay feedback when available, and formula
  complexity penalty. Notes record AlphaGPT/CFG/MAP-Elites-inspired design
  choices without importing competitor code.
- runtime integration:
  the evaluation loop skips exact canonical duplicates before evaluator spend
  and records each evaluated candidate's source mode, frontier lane, production
  rule, complexity, archive cell, and reward proxy.
- smoke:
  `phase2-4f93c8db04` continued from generator-hygiene smoke and wrote
  `search_memory.json`. It inherited the previous compact ledger, recorded
  `29` memory records, `29` expression keys, `29` skeleton keys, and skipped
  `4` duplicate proposed expressions before evaluation. A second chain smoke
 `phase2-55a18bd225` confirmed dedicated schema
  `phase2-v2_1-search-memory-v1`, inherited prior memory, recorded `30`
  expression/skeleton keys, skipped `10` duplicates, and evaluated only `1`
  new generated candidate.
- tests:
  local search memory unit coverage plus continuation smoke path passed under
  `pytest tests/test_phase2_v21_runtime.py -q -k "local_search_memory or generator_hygiene or generation_runtime_supports_continuation"`.

2026-04-30 Sortino-aware replay reward memory:

- issue:
  the first local search memory reward was still mostly synthetic/search-proxy
  based. For small-capital long-only search, this underweights the metric that
  matters most for deployment triage: realized long-only Sortino after the
  A-share signal/execution/tradability protocol.
- action:
  added replay reward enrichment to `search_memory.py`. Auto long-only replay
  now writes back into `search_memory.json` when it runs in the same run root.
  Continuation memory also automatically ingests a previous run's
  `auto_long_only_replay_report.json` when present.
- reward policy:
  kept reward transparent rather than training a reward model. The replay
  component includes auto long-only decision, mean long return, long-only
  Sortino, rank IC, tradability availability, and smoke-flag penalty. It is
  recorded as
  `transparent_sortino_long_only_component_no_reward_model_training`.
- smoke:
  running auto replay with `max_candidates=4` on `phase2-55a18bd225` enriched
  `4` memory records and wrote the replay path under `replay_enrichment_paths`.
  In this tiny smoke all four replayed candidates had no long-only metrics and
  were penalized, which is the intended behavior before scaling.
- tests:
  `pytest tests/test_phase2_v21_runtime.py -q -k "local_search_memory or auto_long_only_replay or generation_runtime_supports_continuation"`
  passed with `4 passed, 154 deselected`.
- next search readiness:
  the next large run should start from a run root that has both
  `search_memory.json` and, where available, `auto_long_only_replay_report.json`,
  so the generator avoids duplicates and future policy learning receives
  Sortino-aware reward traces.

2026-04-30 next large search readiness:

- objective file:
  added
  `reports/PHASE2_NEXT_SORTINO_MEMORY_SEARCH_OBJECTIVE_2026-04-30.json`.
  It defines the next broad search as small-capital A-share long-only discovery
  with local search memory, canonical duplicate skipping, transparent
  Sortino-aware replay reward, and no trained reward model.
- suggested parameters:
  `min_runtime_hours=24`, `flow_length=1`, `rounds=20`,
  `per_lane_budget=10`, `artifact_profile=compact`,
  `max_continuation_seeds=220`, `auto_replay_top_k=32`.
- runner status:
  the already-running distilled compact runner remained active. From cycle 35
  onward, completed cycles began writing `search_memory.json`, so the safest
  launch point for the next large run is the latest completed cycle with
  `search_memory.json` after the current runner reaches a clean checkpoint.
- launch discipline:
  do not start another 24h runner on top of the active one unless compute is
  intentionally allocated; use the latest completed memory-bearing cycle as
  `--initial-previous-run-root`.

2026-04-30 distilled runner stopped at checkpoint:

- reason:
  the active distilled compact runner slowed sharply after memory-bearing
  cycles began. Cycle 35/36/37 took roughly `305s`, `315s`, and `340s`, then
  cycle 38 stalled in `round 15 / bridge_frontier` with near-zero child CPU.
- action:
  wrote the runner `STOP` file, then terminated the stalled cycle-38 generation
  child after preserving the latest complete checkpoint. The runner heartbeat
  moved to `stopped_by_stop_file`.
- final checkpoint:
  `runtime/next_stage_artifacts/phase2-24h-broad-space-search-20260430-distilled-compact/cycle_037/phase2-d2eec358c0`.
- checkpoint summary:
  cycle 37 generated `39`, retained `30`, created `27` new behavior cells,
  retained yield `0.769231`, non-score retained ratio `1.0`, and wrote
  `search_memory.json` with `539` expression keys, `558` memory records, and
  `656` duplicate skips.
- stopped extras:
  stopped the auto long-only replay sidecar and its orphan replay child to keep
  the machine free for the next controlled search.
- next:
  use the cycle-37 root as the next continuation root unless a later manually
  audited checkpoint is selected.

2026-04-30 crossover hot-path bounded:

- issue:
  the first Sortino-memory pilot was abandoned because cycle 1 was still running
  after roughly `18+` minutes. The main hot path was behavior-guided crossover:
  complex parent expressions could create a full subexpression Cartesian product,
  so one crossover event could spend too much time before producing a candidate.
- action:
  bounded crossover subtree sampling to at most `8 x 8` candidate replacement
  pairs while preserving field atoms plus high-value multi-field/operator
  subtrees. This is a compute-budget bound, not a fixed parameter/window
  whitelist, so the generator still searches open formula structures.
- smoke:
  compact continuation smoke `phase2-b0a15e5a75` from cycle-37 completed
  `rounds=2`, `per_lane_budget=2`, `max_continuation_seeds=40`.
  It generated `5`, retained `5`, created `5` new behavior cells, retained
  yield `1.0`, and wrote `search_memory.json` with `544` expression keys,
  `563` records, and `209` duplicate skips in the inherited chain.
- crossover audit:
  all smoke crossover events recorded `bounded_subtree_sampling=true`.
  Observed evaluated subtree-pair counts were `34`, `8`, `1`, and `25`, safely
  below the `64` maximum.
- next:
  after tests pass, use either the cycle-37 root or the bounded smoke root as the
  next continuation root. Prefer a short controlled run first, then scale only if
  first-cycle wall time is acceptable.

2026-04-30 bounded controlled scale check:

- run:
  continued from bounded smoke root with
  `rounds=6`, `per_lane_budget=4`, `max_continuation_seeds=80`,
  artifact root
  `runtime/next_stage_artifacts/phase2-next-bounded-controlled-20260430/phase2-6c65298146`.
- wall time:
  completed in `142s`, so the previous stalled-pilot hot path is no longer
  blocking at this scale.
- generation summary:
  generated `28`, retained `25`, created `23` new behavior cells, retained yield
  `0.892857`, non-score retained ratio `0.64`, retained OOS IC mean `0.26468`,
  and lane-yield guard allowed scaling.
- crossover audit:
  `15` crossover events, all bounded, max evaluated subtree pairs `48`, average
  `22.2`.
- memory:
  wrote `search_memory.json` with `572` expression keys, `591` records, and
  replay enrichment support. Exact duplicate skipping remains active before
  evaluator spend.
- auto long-only replay:
  replayed `8` selected retained candidates over `4` recent quarter windows with
  after-open signal clock, T+1 execution, `feature_lag_days=0`, and entry
  limit-up/down/suspension masks. Result: `0` LONG_ONLY_REVIEW, `1`
  WATCHLIST_LONG_ONLY. Top candidate `v2cand-bf1a9e58bf89` had mean long return
  `0.003213`, long Sortino `3.363515`, rank IC `0.002463`.
- interpretation:
  the controlled run proves the generator is usable again and that replay memory
  is being updated, but it does not prove commercial-grade edge. The current top
  long-only signal is a watchlist seed: return/Sortino are interesting, IC is too
  small for a claim.
- next:
  launch the next broader search from
  `phase2-6c65298146`, with bounded crossover enabled, local search memory
  inherited, and periodic auto long-only replay. Keep the first large cycle under
  observation before letting it run unattended.

2026-04-30 bounded broad search launched:

- runner:
  started background process PID `16540` using the existing long-runner script,
  not a new bespoke search file.
- output root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-bounded`.
- starting root:
  `runtime/next_stage_artifacts/phase2-next-bounded-controlled-20260430/phase2-6c65298146`.
- parameters:
  `min_runtime_hours=24`, `flow_length=1`, `rounds=20`,
  `per_lane_budget=10`, `artifact_profile=compact`,
  `max_continuation_seeds=220`, `auto_replay_top_k=16`.
- live files:
  heartbeat at `heartbeat.json`, manifest at `overnight_manifest.json`, stop file
  path `STOP`.
- launch check:
  manifest status was `running`, heartbeat status was `running`, and
  `cycle_001` had been created.

2026-04-30 bounded broad search stopped for memory saturation:

- runner:
  wrote `STOP` and let the bounded broad runner finish cleanly at cycle `003`.
  Final status `stopped_by_stop_file`; final root
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-bounded/cycle_003/phase2-32c5a28b63`.
- cycle summary:
  cycle 1 generated `299`, retained `171`, new cells `152`, watchlist `3`;
  cycle 2 generated `85`, retained `39`, new cells `21`, watchlist `3`;
  cycle 3 generated only `8`, retained `6`, new cells `4`, watchlist `3`.
- diagnosis:
  cycle 3 was not stuck in crossover. Generation completed; auto replay then
  ran successfully. The real issue was local search memory saturation:
  `duplicate_skip_count=954` and only `8` generated candidates over `20` rounds.
  Existing saturation logic only used novelty-lane min distance, so zero/low
  generation caused by duplicate skips did not trigger from-scratch escape.
- fix:
  added `memory_duplicate_saturation(generated_count, duplicate_skip_count,
  per_lane_budget)`. Duplicate-heavy or zero-generation rounds now advance the
  saturation counter and can trigger archive-aware from-scratch synthesis.
  Also fixed previous-run search memory replay ingestion when a memory file
  already exists.
- first smoke:
  `phase2-faa1e45235` from the cycle-3 root with `rounds=5`,
  `per_lane_budget=4`, `max_continuation_seeds=80` completed in `24s`.
  It triggered from-scratch on round 3 and produced `18` generated candidates,
  `15` retained candidates, `12` new behavior cells, retained yield `0.833333`,
  `14` from-scratch generated candidates, and lane-yield guard `scaling_allowed`.
- interpretation:
  local memory is doing its job by preventing repeated formulas, but the
  generator needed a real escape hatch once memory made normal variation
  repetitive. This preserves the broad-space requirement better than simply
  disabling duplicate memory.
- next:
  relaunch broad search from
  `runtime/next_stage_artifacts/phase2-memory-saturation-escape-smoke3-20260430/phase2-eb831d10ca`
  after tests and commit.

2026-04-30 escape broad search relaunched:

- runner:
  started background process PID `17804` using the existing long-runner script.
- output root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-escape`.
- starting root:
  `runtime/next_stage_artifacts/phase2-memory-saturation-escape-smoke3-20260430/phase2-eb831d10ca`.
- parameters:
  `min_runtime_hours=24`, `flow_length=1`, `rounds=20`,
  `per_lane_budget=10`, `artifact_profile=compact`,
  `max_continuation_seeds=220`, `auto_replay_top_k=16`.
- launch check:
  manifest status `running`, heartbeat status `running`, and `cycle_001`
  created.
- stop file:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-escape/STOP`.

2026-04-30 escape broad search cycle-1 review:

- clarification:
  the earlier "memory lock" wording means search degeneration, not a program
  deadlock. Local search memory was correctly rejecting repeated formulas; the
  missing piece was an escape path when duplicate rejection made useful
  generation collapse. After the escape patch, memory still prevents repeats but
  duplicate-heavy rounds can route into archive-aware from-scratch synthesis.
- cycle 1:
  `phase2-cc7b518ab1` completed generation in `255.986s`.
  It generated `191`, retained `120`, created `113` new behavior cells, retained
  yield `0.628272`, non-score retained ratio `0.833333`, and generated `32`
  from-scratch candidates. This confirms the current runner is not stuck in
  memory saturation.
- replay:
  auto long-only replay evaluated `16` candidates in `105.217s` and produced
  `1` LONG_ONLY_REVIEW plus `2` WATCHLIST_LONG_ONLY.
- top review candidate:
  `v2cand-9c525090b79f`, source `operator_aware_bridge_pool`,
  lane `bridge_frontier`, archive cell
  `high_momentum|high_size|transition|high_vol|trend`.
  Recent 4-quarter replay: mean rank IC `0.017194`, mean long return `0.00412`,
  long Sortino `5.864887`, positive rank IC ratio `0.75`, tradability filters
  available, no smoke flags. Window detail: 2025Q2/Q3/Q4 positive IC, 2026Q1
  negative IC but positive long return.
- interpretation:
  this is the first candidate in the current memory-aware search that deserves
  strict follow-up review. It is still `HOLD_RESEARCH`, not a commercial edge
  claim, because it needs independent PIT validation, turnover/cost/capacity,
  and robustness checks beyond the recent-quarter replay.
- runner:
  cycle 2 had already reached round 20, so the relaunched broad search is
  progressing normally after the memory-saturation escape patch.

2026-04-30 auto replay fresh-candidate preference:

- issue:
  cycle 2 replay again selected the cycle-1 top candidate
  `v2cand-9c525090b79f`. That is not wrong for ranking, but it wastes replay
  budget during long continuation runs because the same already enriched
  candidate can be revalidated every cycle.
- action:
  auto long-only replay now reads `search_memory.json` and prefers candidates
  without `real_replay_enriched=true`. Already replayed candidates remain
  eligible only as fallback when there are too few fresh candidates to fill
  `max_candidates`.
- tests:
  `pytest tests/test_phase2_v21_runtime.py -q -k "auto_long_only_replay_selection or local_search_memory"`
  passed with `4 passed, 157 deselected`.
- effect:
  future replay cycles should spend more budget discovering new long-only
  candidates instead of repeatedly confirming the same top review seed.

2026-04-30 escape broad search cycle-2/3 review:

- cycle 2:
  completed generation in `220.037s`, generated `103`, retained `81`, created
  `72` new behavior cells, retained yield `0.786408`. Replay still selected the
  cycle-1 top candidate because the fresh-replay patch was committed after the
  cycle-2 replay process had already started.
- cycle 3:
  completed generation in `230.032s`, generated `71`, retained `51`, created
  `41` new behavior cells, retained yield `0.71831`. Replay completed in
  `99.927s` and produced `1` LONG_ONLY_REVIEW plus `3` WATCHLIST_LONG_ONLY.
- fresh replay effect:
  cycle-3 top changed to `v2cand-f99be807d45b`, so replay budget is now finding
  new review seeds rather than only repeating `v2cand-9c525090b79f`.
- new review candidate:
  `v2cand-f99be807d45b`, source `variation`, lane `score_frontier`, archive cell
  `high_momentum|high_size|transition|high_vol|trend`.
  Recent 4-quarter replay: mean rank IC `0.015224`, mean long return `0.00178`,
  long Sortino `2.185115`, positive rank IC ratio `0.75`, no smoke flags.
  It is structurally close to the cycle-1 review candidate, replacing the
  `$vwap` momentum leg with `$amtm`; this looks like local neighborhood
  exploitation around a promising relation structure, not exact duplicate
  replay.
- runner:
  cycle 4 started normally from cycle 3.

2026-04-30 escape broad search cycle-4/5/6 and deeper escape patch:

- cycle 4:
  `phase2-8a60d0f143` generated `26`, retained `22`, created `17`
  new behavior cells, retained yield `0.846154`. Replay produced no
  LONG_ONLY_REVIEW and `2` WATCHLIST_LONG_ONLY. Top watch candidate
  `v2cand-d879e73e10b3`: mean long return `0.001851`, long Sortino
  `1.769346`, mean rank IC `0.008892`.
- cycle 5:
  `phase2-8a84bc6816` generated `21`, retained `14`, created `8`
  new cells, retained yield `0.666667`. Replay again produced no review and
  `2` watchlist names. Top watch candidate `v2cand-a4068d4515ff`: mean long
  return `0.001855`, long Sortino `1.894773`, mean rank IC `0.002791`.
  Round report showed `duplicate_skip_count=305` and only
  `generated_from_scratch_count=1`, so the existing escape path was still too
  local after memory saturation.
- cycle 6:
  `phase2-79573c9540` generated `0`, retained `0`, and created `0`
  new cells. Replay had no review/watchlist candidates; the top weak
  long-only candidate was `v2cand-749b28d0fdc0` with mean long return
  `0.002976`, long Sortino `3.025592`, and mean rank IC `-0.001544`.
  This was a search-generation failure, not a replay/computation failure.
- stop:
  the escape runner was stopped cleanly with STOP reason
  `stop_after_current_cycle_for_deeper_memory_escape_upgrade` after cycle 6.
- deeper escape patch:
  added seeded `generate_distant_axis_recompositions`, which recombines
  momentum/size/regime/volatility/style axes with seed-derived natural windows
  before the normal candidate sorting and duplicate memory filters. This keeps
  duplicate memory intact while giving saturated runs a farther jump than local
  operator variation.
- smoke:
  `phase2-c780c34e27` from cycle 6 completed in `40s`, generated `35`,
  retained `31`, created `30` new behavior cells, retained yield `0.885714`,
  non-score retained ratio `1.0`, and `from_scratch_generated_count=35`.
  Lane totals were novelty `12/12`, uncertainty `11/8`, bridge `12/11`.
  This confirms the deeper escape restores candidate flow from the zero
  generation state.
- smoke replay:
  evaluated `8` fresh-preferred candidates in `59.2s`, produced no
  LONG_ONLY_REVIEW and `3` WATCHLIST_LONG_ONLY. Top candidate
  `v2cand-a4b054279c41` was WATCHLIST_LONG_ONLY with mean long return
  `0.003425`, long Sortino `3.668287`, and mean rank IC `0.002579`.
  This is useful as a generation-flow check, but not a commercial edge claim.

2026-04-30 distant-axis broad search relaunched:

- runner:
  started background process PID `28476`.
- output root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis`.
- starting root:
  `runtime/next_stage_artifacts/phase2-distant-axis-escape-smoke-20260430/phase2-c780c34e27`.
- parameters:
  `min_runtime_hours=24`, `flow_length=1`, `rounds=22`,
  `per_lane_budget=12`, `artifact_profile=compact`,
  `max_continuation_seeds=260`, `auto_replay_top_k=16`.
- purpose:
  verify that the distant-axis escape can sustain broad candidate flow across
  repeated memory-aware cycles, not only in a single smoke run.
- stop file:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis/STOP`.

2026-04-30 throughput correction after parallelism review:

- issue:
  the first distant-axis launch was too light for throughput. It was a single
  sequential long-runner: one generation cycle at a time, then one replay
  sidecar. That is safe but underuses a 12-logical-CPU machine.
- hardware check:
  local machine reports `6` CPU cores / `12` logical processors and CUDA-capable
  torch with `NVIDIA GeForce GTX 1650` / `4GB` VRAM. Current main Phase2 search
  does not use GPU; `nvidia-smi` showed `0` GPU utilization and `0MB` used
  before the training-device patch.
- immediate parallel search action:
  kept the original runner as worker 01 and launched three additional workers
  from the same distant-axis smoke root:
  - worker 02 PID `36780`: `rounds=26`, `per_lane_budget=12`,
    `max_continuation_seeds=320`, `auto_replay_top_k=16`.
  - worker 03 PID `31956`: `rounds=22`, `per_lane_budget=16`,
    `max_continuation_seeds=280`, `auto_replay_top_k=12`.
  - worker 04 PID `7472`: `rounds=18`, `per_lane_budget=18`,
    `max_continuation_seeds=360`, `auto_replay_top_k=12`.
- interpretation:
  parallelism is now worker-level search parallelism plus replay sidecars per
  worker. This increases formula-space throughput immediately without changing
  the core retention/gating rules.
- training/GPU action:
  Phase3 offline LoRD policy training now supports `--device auto|cpu|cuda`.
  The report records requested/resolved device, CUDA availability, and GPU name.
  This enables VRAM acceleration for offline policy training, but it still does
  not control Phase2 generation until a later reviewed integration step.
- tests:
  `pytest tests/test_phase3_policy_training.py -q` passed with `4 passed`.

2026-04-30 replay validation acceleration patch:

- issue:
  worker-level parallelism increases search throughput, but the replay validator
  itself was still serial inside each `auto_long_only_replay` call.
- action:
  added `parallel_workers` to `batch_validate_candidate_ledger` and exposed
  `--parallel-workers` on `auto_long_only_replay`. Default remains `1` to keep
  historical behavior stable.
- design:
  the parallel path uses thread workers against one already-loaded market panel,
  so it avoids the low-memory failure mode of spawning multiple processes that
  each reload the A-share CSV. Each candidate gets its own expression cache, and
  the report records `parallel_workers` plus `parallel_validation_mode`.
- smoke:
  `auto_long_only_replay` with `--max-candidates 4 --parallel-workers 2`
  completed successfully on `phase2-c780c34e27` and wrote
  `auto_long_only_replay_parallel_smoke.json`.
- tests:
  `pytest tests/test_phase2_v21_runtime.py -q -k "auto_long_only_replay_selection or real_market_validation or validation"`
  passed with `27 passed, 135 deselected`.

2026-04-30 distant-axis worker-01 cycle-1 result:

- generation:
  worker 01 cycle 1 completed in `1758.928s` with `748` generated candidates,
  `163` retained candidates, `152` new behavior cells, retained yield
  `0.217914`, and non-score retained ratio `0.877301`.
- replay:
  serial auto replay evaluated `16` candidates in `190.142s`. It found `0`
  LONG_ONLY_REVIEW and `1` WATCHLIST_LONG_ONLY. Top candidate
  `v2cand-ab8afeeaaee0`: mean long return `0.002816`, long Sortino
  `2.678541`, mean rank IC `0.005899`.
- parallel replay sidecar:
  manual `auto_long_only_replay --max-candidates 8 --parallel-workers 4`
  completed in `119s`, with `parallel_validation_mode=threaded_shared_loaded_panel`,
  `8` evaluated and `0` unsupported. It found no review/watchlist names.
- interpretation:
  search throughput is now much higher, but replay remains expensive. The new
  threaded replay path is functionally available; the measured speedup is not
  yet strong enough to call solved. Further replay acceleration should target
  expression-DAG cache reuse, relation/rolling operator vectorization, or
  chunked process workers with memory guards.

2026-04-30 replay runner wiring and cache experiment:

- runner wiring:
  `run_overnight_phase2_search.py` now accepts
  `--auto-replay-parallel-workers` and passes it through to
  `auto_long_only_replay`. Existing already-running workers do not pick this up,
  but new workers can run parallel replay inside the normal cycle loop.
- cache experiment:
  tested a shared expression-cache variant for threaded replay. It was slower:
  `8` candidates with `parallel_workers=4` took `196s`, versus the earlier
  independent-cache threaded smoke at about `119s`.
- decision:
  do not keep shared-cache locking in the replay path. Lock contention and
  pandas object sharing outweighed reuse benefits. The correct next acceleration
  target is compiled/vectorized expression evaluation, not a locked dict around
  recursive pandas evaluation.

2026-04-30 CUDA policy-training smoke:

- command:
  Phase3 offline policy training was run on worker-01 cycle-1 root with
  `--device cuda --epochs 24`.
- result:
  artifact root `runtime/phase3_artifacts/cuda_smoke_20260430/phase3-eb106b7026`.
  Training resolved to `cuda` on `NVIDIA GeForce GTX 1650`, used `22` outcome
  samples, and completed in `8041.414ms`.
- metrics:
  loss moved from `23.373623` to `20.161793`, but final lane accuracy was only
  `0.045455`.
- gate:
  Phase3 gate verdict remained `FLAG`, and
  `allows_policy_to_control_search=false`. GPU training is now operational as
  infrastructure, but it is not yet a usable controller for Phase2 search.

2026-04-30 parallel replay runner integration probe:

- probe:
  ran `run_overnight_phase2_search.py` for one short cycle with
  `--auto-replay-parallel-workers 2`, `rounds=4`, `per_lane_budget=4`,
  and `auto_replay_top_k=4`.
- result:
  output root `runtime/next_stage_artifacts/phase2-parallel-replay-runner-probe-20260430`.
  The cycle completed in `110.358s`, generated `23`, retained `21`, created
  `21` new cells, and retained yield `0.913043`.
- replay:
  runner-integrated replay completed in `95.134s`, evaluated `4`, unsupported
  `0`, and the replay report recorded `parallel_workers=2` with
  `parallel_validation_mode=threaded_shared_loaded_panel`.
- interpretation:
  the long-runner now passes replay parallelism correctly. Existing already
  running workers still use the old in-memory runner code; newly launched
  workers can use the parallel replay option.

2026-04-30 worker-05 parallel replay launch:

- runner:
  started `worker_05_parallel_replay` as PID `25408`.
- output root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis-worker_05_parallel_replay`.
- starting root:
  worker-01 cycle-1 root
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis/cycle_001/phase2-58d78c049a`.
- parameters:
  `min_runtime_hours=24`, `flow_length=1`, `rounds=16`,
  `per_lane_budget=10`, `artifact_profile=compact`,
  `max_continuation_seeds=180`, `auto_replay_top_k=12`,
  `auto_replay_parallel_workers=3`.
- purpose:
  run a production-length worker that uses runner-integrated parallel replay
  rather than only manual replay sidecars.

2026-04-30 worker-05 capacity guard:

- observation:
  after worker 05 started, machine load hit CPU `100%` and available memory fell
  below `1GB` (`905MB`, then `838MB`). That is not useful throughput; it risks
  paging and slowing every worker.
- action:
  wrote STOP reason `stop_capacity_guard_cpu_100_memory_below_1gb` and
  terminated the worker-05 process tree.
- result:
  CPU returned to roughly `14-24%` and available memory recovered to about
  `1.5GB`.
- decision:
  keep the current capacity at four main workers on this machine. Use
  runner-integrated parallel replay for new workers when replacing old workers,
  not by adding a fifth concurrent worker under low-memory conditions.

2026-04-30 old-worker replacement plan:

- action:
  STOP files were set for the four original distant-axis workers with reason
  `stop_after_current_cycle_replace_with_parallel_replay_runner`.
- reason:
  those workers were launched before the runner supported
  `--auto-replay-parallel-workers`, so their future cycles would continue using
  serial replay. The STOP files let each worker finish its current cycle and
  replay, then stop before starting another serial-replay cycle.
- next:
  once each old worker stops, replace it with a new worker using the same
  four-worker capacity budget and runner-integrated parallel replay.

2026-04-30 worker-02 replacement:

- old worker-02 result:
  stopped by STOP after cycle 1. It generated `859`, retained `167`, created
  `156` new cells, retained yield `0.194412`, and serial replay evaluated `16`
  in `131.54s`. Top replay was again WATCHLIST_LONG_ONLY
  `v2cand-ab8afeeaaee0` with mean long return `0.002816`, long Sortino
  `2.678541`, and mean rank IC `0.005899`.
- replacement:
  started `worker_02_parallel_replay` as PID `9924` from old worker-02 final
  root.
- parameters:
  `rounds=22`, `per_lane_budget=12`, `max_continuation_seeds=260`,
  `auto_replay_top_k=16`, `auto_replay_parallel_workers=3`.
- capacity:
  after replacement launch, CPU was about `18-19%` and available memory about
  `1.39GB`, so the four-worker budget is still acceptable.

2026-04-30 parallel replay worker check:

- process state:
  old workers 01/03/04 have stopped by STOP. Only `worker_02_parallel_replay`
  was still running before replacement. After replacement, workers
  01/02/03/04 are all running with `auto_replay_parallel_workers=3`.
- replacement launches:
  started `worker_01_parallel_replay` PID `26476` from old worker-01 cycle-2
  root, `worker_03_parallel_replay` PID `42332` from old worker-03 root, and
  `worker_04_parallel_replay` PID `43180` from old worker-04 root.
- old worker summaries:
  old worker-01 ran two cycles: cycle 1 `748/163/152`, cycle 2
  `657/62/49`. Old worker-03 ran `1065/206/187`. Old worker-04 ran
  `1015/218/195`. None found a new LONG_ONLY_REVIEW.
- active worker-02 parallel replay:
  cycle 1 generated `720`, retained `60`, created `50` new cells. Cycle 2
  generated `616`, retained `62`, created `29` new cells. Both cycles used
  `parallel_workers=3` and replay mode `threaded_shared_loaded_panel`.
- replay issue:
  worker-02 parallel replay found `v2cand-9c525090b79f` as LONG_ONLY_REVIEW in
  both cycle 1 and cycle 2. This confirms the runner-integrated parallel replay
  works, but also shows replay budget is still being spent on known strong
  candidates across worker families. Fresh selection is local to the current
  root's memory, not a global family-level replay exclusion.
- next:
  add a family-level replay exclusion or shared replay-memory input for broad
  worker groups so replay budget prioritizes newly discovered candidates after
  known review seeds are already captured.

2026-04-30 family-level replay exclusion patch:

- issue:
  `auto_long_only_replay` only excluded candidates replay-enriched in the local
  root chain. In multi-worker broad search, that allowed known review seeds such
  as `v2cand-9c525090b79f` to consume replay slots repeatedly across worker
  families.
- action:
  added replay-family exclusion support. `auto_long_only_replay` now accepts
  `--exclude-replayed-from-root` and collects candidate ids from those roots'
  `auto_long_only_replay_report.json` files, overnight manifests, and cycle
  folders. The long runner now accepts `--auto-replay-exclude-root` and passes
  those roots through to replay.
- tests:
  targeted replay-selection tests passed with `27 passed, 136 deselected`.
- smoke:
  reran worker-02 cycle-2 replay with four old worker roots as exclusion inputs.
  Excluded replay candidate count increased to `111`, and the selected top no
  longer repeated `v2cand-9c525090b79f`.
- new review seed:
  `v2cand-c6a857d996cd`, source `variation`, lane `score_frontier`, archive cell
  `low_momentum|low_size|stable|high_vol|mean_revert`.
  Recent 4-quarter replay: mean rank IC `0.027921`, mean long return
  `0.005393`, long Sortino `7.118007`, tradability filters available, no smoke
  flags. Status remains `HOLD_RESEARCH`: this is a replay-smoke review seed,
  not a commercial edge claim.
- next:
  replace active parallel replay workers after their current cycles so future
  cycle replays use family-level exclusions by default.

2026-04-30 family-exclusion worker launch/check:

- action:
  non-family-exclusion replacement workers 01/02 had started their next cycles
  before the family replay exclusion patch was available. They were terminated
  early to avoid spending another replay batch on already-known candidates.
- launched:
  `worker_01_family_exclusion` PID `14984` from worker-01 parallel cycle-1 root,
  and `worker_02_family_exclusion` PID `31124` from worker-02 parallel cycle-3
  root.
- parameters:
  worker-01 uses `rounds=20`, `per_lane_budget=10`,
  `max_continuation_seeds=220`, `auto_replay_top_k=16`,
  `auto_replay_parallel_workers=3`, `min_runtime_hours=24`.
  Worker-02 uses `rounds=22`, `per_lane_budget=12`,
  `max_continuation_seeds=260`, `auto_replay_top_k=16`,
  `auto_replay_parallel_workers=3`, `min_runtime_hours=24`.
- exclusion roots:
  both workers include six replay-family roots: the original distant-axis root,
  deep-rounds, wide-lanes, wide-escape, worker-01 parallel replay, and worker-02
  parallel replay. Manifest check confirms `auto_replay_exclude_roots=6`.
- live check:
  worker-01 family-exclusion is in cycle 1 generation around round `4/20`;
  worker-02 family-exclusion is in cycle 1 generation around round `3/22`.
  Older workers 03/04 have STOP files set and are finishing their current
  generation cycles before replacement; worker-03 was around round `18/18`,
  worker-04 around round `16/18`.
- capacity:
  CPU sampled between roughly `22%` and `66%`; available memory was about
  `1.69GB`. Do not add a fifth worker on this machine unless memory recovers
  materially.

2026-04-30 family-exclusion worker first results:

- old worker-03/04 parallel replay:
  both finished their STOP-controlled cycles before family-exclusion relaunch.
  Each replay evaluated `12`, found `0` LONG_ONLY_REVIEW and `1`
  WATCHLIST_LONG_ONLY. Top was `v2cand-47f1c860dc26`, mean long return
  `0.006625`, long Sortino `5.548027`, mean rank IC `0.007264`.
  This remains `HOLD_RESEARCH`/watchlist only.
- capacity guard:
  attempted to start a worker-03 family-exclusion replacement after worker-03
  finished, but memory dropped below `1GB` while worker-04 replay and workers
  01/02 were active. The replacement was stopped. A later retry after worker-04
  finished still pushed available memory to about `0.74GB`, so it was also
  stopped. Practical capacity on this machine is currently closer to two active
  generation workers plus at most one replay child, not four full generation
  workers with replay sidecars.
- worker-01 family-exclusion cycle 1:
  replay evaluated `16`, excluded `112` already-replayed candidates, used `191`
  fresh candidates, and found `0` LONG_ONLY_REVIEW / `0` WATCHLIST_LONG_ONLY.
  Top was `v2cand-ae33e9e44dc2`, decision `HOLD_WEAK_LONG_ONLY`, mean long
  return `0.002192`, long Sortino `1.785996`, mean rank IC `-0.004935`.
- worker-02 family-exclusion cycle 1:
  replay evaluated `16`, excluded `112` already-replayed candidates, used `211`
  fresh candidates, and found `1` LONG_ONLY_REVIEW. Top was
  `v2cand-c6a857d996cd`, mean long return `0.005393`, long Sortino `7.118007`,
  mean rank IC `0.027921`.
- interpretation:
  family-level exclusion is working, but the manual smoke report that first
  observed `v2cand-c6a857d996cd` was not one of the shared exclusion roots, so
  worker-02 rediscovered it as fresh. Now that it is in worker-02's formal
  replay report/search memory, later worker-family replays should exclude it
  when worker-02 family-exclusion is included as an exclusion root.
- current action:
  keep only workers 01/02 family-exclusion running until at least one current
  cycle completes; do not relaunch 03/04 while available memory stays near the
  `1-1.5GB` range.

2026-04-30 family-exclusion follow-up check:

- worker-01 cycle 2:
  replay evaluated `16`, excluded `128` already-replayed candidates, used `181`
  fresh candidates, and found `0` LONG_ONLY_REVIEW / `0` WATCHLIST_LONG_ONLY.
  Top was `v2cand-391616720299`, decision `HOLD_WEAK_LONG_ONLY`, mean long
  return `0.003062`, long Sortino `2.752940`, mean rank IC `-0.003017`.
- worker-02 cycle 2:
  replay evaluated `16`, excluded `128` already-replayed candidates, used `196`
  fresh candidates, and found `0` LONG_ONLY_REVIEW / `0` WATCHLIST_LONG_ONLY.
  Top was `v2cand-f646eddc2354`, decision `HOLD_WEAK_LONG_ONLY`, mean long
  return `0.002566`, long Sortino `2.174904`, mean rank IC `-0.012012`.
- live state:
  worker-01 entered cycle 3 and reached about round `18/20`; worker-02 entered
  cycle 3 and reached about round `3/22`.
- interpretation:
  after family-level exclusion removes the known review seed bucket, the next
  fresh replay batches are weak. This is useful negative evidence: the current
  broad/distant-axis stream is not yet producing a dense supply of new
  long-only edges under the A-share/PIT/tradability replay contract.
- capacity:
  available memory stayed around `1.1-1.5GB`; keep the active budget at workers
  01/02 only until more memory is free or a worker stops cleanly.

2026-04-30 family-exclusion later status:

- worker-01:
  completed `12` family-exclusion replay cycles and is running cycle `13`
  around round `7/20`. Recent cycles show mostly WATCHLIST-level candidates.
  The only recent LONG_ONLY_REVIEW in this segment was
  `v2cand-c56892345f8b` from cycle 9, with mean long return `0.001741`, long
  Sortino `1.569112`, and mean rank IC `0.011734`. This is materially weaker
  than `v2cand-c6a857d996cd`.
- worker-02:
  completed `7` family-exclusion replay cycles and is at cycle `8`
  generation completion (`22/22`) before replay. Additional LONG_ONLY_REVIEW
  candidates:
  `v2cand-0dc03220e0e4` from cycle 3 with mean long return `0.002472`, long
  Sortino `2.873267`, mean rank IC `0.025861`;
  `v2cand-336acec3cae3` from cycle 4 with mean long return `0.002668`, long
  Sortino `2.095144`, mean rank IC `0.013239`;
  `v2cand-b25b15ea9ff8` from cycle 6 with mean long return `0.001776`, long
  Sortino `1.488473`, mean rank IC `0.012765`.
- exclusion trend:
  replay exclusion counts continue rising as expected: worker-01 reached
  `288` excluded / `56` fresh in cycle 12, while worker-02 reached `208`
  excluded / `144` fresh in cycle 7. The search is not falling back to replayed
  candidates.
- current read:
  family-exclusion is technically working and still finds sparse review seeds,
  but the newly discovered review quality is mostly modest. The strongest
  observed seed remains `v2cand-c6a857d996cd` from worker-02 cycle 1 / manual
  smoke, still only a replay-smoke research seed rather than a commercial edge
  claim.
- capacity:
  available memory improved to about `2.47GB`; CPU sampled low after the check.
  Worker-02 was near replay start, so avoid launching more workers until cycle
  8 replay confirms actual memory load.

2026-04-30 stop narrow family and deploy fresh-reset round:

- stop:
  user requested stopping the current narrowed family stream and deploying the
  next round. STOP files were written for
  `worker_01_family_exclusion` and `worker_02_family_exclusion` with reason
  `stop_user_requested_deploy_next_round_fresh_reset`, and their active process
  trees were terminated.
- completed roots used:
  worker-01 last completed cycle root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis-worker_01_family_exclusion/cycle_028/phase2-feb3ed37ba`.
  Worker-02 last completed cycle root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-distant-axis-worker_02_family_exclusion/cycle_018/phase2-49fa425d3c`.
- reason:
  the family-exclusion stream was still technically productive but had become
  narrow. Fresh counts had fallen to roughly `40-50` per replay selection and
  most new LONG_ONLY_REVIEW candidates were weaker than the earlier
  `v2cand-c6a857d996cd` smoke seed.
- next round:
  launched four lighter `fresh-reset` workers with lower per-cycle weight:
  `rounds=10-12`, `per_lane_budget=8`, `max_continuation_seeds=120`,
  `auto_replay_top_k=16`, `auto_replay_parallel_workers=2`,
  `min_runtime_hours=24`.
- workers:
  `worker_01_light_fresh` starts from worker-01 cycle 28;
  `worker_02_light_fresh` starts from worker-02 cycle 18;
  `worker_03_strong_seed_escape` starts from worker-02 cycle 1, where
  `v2cand-c6a857d996cd` was found;
  `worker_04_old_wide_reset` starts from old worker-04 parallel replay cycle 1.
- exclusion roots:
  all four fresh-reset workers use ten exclusion roots: original distant-axis,
  deep-rounds, wide-lanes, wide-escape, old parallel workers 01/02/03/04, and
  the completed family-exclusion roots 01/02.
- capacity check:
  after launch, all four workers reached early generation progress (`3-4` of
  `10-12` rounds). Available memory was about `4.36GB`; CPU sampled between
  roughly `15%` and `53%`; disk was not saturated. Keep this four-worker setup
  unless paging rises persistently or replay sidecars push memory below `1GB`.
- experiment_id:
  `20260430_fresh_reset_001`.
- reproducibility:
  partial. Runtime manifests record exact commands and exclusion roots; the
  large live dataset is referenced by path through the replay reports rather
  than copied into this status file.

2026-05-01 fresh-reset strict audit:

- experiment_id:
  `20260501_fresh_reset_strict_audit_001`.
- objective:
  strict A-share PIT/tradability/cost audit for the strongest fresh-reset and
  prior smoke seeds before any keep/promotion discussion.
- inputs:
  replay reports under
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-fresh-reset-*`
  plus the prior family-exclusion roots. Dataset path is the standard
  `G:/Project_V7_Rotation/scripts/data/tdx_sector_data_p3_enhanced.csv` as
  referenced by replay reports.
- parameters:
  signal clock `after_open`; feature lag days `0` with field-level signal-clock
  lags; horizons `[1, 5, 20]`; top/bottom quantile `0.05`; cost `20bps`;
  recent quarter windows `4`; warmup days `60`.
- outputs:
  `runtime/next_stage_artifacts/phase2-fresh-reset-strict-audit-20260501/strict_audit_report.json`
  and
  `runtime/next_stage_artifacts/phase2-fresh-reset-strict-audit-20260501/strict_audit_c6a857d996cd.json`.
- results:
  `v2cand-c6a857d996cd`: strict 1-day mean rank IC `0.027921`,
  positive-window IC ratio `0.75`, cost-adjusted spread `0.003500`, one-way
  turnover `0.193175`.
  `v2cand-fd9d310d0fe1`: strict 1-day mean rank IC `0.062045`,
  positive-window IC ratio `1.00`, cost-adjusted spread `0.001780`, one-way
  turnover `0.167077`.
  `v2cand-b6aee649bf98`: strict 1-day mean rank IC `0.024110`,
  positive-window IC ratio `1.00`, cost-adjusted spread `0.001530`, one-way
  turnover `0.172956`.
  `v2cand-192eff278bfa`: strict 1-day mean rank IC `0.011057`,
  positive-window IC ratio `0.75`, cost-adjusted spread `0.001332`, one-way
  turnover `0.683773`.
  `v2cand-3ae7d9211d0e`: strict 1-day mean rank IC `0.010331`,
  positive-window IC ratio `0.75`, cost-adjusted spread `0.001368`, one-way
  turnover `0.676897`.
  `v2cand-1e79f2a85977`: strict 1-day mean rank IC `0.014439`,
  positive-window IC ratio `0.75`, cost-adjusted spread `0.000937`, one-way
  turnover `0.566340`.
- bias audit:
  all audited candidates remain `HOLD_RESEARCH`, not KEEP. Blocking issues are
  generic but real: sector neutralization not run, capacity model not run, and
  survivorship/universe policy not promotion-grade. The audit does include
  after-open field-lag policy, T+1 execution alignment, entry limit-up/down
  tradability filtering, turnover shadow, and cost-adjusted spread.
- candidate review:
  the current best strict-review ordering is `c6a857d996cd` for spread quality
  and `fd9d310d0fe1` for IC stability. `b6aee649bf98` is a secondary candidate.
  The high-smoke-Sortino close-reversal variants
  `192eff278bfa` and `3ae7d9211d0e` have high one-way turnover and weaker IC,
  so they are lower priority despite impressive smoke Sortino.
- next:
  run exposure/sector-neutrality checks and a focused portfolio replay only for
  `c6a857d996cd`, `fd9d310d0fe1`, and optionally `b6aee649bf98`. Do not make a
  commercial edge claim until those pass.

2026-05-01 fresh-reset exposure neutrality probe:

- experiment_id:
  `20260501_fresh_reset_exposure_neutrality_001`.
- output:
  `runtime/next_stage_artifacts/phase2-fresh-reset-strict-audit-20260501/exposure_neutrality_report.json`.
- candidates:
  `v2cand-c6a857d996cd`, `v2cand-fd9d310d0fe1`,
  `v2cand-b6aee649bf98`.
- raw vs exposure-residualized:
  `c6a857d996cd` raw mean rank IC `0.027921`, exposure-residualized mean rank
  IC `0.020659`, delta `-0.007262`; turnover rises from `0.193175` to
  `0.437955`.
  `fd9d310d0fe1` raw mean rank IC `0.062045`, exposure-residualized mean rank
  IC `0.015138`, delta `-0.046907`; turnover rises from `0.167077` to
  `0.546911`.
  `b6aee649bf98` raw mean rank IC `0.024110`, exposure-residualized mean rank
  IC `0.024014`, delta `-0.000096`; turnover rises from `0.172956` to
  `0.310475`.
- exposure read:
  `fd9d310d0fe1` has material amount/volume exposure
  (`amount` rank corr about `0.362`, `volume` about `0.333`) and loses much of
  its IC after control residualization. Treat it as a likely liquidity/size
  composite until proven otherwise.
  `c6a857d996cd` has modest turnover/crowding exposure and weakens after
  residualization, but less severely than `fd9d310d0fe1`.
  `b6aee649bf98` is much cleaner against amount, volume, turnover, crowding,
  rps score, and money flow controls; its IC is lower than `fd9d310d0fe1` but
  survives residualization best.
- sector note:
  the current panel's `sector` column is not a usable stock-level industry map:
  diagnostics show `574` groups for `574` codes, median one code per group.
  Therefore true sector neutralization is not available from this panel and
  remains a blocker. A real PIT industry/sector join is still needed.
- decision:
  all three remain `HOLD_RESEARCH`.
  Priority for next focused replay shifts to `b6aee649bf98` as the cleanest
  residualized candidate, with `c6a857d996cd` as spread-quality backup and
  `fd9d310d0fe1` demoted until liquidity/size exposure is addressed.

2026-05-01 fresh-reset focused replay partial:

- experiment_id:
  `20260501_fresh_reset_focused_portfolio_replay_001`.
- objective:
  replay the best strict/exposure-audited candidates as small-capital
  long-only/long-short portfolios under A-share PIT/tradability rules, before
  deciding whether the fresh-reset line has any commercial-grade path.
- output:
  partial file only:
  `runtime/next_stage_artifacts/phase2-fresh-reset-strict-audit-20260501/focused_portfolio_replay_report.partial.json`.
- status:
  abandoned after `826.358s` because the full replay design recomputed signal
  and portfolio slices too expensively. The residue `python -` process tree was
  terminated; no final `focused_portfolio_replay_report.json` exists.
- completed partial:
  only `single_b6aee649bf98` completed for rebalance frequencies `1` and `3`.
  The test used dataset
  `G:/Project_V7_Rotation/scripts/data/tdx_sector_data_p3_enhanced.csv`,
  signal clock `after_open`, T+1 execution, top/bottom quantile `0.05`,
  cost grid `10/20/30bps`, and recent window `2025-04-01` to `2026-02-04`
  plus quarterly slices.
- recent 4-quarter long-only, 20bps:
  freq `1`: raw mean `0.003811`, net mean `0.003448`, net Sortino
  `4.544058`, one-way turnover `0.181332`, max drawdown `-0.092807`,
  positive-day ratio `0.565217`.
  freq `3`: raw mean `0.003607`, net mean `0.003363`, net Sortino
  `4.317381`, one-way turnover `0.121749`, max drawdown `-0.095744`,
  positive-day ratio `0.570048`.
- quarterly long-only, 20bps:
  freq `1` net means: `2025Q2=0.005956`, `2025Q3=0.003454`,
  `2025Q4=0.001221`, `2026Q1_partial=0.002409`.
  freq `3` net means: `2025Q2=0.006200`, `2025Q3=0.003091`,
  `2025Q4=0.001201`, `2026Q1_partial=0.002112`.
- read:
  `b6aee649bf98` is now the cleanest focused candidate: strict IC survives
  exposure residualization and the partial portfolio replay is positive across
  the tested recent quarterly slices. This is still not a promotion claim:
  true PIT industry neutralization, survivorship/universe proof, and a faster
  reproducible replay harness remain blockers.
- live search status at check:
  four fresh-reset workers were still active with no stuck portfolio-replay
  residue observed. Latest running cycles were worker-01 `cycle_156`,
  worker-02 `cycle_154`, worker-03 `cycle_174`, worker-04 `cycle_171`.
  Across `651` fresh-reset replay reports, top smoke examples remain mixed:
  high-Sortino candidates often have low IC or high turnover, while the highest
  IC candidate `fd9d310d0fe1` weakens materially under exposure residualization.
- next:
  do not rerun the heavy focused replay as written. Use a lighter harness that
  loads the panel once, evaluates each expression once, and then reuses the
  signal for frequencies/slices. Prioritize `b6aee649bf98`, then
  `c6a857d996cd`, then only retest `fd9d310d0fe1` if liquidity/size exposure is
  explicitly controlled.

2026-05-01 focused replay light rerun:

- experiment_id:
  `20260501_fresh_reset_focused_portfolio_replay_light_001`.
- output:
  `runtime/next_stage_artifacts/phase2-fresh-reset-strict-audit-20260501/focused_portfolio_replay_light_report.json`.
- runtime:
  completed in `212.407s`. This confirms the faster replay direction: load the
  panel once, evaluate each expression once, then reuse signals across
  rebalance frequencies and slices.
- candidates:
  `v2cand-b6aee649bf98`, `v2cand-c6a857d996cd`,
  `v2cand-fd9d310d0fe1`.
- recent 4-quarter long-only, 20bps:
  `b6aee649bf98`: freq `1/3/5` net means `0.003448 / 0.003363 /
  0.003582`, net Sortino `4.544058 / 4.317381 / 4.526443`, max drawdown
  about `-0.093` to `-0.096`, one-way turnover `0.181332 / 0.121749 /
  0.100114`.
  `c6a857d996cd`: freq `1/3/5` net means `0.001972 / 0.002066 /
  0.001455`, net Sortino `1.979181 / 2.096005 / 1.465942`, max drawdown
  about `-0.116`.
  `fd9d310d0fe1`: freq `1/3/5` net means `0.003711 / 0.003721 /
  0.003653`, net Sortino `2.483754 / 2.930730 / 2.327160`, max drawdown
  about `-0.127` to `-0.160`.
- b6 quarterly long-only, 20bps:
  freq `1` net means: `2025Q2=0.005956`, `2025Q3=0.003454`,
  `2025Q4=0.001221`, `2026Q1_partial=0.002409`.
  freq `3` net means: `2025Q2=0.006200`, `2025Q3=0.003091`,
  `2025Q4=0.001201`, `2026Q1_partial=0.002112`.
  freq `5` net means: `2025Q2=0.006879`, `2025Q3=0.002912`,
  `2025Q4=0.001269`, `2026Q1_partial=0.001465`.
- capacity proxy:
  `b6aee649bf98` selects about `28` long names per day at 5% quantile.
  Recent 4Q long-entry amount p10 mean is about `4.6B-4.8B`, so capacity is
  not the immediate blocker for small capital. `c6` and `fd9` select similarly
  sized baskets but their p10 entry amount is closer to about `1.0B-1.2B`.
- read:
  `b6aee649bf98` is the current best research candidate because it combines
  exposure-clean IC with stable recent long-only replay and tolerable turnover.
  `fd9d310d0fe1` has attractive long-only replay but remains suspect because
  exposure residualization cut its IC from `0.062045` to `0.015138`.
  `c6a857d996cd` is usable as a backup/ensemble component but has weaker
  long-only replay and worse long-short behavior.
- decision:
  still `HOLD_RESEARCH`. The next blockers are real PIT industry mapping,
  survivorship/universe proof, and a lightweight promotion-grade replay that
  explicitly controls liquidity/size exposure before any commercial/private
  fund-level claim.

2026-05-01 b6 exposure-clean soft-prior worker:

- objective file:
  `reports/PHASE2_B6_EXPOSURE_CLEAN_SOFT_PRIOR_OBJECTIVE_2026-05-01.json`.
- purpose:
  feed the strict/exposure/focused-replay result back into generation as a
  soft prior, not a formula lock. The objective uses decision
  `USE_WEAK_REAL_REPLAY_PRIORS_FOR_NEXT_SEARCH`, watches `b6aee649bf98`-like
  bridge/operator-aware motifs, keeps `c6a857d996cd` as backup, and mildly
  demotes `$amount` exposure after the `fd9d310d0fe1` residualization failure.
- failed launch:
  `phase2-next-sortino-memory-broad-search-20260501-b6-exposure-clean-soft-prior-worker_01`
  was stopped. It repeatedly failed because it was pointed at worker-01
  `cycle_158/phase2-4e573ff7fb`, a phase directory that existed but did not yet
  contain `archive_state.json`.
- active launch:
  `phase2-next-sortino-memory-broad-search-20260501-b6-exposure-clean-soft-prior-worker_02`
  started from the last complete worker-01 root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260430-fresh-reset-worker_01_light_fresh/cycle_157/phase2-2aa3376400`.
- parameters:
  `min_runtime_hours=12`, `flow_length=1`, `rounds=12`,
  `per_lane_budget=8`, `artifact_profile=compact`,
  `max_continuation_seeds=160`, `auto_replay_top_k=16`,
  `auto_replay_parallel_workers=2`, excluding the four fresh-reset worker roots
  from replay memory.
- initial health:
  `cycle_001` reached `entering_prototype`; continuation context loaded `178`
  retained records and selected `160` seeds; `real_replay_feedback_active=true`.
  Free memory after launch was about `5.69GB`.
- caution:
  keep the original four fresh-reset workers running to preserve broad search.
  The b6 worker is a sidecar to test whether exposure-clean replay feedback can
  improve useful hit rate without sacrificing broad formula-space coverage.

2026-05-01 cold fresh sidecar deployment:

- reason:
  after the b6 soft-prior continuation worker was healthy, there was still
  enough resource headroom to add fresh exploration without replacing the four
  broad fresh-reset workers.
- resource snapshot before launch:
  git clean; free memory about `5.64GB`; CPU sampled around `17-27%`.
- launched:
  `phase2-next-sortino-memory-broad-search-20260501-cold-fresh-broad-worker_01`
  and
  `phase2-next-sortino-memory-broad-search-20260501-cold-fresh-b6-soft-worker_01`.
- key difference:
  both use `previous_run_root=null` / cold start. The broad worker uses
  `PHASE2_NEXT_SORTINO_MEMORY_SEARCH_OBJECTIVE_2026-04-30.json`; the b6-soft
  worker uses
  `PHASE2_B6_EXPOSURE_CLEAN_SOFT_PRIOR_OBJECTIVE_2026-05-01.json`.
- parameters:
  `min_runtime_hours=12`, `flow_length=1`, `rounds=8`,
  `per_lane_budget=6`, `artifact_profile=compact`,
  `max_continuation_seeds=0`, `auto_replay_top_k=12`,
  `auto_replay_parallel_workers=1`.
- replay memory:
  both cold fresh workers exclude the four 2026-04-30 fresh-reset roots and the
  active b6 soft-prior continuation worker root, so replay should prefer fresh
  candidates rather than rediscovering already reviewed expressions.
- health:
  both reached `entering_prototype` with `previous_run_root=null`,
  `continuation_context=null`, and `real_replay_feedback_active=true`; stderr was
  empty at the launch check. Post-launch free memory was about `5.07GB`, CPU
  sampled around `25-32%`.
- caution:
  these are deliberately light. If memory falls below about `2GB` during replay
  overlap, stop the cold fresh sidecars first, not the original four broad
  workers or the b6 continuation worker.

2026-05-01 replay/backtest acceleration and fuller space fill:

- acceleration finding:
  the validation stack already supports parquet, but the default market panel
  was still the `486MB` CSV
  `G:/Project_V7_Rotation/scripts/data/tdx_sector_data_p3_enhanced.csv`.
  Replay workers therefore repeatedly paid CSV scan cost.
- implemented:
  added a default local parquet preference in `real_market_data.py`: if
  `tdx_sector_data_p3_enhanced.parquet` exists, it becomes
  `DEFAULT_REAL_MARKET_DATASET_PATH`; otherwise the code falls back to CSV.
  `PHASE2_REAL_MARKET_DATASET_PATH` can override both. Also changed parquet
  column discovery to use parquet metadata instead of loading the full parquet
  just to inspect columns.
- local cache:
  generated
  `G:/Project_V7_Rotation/scripts/data/tdx_sector_data_p3_enhanced.parquet`
  from the CSV, `1,607,969` rows and `25` columns. Size is about `150MB`.
- load benchmark:
  `_load_recent_quarter_market_panel(..., quarter_window_count=4,
  warmup_days=60)` on the same data returned `138,923` rows.
  CSV took about `27.177s`; parquet took about `5.604s`, roughly `4.8x`
  faster for this replay panel load.
- validation:
  `py_compile` passed for `real_market_data.py` and
  `real_market_validation.py`. The result is a data-path/read optimization, not
  a trading-rule change.
- added search capacity:
  launched two more light parquet-aware continuation sidecars:
  `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-wide-worker_01`
  from worker-04 `cycle_176/phase2-14ceb065a6` with the broad objective, and
  `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-b6-worker_01`
  from worker-02 `cycle_158/phase2-49ca914cfb` with the b6 soft-prior
  objective.
- parameters:
  both use `min_runtime_hours=12`, `flow_length=1`, `rounds=8`,
  `per_lane_budget=6`, `artifact_profile=compact`,
  `max_continuation_seeds=120`, `auto_replay_top_k=12`,
  `auto_replay_parallel_workers=1`, and explicitly inherit
  `PHASE2_REAL_MARKET_DATASET_PATH` pointing at the parquet cache.
- health:
  both reached `entering_prototype` with `real_replay_feedback_active=true`.
  Post-launch free memory was about `4.68GB`; CPU sampled about `50-55%`.
  This is close to a useful saturation point without yet forcing paging.
- stop priority if pressure rises:
  first stop cold fresh sidecars, then the two parquet continuation sidecars;
  keep the original four broad workers and the main b6 continuation worker
  unless memory drops below safe operating range.

2026-05-01 soft-prior validation decision:

- question:
  the b6 `soft` objective is a validation of search guidance, not a direct
  validation of commercial factor edge. It answers whether replaying
  exposure-clean motifs around `b6aee649bf98` improves useful discovery rate
  versus broad search under comparable budget.
- validation method:
  compare broad versus soft-guided workers on review hit rate, best IC,
  long-only replay quality, duplicate concentration, and strict-audit
  candidates. This remains a search-policy A/B test; any candidate still needs
  PIT/tradability/focused replay and strict audit before promotion.
- current A/B read:
  `b6-exposure-clean-soft-prior-worker_02` is useful as a continuation
  sidecar. At the last aggregation it had 37 replay reports, 592 evaluated
  candidates, 13 `LONG_ONLY_REVIEW` candidates, and 90 watch candidates. Its
  best IC candidate was `v2cand-0b002337b1bb` with replay return about
  `0.004451`, Sortino about `3.978074`, and IC about `0.038570`; its best
  Sortino candidate was `v2cand-9c525090b79f` with replay return about
  `0.004120`, Sortino about `5.864887`, and IC about `0.017194`.
- negative cold-start result:
  `cold-fresh-b6-soft-worker_01` was not useful as a cold-start policy. It had
  13 reports, 156 evaluated candidates, 0 `LONG_ONLY_REVIEW` candidates, and
  13 watch candidates; its top visible candidate had return about `0.002027`,
  Sortino about `2.325389`, and IC about `-0.033637`. Decision: stop this
  worker and do not treat cold-start b6-soft as proven.
- broad control remains viable:
  `cold-fresh-broad-worker_01` had 42 reports, 504 evaluated candidates,
  11 `LONG_ONLY_REVIEW` candidates, and 57 watch candidates. Its best IC
  candidate was `v2cand-48ea9a35d523` with replay return about `0.002701`,
  Sortino about `2.114933`, and IC about `0.033182`.
- parquet continuation read:
  the broad parquet continuation found `v2cand-4f03733a228d` with replay
  return about `0.004967`, Sortino about `7.085510`, and IC about `0.009914`,
  plus `v2cand-b0768c3e576f` with IC about `0.028683`. The b6 parquet
  continuation is useful but showed duplicate concentration around
  `v2cand-9c525090b79f`, so later search memory should strengthen cross-worker
  de-duplication before adding more b6-soft capacity.
- action taken:
  placed a `STOP` marker under
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260501-cold-fresh-b6-soft-worker_01`.
  The stop command overmatched command lines containing this root as an
  `--auto-replay-exclude-root`, which also stopped the first parquet
  continuation worker processes. This was corrected by restarting the parquet
  continuations from their latest complete checkpoints:
  `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-wide-worker_02`
  from `parquet-cont-wide-worker_01/cycle_079/phase2-93fe632d6d`, and
  `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-b6-worker_02`
  from `parquet-cont-b6-worker_01/cycle_079/phase2-cf7fcf46cc`.
- health after correction:
  no active process matches `cold-fresh-b6-soft-worker_01`; both parquet
  worker_02 roots reached `entering_prototype` with
  `real_replay_feedback_active=true`. Free memory was about `3.5-3.7GB`, with
  CPU saturated. Do not launch more workers until current workers age or CPU
  frees up.
- next strict-audit shortlist:
  `v2cand-0b002337b1bb`, `v2cand-9c525090b79f`,
  `v2cand-48ea9a35d523`, `v2cand-b0768c3e576f`,
  `v2cand-4f03733a228d`.
- decision:
  `cold-start b6-soft = FAIL/retired`; `b6 continuation soft = HOLD_RESEARCH`
  but useful; `broad and parquet-wide continuations = HOLD_RESEARCH`.

2026-05-02 overnight task allocation:

- state before allocation:
  the original four broad fresh-reset workers completed their 24h minimum
  runtime. `b6-exposure-clean-soft-prior-worker_02` completed its 12h minimum
  runtime with 71 replay reports, 1136 evaluated candidates, 29
  `LONG_ONLY_REVIEW` candidates, and 175 watch candidates. `cold-fresh-broad`
  completed its 12h minimum runtime with 90 replay reports, 1080 evaluated
  candidates, 11 `LONG_ONLY_REVIEW` candidates, and 153 watch candidates.
  The two parquet continuation workers were still running at about 6.2h and
  should continue to 12h instead of being interrupted.
- night split:
  keep `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-wide-worker_02`
  and `phase2-next-sortino-memory-broad-search-20260501-parquet-cont-b6-worker_02`
  running as the remaining broad/soft sidecar search capacity. Do not launch
  more search workers while these are active.
- strict-audit batch:
  launched
  `runtime/next_stage_artifacts/phase2-overnight-strict-audit-20260502/run_strict_audit_batch_20260502.py`
  in the background using `G:/PythonProject/.venv/Scripts/python.exe`.
  It writes `heartbeat.json`, `audit_input_manifest.json`,
  `strict_exposure_batch_report.partial.json`, and on completion
  `strict_exposure_batch_report.json`.
- strict-audit candidate set:
  `v2cand-a6a0520a5c2f`, `v2cand-0b002337b1bb`,
  `v2cand-9c525090b79f`, `v2cand-9d437531f65c`,
  `v2cand-c15df6ea6021`, `v2cand-192eff278bfa`,
  `v2cand-9f4cc162c00c`, `v2cand-7493cba22788`,
  `v2cand-ae1e92f81a2d`, `v2cand-9ea8b6e76bd9`,
  `v2cand-f38444908624`, and `v2cand-37cbd5f6e832`.
- strict-audit parameters:
  after-open signal semantics, T+1 execution, `feature_lag_days=0`, entry
  limit-up/limit-down/suspension masks through the existing validation stack,
  recent 4 quarterly windows, `recent_warmup_days=60`,
  `top_bottom_quantile=0.05`, `cost_bps=20`, horizons `[1, 3, 5]`, and a
  panel exposure-neutrality probe using amount, volume, turnover, crowding,
  RPS, and money-flow controls where available.
- purpose:
  this batch is not a commercial edge claim. It is a candidate-factor review
  and quant backtest bias-audit gate before any keep-list or next-search
  expansion. Expected outcome is that many candidates fail or remain
  `HOLD_RESEARCH`; a single candidate surviving strict/exposure checks is
  enough to justify a focused expansion run.
- wake-up checks:
  inspect the strict batch heartbeat/report first, then the two parquet worker
  heartbeats. If strict is complete, rank by: no blocker flags, residualized
  IC retention, positive 4-quarter distribution, 20bps cost-adjusted spread,
  and low single-control exposure. If parquet workers are complete, fold their
  late candidates into the next audit queue rather than launching a fresh
  search immediately.
- resource protection update:
  after the strict batch started, free memory briefly dropped to about `1.42GB`
  while both parquet sidecars were also generating/replaying. To avoid overnight
  paging or killing the strict audit, both parquet continuation sidecars were
  stopped with `STOP` markers and their active child generation/replay
  processes were terminated. They closed as `stopped_by_stop_file`:
  `parquet-cont-wide-worker_02` at about `6.36h`, `cycle_count=92`,
  final checkpoint
  `cycle_092/phase2-378e44f046`; `parquet-cont-b6-worker_02` at about `6.36h`,
  `cycle_count=94`, final checkpoint `cycle_093/phase2-3e5f918686`.
  The strict audit batch remained alive and had reached candidate `7/12`
  immediately after the stop. Next continuation, if desired, should resume from
  those final parquet checkpoints rather than restarting from worker_01.
- strict batch completion:
  `strict_exposure_batch_report.json` completed 12/12 candidates. All remain
  `HOLD_RESEARCH`; no commercial edge claim is allowed because sector/PIT
  industry neutralization, capacity model, and promotion-grade survivorship
  policy remain unresolved.
- strict survivors for next human review:
  `v2cand-0b002337b1bb` kept strong IC after exposure residualization
  (`strict_ic=0.038570`, residual IC `0.034238`, delta `-0.004332`), with
  cost-adjusted primary spread about `0.002701` and turnover about `0.182176`.
  `v2cand-c15df6ea6021` also remained relatively clean (`strict_ic=0.027384`,
  residual IC `0.023993`, delta `-0.003391`, spread about `0.002000`,
  turnover about `0.214136`). `v2cand-a6a0520a5c2f` is balanced and residual
  improves (`strict_ic=0.011135`, residual IC `0.013922`, spread about
  `0.001556`) but turnover is high at about `0.680498`.
- secondary candidates:
  `v2cand-192eff278bfa` and `v2cand-9f4cc162c00c` have low but residual-improving
  IC with high turnover; useful as structure references, not promotion
  candidates. `v2cand-ae1e92f81a2d` has weak raw primary IC (`0.007775`) but
  residual improves to `0.010755`; keep as watch only.
- demotions:
  `v2cand-9c525090b79f`, `v2cand-7493cba22788`, `v2cand-9ea8b6e76bd9`,
  `v2cand-f38444908624`, `v2cand-37cbd5f6e832`, and
  `v2cand-9d437531f65c` all triggered material IC weakening after exposure
  residualization or non-positive primary spread. In particular
  `v2cand-9ea8b6e76bd9` raw IC `0.058040` fell to residual IC `0.011618`, so it
  should not be treated as a true edge without further decomposition.
- next morning action:
  review the formulas for `0b002337b1bb`, `c15df6ea6021`, and `a6a0520a5c2f`;
  decide whether to run a focused expansion from the first two plus a
  turnover-reduced variant search for `a6`, or first find a PIT stock-level
  industry map for true neutralization.

2026-05-02 sleep-time focused expansion:

- user intent:
  user clarified that the sleep window should keep the machine doing useful
  work, not merely record a plan. Given free memory was only about `3GB`, the
  correct allocation is one compact focused search, not more multi-worker
  broad search.
- objective file:
  `reports/PHASE2_SURVIVOR_FOCUSED_EXPANSION_OBJECTIVE_2026-05-02.json`.
- active worker:
  `runtime/next_stage_artifacts/phase2-survivor-focused-expansion-20260502-worker_01`.
- start root:
  `runtime/next_stage_artifacts/phase2-next-sortino-memory-broad-search-20260501-b6-exposure-clean-soft-prior-worker_02/cycle_071/phase2-613dbec1b1`.
- search role:
  focused expansion around strict/exposure survivors `v2cand-0b002337b1bb`
  and `v2cand-c15df6ea6021`, plus turnover-reduced structural variants of
  `v2cand-a6a0520a5c2f`. The objective is a soft routing/reward bias, not
  formula locking.
- parameters:
  one worker only, `min_runtime_hours=8`, `flow_length=1`, `rounds=8`,
  `per_lane_budget=5`, `artifact_profile=compact`,
  `max_continuation_seeds=100`, `auto_replay_top_k=8`,
  `auto_replay_parallel_workers=1`, excluding the four 24h broad roots,
  completed b6/cold broad roots, and stopped parquet roots from replay memory.
- health:
  worker reached `cycle_001`; generation child was alive; free memory after
  launch was about `2.86GB`. If memory drops below about `1.5GB`, stop this
  worker with a `STOP` marker rather than starting any other work.
- aggressive chain supervisor:
  the earlier single-follow-up supervisor was stopped and replaced with
  `runtime/next_stage_artifacts/phase2-survivor-focused-expansion-20260502-worker_01/aggressive_chain_supervisor.ps1`
  (PID `4328`). It is intentionally sequential, not parallel, because free
  memory is still only about `2.6GB`. It watches worker_01, reads each finished
  worker's `final_previous_run_root`, and then launches the next worker only
  after the memory gate is satisfied.
- planned chain:
  after worker_01 completes, launch
  `phase2-survivor-focused-expansion-20260502-worker_02` for `10h` with
  `rounds=10`, `per_lane_budget=6`, `max_continuation_seeds=140`,
  `auto_replay_top_k=10`, memory gate `>=2.6GB`; then launch
  `phase2-survivor-focused-expansion-20260502-worker_03` for `10h` with
  `max_continuation_seeds=160`, memory gate `>=2.6GB`; finally launch
  `phase2-survivor-focused-expansion-20260502-worker_04_broad_escape` for `6h`
  with a broader escape role, memory gate `>=3.2GB`.
- current chain health:
  aggressive supervisor log shows `aggressive_chain_started` and is watching
  worker_01. Worker_01 is around `cycle_018`, elapsed about `0.72h`, with
  latest checkpoint
  `cycle_017/phase2-8220deebd7`; free memory was about `2.66GB`.

2026-05-02 post-wake aggressive fan-out:

- user freed memory by closing a game; free memory rose to about `7.53GB`.
- kept the existing survivor chain alive. `worker_01` had completed
  `8.03h` / `215` cycles and the supervisor launched
  `phase2-survivor-focused-expansion-20260502-worker_02`, which was around
  `cycle_049` at the fan-out check.
- launched two additional independent compact lines:
  `phase2-aggressive-extra-broad-20260502-worker_01_from_cold90` from
  cold-broad `cycle_090/phase2-79f78f2f08`, and
  `phase2-aggressive-extra-parquet-escape-20260502-worker_01_from_wide92`
  from parquet-wide `cycle_092/phase2-378e44f046`.
- both extra lines use compact artifacts, `flow_length=1`, local replay
  exclusion against prior major roots and survivor workers, and
  `auto_replay_parallel_workers=1` to preserve the serial shared-expression
  cache while three search lines are active.
- acceleration notes were recorded in
  `reports/PHASE2_ACCELERATION_CONFIG_2026-05-02.md`: Torch CUDA is available
  on `NVIDIA GeForce GTX 1650`, but current Phase2 runtime is mostly pandas
  expression/backtest/replay bound. CUDA is useful for Phase3 policy training
  (`--device cuda:0` / `auto`) but not a direct fix for the current replay
  bottleneck.
- more aggressive microburst fan-out:
  user asked whether the 3-line setup was still too small. With free memory
  around `5.79GB`, two extra compact microburst workers were launched while
  keeping replay top-k small:
  `phase2-aggressive-microburst-b6-20260502-worker_01_from_b6_071` from
  b6/exposure `cycle_071/phase2-613dbec1b1`, and
  `phase2-aggressive-microburst-parquet-b6-20260502-worker_01_from_b6_093`
  from parquet-b6 `cycle_093/phase2-3e5f918686`. Both use `min_runtime_hours=4`,
  `flow_length=1`, `rounds=6`, `per_lane_budget=4`,
  `artifact_profile=compact`, `max_continuation_seeds=80`,
  `auto_replay_top_k=4`, and `auto_replay_parallel_workers=1`.
- five-line health:
  after the two microbursts started, total free memory was about `4.76GB`.
  All five lines had heartbeats: survivor worker_02 around `cycle_051`,
  cold90 extra around `cycle_002`, wide92 extra around `cycle_003`, and both
  b6 microbursts entering `cycle_001`. This is the current aggressive ceiling;
  adding more lines before any of these complete risks synchronized replay
  memory pressure.
- generation-only scout escalation:
  user asked for even more aggressive search. Rather than adding more
  replay-heavy workers, two generation-only scouts were launched with
  `auto_replay_top_k=0` so they expand formula space first and defer A-share
  replay/strict validation to a later batch. The scouts are
  `phase2-aggressive-generation-scout-20260502-worker_01_from_strong247` from
  20260430 strong-seed escape `cycle_247/phase2-ba3f05ba48`, and
  `phase2-aggressive-generation-scout-20260502-worker_02_from_wide244` from
  20260430 old-wide reset `cycle_244/phase2-7398bcb003`.
- seven-line health:
  both scouts started and wrote heartbeats at `cycle_001`; free memory after
  launch was about `5.25GB`. The active setup is now 5 replaying/searching
  lines plus 2 generation-only scouts. Next validation action should batch
  replay scout outputs after one or more replay-heavy lines finish, not add
  more immediate replay workers.
- CPU utilization follow-up:
  a later CPU sample showed the 7-line setup using about `78-88%` total CPU,
  with free memory about `6.21GB`; this confirmed the scout lines had started
  using cores effectively. One additional generation-only scout was launched:
  `phase2-aggressive-generation-scout-20260502-worker_03_from_light221`, from
  20260430 light-fresh worker_01 `cycle_221/phase2-d393eb1800`, with
  `min_runtime_hours=4`, `flow_length=1`, `rounds=8`, `per_lane_budget=5`,
  `artifact_profile=compact`, `max_continuation_seeds=100`, and
  `auto_replay_top_k=0`.
- eight-line health:
  the new light221 scout wrote heartbeat at `cycle_001`; memory remained about
  `5.61GB`. CPU utilization is expected to fluctuate by phase, so do not add
  more scouts unless a follow-up sample shows sustained low CPU with memory
  still above about `4GB`.

2026-05-04 stock-PIT contamination cleanup and next-search definition:

- confirmed the 2026-05-01 to 2026-05-04 sector-panel lineage is not valid
  stock-level evidence and must not be used as stock-PIT replay exclusion or
  stock-PIT space-memory exclusion.
- committed dataset-role quarantine for replay, reward, and continuation space
  memory:
  - `5b21ccb phase2 quarantine sector panel memory`
  - `1315532 phase2 scope space memory by dataset role`
- chain smoke found and fixed a real parquet-window bug: `infer_real_data_windows`
  was still using `pd.read_csv(path)` and failed on the stock-PIT parquet default.
  The function now reads parquet date columns with `pd.read_parquet`.
- stock-PIT chain smoke passed on
  `phase2_stock_validation_slice_2026-04-27.parquet`: `12` generated candidates,
  `6` validated, `0` unsupported, `after_open`, `feature_lag_days=0`,
  `execution_lag_days=1`, tradability filter available, and entry-tradability IC
  exclusions observed.
- next large-search spec is defined in
  `reports/PHASE2_CLEAN_STOCK_PIT_CHAIN_AUDIT_AND_NEXT_SEARCH_2026-05-04.md`:
  primary stock-PIT generator slice has `31314` candidates, planned as `16`
  shards of about `2000` candidates, with `top_bottom_quantile=0.05`,
  `recent_quarter_window_count=2`, no sector root inheritance, and
  `search_memory_dataset_role=stock_pit_panel`.

2026-05-04 clean stock-PIT large search launch:

- started rolling supervisor at
  `runtime/next_stage_artifacts/phase2-clean-stock-pit-large-search-20260504-launch`.
- launched `16` total stock-PIT shards with `4` active workers under current
  memory conditions; initial active shards are `00`-`03`, queued shards are
  `04`-`15`.
- each shard validates about `2000` candidates from the clean
  `31314`-candidate stock-PIT forward-first parameter slice.
- launch contract: `after_open`, `feature_lag_days=0`, `execution_lag_days=1`,
  `top_bottom_quantile=0.05`, `recent_quarter_window_count=2`, entry
  limit/suspension masks active where available.
- report:
  `reports/PHASE2_CLEAN_STOCK_PIT_LARGE_SEARCH_LAUNCH_2026-05-04.md`.
- runtime throttle: initial `4` active workers pushed free RAM to about `0.48GB`,
  so the first supervisor was stopped, shards `02`/`03` were terminated before
  material validation progress, shards `00`/`01` remain running, and a tail
  supervisor at
  `runtime/next_stage_artifacts/phase2-clean-stock-pit-large-search-20260504-tail-max2`
  is waiting for shard `00`/`01` pids before continuing shard `02`-`15` with
  `max_active=2`. Total candidate coverage is unchanged; concurrency was reduced
  to avoid Windows paging.
- additional unreached-space deployment: launched
  `phase2-stock-pit-unreached-shape-liquidity-20260504` to cover
  shape/location, gap-state, liquidity-state, volatility-curve, and
  momentum-gated residual formula regions not directly targeted by the main
  forward-first shard schedule. It uses stock-PIT, `after_open`, T+1,
  `top_bottom_quantile=0.02`, `8` shards, and `max_active=1` so it consumes
  spare resources without overwhelming the main search. Report:
  `reports/PHASE2_STOCK_PIT_UNREACHED_SEARCH_LAUNCH_2026-05-04.md`.
2026-05-06 A-share state fresh search definition:

- current clean stock-PIT survivor board remains `stockpit-ff-f39415102d09`,
  `stockpit-ff-7ac4c3264a5e`, `stockpit-ff-4d93ccb3a77f`, and
  `stockpit-ff-24d31e152c88`.
- unreached top17 is held in memory but not promoted: 20bps long-only
  execution audit had no policy with Sortino >= 1.
- added a fresh stock-PIT A-share state search lane without changing the core
  reusable searcher:
  `src/our_system_phase2/services/stock_pit_ashare_state_search.py`,
  `src/our_system_phase2/runtime/stock_pit_ashare_state_search_worker.py`,
  and
  `src/our_system_phase2/runtime/stock_pit_ashare_state_search_supervisor.py`.
- the new lane targets after-open A-share state transitions around prior
  limit-up/down pressure proxies, open-gap confirmation, prior range location,
  volume/amount/turnover pressure, momentum curve, and volatility curve.
- limit-up/down flags are explicitly not used as formula features; they remain
  validation/execution tradability filters only.
- smoke on the stock-PIT validation slice produced `27866` candidates over
  `16` shards, about `1742` candidates per shard, with no `$is_limit_up` or
  `$is_limit_down` expression references.
- report:
  `reports/PHASE2_ASHARE_STATE_FRESH_SEARCH_2026-05-06.md`.
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "ashare_state_ledger or forward_first_large_search"`
  passed `2 passed, 165 deselected`.

2026-05-06 A-share state execution audit follow-up:

- froze the first 50 fine256 A-share state shards into top20 review under
  `runtime/next_stage_artifacts/phase2-ashare-state-top20-audit-20260506`.
- predev holdout (`2025-04-01` to `2025-08-08`) showed real raw predictive
  strength: `20/20` positive long-only Sortino, `14/20` Sortino >= `2`,
  and `20/20` positive rank IC.
- daily topN long-only execution at `20bps` failed because average turnover
  was about `0.956807`; best net Sortino was only `0.155665`.
- low-turnover execution audit added fixed rebalance, keep-buffer, T+1,
  limit-up buy block, and limit-down/suspension sell block handling. Predev
  improved to `15/240` rows with 20bps net Sortino >= `1`, best `1.362095`.
- non-overlapping cross-slice check (`2025-04-01` to `2025-08-08`,
  `2025-10-01` to `2025-12-31`, `2026-01-01` to `2026-04-17`) found
  `61/240` candidate-policy-scenario rows positive in all slices, but none
  with Sortino >= `1` in all slices. Decision remains `HOLD_RESEARCH`, not
  commercial proof.
- next target: continue A-share state search with reward tied to low-turnover
  executable performance and add timestamp-safe limit-event fields where the
  local stock-PIT data supports them.
- implemented the timestamp-safe limit-event field layer in the reusable
  evaluator: `limit_up_event`, `limit_down_event`, `limit_up_streak`,
  `limit_down_streak`, `limit_up_break`, `limit_down_repair`,
  `limit_flip_up_to_down`, and `limit_flip_down_to_up`. These are full-day
  fields and are lagged by `1` under `after_open`.
- extended the A-share state generator to search prior limit-event interactions
  without raw `$is_limit_up`/`$is_limit_down` references. New full space is
  `60830` candidates; fine256 shard0 has `238` candidates, `129` using prior
  limit-event features, raw `$is_limit_*` references `0`.
- validation smoke on `32` candidates had `0` unsupported; targeted tests
  passed `3 passed, 165 deselected`.
- launched event-field large search at
  `runtime/next_stage_artifacts/phase2-ashare-event-field-large-search-20260506-fine256-max2`:
  `256` shards, `max_active=2`, clean stock-PIT validation slice,
  `top_bottom_quantile=0.02`, `recent_quarter_window_count=2`,
  `recent_warmup_days=60`. Initial shard `00` and `01` each have `238`
  candidates, about half using prior limit-event fields. Keep concurrency at
  `2` unless memory stays comfortably above about `4GB` after several shard
  completions.

2026-05-07 overnight event-field search escalation:

- the initial event-field search completed shards `00`-`19` with `0` failures.
  It was stopped after confirming memory recovered, and a higher-throughput
  overnight continuation was launched from shard `20`.
- new launch root:
  `runtime/next_stage_artifacts/phase2-ashare-event-field-large-search-20260507-resume20-max4`.
- continuation contract: shards `20`-`255`, `max_active=4`,
  clean stock-PIT validation slice, `top_bottom_quantile=0.02`,
  `recent_quarter_window_count=2`, `recent_warmup_days=60`,
  `parallel_workers=1`.
- health after launch: running shards `20`-`23`, failed `0`, queued `232`,
  free memory about `7.7GB` after data load.
- completed `00`-`19` board before sleep:
  - all-candidate top: `stockpit-as-f98a725b0ff7`, family
    `range_repair_x_turnover_surge`, Sortino `5.4889`, return `0.001615`,
    IC `0.020641`;
  - event-field top: `stockpit-as-2f7e90bffd4c`, family
    `limit_down_streak_x_momentum_curve`, Sortino `2.041797`,
    return `0.00242`, IC `0.007019`;
  - other event-field leaders cluster around `limit_down_repair` and
    `limit_down_streak` crossed with volatility/volume/amount surge.

2026-05-07 PIT trend-state adapter:

- user rejected HMM integration for this layer; implementation is deterministic
  trend-state proxy fields only.
- added a pluggable, default-off trend-state feature adapter in
  `market_regime_state.py`: `market_trend_eff`, `market_trend_state`,
  `market_breadth_state`, `market_vol_state`, `stock_trend_eff`,
  `stock_trend_state`, `stock_trend_slope`, and
  `stock_price_position_state`.
- fields are computed from same-date completed daily bars only and are treated
  as full-day fields by the evaluator, so `after_open` validation lags them by
  one trading day before formula evaluation.
- batch validation now supports explicit
  `enable_trend_state_features`; ledgers must opt in through
  `recommended_validation_kwargs`, preserving portability of the core search
  runtime.
- A-share state-search v2 can use stock self-trend atoms and market trend /
  breadth gates without raw HMM state or trained posterior probabilities.
- smoke: fine256 shard0 now has `511` records from a `130716` full space, with
  `264` shard0 records using PIT trend-state fields; trend fields are enabled
  explicitly in that ledger's validation kwargs.
- verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_market_regime_state.py tests/test_phase2_v21_runtime.py -k "field_encoder or market_regime_state or stock_pit_ashare_state_ledger or after_open_clock or trend_state"`
  passed `10 passed, 163 deselected`.

2026-05-07 search checkpoint/quarantine:

- status check near 19:00 found the old
  `phase2-ashare-event-field-large-search-20260507-resume20-max4` supervisor
  had continued after the trend-state code change.
- shards `20`-`163` are the old no-trend event-field space
  (`237`/`238` evaluated candidates per shard).
- shards `164`-`171` had already switched into the new v2 trend-state space
  (`510` evaluated candidates per shard) inside the old root name; do not merge
  them into the old v1 board.
- shards `172`-`175` were running in the same v2-mixed state when checked; the
  supervisor pids were stopped to prevent launching queued shards `176`-`255`,
  while active workers were left to finish naturally.
- decision: quarantine the root into `v1_no_trend_baseline` (`20`-`163`) and
  accidental `v2_warm_start_smoke` (`164`-`175` if completed). The next clean
  primary search should use a new v2 launch root.

2026-05-07 clean replay and low-turnover execution review:

- created fixed review root:
  `runtime/next_stage_artifacts/phase2-ashare-v2-trend-state-review-20260507`.
- fixed `28` candidates from the quarantined mixed root into
  `candidate_review_ledger.json`: v2 positive-IC trend, v2 weak-IC risk
  controls, v1 no-trend baselines, and v1 event-field leaders. v2 mixed-root
  candidates are marked warm-start/replay evidence, not clean discovery.
- clean replay on three stock-PIT slices:
  - predev holdout: `28/28` evaluated, `0` unsupported, `9` with long Sortino
    >= `2`, `17` >= `1`, `20` positive IC;
  - validation: `28/28` evaluated, `0` unsupported, `24` with long Sortino >=
    `2`, `28` >= `1`, `24` positive IC;
  - forward shadow: `28/28` evaluated, `0` unsupported, `3` with long Sortino
    >= `2`, `20` >= `1`, `22` positive IC.
- cross-slice replay: `24/28` candidates had positive Sortino in all three
  slices, `15/28` had Sortino >= `1` in all three, and `2/28` had Sortino >=
  `2` in all three.
- low-turnover long-only execution audit on the selected `12` cross-slice
  candidates used T+1, limit-up/suspension buy block, limit-down/suspension
  rebalance sell block, keep-buffer scenarios, and `10/20/30bps` cost grid.
- at `20bps`, `11/12` candidates had positive net Sortino and positive net mean
  across all three slices; `2/12` exceeded net Sortino `1` in all three slices:
  - `stockpit-as-b0e015f8501e` (`limit_down_pressure_x_turnover_surge`, v1
    baseline): best net Sortino `1.530` predev, `1.616` validation, `1.349`
    forward; best forward policy `top50/r10_keep5x`, mean turnover about
    `0.104`.
  - `stockpit-as-8c8d363e0667` (`limit_down_pressure_x_turnover_surge` with
    `market_breadth_state` gate, v2 warm-start): best net Sortino `1.124`
    predev, `1.997` validation, `1.400` forward; best forward policy
    `top50/r5_keep3x`, mean turnover about `0.191`.
- decision remains `HOLD_RESEARCH`: promising executable edge candidates exist,
  but no commercial edge claim until a clean v2 primary search root and
  promotion-grade OOS/capacity/exposure review are complete.
- launched clean v2 primary trend-state search root:
  `runtime/next_stage_artifacts/phase2-ashare-v2-trend-state-primary-search-20260507-max4`.
  Contract: `256` shards, `max_active=4`, clean stock-PIT validation slice,
  `after_open`, T+1, `top_bottom_quantile=0.02`,
  `recent_quarter_window_count=2`, `recent_warmup_days=60`,
  `enable_trend_state_features=True` through the v2 ledger. Initial running
  shards: `00`-`03`.

2026-05-08 company compute node expansion:

- Hermes reverse-tunnel company PC was promoted from connectivity test to a
  real Phase2 CPU worker. Verified host/user: `DESKTOP-7877972`,
  `desktop-7877972\edy`; CPU `i5-14400`, `16` logical processors, about
  `34GB` RAM. No usable NVIDIA GPU was detected, so treat it as a CPU node.
- installed Python `3.11.9` at `D:\Python311`, created worker venv at
  `D:\HermesWorker\workspace\.venv`, and installed the core pandas/numpy/scipy
  worker dependency set.
- synchronized `src`, the clean stock-PIT validation slice, and the A5 archive
  used by `infer_real_data_windows`. `subst G: D:\HermesWorker\GDrive` is
  required in company jobs so the A5 path resolves consistently with the home
  machine.
- environment parity smoke passed on company PC:
  `a5_observed_windows` matched local, candidate-space size matched local
  (`130716`), and the first shard candidate ids matched local.
- launched independent tail search on company PC:
  `D:\HermesWorker\runtime\company-v2-tail-search-20260508-shards128-256`,
  job id `cb69e29bc46eed28`, shards `128`-`255`, `max_active=4`, same clean v2
  stock-PIT/trend-state contract as the home primary search.
- latest company status: running shards `128`-`131`, completed `0`, failed `0`,
  queued `132`-`255`. The compute queue is occupied by this long job, so status
  checks should use direct SSH file reads rather than submitting another compute
  job.
- latest home primary status: completed `76/256`, running shards `76`-`79`,
  failed `0`, queued `80`-`255`. Current clean-v2 board has `38836` evaluated
  candidates, `37` with Sortino >= `5`, `303` with IC >= `0.05`, and `37`
  passing joint Sortino >= `4` plus IC >= `0.045`.
- merge rule: company tail results are independent acceleration output. Before
  promotion, aggregate by `(shard_id, candidate_id)` and deduplicate against
  the home primary root; if the home run reaches shard `128`, duplicated tail
  shards must be treated as redundant confirmations, not extra discoveries.

2026-05-08 validation acceleration sidecar:

- diagnosed the clean v2 search bottleneck: the run is using a short recent
  two-quarter validation window, not full history, but each shard still
  evaluates about `511` expressions over `679556` stock-PIT rows. Recent home
  shards took about `68` minutes per shard with `parallel_workers=1`.
- benchmarked the validation path on shard `91`: loading the panel took about
  `32.5s`; expression-independent forward return and tradability mask
  construction took about `0.8s`; individual expression evaluation ranged from
  about `0.7s` to `5.5s`. The main bottleneck remains repeated
  rolling/groupby/rank/residual expression evaluation, not portfolio replay.
- added an opt-in precomputed validation work context:
  `prepare_validation_work_context` and
  `validate_expression_on_loaded_panel_fast_context`. It reuses
  expression-independent forward return, entry/exit tradability masks, and
  quarterly window labels while preserving the same timestamp, T+1, and
  limit-up/down/suspension semantics.
- wired the sidecar through `batch_validate_candidate_ledger(use_fast_context=True)`
  and the A-share worker/supervisor CLI flag `--use-fast-context`. Default
  remains `False`, so active roots and older commands retain baseline behavior.
- equivalence gate:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests/test_phase2_v21_runtime.py -k "fast_context_matches_baseline or stock_pit_ashare_state_ledger or batch_validation_uses_ashare"`
  passed `3 passed, 168 deselected`.
- small real-data benchmark on `24` shard-91 candidates:
  baseline `664.16s`, fast context `178.78s`, about `3.715x` speedup. Top
  candidate and metrics matched exactly in the benchmark output.
- risk boundary: this is safe only as an opt-in new-root path until broader
  equivalence checks pass. Larger accelerations such as `argpartition` top/bottom
  selection, vectorized rank IC, Polars/Numba rolling, or subtree materialization
  must explicitly test tie handling, NaN/min-period behavior, signal clock field
  lags, T+1 execution lag, and tradability mask shifts before replacing the
  baseline evaluator.

2026-05-08 aggressive fast-context full root:

- user approved a more aggressive path as long as the existing baseline roots
  are not modified. Current baseline home root and company tail root remain
  untouched.
- synchronized the fast-context sidecar code to the company PC and verified
  remote compile plus `--use-fast-context` CLI availability.
- launched a full independent fast-context root on the company PC through a
  scheduled task after SSH background process launching proved unreliable:
  `D:\HermesWorker\runtime\company-v2-fast-context-full-search-20260508-max3-gated`.
- launch contract: shards `0`-`255`, `max_active=3`, clean stock-PIT validation
  slice, `after_open`, T+1, `top_bottom_quantile=0.02`,
  `recent_quarter_window_count=2`, `recent_warmup_days=60`,
  `--use-fast-context`, `parallel_workers=1`.
- gate contract: wait for at least `12000MB` free RAM on the company PC, but
  force-start at `2026-05-08 20:30 +08:00` if the gate has not opened. In
  practice, the gate opened at `2026-05-08 18:28 +08:00` with about `20447MB`
  free RAM.
- initial fast root status: running shards `0`-`2`, queued `3`-`255`, failed
  `0`, company free memory about `17411MB` shortly after launch.
- checkpoint deadline: inspect no later than `2026-05-08 20:30 +08:00`. If the
  fast root has failures, compare the failed shard against baseline semantics;
  if it is merely resource pressure, reduce `max_active`; if metrics diverge,
  quarantine this fast root and keep baseline as source of truth.

2026-05-10 maxopt reward/generator upgrade:

- inspected fixed stock-PIT `maxopt` data:
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`.
  It is stock-level, `1,090,783` rows, `6,333` symbols, dates `2025-08-06` to
  `2026-05-08`, with final total/float market-cap fields and conflict flags.
- changed stock-PIT default data preference to `maxopt`, with the old validation
  slice only as fallback.
- added capacity/capital fields to validation loading and marked them as
  full-day fields so `after_open` and `pre_open` validation lags them instead of
  using same-day close-derived values.
- added long-side capacity diagnostics to validation output and a mild
  capacity/coverage plus market-cap-conflict component to the terminal reward
  proxy.
- updated derived `turnover_rate`: when `float_share` exists, validation now uses
  `volume / float_share`; the old rolling-volume proxy is only fallback.
- upgraded RX typed beam generation to use canonical capacity fields only:
  `final_float_market_cap` and `final_total_market_cap` on the maxopt panel.
  Redundant same-source fields are excluded from formula generation and kept for
  diagnostics only.
- real smoke root:
  `runtime\next_stage_artifacts\maxopt_reward_capacity_smoke_20260510`.
  The smoke generated `96` records, `36` cap-aware expressions, and confirmed
  cap fields are lagged in `after_open` validation.
- focused verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests\test_phase2_v21_runtime.py -k "stock_pit"`
  passed `20 passed, 165 deselected`.
- detailed note:
  `reports/PHASE2_MAXOPT_REWARD_GENERATOR_UPGRADE_2026-05-10.md`.

2026-05-10 maxopt next-wave flow freeze:

- deleted outdated untracked 2026-05-09 deployment docs because they still named
  the old validation slice as active data and claimed market-cap/float-share
  fields were missing:
  - `reports/PHASE2_ENGINEERING_CHAIN_CONTRACT_2026-05-09.md`
  - `reports/PHASE2_NEXT_WAVE_DEPLOYMENT_READY_2026-05-09.md`
- renamed the pending approval launcher to:
  `launch_phase2_maxopt_next_wave_pending_approval_20260510.ps1`.
- launcher default is now `-RunMode forward_first`, because the current upgrade
  lives in the `rx_typed_beam` maxopt/capacity generator. `both_sequential`
  now runs RX typed-beam first, then unreached-space.
- frozen current flow in:
  `reports/PHASE2_MAXOPT_NEXT_WAVE_SEARCH_FLOW_2026-05-10.md`.
- machine-readable objective:
  `reports/PHASE2_MAXOPT_NEXT_WAVE_SEARCH_OBJECTIVE_2026-05-10.json`.
- next primary approval command:
  `.\launch_phase2_maxopt_next_wave_pending_approval_20260510.ps1 -Approved -RunMode forward_first`.

2026-05-10 proof-gate suite:

- added repeatable stock-PIT proof suite for:
  searcher A/B, fast-to-strict calibration, and coverage/cluster health.
- new service:
  `src/our_system_phase2/services/stock_pit_proof_suite.py`.
- new CLI:
  `src/our_system_phase2/runtime/stock_pit_proof_suite.py`.
- focused tests:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests\test_phase2_v21_runtime.py -k "stock_pit_search_ab_test or fast_to_strict_calibration or proof_suite"`
  passed `3 passed, 185 deselected`.
- broader stock-PIT verification:
  `G:\PythonProject\.venv\Scripts\python.exe -m pytest -q tests\test_phase2_v21_runtime.py -k "stock_pit"`
  passed `22 passed, 166 deselected`.
- real maxopt proof smoke output:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-smoke-20260510`.
- smoke decision:
  `PASS_RESEARCH_PROOF_GATES_NOT_COMMERCIAL_PROOF`.
- nuance: `rx_typed_beam_no_policy` beat baseline in this tiny equal-budget smoke
  on mean terminal reward, but `rx_typed_beam_ucb` did not beat baseline. UCB is
  therefore not proven yet and should remain an optional exploration scheduler
  until a larger A/B gate says otherwise.
- proof-gate note:
  `reports/PHASE2_STOCK_PIT_PROOF_GATES_2026-05-10.md`.

2026-05-10 medium proof run:

- added launcher:
  `launch_phase2_stock_pit_proof_suite_medium_20260510.ps1`.
- added reproducibility record:
  `reports/PHASE2_STOCK_PIT_PROOF_GATES_MEDIUM_2026-05-10.md`.
- launched background proof run at about `2026-05-10 17:08 +08:00`.
- output root:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510`.
- process chain at launch:
  powershell launcher PID `2416`, Python module process PID `48184`, real Python child PID `25520`.
- run parameters: `128` candidates per variant, strict top `8`, beam width `24`,
  max beam records `512`, `after_open`, T+1, `top_bottom_quantile=0.02`,
  recent `2` quarters, warmup `60` days, strict cost `10bps`.
- expected runtime: roughly `2` to `4` hours under local CPU/memory pressure.
- immediate status: running; no stderr yet; first report files are expected after
  a variant validation stage completes.

2026-05-10 company takeover for medium proof run:

- user requested moving the current local medium proof run to the company PC
  because local resource pressure was too poor.
- direct SSH verified through:
  `ssh -F G:\Chengbo\company-pc-ssh-config.example company-pc-via-hermes-portable`.
- company PC:
  `DESKTOP-7877972`, user `desktop-7877972\edy`, i5-14400, `16` logical
  threads, about `31.6GB` RAM.
- harvested company old search artifacts into:
  `runtime\next_stage_artifacts\company_harvest_20260510`.
  Remote zip source:
  `D:\HermesWorker\runtime\20260510_ashare_company_harvest.zip`.
  Harvest included `661` files, including supervisor statuses, stage1 summaries,
  validation reports, candidate ledgers, and worker logs for completed shards.
- company old searches before stop:
  `company-v2-fast-context-full-search-20260508-max3-gated` had `98`
  completed, `3` running, `3` failed; `company-v2-tail-search-20260508-shards128-256`
  had `117` completed, `4` running, `3` failed.
- after harvest, stopped `18` old company `company-v2-*` Python/Powershell
  processes to free resources. Company free RAM rose to about `19.9GB`, then
  `22.5GB` after sync/settling.
- synchronized only required files and maxopt data to company workspace:
  `D:\HermesWorker\workspace\our_system_phase1_repo` and
  `D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`.
  Remote `py_compile` passed for proof suite service/runtime.
- launched company medium proof run via scheduled task:
  `Phase2ProofMediumCompany20260510`.
  Output root:
  `D:\HermesWorker\runtime\phase2-stock-pit-proof-suite-medium-company-20260510`.
  Process chain confirmed:
  `cmd.exe` PID `25368`, `.venv` Python PID `17964`, real Python PID `21464`.
- company run parameters mirror the local medium proof run:
  `128` candidates per variant, strict top `8`, beam width `24`,
  max beam records `512`, `after_open`, T+1, `top_bottom_quantile=0.02`,
  recent `2` quarters, warmup `60` days, strict cost `10bps`.
- company run has begun producing:
  `ab_test\baseline_forward_first\candidate_ledger.json`; stderr was empty at
  the first post-launch check.
- stopped local medium proof run after company run was confirmed active:
  local PIDs `2416`, `48184`, `25520`. Local partial output remains at
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510`
  and should be treated as abandoned/partial, not evidence.
- next check recommendation: inspect company root in about `60` to `90` minutes,
  or sooner if local CPU/RAM unexpectedly rises.

2026-05-10 company medium proof final:

- company proof run completed with exit code `0`; no active company proof
  processes remained at verification.
- remote final root:
  `D:\HermesWorker\runtime\phase2-stock-pit-proof-suite-medium-company-20260510`.
- pulled final archive to:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-company-20260510\phase2-stock-pit-proof-suite-medium-company-20260510-final.zip`.
- expanded local final root:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-company-20260510\expanded`.
- top-level proof decision:
  `PASS_RESEARCH_PROOF_GATES_NOT_COMMERCIAL_PROOF`.
- proof gates:
  search A/B `PASS_AB_ADVANTAGE_RESEARCH_EVIDENCE`,
  fast-to-strict `PASS_FAST_TO_STRICT_CALIBRATION_SMOKE`,
  coverage `PASS_COVERAGE_CLUSTER_HEALTH`.
- variant summary:
  baseline mean reward `0.223750`, mean IC `-0.000839`, mean long sortino
  `0.737332`, strong long sortino count `7`;
  `rx_typed_beam_no_policy` mean reward `0.339562`, mean IC `0.005766`,
  mean long sortino `1.270762`, strong long sortino count `10`;
  `rx_typed_beam_ucb` mean reward `0.236572`, mean IC `0.003491`,
  mean long sortino `0.678738`, strong long sortino count `0`.
- interpretation: `rx_typed_beam_no_policy` is the clear medium-proof winner.
  UCB is only slightly above baseline by mean reward and clearly loses to no-policy
  RX; keep UCB as exploration-only until a stronger proof says otherwise.
- fast-to-strict calibration: strict top `8`, pass proxy count `8`, pass proxy
  rate `1.0`, Spearman fast reward to strict IC `0.383240`, Spearman fast IC to
  strict IC `1.0`.
- best fast/strict candidate:
  `CSRank(CSResidual(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))),CSRank(Log($final_float_market_cap))))`.
  Strict IC `0.028931`, strict cost-adjusted spread `0.005492`, strict
  cost-adjusted sortino `6.219060`, mean one-way turnover `0.867862`.
- audit decision remains `HOLD_RESEARCH` for commercial use: no strong IC
  breakout under threshold `0.045`, no sector neutralization/capacity/promotion
  grade universe proof yet, and high one-way turnover needs an execution/cost
  model before any capital claim.

2026-05-11 true-limit search bakeoff v2 smoke:

- implemented dedicated runner:
  `src/our_system_phase2/services/stock_pit_true_limit_search_bakeoff_v2.py`
  and CLI:
  `src/our_system_phase2/runtime/stock_pit_true_limit_search_bakeoff_v2.py`.
- original UCB is not in the main budget:
  `DISABLED_PENDING_REDESIGN`.
- accepted smoke output root:
  `runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-smoke2-local-20260511-seed1`.
- first smoke root:
  `runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-smoke-local-20260511-seed1`
  is diagnostic only; its gap/non-gap summary was polluted by a family-name
  parser bug that treated `non_gap` as gap. Code was fixed and smoke2 reran.
- true-limit source verified in all 8 lanes:
  `tdxgp_gpjvalue_15_status==2/-2`; no 9.8 fallback.
- smoke2 contract:
  `32` candidates per lane, strict `top2 + stratified random2`, seed
  `smoke2_seed1_20260511`, after-open, T+1, `10bps`, q `0.02`, recent
  `2` quarters, warmup `60` days.
- lanes:
  simple template, unreached space, RX no-policy true-limit, RX diverse beam,
  typed random dark, non-gap forced sampler, AST evolutionary mutation,
  CEM adaptive grammar.
- main smoke result:
  simple template replay `1`, non-gap replay `1`;
  AST replay `1`, non-gap replay `1`;
  CEM replay `1`, non-gap replay `1`.
  RX/no-policy and unreached had strict passes but no replay pass in this smoke.
- decision:
  `PASS` as search-method smoke only, not commercial proof.
- detailed report:
  `reports\PHASE2_TRUE_LIMIT_SEARCH_BAKEOFF_V2_2026-05-11.md`.
- next target:
  run medium bakeoff with `128` candidates per lane, strict `top8 + stratified
  random4`, `3` seeds, fixed R0 true-limit reward, shadow rewards passive.

2026-05-11 true-limit search bakeoff v2 medium launch:

- added company launcher:
  `launch_phase2_true_limit_search_bakeoff_medium_company_20260511.ps1`.
- synchronized new bakeoff service/runtime/launcher to company PC workspace:
  `D:\HermesWorker\workspace\our_system_phase1_repo`.
- company py_compile passed for the new bakeoff service/runtime using absolute
  remote paths.
- company debug seed completed successfully:
  `D:\HermesWorker\runtime\phase2-true-limit-search-bakeoff-v2-debug-company-20260511`.
- launched medium via Windows Scheduled Task:
  `Phase2TrueLimitBakeoffMedium20260511`.
- remote medium root:
  `D:\HermesWorker\runtime\phase2-true-limit-search-bakeoff-v2-medium-company-20260511`.
- status file:
  `D:\HermesWorker\runtime\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\medium_status.jsonl`.
- medium parameters:
  seeds `1,2,3`, `128` candidates per lane, strict `top8 + stratified random4`,
  after-open, T+1, `10bps`, q `0.02`, recent `2` quarters, warmup `60`.
- first check confirmed seed1 started and is producing:
  `medium_seed1_20260511\cem_internal\cem_round_00_candidate_ledger.json`.
- process check confirmed company Python workers active:
  `.venv` launcher Python plus real Python worker, real worker using about
  `2.98GB` working set after startup.
- next check recommendation:
  inspect in about `45` to `60` minutes for seed1 stage1 progress; full 3-seed
  medium is likely multi-hour.

2026-05-11 03:29 medium bakeoff live check:

- company medium remains active.
- status file still shows seed1 running:
  `seed_started`, output root
  `D:\HermesWorker\runtime\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\medium_seed1_20260511`.
- active company Python processes observed:
  `.venv` launcher Python PID `30456` and real worker PID `16364`.
- seed1 CEM internal rounds completed:
  `cem_round_00_stage1_validation_report.json` and
  `cem_round_01_stage1_validation_report.json`.
- seed1 formal stage1 progress:
  `simple_template` done, `unreached_space` done,
  `rx_no_policy_true_limit` running or pending completion.
- stderr still empty at this check.

2026-05-11 true-limit bakeoff medium final:

- company medium completed successfully; no active company Python worker remained
  at the final check.
- status:
  seed1 finished exit code `0` at `03:51:50 +08:00`;
  seed2 finished exit code `0` at `04:25:52 +08:00`;
  seed3 finished exit code `0` at `04:59:34 +08:00`;
  root status `completed`.
- pulled and expanded final archive locally:
  `runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\phase2-true-limit-search-bakeoff-v2-medium-company-20260511-final.zip`
  and
  `runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\expanded`.
- medium aggregate across `3` seeds, `128` candidates per lane per seed, strict
  `top8 + stratified random4`:
  - `cem_adaptive_grammar`: replay `22`, non-gap replay `22`,
    low-corr strict `8`, replay yield per 100 valid candidates `5.729167`.
  - `ast_evolutionary_mutation`: replay `13`, non-gap replay `13`,
    low-corr strict `6`, replay yield per 100 `3.385417`.
  - `simple_template`: replay `3`, non-gap replay `3`,
    replay yield per 100 `0.781250`.
  - `unreached_space`: replay `3`, non-gap replay `0`;
    still gap-heavy, avg gap share `0.527778`.
  - `non_gap_forced_sampler`: strict `24`, non-gap strict `24`, but replay `0`;
    strong evidence that strict pass alone is not selection-sufficient.
  - `rx_no_policy_true_limit`, `rx_diverse_beam`, and `typed_random_dark`:
    replay `0` in this medium bakeoff.
- interpretation:
  CEM is the clear current winner for replay-useful non-gap discovery, AST is
  second, simple template remains a serious but weaker baseline, and original RX
  lanes should not be treated as current best search under true-limit replay.
- decision:
  `PASS` for search-method bakeoff only; no commercial claim.
- next engineering target:
  promote CEM + AST into the next budget, keep original UCB disabled, and use
  the non-gap forced sampler result to improve replay-aware selection instead of
  trusting strict pass counts alone.

2026-05-11 replay-aware ranker flow:

- structured true-limit bakeoff candidates into replay-training artifacts:
  `data/candidates.parquet` (`3072` rows) and
  `data/replay_results.parquet` (`288` replay rows).
- added builder and leakage manifest:
  `features/build_features.py`,
  `data/candidate_feature_manifest.json`.
- trained first replay-aware tree rankers:
  `data/models/non_gap_replay_pass_ranker.joblib` and
  `data/models/replay_pass_ranker.joblib`.
- leakage guard:
  ranker feature set has no overlap with forbidden replay/strict/shadow columns.
- non-gap replay target:
  grouped OOF baseline `0.131944`, top 5% pass rate `1.000000`,
  lift `7.578947`, AUC `0.953947`, AP `0.875989`.
- shadow selector output:
  `data/replay_selector_shadow.parquet`;
  selected `96` candidates with buckets `58` exploit, `18` lane-floor explore,
  `14` low-corr diversity, `6` overflow.
- fast-to-replay calibration output:
  `data/replay_ranker_calibration_deciles.parquet` and
  `data/replay_ranker_calibration_report.json`.
  `p_non_gap_replay` and final `selection_score` both show top 5% non-gap
  replay pass rate `1.000000` with lift `7.578947` on the internal replay
  sample; `cheap_backtest_rank_ic` only reaches top 5% pass rate `0.200000`,
  so rank IC alone is not a good replay selector here.
- pure RL control artifact:
  `data/pure_rl_selector_shadow.parquet`,
  `data/models/pure_rl_control_policy.joblib`.
  This is explicitly marked
  `premature_shadow_diagnostic_not_formal_ablation`; it is not yet a formal
  pure-RL generator/control group.
- bandit output:
  `data/lane_bandit_state.json`, `data/lane_bandit_allocation.json`;
  example `1024` budget allocation gives CEM `359`, AST `273`, simple template
  `89`, unreached `61`, RX no-policy `71`, RX diverse `66`,
  typed random `53`, non-gap forced `52`.
- report:
  `reports/PHASE2_REPLAY_AWARE_RANKER_FLOW_2026-05-11.md`.
- decision:
  `HOLD_RESEARCH` for commercial/alpha promotion; infrastructure is ready for
  shadow or small-slice live replay A/B, but not for replacing the search/replay
  queue without fresh out-of-sample replay evidence.

2026-05-11 replay-aware slice integration:

- added optional true-limit bakeoff args:
  `--replay-ranker-model-dir` and
  `--replay-aware-slice-n-per-variant`.
- default behavior is unchanged; replay-aware slice is disabled unless requested.
- R0 remains the main decision/control table:
  report field `main_table_scope = r0_control_only`.
- replay-aware candidates are audited as extra capped strict/replay rows tagged
  `selection_policy = replay_aware_shadow_slice`; pure RL does not control the
  main search.
- fixed selector tiny-budget behavior so `selection_budget=1` selects exactly
  one candidate, not one per internal bucket.
- smoke2 output:
  `runtime\next_stage_artifacts\phase2-true-limit-replayaware-smoke2-local-20260511`.
  R0 selected `8`, replay-aware selected `8`, strict rows `16`;
  replay-aware slice replay pass `8`, non-gap replay pass `6`.
- prepared medium local launcher:
  `launch_phase2_true_limit_replayaware_slice_medium_local_20260511.ps1`.
- launched medium local run at `2026-05-11T11:41:05+08:00`:
  `runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511`.
  Parameters: seeds `1,2,3`, candidate budget `64`, strict `top4 + random2`,
  replay-aware slice `2` per lane, R0 control table remains the decision table.
  Status file:
  `runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511\medium_status.jsonl`.
- detailed report:
  `reports\PHASE2_REPLAY_AWARE_SLICE_INTEGRATION_2026-05-11.md`.

2026-05-11 replay-aware slice medium final:

- run completed successfully at `2026-05-11T14:01:39+08:00`; all seeds exit
  code `0`, all seed `stderr.log` files empty.
- root:
  `runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511`.
- R0 control aggregate:
  CEM replay/non-gap replay `13/13`, replay yield per 100 valid `6.770833`;
  AST `6/6`, yield `3.125000`; simple template `3/3`, yield `1.562500`.
  Other lanes had zero replay passes.
- replay-aware slice aggregate:
  CEM replay/non-gap replay `5/5`, AST `1/1`, all other lanes `0`.
  Total slice contribution `6` non-gap replay passes over `48` audited rows.
- decision:
  keep replay-aware selector as a capped additive slice only. It produced useful
  incremental CEM/AST candidates, but it did not beat R0 per audited row and did
  not unlock RX/random/unreached/non-gap-forced.
- detailed result report:
  `reports\PHASE2_REPLAY_AWARE_SLICE_MEDIUM_RESULTS_2026-05-11.md`.

2026-05-11 Phase3 repair audit:

- added audit runtime:
  `src\our_system_phase2\runtime\stock_pit_phase3_repair_audit.py`.
- outputs:
  `reports\PHASE3_REPAIR_AUDIT_2026-05-11.md`,
  `reports\PHASE3_REPAIR_AUDIT_2026-05-11.json`,
  plus pass cluster, pool summary, score decile, failure detail, and scored
  leftover tables.
- independence check:
  raw non-gap replay pass `28` compresses to `8` return-corr clusters and only
  `5` cost/turnover deployable return-corr clusters. CEM count is therefore
  materially inflated by repeated correlated structures.
- slice increment check:
  replay-aware slice was confirmed as `R0_leftover`, not common pool. It added
  `6` non-gap replay passes, across `4` return-corr clusters, but only `2` new
  clusters versus R0. This supports residual-miner status, not budget promotion.
- score decile check:
  all `6` replay-aware non-gap replay passes are in top score decile; deciles
  `2-3` had `8` audited candidates and zero pass; deciles `4-10` were not
  audited, so full monotonicity still needs score-decile random pass-through.
- failure diagnosis:
  `non_gap_forced_sampler` is not failing from gap/turnover; it is mostly
  duplicate/pathology (`corr_duplicate 15/24`, `operator_pathology 23/24`).
  RX lanes fail from mixed duplicate corr, turnover, price-shape/open field
  pathology, and subperiod weakness. `unreached_space` is clear quarantine:
  gap dependency `13/24`, high turnover `24/24`, complexity overfit `17/24`.
- Phase3 definition:
  `phase3_repair = CEM control + AST failure-aware repair + replay-aware
  residual slice`; suggested budget R0/CEM-led `60%`, AST repair `20%`,
  replay-aware residual `10%`, novelty/diagnostic `10%`.

2026-05-11 Phase3A repair implementation:

- primary KPI changed for Phase3A:
  `cost/turnover deployable unique clusters / audited`.
  Raw non-gap replay pass is diagnostic only.
- added service/runtime:
  `src\our_system_phase2\services\stock_pit_phase3_repair.py`,
  `src\our_system_phase2\runtime\stock_pit_phase3_repair.py`.
- CEM elite update now applies inverse-sqrt structural cluster downweight:
  `fast_reward / sqrt(structural_cluster_count)`.
- Phase3A selector implements:
  R0/CEM-led cluster quota, AST `duplicate_escape` +
  `operator_sanitize`, replay-aware residual decile pass-through, and
  quarantine diagnostic budget.
- added launcher:
  `launch_phase3A_repair_medium_local_20260511.ps1`.
- smoke2 root:
  `runtime\next_stage_artifacts\phase3A-repair-smoke2-local-20260511`.
  Smoke primary deployable unique clusters `6/16`, unique return-corr clusters
  `10/16`, top cluster raw pass share `0.214286`. Smoke validates wiring, not
  promotion.
- launched Phase3A medium local at `2026-05-11T15:37:31+08:00`:
  `runtime\next_stage_artifacts\phase3A-repair-medium-local-20260511`.
  Seeds `1,2,3`, candidate budget `64`, strict audit budget `64`, KPI
  `deployable_unique_clusters_per_audited`.
  Status file:
  `runtime\next_stage_artifacts\phase3A-repair-medium-local-20260511\medium_status.jsonl`.
- detailed implementation report:
  `reports\PHASE3A_REPAIR_IMPLEMENTATION_2026-05-11.md`.
