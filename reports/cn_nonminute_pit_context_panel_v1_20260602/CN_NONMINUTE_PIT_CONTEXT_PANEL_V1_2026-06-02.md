# CN Non-1min PIT Context Panel v1 - 2026-06-02

decision: `PASS_NONMINUTE_PIT_CONTEXT_PANEL_V1`
total_rows: `3997944`
field_count: `126`

## Output

- panel_root: `runtime\nonminute_context_panels\cn_nonminute_pit_context_panel_v1_20260602`
- field_contract: `runtime\nonminute_context_panels\cn_nonminute_pit_context_panel_v1_20260602\field_contract.csv`
- coverage: `runtime\nonminute_context_panels\cn_nonminute_pit_context_panel_v1_20260602\coverage_by_family_year.csv`

## Boundary

- RZRQ and market distribution are lagged to the next trading day.
- Fundamentals and holder fields are available only after notice date plus next trading day.
- Billboard fields are diagnostic-only until a stronger disclosure timestamp contract is proven.
- Metadata columns are audit-only and cannot enter selector scoring.

## Year Outputs

- `2023`: rows `1186529`, columns `126`
- `2024`: rows `1222009`, columns `126`
- `2025`: rows `1249440`, columns `126`
- `2026`: rows `339966`, columns `126`
