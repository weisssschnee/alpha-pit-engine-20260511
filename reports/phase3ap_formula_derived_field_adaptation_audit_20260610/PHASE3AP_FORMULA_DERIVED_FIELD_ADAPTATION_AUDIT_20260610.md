# Phase3AP Formula And Derived Field Adaptation Audit

decision: `PHASE3AP_FORMULA_ADAPTATION_AUDIT_READY_WITH_BLOCKERS`

## Scope

- factor packs: `9`
- candidates audited: `1370`
- unique formula fields: `391`

## Candidate Status Counts

- `adaptable_after_recompute_on_trade_time`: 73
- `adaptable_with_lagged_context_sidecar`: 194
- `blocked_for_true_1min_search`: 5
- `diagnostic_context_or_disclosure_contract_needed`: 144
- `direct_true_1min_ready`: 90
- `event_state_lane_only`: 111
- `needs_route_mapping_or_rederivation`: 753

## Main Finding

`first5` / `first15` / `first30` are acceptable opening-window feature families, but existing formulas are not automatically true 1min-ready because many were built against code-date or daily-derived panels. They need a trade_time backbone adapter and field availability guards.

## Required Before Large Search

- Build a true trade_time-code 1min formula panel or evaluator adapter.
- Recompute m1_firstN fields as opening-window features with availability guards; do not split the data into firstN frequencies.
- Block m1_day_* and label_* fields as selector inputs unless they are lagged explicitly.
- Route evt_* fields to event-state lanes with observable-time guards.
- Map legacy/current-panel-only fields to PIT context sidecars or drop them from true 1min packs.
