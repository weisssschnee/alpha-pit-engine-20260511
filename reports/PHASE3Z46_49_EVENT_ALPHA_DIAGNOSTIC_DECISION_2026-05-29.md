# Phase3Z46-Z49 Event Alpha Diagnostic Decision

Date: 2026-05-29

## Decision

`HOLD_EVENT_ALPHA_DIAGNOSTIC_ONLY`

The event/limit/high-board line has research value, but current evidence does not justify promotion into:

- X0/R3 official shadow,
- mature G2 discovery budget,
- stock-level X0/R3 veto,
- market-day R3 veto,
- or standalone event alpha book.

## Scope

This decision covers the diagnostic event line only. X0/R3 remains locked and read-only.

## Results

### Z46 Reward Lane Dry Audit

Decision: `PASS_Z46_REWARD_DRY_AUDIT`

The lane reward correctly rejects known weak Z45b cases:

- overlay rejects do not enter overlay top bucket,
- cluster_002 is not promoted as overlay,
- cluster_007 is not promoted despite event interest,
- cluster_030 is correctly marked very-short-horizon diagnostic,
- fragile regime slices are penalized.

This validates the reward governance, not event alpha promotion.

### Event Alpha Validation

Decision: `HOLD_EVENT_ALPHA_VALIDATION_DIAGNOSTIC_ONLY`

Five Z45b candidates were checked:

- `1` research candidate,
- `1` fragile 20-49 event-count candidate,
- `3` candidates held for missing/weak tradability controls.

No candidate is promotion-grade.

### Z47 Sparse Event Study

Decision: `HOLD_Z47_EVENT_STUDY_HAS_RESEARCH_CANDIDATES`

Four event-study research candidates were found. They are primarily negative-event/veto candidates:

- `break_board_after_streak_ge_3`,
- `break_board_after_streak_ge_2`,
- `limit_up_open_not_close`,
- `limit_up_touch_not_close`.

High-board / streak long events show strong raw event returns in some cases, but tradability failure is too high for promotion.

### Z48 Market-Day Veto Audit

Decision: `HOLD_Z48_MARKET_DAY_VETO_NO_X0_R3_IMPROVEMENT`

No market-day event veto improves locked X0/R3. Several event-density vetoes remove profitable R3 days and reduce full-calendar annualized return.

### Z49 Stock-Level Long Selection Overlap

Decision: `HOLD_Z49_STOCK_VETO_NOT_JUSTIFIED_BY_OVERLAP`

The negative-event stocks do not create a material bad-selection problem inside locked X0/R3 long legs.

Summary:

| trigger | selected event count | selected event share | weighted event-minus-non-event |
|---|---:|---:|---:|
| touch_not_close_up | 1340 | 5.42% | +0.00097559 |
| break_after_streak_ge2 | 25 | 0.10% | +0.01269824 |
| open_not_close_up | 34 | 0.14% | +0.03533670 |
| break_after_streak_ge3 | 4 | 0.02% | n/a |

No trigger has material bad overlap with X0/R3 long selections.

## Interpretation

The event line failed three promotion paths:

1. Direct factor injection diluted mature G2 in Phase3AA.
2. Market-day veto did not improve X0/R3.
3. Stock-level veto is not justified by X0/R3 long-selection overlap.

The event line still has useful research findings:

- limit-break and open-not-close states identify adverse short-horizon event behavior,
- high-board continuation has strong raw event evidence but poor tradability,
- the correct future form is likely event-module research with execution constraints, not daily book overlay.

## Policy

Allowed next actions:

- keep event/limit/high-board features in diagnostic registry,
- use them for event-study research,
- improve tradability-aware event validation,
- revisit only after minute/execution data or stronger event-module evidence.

Blocked actions:

- no X0/R3 modification,
- no G2 budget promotion,
- no J2/J4 book filter modification,
- no stock-level veto in locked shadow,
- no standalone event book.

## Evidence Level

`diagnostic_event_research_only`

Not confirmed:

- production readiness,
- true execution,
- tradability-adjusted event alpha,
- capacity,
- live/paper survival.
