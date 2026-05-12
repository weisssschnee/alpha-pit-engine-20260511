# Phase2 Replay-Aware Ranker Flow - 2026-05-11

## Experiment Record

- date: 2026-05-11
- experiment_id: 20260511_replay_aware_ranker_flow_001
- objective: turn true-limit bakeoff candidates into replay-aware training artifacts, train first replay success rankers, and validate a shadow selector plus lane budget bandit without changing live search selection.
- status: completed
- mode: research
- decision: HOLD_RESEARCH, because this is replay/discovery infrastructure validation, not promotion evidence.

## Inputs

- candidates: data/candidates.parquet (3072 rows)
- replay results: data/replay_results.parquet (288 rows)
- source true-limit reports: 3
- evaluator contract inherited from true-limit bakeoff: TDXGP limit status, after_open signal clock, T+1 execution, 10bps, top/bottom 0.02.

## Commands

```text
G:\PythonProject\.venv\Scripts\python.exe features\build_features.py --input-root runtime\next_stage_artifacts\phase2-true-limit-search-bakeoff-v2-medium-company-20260511\expanded --output-dir data
$env:PYTHONPATH="src"; G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.stock_pit_replay_ranker_flow --candidates-path data\candidates.parquet --replay-path data\replay_results.parquet --output-dir data --selection-budget 96 --bandit-budget 1024 --seed 42
G:\PythonProject\.venv\Scripts\python.exe -m pytest tests\test_candidate_feature_builder.py tests\test_stock_pit_replay_ranker.py -q
git diff --check -- features\build_features.py src\our_system_phase2\services\stock_pit_replay_ranker.py src\our_system_phase2\runtime\stock_pit_replay_ranker_flow.py tests\test_candidate_feature_builder.py tests\test_stock_pit_replay_ranker.py
```

## Leakage Contract

- Ranker feature source: replay-before candidate context plus cheap validation metrics only.
- Forbidden for ranker: strict/replay labels, portfolio replay metrics, strict audit metrics, and shadow rewards.
- Forbidden overlap found: []
- Generated manifest: data/candidate_feature_manifest.json

## Ranker Metrics

### non_gap_replay_pass

- training rows: 288, positives: 38, groups: 75, features: 95
- grouped OOF baseline pass rate: 0.131944; top 5% pass rate: 1.0; lift: 7.578947; AUC: 0.953947; AP: 0.875989
- seed holdout top 5% pass rate: 0.933333; lift: 7.073684; AUC: 0.996; AP: 0.941095
- lane holdout top 5% pass rate: 1.0; lift: 7.578947; AUC: 0.995789; AP: 0.967358

### replay_pass

- training rows: 288, positives: 41, groups: 75, features: 95
- grouped OOF baseline pass rate: 0.142361; top 5% pass rate: 1.0; lift: 7.02439; AUC: 0.961637; AP: 0.885383
- seed holdout top 5% pass rate: 1.0; lift: 7.02439; AUC: 0.997136; AP: 0.975852
- lane holdout top 5% pass rate: 1.0; lift: 7.02439; AUC: 0.978967; AP: 0.926205

## Fast-To-Replay Calibration

- calibration outputs: data/replay_ranker_calibration_deciles.parquet and data/replay_ranker_calibration_report.json
- replay attempted rows: 288; replay pass rows: 41; non-gap replay pass rows: 38
- strict pass rows: 109; non-gap strict pass rows: 74
- `p_non_gap_replay`: top 5% non-gap replay pass rate 1.0, lift 7.578947; decile top-minus-bottom 1.0
- `selection_score`: top 5% non-gap replay pass rate 1.0, lift 7.578947; decile top-minus-bottom 1.0
- `cheap_backtest_fitness`: top 5% non-gap replay pass rate 1.0, lift 7.578947; top 10% 0.965517
- `cheap_backtest_rank_ic`: top 5% non-gap replay pass rate 0.2, lift 1.515789; top 10% 0.103448
- interpretation: rank IC alone is a weak replay selector in this run; replay-aware features and cheap fitness carry most of the ordering signal.

## Pure RL Diagnostic

- output: data/pure_rl_selector_shadow.parquet and data/models/pure_rl_control_policy.joblib
- status: `premature_shadow_diagnostic_not_formal_ablation`
- reason: this is an offline logged-policy diagnostic over the same replay sample, not a fresh pure-RL generator and not an A/B control.
- observed diagnostic lift: `pure_rl_score` top 5% non-gap replay pass rate 0.8, lift 6.063158.
- decision: do not promote pure RL control yet; keep it as a diagnostic feature until the replay-aware selector and bandit have fresh replay outcomes.

## Shadow Selector

- budget: 96; selected: 96
- buckets: {'exploit_ranker_top': 58, 'explore_lane_floor': 18, 'diversity_low_corr': 14, 'overflow_ranker_top': 6}
- generator mix: {'cem_adaptive_grammar': 70, 'ast_evolutionary_mutation': 8, 'simple_template': 3, 'unreached_space': 3, 'rx_diverse_beam': 3, 'rx_no_policy_true_limit': 3, 'non_gap_forced_sampler': 3, 'typed_random_dark': 3}
- known replay-attempted selected: 25; known non-gap replay pass inside those: 25
- interpretation: selector is shadow-only. It did not alter replay queue or search generation in this run.

## Lane Bandit

- budget: 1024
- allocation: {'ast_evolutionary_mutation': 273, 'cem_adaptive_grammar': 359, 'non_gap_forced_sampler': 52, 'rx_diverse_beam': 66, 'rx_no_policy_true_limit': 71, 'simple_template': 89, 'typed_random_dark': 53, 'unreached_space': 61}
- reward: non_gap_replay_pass only, with CEM/AST priors and a 5% minimum lane floor.

## Bias Audit

- Factor: not a single tradable factor; this is a selector/ranker over discovered alpha candidates.
- Data source and universe: true-limit stock PIT panel from the 2026-05-11 bakeoff artifacts.
- Frequency and horizon: daily, horizon 1d, after_open signal, T+1 execution.
- OOS sample grade: WEAK. This uses replay rows from the same bakeoff family and recent 2026 windows, not full walk-forward production evidence.
- Costs: inherited 10bps replay cost; no full slippage/capacity promotion model.
- Turnover: used as pre-replay selector penalty when available; full portfolio turnover proof remains separate.
- Replay vs discovery: replay infrastructure validation. It cannot be counted as new alpha discovery.
- Decision: HOLD_RESEARCH. Good enough to run shadow/small-flow replay-aware selection next, not enough for commercial claim.

## Outputs

- data/candidates.parquet
- data/replay_results.parquet
- data/candidates_scored.parquet
- data/replay_selector_shadow.parquet
- data/replay_ranker_calibration_deciles.parquet
- data/replay_ranker_calibration_report.json
- data/replay_ranker_report.json
- data/models/non_gap_replay_pass_ranker.joblib
- data/models/replay_pass_ranker.joblib
- data/models/pure_rl_control_policy.joblib
- data/pure_rl_selector_shadow.parquet
- data/lane_bandit_state.json
- data/lane_bandit_allocation.json

## Next Action

- Use this in shadow mode on the next true-limit search: keep R0 selection as control, let replay-aware selector control only a capped replay slice, and keep pure RL diagnostic out of the formal decision until there is fresh replay evidence.
