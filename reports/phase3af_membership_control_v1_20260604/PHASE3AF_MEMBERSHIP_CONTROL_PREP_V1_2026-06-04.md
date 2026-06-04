# Phase3AF Membership Control Prep V1

decision: `PASS_PHASE3AF_MEMBERSHIP_CONTROL_PREP_READY`

## Counts

- `selected_rows`: `31`
- `coverage_fields`: `11`
- `control_columns`: `22`

## Matching Policy

- `same_count_random`: Preserve per-date active count; prefer inactive names on the same date.
- `matched_control`: Preserve per-date and amount/cap bucket active count; fallback to date-level inactive names when bucket sample is insufficient.
- `cap_bucket_source`: final_float_market_cap

## Outputs

- `control_panel`: `runtime\phase3af_membership_control_v1_20260604\phase3af_membership_control_panel_v1.parquet`
- `field_diagnostics_csv`: `reports\phase3af_membership_control_v1_20260604\phase3af_membership_control_field_diagnostics.csv`
- `summary_json`: `reports\phase3af_membership_control_v1_20260604\phase3af_membership_control_prep_v1.json`
- `markdown`: `reports\phase3af_membership_control_v1_20260604\PHASE3AF_MEMBERSHIP_CONTROL_PREP_V1_2026-06-04.md`
