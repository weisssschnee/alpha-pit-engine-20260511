# Phase3Z45b vs X0/R3 Marginal Audit

Decision: `HOLD_RESEARCH_NO_FORMAL_OVERLAY_PROMOTION`.

- X0/R3 2026 ann: `0.723808`
- X0/R3 2026 sortino: `6.209199`

| cluster | decision | cand R3 ann | blend ann delta | blend sortino delta | corr to X0 | turnover | expression |
|---|---|---:|---:|---:|---:|---:|---|
| cluster_007 | `REJECT_OVERLAY_HIGH_TURNOVER` | 0.114617 | -0.104024 | -0.014956 | None | 0.700136 | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($market_hi...` |
| cluster_030 | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | 0.096576 | -0.10779 | -0.718506 | None | 0.036532 | `Neg(ZScore(Delay($limit_up_open_not_close,1)))` |
| cluster_001 | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | 0.09236 | -0.108678 | -0.306951 | None | 0.013678 | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge9,1),15)))` |
| cluster_017 | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | 0.079139 | -0.11148 | -0.328354 | None | 0.01372 | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge8,1),14)))` |
| cluster_002 | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | 0.040901 | -0.119755 | -0.303131 | None | 0.013804 | `Neg(ZScore(Mean(Delay($limit_up_streak_ge8,1),7)))` |

## Interpretation

- This audit is stricter than standalone OOS: a candidate must add marginal value to the locked X0/R3 object.
- Standalone positive return is insufficient for overlay promotion.
- High-turnover event interactions remain diagnostic only.
