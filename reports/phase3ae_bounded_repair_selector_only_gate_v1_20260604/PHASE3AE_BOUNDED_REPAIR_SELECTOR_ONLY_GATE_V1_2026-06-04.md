# Phase3AE Bounded Repair Selector-Only Gate V1

decision: `PASS_AE2_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_HOLD_REPLAY_CANARY`

## Counts

- source_factor_pack_candidates: `686`
- available_candidates: `686`
- value_filtered_candidates: `294`
- missing_field_candidates: `0`
- low_coverage_candidates: `392`
- base_pool_rows: `1065`
- enriched_pool_rows: `1257`
- ae2_rows_in_pool: `192`
- selector_selected_count: `64`
- ae2_selected_count: `31`
- selector_audit_rows: `379`
- forbidden_selected_hits: `0`
- low_coverage_selected_hits: `0`
- missing_audit_metadata_rows: `0`

## AE2 Selected By Factor Lane

- `announcement_pit_formula_lane`: `9`
- `event_state_machine_formula_lane`: `15`
- `lagged_daily_formula_lane`: `7`

## Blockers

- none

## Interpretation

AE2 bounded repair candidates are panel-visible and selected by the mature G2 selector in a no-replay dry run.
This only permits a 64-audited replay canary after coverage-mask and shuffled-field placebo checks.

## Outputs

- summary_json: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_selector_only_gate_v1.json`
- markdown: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\PHASE3AE_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_V1_2026-06-04.md`
- ae2_selected_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_selected_candidates.csv`
- missing_field_candidates_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_missing_field_candidates.csv`
- field_locations_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_field_locations.csv`
- value_coverage_fields_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_value_coverage_fields.csv`
- low_coverage_candidates_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_low_coverage_candidates.csv`
- low_coverage_selected_hits_csv: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_low_coverage_selected_hits.csv`
- joined_panel_report: `reports\phase3ae_bounded_repair_selector_only_gate_v1_20260604\phase3ae_bounded_repair_joined_panel_report.json`
