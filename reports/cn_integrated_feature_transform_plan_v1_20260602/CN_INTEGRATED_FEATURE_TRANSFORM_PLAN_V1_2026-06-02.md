# CN Integrated Feature Transform Plan v1

decision: `PASS_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1`

## Counts

- minute_field_count: `48`
- nonminute_context_field_count: `126`
- nonminute_registry_field_count: `1855`
- transform_plan_rows: `474`
- high_priority_backlog_rows: `76`
- medium_priority_backlog_rows: `54`

## Family Summary

| family | fields | materialized | selector | blocked | diagnostic | regime | not panelized |
|---|---:|---:|---:|---:|---:|---:|---:|
| audit_meta_forbidden | 7 | 7 | 0 | 7 | 0 | 0 | 0 |
| billboard_disclosure_diagnostic | 16 | 16 | 0 | 0 | 16 | 0 | 0 |
| capacity_size | 8 | 0 | 0 | 0 | 0 | 0 | 8 |
| disclosure_event | 13 | 0 | 0 | 0 | 0 | 0 | 13 |
| fundamental | 279 | 0 | 0 | 0 | 0 | 0 | 279 |
| fundamental_balance_risk | 18 | 18 | 18 | 0 | 0 | 0 | 0 |
| fundamental_cashflow_quality | 8 | 8 | 8 | 0 | 0 | 0 | 0 |
| fundamental_income_quality | 17 | 17 | 17 | 0 | 0 | 0 | 0 |
| holder_structure | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| key | 6 | 6 | 0 | 6 | 0 | 0 | 0 |
| label_forbidden | 5 | 5 | 0 | 5 | 0 | 0 | 0 |
| market_breadth_regime | 15 | 15 | 0 | 0 | 0 | 15 | 0 |
| minute_coverage | 4 | 4 | 4 | 0 | 0 | 0 | 0 |
| minute_flow_liquidity | 8 | 8 | 8 | 0 | 0 | 0 | 0 |
| minute_other | 3 | 3 | 3 | 0 | 0 | 0 | 0 |
| minute_price_state | 3 | 3 | 3 | 0 | 0 | 0 | 0 |
| minute_range_volatility | 11 | 11 | 11 | 0 | 0 | 0 | 0 |
| minute_return_pressure | 5 | 5 | 5 | 0 | 0 | 0 | 0 |
| minute_vwap_pressure | 6 | 6 | 6 | 0 | 0 | 0 | 0 |
| rzrq_flow_leverage | 31 | 31 | 31 | 0 | 0 | 0 | 0 |

## Critical Findings

- 1-minute fields are usable as early-window execution/signal features, but label_* fields are blocked from selector input.
- RZRQ, holder, and fundamental context fields are now materialized as PIT-safe lagged context and should enter factor-pack templates.
- Market up/down breadth fields should be used as regime or interaction context first, not as standalone alpha proof.
- Billboard fields remain diagnostic until disclosure timestamp policy is strong enough.
- High-value non-minute gaps still exist; next panelization should prioritize fields with selector_candidate routes and high/medium priority.

## Next Action

`build_integrated_factor_pack_v1_from_high_priority_backlog_then_run_selector_only_smoke`
