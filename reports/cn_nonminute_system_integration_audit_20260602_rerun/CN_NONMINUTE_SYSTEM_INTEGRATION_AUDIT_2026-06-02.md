# CN Non-1min System Integration Audit - 2026-06-02

decision: `PASS_NONMINUTE_SYSTEM_INTEGRATION_AUDIT_WITH_GAPS`
registry_fields: `1855`
minute_panel_columns: `231`
event_panel_columns: `78`
high_value_gap_count: `684`

## Integration Status Counts

- `registered_pit_not_panelized`: `1420`
- `registered_lagged_not_panelized`: `186`
- `registered_diagnostic_not_panelized`: `82`
- `integrated_minute_context_panel`: `73`
- `registered_not_panelized`: `53`
- `integrated_event_alignment_panel`: `34`
- `blocked_manual_contract`: `5`
- `key_or_metadata_integrated_indirectly`: `2`

## Interpretation

- `integrated_*` fields are already wired into minute/context/event panels.
- `registered_*_not_panelized` fields are preserved with PIT rules but need a dedicated panel builder before search.
- High-value gaps should become the next feature-panel work item, not be silently ignored.
