# CN Multifrequency Field Route Audit - 2026-06-01

decision: `PASS_MULTIFREQUENCY_ROUTE_AUDIT_WITH_BLOCKERS`
dataset_count: `33121`
blocked_or_manual_contract_count: `15795`

## Route Counts

- `unclassified_needs_contract`: `15792`
- `minute_native_feature`: `15677`
- `announcement_pit_context`: `1425`
- `daily_lagged_context`: `217`
- `date_keyed_context_needs_manual_contract`: `3`
- `event_disclosure_context`: `3`
- `timestamped_stock_intraday_event_feature`: `3`
- `timestamped_market_intraday_event_feature`: `1`

## Critical Findings

- `review_uplimit_reason.up_limit_time` is a timestamped stock-level intraday event candidate.
- `uplimit_trend.time` is a timestamped market-level intraday candidate, but current 2026 silver rows are null and must not be used until repaired.
- Daily, margin, fundamental, holder, dividend, and billboard fields are retained as lagged/PIT context rather than discarded.
