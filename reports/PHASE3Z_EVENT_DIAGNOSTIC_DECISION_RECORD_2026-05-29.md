# Phase3Z Event Diagnostic Decision Record

- decision: `HOLD_EVENT_LINE_DIAGNOSTIC_NO_X0_PROMOTION`
- date: `2026-05-29`
- commits:
  - `4d551e9` Phase3Z46 EventAlpha canary
  - `072e929` Phase3Z47 sparse event study
  - `8c02bd5` Phase3Z48 event veto gate audit
  - `b61e11e` Phase3Z49 long-selection overlap audit

## Scope

This record covers the isolated event / limit / high-board diagnostic line. It
does not alter:

- `X0_official_6_R3_liquidity_low_v1`
- `G2_signal_vector_diversified_selector`
- `J2/J4` locked book filters
- `Phase3P` locked daily forward
- formula search reward or official generator budgets

## Results

### Z46 Dense EventAlpha Canary

- generated event-state candidates: `390`
- frozen queue: `64`
- evaluated: `64`
- unsupported count: `0`
- smoke pass count: `0`
- decision: `HOLD_Z46_CANARY_NO_SMOKE_PASS`

Interpretation: dense formula-style event canary did not produce candidates
worth expanding. This rejects the current direct event-formula path, not all
event alpha hypotheses.

### Z47 Sparse Event Study

- trigger count: `15`
- research candidates: `4`
- decision: `HOLD_Z47_EVENT_STUDY_HAS_RESEARCH_CANDIDATES`

Research candidates were all negative-event / veto style:

- `break_after_streak_ge2`
- `break_after_streak_ge3`
- `open_not_close_up`
- `touch_not_close_up`

Interpretation: the useful event signal is not a buy alpha. It is a possible
risk / veto structure.

### Z48 Market-Day Veto Audit

- audit mode: `market_day_veto`
- base X0/R3 OOS annualized: `1.175657`
- base X0/R3 OOS total return: `0.266314`
- base X0/R3 active days: `38`
- research candidates: `0`
- decision: `HOLD_Z48_MARKET_DAY_VETO_NO_X0_R3_IMPROVEMENT`

All tested event-density market-day vetoes either removed too few days to be
useful or removed profitable X0/R3 active days. The best-looking rows still had
negative annualized delta.

Interpretation: Z47 negative events should not be used as whole-day cash gates
for X0/R3.

### Z49 Long-Selection Overlap Audit

- selected X0/R3 long rows checked: `24707`
- research candidates: `0`
- decision: `HOLD_Z49_STOCK_VETO_NOT_JUSTIFIED_BY_OVERLAP`

Summary:

| trigger | selected event count | selected event share | weighted event-minus-non-event return | decision |
|---|---:|---:|---:|---|
| `break_after_streak_ge2` | 25 | 0.001012 | 0.01269824 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| `break_after_streak_ge3` | 4 | 0.000162 | null | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| `open_not_close_up` | 34 | 0.001376 | 0.0353367 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |
| `touch_not_close_up` | 1340 | 0.054236 | 0.00097559 | `HOLD_STOCK_VETO_NOT_JUSTIFIED` |

Interpretation: these negative-event stocks are not materially hurting the
locked X0 long legs. In the selected long set, overlap is either tiny or the
event names are not worse than non-event selections.

## Decision

The current event/limit diagnostic line is retained as research evidence only.
It does not justify:

- promoting an event overlay to X0/R3
- adding a market-day veto gate
- running expensive stock-level veto replay
- changing official formula search reward
- changing official daily shadow forward

## Confirmed

- Direct dense event-formula canary failed under current reward and validation.
- Sparse event study found real negative-event structures.
- Those structures do not improve X0/R3 as market-day vetoes.
- Those structures do not materially contaminate X0/R3 long selections.

## Not Confirmed

- Event alpha as a standalone short book.
- Intraday / minute execution value of open-board and touch-not-close events.
- Actor-specific event modules outside the X0/R3 overlay use case.
- Limit/order-flow event modeling with minute data.

## Next Allowed Work

Allowed:

- Keep event-state features as diagnostic metadata.
- Use Z47 negative-event structures for later short-side or intraday research.
- Revisit event alpha only with a separate objective, such as event short book,
  execution risk model, or minute-data microstructure audit.

Blocked without new decision record:

- X0/R3 event overlay.
- R3 threshold changes based on event results.
- Official book membership changes.
- Full-scale event formula search using the failed Z46 reward.

## Bottom Line

Event morphology is informative, but the current evidence says it is not an
incremental X0/R3 overlay. The official X0/R3 shadow remains unchanged.
