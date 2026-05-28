# Phase3Z45b OOS / Regime Candidate Audit

Decision: `HOLD_RESEARCH_OOS_REGIME_AUDIT_COMPLETE`.

This audit is no-search and no-promotion. It replays frozen representative expressions on the long daily panel.

## 2026 OOS Summary

| cluster | action | family | ann | sortino | max_dd | median_turnover | p90_turnover |
|---|---|---|---:|---:|---:|---:|---:|
| cluster_002 | ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG | limit_streak | 0.687009 | 6.783088 | -0.0387938 | 0.013804 | 0.020313 |
| cluster_017 | ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG | limit_streak | 0.252193 | 2.470963 | -0.0450256 | 0.01372 | 0.018555 |
| cluster_001 | ALLOW_OOS_REGIME_REPLAY | limit_streak | 0.136626 | 1.684521 | -0.06690866 | 0.013678 | 0.018519 |
| cluster_007 | HOLD_TURNOVER_COST_STRESS_BEFORE_OOS | limit_streak | 0.203679 | 1.43294 | -0.09068955 | 0.700136 | 0.981531 |
| cluster_030 | HOLD_EXPAND_SAMPLE_BEFORE_REPLAY | limit_open_not_close | 0.098834 | 1.116681 | -0.06785077 | 0.036532 | 0.06945 |

## Bias Boundary

- Signal clock: after-open with full-day fields lagged by the existing evaluator policy.
- Execution lag: T+1 daily proxy.
- Cost stress: 0/10/20/30/50 bps one-way turnover deduction.
- Evidence remains weak recent-daily until longer locked forward replay exists.
