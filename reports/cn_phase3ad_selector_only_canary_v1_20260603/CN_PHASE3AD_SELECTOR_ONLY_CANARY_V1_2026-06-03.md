# CN Phase3AD Selector-Only Canary v1

decision: `PASS_PHASE3AD_SELECTOR_ONLY_CANARY`

## Counts

- selected_count: `32`
- strict_audit_budget: `32`
- budget_sum: `32`
- candidate_pool_count: `180`
- candidate_pool_count_before_prefilter: `1065`
- newdata_selected_count: `16`
- event_candidates_selected: `8`
- fundamental_candidates_selected: `8`

## Selected New-Data Factor Lanes

- `event_auction_premax_strength`: `1`
- `stock_heat_small_liquid_momentum`: `1`
- `event_auction_buy_offer_imbalance`: `1`
- `stock_heat_rank_strength`: `1`
- `sentiment_downlimit_pressure_inverse`: `1`
- `fundamental_inventory_asset_inverse`: `1`
- `event_seal_max_strength`: `1`
- `atomic_direct_rank`: `2`
- `fundamental_yoy_operate_profit_yoy`: `1`
- `fundamental_intangible_asset_inverse`: `1`
- `fundamental_sales_expense_intensity_inverse`: `1`
- `fundamental_operate_profit_margin`: `1`
- `fundamental_yoy_goodwill_yoy`: `1`
- `fundamental_yoy_inventory_yoy`: `1`
- `fundamental_finance_expense_inverse`: `1`

## Guards

- selector_uses_forbidden_fields: `False`
- signal_vector_proxy_requirement_pass: `True`

## Boundary

This is selector-only. It proves the new-data sidecar and coverage-filtered formulas can be evaluated and selected by the mature G2 path. It does not prove replay/deployability.
