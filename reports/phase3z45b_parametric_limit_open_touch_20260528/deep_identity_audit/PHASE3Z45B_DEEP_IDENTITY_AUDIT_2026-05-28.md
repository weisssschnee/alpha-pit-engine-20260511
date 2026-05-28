# Phase3Z45b Deep Identity Audit

## Decision

`HOLD_RESEARCH_AFTER_IDENTITY_AUDIT`: this audit routes candidates to deeper validation, but does not promote any candidate.

## Action Counts

- `ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG`: `2`
- `ALLOW_OOS_REGIME_REPLAY`: `1`
- `HOLD_TURNOVER_COST_STRESS_BEFORE_OOS`: `1`
- `HOLD_EXPAND_SAMPLE_BEFORE_REPLAY`: `1`

## Cluster Routing

| cluster | action | family | replay_pass | cost_survival | turnover | best_sortino | flags | representative |
|---|---|---|---:|---:|---:|---:|---|---|
| cluster_002 | `ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG` | limit_streak | 3 | 4 | 0.0325 | 2.5946 | strict_replay_mismatch|parameter_family_variants|negative_strict_cost_adjusted_sortino | `Neg(ZScore(Mean(Delay($limit_up_streak_ge8,1),7)))` |
| cluster_017 | `ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG` | limit_streak | 5 | 10 | 0.0284 | 1.1162 | strict_replay_mismatch|parameter_family_variants | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge8,1),14)))` |
| cluster_001 | `ALLOW_OOS_REGIME_REPLAY` | limit_streak | 5 | 9 | 0.0240 | 0.7344 | parameter_family_variants | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge9,1),15)))` |
| cluster_007 | `HOLD_TURNOVER_COST_STRESS_BEFORE_OOS` | limit_streak | 5 | 21 | 0.7624 | 0.6139 | high_turnover|limit_dominant|parameter_family_variants | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($market_high_board_l...` |
| cluster_030 | `HOLD_EXPAND_SAMPLE_BEFORE_REPLAY` | limit_open_not_close | 1 | 2 | 0.0534 | 0.5694 | low_sample|strict_replay_mismatch|limit_dominant | `Neg(ZScore(Delay($limit_up_open_not_close,1)))` |

## Interpretation

- Low-turnover high-board density clusters are the only candidates ready for OOS/regime replay routing.
- `cluster_007` is a real structural event interaction, but its turnover is too high for immediate replay promotion.
- `cluster_030` is the cleanest open-not-close event candidate, but sample size is too small.
- Direct touch/not-close families remain HOLD because strict/replay evidence is weak.
