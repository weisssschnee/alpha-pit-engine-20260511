# Phase2 Replay-Aware Slice Medium Results - 2026-05-11

## Run Status

- root: `runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511`
- status: completed
- seeds: 1, 2, 3
- started: `2026-05-11T11:41:05+08:00`
- completed: `2026-05-11T14:01:39+08:00`
- stderr: empty for all three seeds

## Contract

- R0 remains the main decision table: `main_table_scope = r0_control_only`
- replay-aware selector is a capped extra strict/replay slice
- pure RL does not control search
- per seed: candidate budget 64, strict top4 + random2 per lane, replay-aware slice 2 per lane

## R0 Control Main Table

Aggregate across three seeds:

| lane | audited | strict | replay | non-gap replay | replay yield / 100 valid | gap share |
|---|---:|---:|---:|---:|---:|---:|
| cem_adaptive_grammar | 18 | 9 | 13 | 13 | 6.770833 | 0.000000 |
| ast_evolutionary_mutation | 18 | 5 | 6 | 6 | 3.125000 | 0.000000 |
| simple_template | 18 | 6 | 3 | 3 | 1.562500 | 0.222222 |
| non_gap_forced_sampler | 18 | 12 | 0 | 0 | 0.000000 | 0.000000 |
| rx_no_policy_true_limit | 18 | 6 | 0 | 0 | 0.000000 | 0.333333 |
| rx_diverse_beam | 18 | 1 | 0 | 0 | 0.000000 | 0.055556 |
| typed_random_dark | 18 | 3 | 0 | 0 | 0.000000 | 0.222222 |
| unreached_space | 18 | 9 | 0 | 0 | 0.000000 | 0.722222 |

Interpretation:

- CEM is still the strongest lane.
- AST remains second.
- simple template is still useful but materially weaker.
- non-gap forced sampler again shows strict-pass can be misleading: strict 12, replay 0.
- unreached is still not useful in this run and is gap-heavy.

## Replay-Aware Slice

Aggregate across three seeds:

| lane | audited | strict | replay | non-gap replay | gap share |
|---|---:|---:|---:|---:|---:|
| cem_adaptive_grammar | 6 | 1 | 5 | 5 | 0.000000 |
| ast_evolutionary_mutation | 6 | 2 | 1 | 1 | 0.000000 |
| all other lanes | 36 | 2 | 0 | 0 | 0.000000 |

Interpretation:

- The slice added 6 extra non-gap replay passes.
- It did not beat R0 per audited candidate: R0 control had 22 non-gap replay passes over 144 audited rows; replay-aware slice had 6 over 48.
- The selector mostly found extra CEM/AST candidates. It did not unlock RX/random/unreached/non-gap-forced.

## Decision

HOLD_RESEARCH for selector promotion.

The replay-aware selector is useful as an extra capped slice, but this medium run does not justify replacing R0 selection. The next practical action is to keep CEM + AST as primary search budget and keep replay-aware selector as a limited additive audit slice while collecting more fresh replay outcomes.
