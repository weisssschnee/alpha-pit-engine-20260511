# CN Factor Pack Shared Pool Preflight

decision: `PASS_FACTOR_PACK_ENRICHMENT_HOLD_SIGNAL_VECTOR_DATASET_JOIN`

## Scope

This is a no-replay, no-promotion preflight for field/factor pack integration into the mature shared pool.

## Counts

- enriched pool rows: 1136
- factor pack rows: 760
- factor pack rows found in enriched pool: 748
- event rows added after search-memory dedupe: 748
- memory duplicates skipped: 421
- factor fields used: 89
- missing from derived feature panel: 0
- missing from mature signal-vector panel: 88

## Factor Lanes

- direct_event: 240
- event_curve: 120
- event_residual_size: 80
- event_x_flow: 288
- event_x_theme: 32

## Selector Micro Smoke

- selector_report_path: runtime\cn_factor_pack_phase3aa_micro_selector_20260531\selector\aa\phase3_selection_only_report.json
- selector_report_present: True
- selected_count: 16
- event_candidates_selected: 8
- selector_uses_forbidden_fields: False
- signal_vector_proxy_requirement_pass: False
- signal_vector_store_ready: False

## Interpretation

The factor pack is visible in the mature shared pool and search-memory dedupe is active, but the mature signal-vector panel does not yet contain the new derived event fields.
Do not rerun large G2 selection until the derived feature panel is joined into the evaluator/signal-vector dataset.

## Outputs

- cn_factor_pack_shared_pool_preflight.json
- cn_factor_pack_field_coverage.csv
- cn_factor_pack_candidate_integration.csv
