# Phase3Z49 Event Long Selection Overlap

- decision: `HOLD_Z49_STOCK_VETO_NOT_JUSTIFIED_BY_OVERLAP`
- candidate_count: `0`
- scope: diagnostic only; no official object changes.

| trigger | selected events | event share | weighted event-minus-non-event | bad clusters | decision |
|---|---:|---:|---:|---:|---|
| break_after_streak_ge2 | 25 | 0.001012 | 0.01269824 | 0 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| break_after_streak_ge3 | 4 | 0.000162 | None | 0 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| open_not_close_up | 34 | 0.001376 | 0.0353367 | 0 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| touch_not_close_up | 1340 | 0.054236 | 0.00097559 | 0 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |

## Interpretation

- This audit only checks whether X0 long selections actually contain the negative-event stocks.
- A pass would justify optimized stock-level veto replay; it still would not promote a gate.
