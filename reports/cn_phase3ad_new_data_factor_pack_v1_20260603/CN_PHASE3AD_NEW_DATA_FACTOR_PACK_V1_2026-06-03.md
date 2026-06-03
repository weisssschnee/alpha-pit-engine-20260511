# CN Phase3AD New Data Factor Pack v1

decision: `PASS_PHASE3AD_FACTOR_PACK_READY_FOR_PANELIZATION_PREFLIGHT`

- candidate_count: `1113`
- alias_count: `531`
- source_seed_axes: `runtime\field_registry\cn_new_data_asset_integration_v1_20260603\next_factor_pack_seed_axes.csv`

## Factor Lanes

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

## Boundaries

- This pack is not a replay result and does not promote any alpha.
- Formula fields use panel aliases from `field_alias_map.csv`; panelization must materialize those aliases before replay.
- Fundamental formulas require `NOTICE_DATE`/`UPDATE_DATE` lag.
- Limit event formulas require event cutoff or lag1 daily materialization.
- X0/R3 remains read-only.

## Next

- Run panelization preflight for all `input_fields`.
- Build selected sidecars for panel aliases.
- Run selector-only smoke before any replay.
