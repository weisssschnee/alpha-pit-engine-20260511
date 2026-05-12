# Phase2 True-Limit Search Bakeoff V2

Date: 2026-05-11

## Objective

Compare search lanes by replay-useful, low-corr, non-gap, cost-survived alpha under the fixed true-limit evaluator.

This run does not promote commercial factors. It is a search-method smoke proof.

## Fixed Contract

- evaluator: TDXGP true-limit preferred
- limit source observed: `tdxgp_gpjvalue_15_status==2/-2`
- fallback 9.8 limit flags: not used in the accepted smoke
- signal clock: `after_open`
- execution: T+1
- feature lag: evaluator field-lag contract, no whole-expression lag
- reward used for selection: `R0_current_true_limit`
- shadow rewards: recorded only, not used for selection
- cost: `10bps`
- top/bottom quantile: `0.02`

## Implemented Runner

- service: `src/our_system_phase2/services/stock_pit_true_limit_search_bakeoff_v2.py`
- CLI: `src/our_system_phase2/runtime/stock_pit_true_limit_search_bakeoff_v2.py`
- original UCB state: `DISABLED_PENDING_REDESIGN`
- old 9.8 results: quarantined for true-limit review

Implemented lanes:

- S0 `simple_template`
- S1 `unreached_space`
- S2 `rx_no_policy_true_limit`
- S3 `rx_diverse_beam`
- S4 `typed_random_dark`
- S5 `non_gap_forced_sampler`
- S6 `ast_evolutionary_mutation`
- S7 `cem_adaptive_grammar`

S8 QD/MAP-Elites is implemented as optional `--include-qd`, not used in this smoke.

## Smoke Command

```text
$env:PYTHONPATH='src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.stock_pit_true_limit_search_bakeoff_v2 --dataset-path G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet --output-root runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-smoke2-local-20260511-seed1 --candidate-budget 32 --target-window-count 8 --max-window 40 --beam-width 24 --max-beam-records 512 --strict-top-n-per-variant 2 --stratified-random-n-per-variant 2 --top-bottom-quantile 0.02 --recent-quarter-window-count 2 --recent-warmup-days 60 --strict-cost-bps 10 --low-corr-threshold 0.80 --turnover-survival-max-one-way 0.75 --seed smoke2_seed1_20260511
```

Output root:

```text
runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-smoke2-local-20260511-seed1
```

## Smoke Main Table

| variant | valid | strict | low-corr strict | non-gap strict | replay | non-gap replay | cost survived | turnover survived | gap share | max cluster | replay yield / 100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| simple_template | 32 | 2 | 2 | 1 | 1 | 1 | 2 | 3 | 0.25 | 0.25 | 3.125 |
| unreached_space | 32 | 2 | 2 | 0 | 0 | 0 | 2 | 0 | 0.50 | 0.25 | 0.000 |
| rx_no_policy_true_limit | 32 | 2 | 1 | 0 | 0 | 0 | 2 | 0 | 0.50 | 0.50 | 0.000 |
| rx_diverse_beam | 32 | 1 | 1 | 0 | 0 | 0 | 2 | 3 | 0.50 | 0.25 | 0.000 |
| typed_random_dark | 32 | 1 | 1 | 0 | 0 | 0 | 2 | 3 | 0.25 | 0.50 | 0.000 |
| non_gap_forced_sampler | 32 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0.00 | 0.50 | 0.000 |
| ast_evolutionary_mutation | 32 | 1 | 1 | 1 | 1 | 1 | 1 | 3 | 0.00 | 0.25 | 3.125 |
| cem_adaptive_grammar | 32 | 2 | 2 | 2 | 1 | 1 | 2 | 4 | 0.00 | 0.25 | 3.125 |

## Accepted Smoke Decision

`PASS`, but only as a search-method smoke.

Pass reasons:

- `ast_evolutionary_mutation_low_corr_strict_survivor`
- `ast_evolutionary_mutation_non_gap_replay_pass_gt_0`
- `cem_adaptive_grammar_low_corr_strict_survivor`
- `cem_adaptive_grammar_non_gap_replay_pass_gt_0`

Hold reasons:

- `rx_diverse_beam_strict_without_replay`
- `rx_no_policy_true_limit_strict_without_replay`
- `typed_random_dark_strict_without_replay`
- `unreached_space_strict_without_replay`

## Notable Survivors

