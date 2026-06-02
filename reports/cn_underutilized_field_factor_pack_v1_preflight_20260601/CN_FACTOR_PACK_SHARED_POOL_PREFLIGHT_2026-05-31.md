# CN Factor Pack Shared Pool Preflight

decision: `PASS_FACTOR_PACK_READY_FOR_G2_SELECTOR`

## Scope

This is a no-replay, no-promotion preflight for field/factor pack integration into the mature shared pool.

## Counts

- enriched pool rows: 2137
- factor pack rows: 344
- factor pack rows found in enriched pool: 344
- event rows added after search-memory dedupe: 506
- memory duplicates skipped: 0
- factor fields used: 39
- missing from derived feature panel: 0
- missing from mature signal-vector panel: 0

## Factor Lanes

- amihud_capacity_cost: 4
- capacity_normalized_activity: 16
- capacity_residual_activity: 16
- event_x_seal_flow: 78
- flow_impulse_curve: 16
- flow_ratio_curve: 40
- flow_volatility_curve: 16
- fundamental_capacity_value: 2
- fundamental_x_activity: 78
- limit_seal_flow: 24
- price_flow_confirmation: 12
- price_flow_correlation: 12
- price_flow_divergence: 12
- seal_to_amount: 9
- theme_activity_proxy: 9

## Selector Micro Smoke

- selector_report_path: runtime\cn_flow_liquidity_factor_pack_v1_selector64_20260601\selector_safe_v2\aa\phase3_selection_only_report.json
- selector_report_present: True
- selected_count: 64
- event_candidates_selected: 13
- selector_uses_forbidden_fields: False
- signal_vector_proxy_requirement_pass: True
- signal_vector_store_ready: True

## Interpretation

The field/factor layer passed this preflight. Selector/replay gates are still separate.

## Outputs

- cn_factor_pack_shared_pool_preflight.json
- cn_factor_pack_field_coverage.csv
- cn_factor_pack_candidate_integration.csv
