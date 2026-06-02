# CN Factor Pack Shared Pool Preflight

decision: `PASS_FACTOR_PACK_READY_FOR_G2_SELECTOR`

## Scope

This is a no-replay, no-promotion preflight for field/factor pack integration into the mature shared pool.

## Counts

- enriched pool rows: 1631
- factor pack rows: 834
- factor pack rows found in enriched pool: 834
- event rows added after search-memory dedupe: 1243
- memory duplicates skipped: 0
- factor fields used: 107
- missing from derived feature panel: 0
- missing from mature signal-vector panel: 0

## Factor Lanes

- direct_event: 240
- event_curve: 120
- event_residual_size: 80
- event_x_flow: 288
- event_x_theme: 32
- fundamental_quality: 30
- fundamental_risk_inverse: 9
- fundamental_size_residual: 5
- fundamental_x_event: 30

## Selector Micro Smoke

- selector_report_path: runtime\cn_research_factor_pack_v2_selector_gate_20260531\selector\aa\phase3_selection_only_report.json
- selector_report_present: True
- selected_count: 64
- event_candidates_selected: 12
- selector_uses_forbidden_fields: False
- signal_vector_proxy_requirement_pass: True
- signal_vector_store_ready: True

## Interpretation

The field/factor layer passed this preflight. Selector/replay gates are still separate.

## Outputs

- cn_factor_pack_shared_pool_preflight.json
- cn_factor_pack_field_coverage.csv
- cn_factor_pack_candidate_integration.csv
