# Phase3O7 Limit Factor Chain Audit

- decision: `HOLD_LIMIT_GENERATOR_COVERAGE_GAP`
- scope: diagnostic only; no retraining, no mainline search, no X0/R3 changes.

## Limit Token Funnel

| stage | raw rows | unique expr | direct-limit rows | direct-limit unique expr | direct-limit share |
| --- | ---: | ---: | ---: | ---: | ---: |
| generated_candidate_ledgers | 1992 | 642 | 0 | 0 | 0.0 |
| stage1_validated | 1728 | 634 | 0 | 0 | 0.0 |
| strict_replay_aggregate_rows | 4672 | 2143 | 0 | 0 | 0.0 |

## Direct Limit Stage1 Metrics

- direct_limit_stage1_rows: `0`
- direct_limit_promoted_to_full_history_review: `None`
- direct_limit_mean_recent_rank_ic: `None`
- direct_limit_mean_recent_sortino: `None`

## Direct Limit Strict/Replay Metrics

- direct_limit_audited_or_strict_rows: `0`
- direct_limit_portfolio_replay_pass: `0`
- direct_limit_deployable_cluster_count_proxy: `0`

## Gate Evidence

| gate | full ann | active ann | active ratio | sharpe | max dd |
| --- | ---: | ---: | ---: | ---: | ---: |
| R3_liquidity_low | 1.175657 | 3.918442 | 0.487179 | 4.547115 | -0.03442312 |
| R4_limit_density_high | 0.197755 | 0.340663 | 0.615385 | 0.88946 | -0.09227455 |

## Interpretation

- `direct_limit` means limit fields/tokens appear in formula or generator-relevant motif metadata.
- Tradability masks and field-lag availability are counted separately; they do not prove limit was used as alpha.
- If direct-limit coverage is low, the next step is a diagnostic `limit_motif_pack`, not retraining the locked mainline.
- If direct-limit coverage is high but replay/deployable is weak, direct limit alpha should stay diagnostic.
