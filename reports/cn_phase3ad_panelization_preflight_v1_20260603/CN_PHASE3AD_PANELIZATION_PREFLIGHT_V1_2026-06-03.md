# CN Phase3AD Panelization Preflight v1

decision: `PASS_PHASE3AD_PANELIZATION_PREFLIGHT`

## Counts

- candidate_count: `1113`
- alias_count: `531`
- source_count: `6`
- materializable_alias_count: `531`
- blocked_alias_count: `0`
- materializable_candidate_count: `1113`
- blocked_candidate_count: `0`
- duplicate_alias_count: `0`
- missing_input_field_count: `0`
- forbidden_candidate_count: `0`

## Materializable Alias Routes

- `announcement_pit_feature`: `495`
- `lagged_market_regime_context`: `23`
- `lagged_stock_heat_context`: `5`
- `timestamped_stock_event_feature`: `8`

## Materializable Candidate Lanes

- `atomic_direct_rank`: `524`
- `atomic_inverse_rank`: `522`
- `event_auction_buy_offer_imbalance`: `1`
- `event_auction_money_share`: `1`
- `event_auction_premax_strength`: `1`
- `event_auction_turnover_share`: `1`
- `event_seal_close_strength`: `1`
- `event_seal_max_strength`: `1`
- `event_x_market_sentiment`: `25`
- `fundamental_cash_asset_quality`: `1`
- `fundamental_cost_intensity_inverse`: `1`
- `fundamental_current_ratio`: `1`
- `fundamental_debt_asset_inverse`: `1`
- `fundamental_equity_asset_quality`: `1`
- `fundamental_finance_expense_inverse`: `1`
- `fundamental_fixed_asset_intensity`: `1`
- `fundamental_goodwill_asset_inverse`: `1`
- `fundamental_intangible_asset_inverse`: `1`
- `fundamental_inventory_asset_inverse`: `1`
- `fundamental_manage_expense_intensity_inverse`: `1`
- `fundamental_netprofit_margin`: `1`
- `fundamental_operate_profit_margin`: `1`
- `fundamental_parent_netprofit_margin`: `1`
- `fundamental_research_intensity`: `1`
- `fundamental_sales_expense_intensity_inverse`: `1`
- `fundamental_total_profit_margin`: `1`
- `fundamental_yoy_goodwill_yoy`: `1`
- `fundamental_yoy_inventory_yoy`: `1`
- `fundamental_yoy_netprofit_yoy`: `1`
- `fundamental_yoy_operate_profit_yoy`: `1`
- `fundamental_yoy_parent_netprofit_yoy`: `1`
- `fundamental_yoy_total_assets_yoy`: `1`
- `fundamental_yoy_total_liabilities_yoy`: `1`
- `fundamental_yoy_total_operate_income_yoy`: `1`
- `sentiment_big_fail_pressure_inverse`: `1`
- `sentiment_board_continuation_ratio`: `1`
- `sentiment_downlimit_pressure_inverse`: `1`
- `sentiment_floor_to_ceiling_strength`: `1`
- `sentiment_heaven_earth_inverse`: `1`
- `sentiment_limit_density`: `1`
- `sentiment_market_high_board`: `1`
- `sentiment_open_board_pressure_inverse`: `1`
- `stock_heat_rank_improvement`: `1`
- `stock_heat_rank_strength`: `1`
- `stock_heat_small_liquid_momentum`: `1`

## Boundary

This preflight only checks schemas, aliases, required keys, and forbidden fields. It does not write a replay panel and does not validate alpha performance.

## Next

`build_phase3ad_selected_sidecars_then_selector_only_smoke`
