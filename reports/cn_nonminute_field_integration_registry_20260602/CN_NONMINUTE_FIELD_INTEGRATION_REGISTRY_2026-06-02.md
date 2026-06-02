# CN Non-1min Field Integration Registry - 2026-06-02

decision: `PASS_NONMINUTE_FIELD_INTEGRATION_REGISTRY`
table_count: `25`
field_count: `1855`
error_count: `0`
blocked_or_diagnostic_table_count: `5`

## Route Counts

- `announcement_pit_context`: `11`
- `lagged_daily_context`: `6`
- `event_disclosure_context`: `3`
- `tradability_calendar_context`: `1`
- `timestamped_stock_intraday_event`: `1`
- `manual_contract_required`: `1`
- `lagged_market_regime_context`: `1`
- `timestamped_market_intraday_event`: `1`

## Integration Policy

- Stock 1min fields are intentionally excluded from this registry and handled by the minute v2 panel.
- Daily/HFQ/RZRQ/context fields are selector-eligible only through lagged joins.
- Fundamental, holder, share-change and dividend data require announcement/PIT availability.
- Billboard/disclosure rows remain diagnostic until disclosure timestamp policy is proven.
- Limit event rows are valid only after the timestamp/cutoff encoded in the feature.
