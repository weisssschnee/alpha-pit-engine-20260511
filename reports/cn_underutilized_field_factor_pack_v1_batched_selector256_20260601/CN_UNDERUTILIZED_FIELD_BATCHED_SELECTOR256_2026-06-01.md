# CN Underutilized Field Batched Selector256

decision: `PASS_BATCHED_SELECTOR_SMOKE_NO_REPLAY`

## Counts

- shard_count: 4
- combined_selected_rows: 256
- combined_unique_selected_rows: 215

## Combined Selected Source Lanes

- cn_flow_liquidity_feature_layer: 89
- cn_research_feature_layer_v2: 47
- cn_underutilized_field_feature_layer: 73
- event_derived_feature_layer: 6

## Combined Selected Factor Lanes

- amihud_illiquidity: 4
- capacity_normalized_activity: 5
- capacity_normalized_flow: 4
- capacity_residual_activity: 7
- capacity_residual_flow: 1
- event_x_flow_liquidity: 28
- event_x_seal_flow: 12
- event_x_theme: 6
- flow_impulse: 7
- flow_ratio_curve: 3
- flow_relative_activity: 15
- flow_volatility: 8
- fundamental_capacity_value: 2
- fundamental_quality: 18
- fundamental_risk_inverse: 8
- fundamental_size_residual: 4
- fundamental_x_activity: 12
- fundamental_x_event: 17
- fundamental_x_flow: 16
- limit_seal_flow: 12
- price_flow_divergence: 17
- seal_to_amount: 6
- theme_activity_proxy: 3

## Shards

- event_seal_flow: status=completed selected=64 elapsed=113.252s
- pure_flow_price: status=completed selected=64 elapsed=279.474s
- capacity_liquidity_cost: status=completed selected=64 elapsed=87.565s
- fund_theme_activity: status=completed selected=64 elapsed=124.232s
