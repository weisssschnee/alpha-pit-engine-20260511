# CN Integrated Factor Pack Selector Preflight

decision: `PASS_INTEGRATED_FACTOR_PACK_SHARED_POOL_LIGHT_PREFLIGHT_HOLD_FULL_G2_SELECTOR`

## Counts

- factor_pack_rows: `211`
- enriched_pool_rows: `1019`
- integrated_rows_in_pool: `211`
- factor_pack_rows_missing_from_pool: `0`
- forbidden_field_hits: `0`
- missing_metadata_rows: `0`
- duplicate_expression_keys_in_pool: `11`
- duplicate_integrated_expression_keys: `0`
- transform_plan_rows: `474`

## Injected Factor Lanes

- `fundamental_quality_direct`: `5`
- `fundamental_quality_direct_zrank`: `5`
- `fundamental_risk_inverse`: `3`
- `holder_dispersion_inverse`: `3`
- `holder_structure_direct`: `5`
- `market_regime_x_signal`: `70`
- `minute_direct_rank`: `19`
- `minute_direct_rank_zrank`: `24`
- `minute_early_amount_share`: `3`
- `minute_early_range`: `3`
- `minute_early_reversal_pressure`: `1`
- `minute_early_volume_share`: `3`
- `minute_frontloaded_amount`: `1`
- `minute_last_vs_vwap_pressure`: `3`
- `minute_vwap_pressure`: `3`
- `rzrq_balance_normalized_flow`: `10`
- `rzrq_direct_rank`: `24`
- `rzrq_direct_rank_zrank`: `24`
- `rzrq_financing_net_flow`: `1`
- `rzrq_short_net_flow`: `1`

## Interpretation

The integrated pack is safely visible in the mature shared pool.
Full G2 selector did not complete in interactive runtime, so this is not a selector-win claim.

## Next

`run micro-G2 selector with reduced pool/sample or company-machine full selector-only job`
