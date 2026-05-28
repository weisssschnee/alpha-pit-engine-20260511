# Phase3Z45b Parametric Limit/Open/Touch Result Audit

## Decision

Decision: `HOLD_RESEARCH_FOR_CANDIDATE_DEEP_AUDIT`.

This run produced strict low-corr candidates, but it is research validation only. No alpha is promoted from this audit.

## Run Summary

- decision: `PASS_AUTOMATED_VALIDATION_HAS_STRICT_LOW_CORR_CANDIDATES_NOT_PROMOTION`
- stage1 reports: `16`
- raw stage1 rows: `3619`
- deduped expression rows: `3523`
- strict audited: `192`
- strict pass: `57`
- low-corr strict pass clusters: `10`
- portfolio replay pass: `22`
- cost survival: `84`

## Limit/Event Split

- `limit_event` audited `101`, strict pass `22`, low-corr `6`, replay pass `6`, cost survival `27`.
- `non_limit` audited `91`, strict pass `35`, low-corr `7`, replay pass `16`, cost survival `57`.

Interpretation: limit/event candidates are valid enough to continue as a diagnostic search family, but direct limit/event formulas did not outperform the non-limit side on replay pass rate or cost survival.

## Top Deep-Audit Clusters

| cluster | audited | strict_pass | replay_pass | cost_survival | limit_share | bucket | decision | representative |
|---|---:|---:|---:|---:|---:|---|---|---|
| cluster_007 | 21 | 21 | 5 | 21 | 0.52381 | limit_up_streak_geN:11; market_high_board_N:10 | ALLOW_DEEP_AUDIT | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($market_high_board_l...` |
| cluster_001 | 17 | 4 | 5 | 9 | 0.176471 | market_high_board_N:14; limit_up_streak_geN:3 | ALLOW_DEEP_AUDIT | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge9,1),15)))` |
| cluster_017 | 10 | 0 | 5 | 10 | 0.2 | market_high_board_N:8; limit_up_streak_geN:2 | ALLOW_DEEP_AUDIT | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge8,1),14)))` |
| cluster_002 | 6 | 0 | 3 | 4 | 0.333333 | market_high_board_N:4; limit_up_streak_geN:2 | ALLOW_DEEP_AUDIT | `Neg(ZScore(Mean(Delay($limit_up_streak_ge8,1),7)))` |
| cluster_011 | 6 | 0 | 3 | 0 | 0.0 | market_high_board_N:4; post_market_high_board_N_tplusD:2 | HOLD_RESEARCH | `Neg(ZScore($post_market_high_board_active_ge8_d1))` |
| cluster_030 | 2 | 0 | 1 | 2 | 1.0 | limit_up_open_not_close:2 | ALLOW_DEEP_AUDIT | `Neg(ZScore(Delay($limit_up_open_not_close,1)))` |
| cluster_003 | 14 | 10 | 0 | 10 | 0.142857 | post_market_high_board_N_tplusD:6; market_high_board_N:6; limit_up_streak_geN:2 | HOLD_RESEARCH | `Neg(ZScore(Delay($limit_up_streak_ge7,1)))` |
| cluster_008 | 9 | 9 | 0 | 9 | 0.333333 | market_high_board_N:6; limit_up_streak_geN:3 | HOLD_RESEARCH | `Neg(CSRank(Mul(ZScore(Div(Mean($amount,1),Mean($amount,5))),ZScore(Sub(Mean(Delay($limit_up_streak_ge9,1),2),Mean(Del...` |
| cluster_014 | 3 | 3 | 0 | 3 | 0.0 | break_after_high_board_geN:3 | HOLD_RESEARCH | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,4))),ZScore(Sub(Mean(Delay($break_after_high_boa...` |
| cluster_016 | 3 | 3 | 0 | 3 | 1.0 | limit_up_streak_geN:3 | HOLD_RESEARCH | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($limit_up_streak_ge8...` |
| cluster_009 | 6 | 2 | 0 | 2 | 0.0 | market_high_board_N:6 | HOLD_RESEARCH | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,5))),ZScore(Sub(Mean(Delay($market_high_board_le...` |
| cluster_025 | 4 | 2 | 0 | 2 | 1.0 | limit_up_streak_geN:4 | HOLD_RESEARCH | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,25))),ZScore(Sub(Mean(Delay($limit_up_streak_ge8...` |

## Bias / Evidence Audit

- signal clock: `after_open`
- execution lag days: `1`
- cost bps: `10.0`
- OOS grade: `WEAK_RECENT_DAILY_UNTIL_LONGER_FORWARD_REPLAY`
- promotion allowed: `False`

Blocking issue for promotion: evidence is recent-daily and research-validation only. Candidate clusters require identity audit, OOS/regime split, turnover/cost stress, and duplicate-family checks.

## Next Actions

1. Deep-audit `ALLOW_DEEP_AUDIT` clusters only; do not promote from this report.
2. Split cluster_007 and high-board leader clusters by 2025H2 / 2026 and R3/non-R3 regime.
3. Check whether `limit_up_streak_ge8/ge9/ge10` variants are genuinely distinct or parameter duplicates.
4. Keep `limit_up_touch/open/not_close` features diagnostic until exact limit-price/tradability audit is added.
