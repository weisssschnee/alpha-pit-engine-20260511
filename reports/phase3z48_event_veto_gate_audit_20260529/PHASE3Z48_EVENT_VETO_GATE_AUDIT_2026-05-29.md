# Phase3Z48 Event Veto Gate Audit

- decision: `HOLD_Z48_MARKET_DAY_VETO_NO_X0_R3_IMPROVEMENT`
- candidate_count: `0`
- audit_mode: `market_day_veto`
- scope: diagnostic only; locked X0/R3 is read-only.

## Results

| trigger | threshold | veto R3 days | delta ann | veto ann | base ann | random p95 | removed day mean | decision |
|---|---|---:|---:|---:|---:|---:|---:|---|
| break_after_streak_ge2 | `train_p90_density` | 1 | -0.024945 | 1.150712 | 1.175657 | 0.179853 | 0.00358041 | `HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS` |
| break_after_streak_ge3 | `train_p90_density` | 1 | -0.108271 | 1.067386 | 1.175657 | 0.179853 | 0.01584713 | `HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS` |
| break_after_streak_ge3 | `train_p80_density` | 2 | -0.175714 | 0.999943 | 1.175657 | 0.164775 | 0.0130709 | `HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS` |
| open_not_close_up | `train_p90_density` | 2 | -0.202655 | 0.973002 | 1.175657 | 0.167674 | 0.01517557 | `HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS` |
| touch_not_close_up | `train_p90_density` | 3 | -0.33936 | 0.836297 | 1.175657 | 0.163716 | 0.01754451 | `HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS` |
| break_after_streak_ge2 | `train_p80_density` | 6 | -0.347741 | 0.827916 | 1.175657 | 0.133876 | 0.0090088 | `REJECT_NO_X0_R3_DELTA` |
| touch_not_close_up | `train_p80_density` | 6 | -0.44731 | 0.728347 | 1.175657 | 0.094595 | 0.01190486 | `REJECT_NO_X0_R3_DELTA` |
| open_not_close_up | `train_p80_density` | 7 | -0.526618 | 0.649039 | 1.175657 | 0.074382 | 0.01228551 | `REJECT_NO_X0_R3_DELTA` |
| break_after_streak_ge2 | `any_event` | 38 | -1.175657 | 0.0 | 1.175657 | -1.175657 | 0.00634142 | `REJECT_NO_X0_R3_DELTA` |
| touch_not_close_up | `any_event` | 38 | -1.175657 | 0.0 | 1.175657 | -1.175657 | 0.00634142 | `REJECT_NO_X0_R3_DELTA` |
| break_after_streak_ge3 | `any_event` | 34 | -1.177553 | -0.001896 | 1.175657 | -0.915 | 0.00710474 | `REJECT_NO_X0_R3_DELTA` |
| open_not_close_up | `any_event` | 34 | -1.180756 | -0.005099 | 1.175657 | -0.931254 | 0.007134 | `REJECT_NO_X0_R3_DELTA` |

## Interpretation

- This run tests market-day event-density vetoes, not stock-level position vetoes.
- A pass means the event may justify a later gate research track; it is not official promotion.
- Same-count random day veto controls whether cashing a similar number of R3 days has comparable improvement.
