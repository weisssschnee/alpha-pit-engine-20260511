# CN Integrated Factor Pack v1

status: `integrated_feature_factor_pack_ready_for_shared_pool_preflight_no_promotion`
candidate_count: `211`
materialized_selector_field_count: `140`

## Factor Lanes

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

## Policy

- official X0/R3 remains read-only.
- This pack is not alpha proof and cannot promote without selector/replay audits.
- `label_*` and `meta_*` fields are excluded.
- 1min features must respect observed-window timing.
