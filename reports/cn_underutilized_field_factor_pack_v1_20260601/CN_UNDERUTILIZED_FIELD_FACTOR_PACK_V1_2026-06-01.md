# CN Underutilized Field Factor Pack V1

status: `underutilized_field_factor_pack_ready_for_shared_pool_preflight_no_promotion`

- candidate_count: 344

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

## Top Fields

- amount: 88
- volume: 67
- turnover_ratio: 67
- daily_ret: 40
- seal_money: 37
- seal_rate: 37
- seal_circulation_rate: 37
- turnover_ratio_real: 18
- final_float_market_cap: 18
- plate_score: 15
- final_total_market_cap: 8
- float_share: 8
- limit_up_any_close_not_open_in_t3: 6
- limit_up_any_open_not_close_in_t3: 6
- limit_up_close_count_t2: 6
- limit_up_close_count_t3: 6
- limit_up_close_count_t5: 6
- limit_up_close_event: 6
- limit_up_close_not_open: 6
- limit_up_open_not_close: 6
- limit_up_touch_not_close: 6
- limit_up_touch_not_close_count_t3: 6
- limit_up_touch_not_close_count_t5: 6
- open_board_record: 6
- fund_cash_to_assets: 6
- fund_current_ratio: 6
- fund_netprofit_margin: 6
- fund_ocf_to_assets: 6
- fund_ocf_to_netprofit: 6
- fund_research_to_income: 6

## Policy

- official_x0_r3: read_only
- promotion: not_allowed_from_pack_generation
- tradability_raw_fields: not promoted as alpha; remain execution controls
- sector_fields: sector_code/sector are metadata; plate_score is numeric theme proxy
- field_lag: all fields must pass evaluator signal-clock lag policy
