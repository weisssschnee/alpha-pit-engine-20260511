# CN Phase3AD HFQ Valuation Selector-Only Canary v1

decision: `PASS_HFQ_VALUATION_SELECTOR_ONLY_CANARY`

## Result

- scope: `selector_only_no_replay`
- selected_count: `32`
- HFQ valuation/liquidity candidates in pool: `12`
- HFQ valuation/liquidity candidates selected: `9`
- selected selector buckets: `{'fundamental_pit_feature_layer': 6, 'research_factor_feature_layer': 3}`
- forbidden replay-label use: `False`
- signal-vector proxy requirement: `True`

## Selected HFQ Candidates

- rank `14` `valuation_low_pe`: `CSRank($ctx_hfq_inv_pe_ttm_lag1)`
- rank `15` `valuation_low_pb_x_liquidity`: `CSRank(Mul($ctx_hfq_inv_pb_lag1,CSRank($ctx_hfq_turnover_ratio_lag1)))`
- rank `17` `valuation_low_pe_raw`: `CSRank(Neg($ctx_hfq_pe_ttm_lag1))`
- rank `18` `valuation_low_ps_x_float_size`: `CSRank(Div($ctx_hfq_inv_ps_ttm_lag1,Add(Abs(Log(Add($ctx_hfq_float_market_cap_yuan_lag1,1))),0.000001)))`
- rank `19` `valuation_low_pb`: `CSRank($ctx_hfq_inv_pb_lag1)`
- rank `20` `liquidity_volume_ratio`: `CSRank($ctx_hfq_volume_ratio_lag1)`
- rank `21` `liquidity_turnover_ratio`: `CSRank($ctx_hfq_turnover_ratio_lag1)`
- rank `22` `valuation_low_ps`: `CSRank($ctx_hfq_inv_ps_ttm_lag1)`
- rank `23` `valuation_pb_size_adjusted`: `CSRank(Div($ctx_hfq_inv_pb_lag1,Add(Abs(Log(Add($ctx_hfq_float_market_cap_yuan_lag1,1))),0.000001)))`

## Interpretation

PE/PB/PS and volume/turnover-ratio were not present in the prior mature evaluator panel or Phase3AD fullA fundamental pack. This canary confirms the lagged HFQ valuation route is materialized and that the mature selector is willing to allocate queue budget to these fields.

This is not replay evidence. The result only supports selector admission for a later replay/style audit.
