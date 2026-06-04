# CN Field Integration Completeness Audit v1

decision: `HOLD_FIELD_INTEGRATION_NOT_FULLY_CLOSED`

## Summary

- asset_field_count: `4775`
- panel_field_count: `1045`
- factor_alias_count: `761`
- selector_alias_count: `143`
- high_value_gap_count: `1319`
- factor_pack_only_missing_panel_count: `0`
- panel_only_high_value_count: `113`
- key_field_watchlist_row_count: `1289`

## Integration Status Counts

- `blocked_or_metadata`: `488`
- `contract_only`: `1822`
- `integrated_selector_ready`: `1682`
- `integrated_selector_selected`: `358`
- `panel_only`: `153`
- `probe_or_backlog`: `272`

## Interpretation

This audit confirms the project has substantial data assets, but field integration is not globally closed. The failure mode is not data absence; it is route incompleteness between field contracts, panel aliases, factor-pack expressions, selector admission, and replay availability.

The PE/PB case is now fixed as an HFQ lag1 valuation selector-only route, but it is the pattern we need to watch for: fields can exist in silver data and still be invisible to the mature search chain.

## Next Repair Order

1. Convert `panel_only_high_value_fields` into bounded factor-pack candidates.
2. Convert `factor_pack_only_missing_panel` into selected sidecars or block those candidates before selector/replay.
3. Keep timestamped event fields separate from daily context fields; event time fields need cutoff proofs, not simple T+1 context.
4. Run replay/style audit only after field availability is closed for the selected queue.
