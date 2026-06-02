# CN Non-1min PIT Context Panel v1 Decision - 2026-06-02

decision: `PASS_NONMINUTE_PIT_CONTEXT_PANEL_V1`

## What Changed

- Built a PIT-safe non-1min context panel for the 2023-2026 minute feature system.
- Added RZRQ daily flow fields, selected fundamental statement fields, holder-count disclosures, billboard diagnostic fields, and market up/down distribution.
- Added read-only QA and system integration audit support for the new context panel.

## Main Output

- panel: `runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602`
- builder report: `reports/cn_nonminute_pit_context_panel_v1_20260602`
- QA report: `reports/cn_nonminute_pit_context_panel_v1_20260602_qa`
- updated integration audit: `reports/cn_nonminute_system_integration_audit_20260602_after_context_panel`

## Result

- rows: `3,997,944`
- years: `2023, 2024, 2025, 2026`
- columns: `126`
- duplicate date-code rows: `0`
- null date/code rows: `0`
- available_date > panel date violations: `0`
- forbidden `label_` columns: `0`

## Integration Impact

- non-1min fields integrated by new context panel: `189`
- high-value non-1min gaps before context panel: `684`
- high-value non-1min gaps after context panel: `544`

## Safe Use Boundary

- `ctx_rzrq_*`: lagged daily context, source date plus next trading day.
- `ctx_fund_*`: PIT announcement context, NOTICE_DATE plus next trading day.
- `ctx_holder_*`: PIT disclosure context, HOLD_NOTICE_DATE plus next trading day.
- `ctx_billboard_*`: diagnostic only until disclosure timestamp policy is stronger.
- `ctx_mkt_updown_*`: lagged market regime context, source date plus next trading day.
- `meta_*`: audit metadata only, not selector input.

## Remaining Gaps

- Most remaining gaps are broad raw financial-statement fields and disclosure/event fields.
- Do not bulk-add all remaining fields before feature selection. The next useful step is a controlled factor-pack smoke using this context panel.
