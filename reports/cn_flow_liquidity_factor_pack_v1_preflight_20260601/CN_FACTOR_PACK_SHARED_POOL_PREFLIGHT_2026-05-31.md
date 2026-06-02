# CN Factor Pack Shared Pool Preflight

decision: `PASS_FACTOR_PACK_READY_FOR_G2_SELECTOR`

## Scope

This is a no-replay, no-promotion preflight for field/factor pack integration into the mature shared pool.

## Counts

- enriched pool rows: 1937
- factor pack rows: 306
- factor pack rows found in enriched pool: 306
- event rows added after search-memory dedupe: 306
- memory duplicates skipped: 0
- factor fields used: 26
- missing from derived feature panel: 0
- missing from mature signal-vector panel: 0

## Factor Lanes

- amihud_illiquidity: 4
- capacity_normalized_flow: 8
- capacity_residual_flow: 4
- event_x_flow_liquidity: 180
- flow_impulse: 16
- flow_relative_activity: 32
- flow_volatility: 16
- fundamental_x_flow: 30
- price_flow_confirmation: 8
- price_flow_divergence: 8

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
