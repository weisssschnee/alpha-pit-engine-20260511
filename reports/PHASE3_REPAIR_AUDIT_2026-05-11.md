# Phase3 Repair Audit - 2026-05-11

## Scope

- input root: `runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511`
- purpose: diagnose whether the 28 non-gap replay passes are independent, whether replay-aware slice is residual value, whether selector scores are calibrated, and why failed lanes fail.
- decision: HOLD_RESEARCH. This is diagnostic evidence, not factor promotion.

## Independent Alpha Check

- raw non-gap replay pass: 28
- unique return-corr clusters: 8
- unique deployable return-corr clusters: 5
- unique AST hashes: 15
- unique normalized expression hashes: 21
- slice new return clusters vs R0: 2
- sector/style exposure available: False

## Selection Pool Type

| lane                      | selection_policy          | selection_pool_type   |   audited_count |   replay_pass |   non_gap_replay_pass |
|:--------------------------|:--------------------------|:----------------------|----------------:|--------------:|----------------------:|
| ast_evolutionary_mutation | r0_control                | common_pool           |              18 |             6 |                     6 |
| ast_evolutionary_mutation | replay_aware_shadow_slice | R0_leftover           |               6 |             1 |                     1 |
| cem_adaptive_grammar      | r0_control                | common_pool           |              18 |            13 |                    13 |
| cem_adaptive_grammar      | replay_aware_shadow_slice | R0_leftover           |               6 |             5 |                     5 |
| non_gap_forced_sampler    | r0_control                | common_pool           |              18 |             0 |                     0 |
| non_gap_forced_sampler    | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |
| rx_diverse_beam           | r0_control                | common_pool           |              18 |             0 |                     0 |
| rx_diverse_beam           | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |
| rx_no_policy_true_limit   | r0_control                | common_pool           |              18 |             0 |                     0 |
| rx_no_policy_true_limit   | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |
| simple_template           | r0_control                | common_pool           |              18 |             3 |                     3 |
| simple_template           | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |
| typed_random_dark         | r0_control                | common_pool           |              18 |             0 |                     0 |
| typed_random_dark         | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |
| unreached_space           | r0_control                | common_pool           |              18 |             0 |                     0 |
| unreached_space           | replay_aware_shadow_slice | R0_leftover           |               6 |             0 |                     0 |

## Replay-Aware Score Decile Lift

|   score_decile_top_first |   candidate_count |   audited_count |   replay_pass |   non_gap_replay_pass |   unique_cluster_pass |   audited_avg_corr |   audited_avg_turnover |
|-------------------------:|------------------:|----------------:|--------------:|----------------------:|----------------------:|-------------------:|-----------------------:|
|                        1 |               140 |              40 |             6 |                     6 |                     4 |           0.7427   |               0.319541 |
|                        2 |               139 |               7 |             0 |                     0 |                     0 |           0.967803 |               0.186869 |
|                        3 |               139 |               1 |             0 |                     0 |                     0 |           0.924796 |               0.080432 |
|                        4 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                        5 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                        6 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                        7 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                        8 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                        9 |               139 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |
|                       10 |               140 |               0 |             0 |                     0 |                     0 |         nan        |             nan        |

## Failure Diagnosis By Lane

| lane                      |   fail_count |   gap_dependency |   turnover_too_high |   corr_duplicate |   factor_exposure |   sector_exposure |   style_exposure |   subperiod_instability |   regime_instability |   complexity_overfit |   operator_pathology |   field_pathology |   unknown |
|:--------------------------|-------------:|-----------------:|--------------------:|-----------------:|------------------:|------------------:|-----------------:|------------------------:|---------------------:|---------------------:|---------------------:|------------------:|----------:|
| ast_evolutionary_mutation |           17 |                0 |                   9 |                9 |                 0 |                 0 |                0 |                      10 |                    0 |                    1 |                   16 |                11 |         1 |
| cem_adaptive_grammar      |            6 |                0 |                   0 |                1 |                 0 |                 0 |                0 |                       4 |                    0 |                    0 |                    2 |                 0 |         2 |
| non_gap_forced_sampler    |           24 |                0 |                   0 |               15 |                 0 |                 0 |                0 |                       4 |                    0 |                    0 |                   23 |                 1 |         0 |
| rx_diverse_beam           |           24 |                1 |                   7 |               19 |                 0 |                 0 |                0 |                      18 |                    0 |                    1 |                   15 |                14 |         0 |
| rx_no_policy_true_limit   |           24 |                6 |                  16 |               10 |                 0 |                 0 |                0 |                      11 |                    0 |                    0 |                   16 |                16 |         0 |
| simple_template           |           21 |                4 |                   4 |               15 |                 0 |                 0 |                0 |                      16 |                    0 |                    0 |                    6 |                 4 |         1 |
| typed_random_dark         |           24 |                4 |                  10 |               21 |                 0 |                 0 |                0 |                      15 |                    0 |                    0 |                   18 |                17 |         0 |
| unreached_space           |           24 |               13 |                  24 |               13 |                 0 |                 0 |                0 |                       9 |                    0 |                   17 |                   24 |                23 |         0 |

## Next Phase Definition

- Phase3 name: `phase3_repair`.
- Main allocation: CEM control + AST failure-aware repair + replay-aware residual slice.
- Suggested budget: R0/CEM-led 60%, AST failure repair 20%, replay-aware residual slice 10%, novelty/diagnostic 10%.
- Replay-aware selector remains residual miner. It should not replace R0 until it wins equal-budget common-pool unique non-gap pass rate by at least 25%-30% without worse corr/turnover/complexity.
- RX/random/non-gap-forced move to quarantine + pathology tests until failure diagnosis shows a fixable concentrated pathology.
