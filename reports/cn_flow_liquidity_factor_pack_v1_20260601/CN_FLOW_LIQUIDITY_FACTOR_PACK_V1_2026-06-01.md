# CN Flow Liquidity Factor Pack V1

status: `flow_liquidity_factor_pack_ready_for_shared_pool_preflight_no_promotion`

- candidate_count: 306

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

## Policy

- official_x0_r3: read_only
- promotion: not_allowed_from_pack_generation
- flow_fields: must be lagged by evaluator signal clock
- capacity_fields: role_separated_as_alpha_candidate_or_filter_proxy
- limit_seal_fields: diagnostic until tradability and lag checks pass