- `simple_template`: `CSRank($close)`, non-gap replay pass, strict IC `0.014278`, cost-adjusted spread `0.004237`, replay long-only Sortino `1.409699`.
- `ast_evolutionary_mutation`: `CSRank(ZScore(CSRank($close)))`, non-gap replay pass, strict IC `0.014278`, cost-adjusted spread `0.004237`, replay long-only Sortino `1.409699`.
- `cem_adaptive_grammar`: `Neg(CSRank(CSResidual(CSRank(Delta($close,3)),CSRank(Delta($close,8)))))`, non-gap replay pass, strict IC `0.014427`, cost-adjusted spread `0.001607`, replay long-only Sortino `1.098366`.

## Interpretation

- True-limit correction did not kill the whole search flow, but it weakened gap-led lanes at replay.
- Original RX/no-policy and unreached still find strict IC in gap-like space, but those candidates did not replay-pass in this smoke.
- AST and CEM are worth medium testing because they produced non-gap, low-corr replay survivors under the fixed R0 reward.
- The strongest smoke survivor is still simple price-level/rank-like; this is not enough for commercial proof and may be regime-dependent.
- Do not restore original UCB to the main budget until a redesigned cluster-aware UCB beats these lanes on replay, non-gap, and low-corr metrics.

## Next Action

Run medium bakeoff with the same fixed contract:

- candidates: `128 / variant`
- strict: `top8 + stratified random4 / variant`
- seeds: `3`
- keep shadow rewards passive
- optional: enable `--include-qd` only if machine memory is stable

Decision after medium:

- If AST/CEM keep non-gap replay pass and low-corr strict across seeds, scale them.
- If simple template remains equal/better, shift attention from search complexity to reward/replay calibration.
- If random/unreached discovers replay candidates missed by topK, increase random pass-through and repair R0 selection.

## Medium Company Final

Remote root:

```text
D:\HermesWorker\runtime\phase2-true-limit-search-bakeoff-v2-medium-company-20260511
```

Local archive:

```text
runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\phase2-true-limit-search-bakeoff-v2-medium-company-20260511-final.zip
```

Local expanded root:

```text
runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\expanded
```

Run finished successfully:

- seed1 exit code `0`, finished `2026-05-11 03:51:50 +08:00`
- seed2 exit code `0`, finished `2026-05-11 04:25:52 +08:00`
- seed3 exit code `0`, finished `2026-05-11 04:59:34 +08:00`
- company Python processes were gone after final check

Medium parameters:

- seeds: `1,2,3`
- candidates: `128 / lane / seed`
- strict selection: `top8 + stratified random4 / lane / seed`
- strict audited rows: `36 / lane` across 3 seeds
- valid candidates: `384 / lane` across 3 seeds
- evaluator: TDXGP true-limit
- signal/execution: after-open + T+1
- cost: `10bps`

Aggregate medium result:

| variant | valid | strict | low-corr strict | non-gap strict | replay | non-gap replay | cost survived | turnover survived | avg gap share | replay yield / 100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cem_adaptive_grammar | 384 | 16 | 8 | 14 | 22 | 22 | 24 | 31 | 0.111111 | 5.729167 |
| ast_evolutionary_mutation | 384 | 15 | 6 | 14 | 13 | 13 | 18 | 26 | 0.027778 | 3.385417 |
| simple_template | 384 | 19 | 13 | 16 | 3 | 3 | 25 | 33 | 0.083333 | 0.781250 |
| unreached_space | 384 | 21 | 9 | 6 | 3 | 0 | 21 | 1 | 0.527778 | 0.781250 |
| non_gap_forced_sampler | 384 | 24 | 8 | 24 | 0 | 0 | 24 | 34 | 0.000000 | 0.000000 |
| rx_no_policy_true_limit | 384 | 6 | 3 | 0 | 0 | 0 | 15 | 18 | 0.194445 | 0.000000 |
| typed_random_dark | 384 | 6 | 3 | 0 | 0 | 0 | 12 | 25 | 0.222222 | 0.000000 |
| rx_diverse_beam | 384 | 2 | 2 | 0 | 0 | 0 | 11 | 24 | 0.083333 | 0.000000 |

Medium interpretation:

- CEM is the clear medium winner on the actual target metric: replay-useful non-gap alpha.
- AST is second and also stable: non-gap replay pass in all 3 seeds.
- Simple template is still a real baseline, but its replay count is far below CEM/AST.
- Unreached keeps finding strict pass rows, but replay contribution is gap-led and non-gap replay is `0`.
- Non-gap forced sampler finds many strict non-gap rows, but replay `0`; this is useful evidence that strict pass alone is not enough.
- RX no-policy / RX diverse / typed random under this fixed true-limit contract did not produce replay pass rows.

Decision:

- `PASS` for search-method bakeoff.
- `commercial_claim_allowed = false`.
- Promote CEM and AST into the next search budget.
- Keep original UCB disabled until it is redesigned and proves replay/non-gap/low-corr value.
