# CN ZZShare Limit Sentiment Selector Pool Preflight V1

decision: `PASS_ZZSHARE_SELECTOR_POOL_PREFLIGHT_HOLD_FULL_G2_SELECTOR`

## Counts

- factor_pack_rows: `49`
- enriched_pool_rows: `437`
- zzshare_rows_in_pool: `49`
- factor_pack_rows_missing_from_pool: `0`
- forbidden_field_hits: `0`
- metadata_missing_rows: `0`
- required_expression_fields: `23`
- required_fields_missing_from_field_gate: `0`
- duplicate_expression_keys_in_pool: `11`
- duplicate_zzshare_expression_keys: `0`

## Factor Lanes

- `zls_auction_money_to_offer`: `1`
- `zls_auction_turnover_to_amount`: `1`
- `zls_event_direct`: `6`
- `zls_event_direct_zrank`: `6`
- `zls_high_board_x_open_board`: `1`
- `zls_hot_rank_direct`: `4`
- `zls_hot_rank_inverse`: `1`
- `zls_hot_rank_x_capacity`: `1`
- `zls_ladder_to_limit_ratio`: `1`
- `zls_lb_height_x_open_board`: `1`
- `zls_limit_up_down_ratio`: `1`
- `zls_market_up_down_ratio`: `1`
- `zls_max_seal_to_amount`: `1`
- `zls_open_board_rate`: `1`
- `zls_seal_to_amount`: `1`
- `zls_sentiment_direct`: `10`
- `zls_sentiment_direct_zrank`: `10`
- `zls_streak_x_seal`: `1`

## Field Gate

- decision: `PASS_ZZSHARE_FIELD_AVAILABILITY_GATE`
- candidate_count: `49`
- required_field_count: `23`
- present_field_count: `23`
- mean_required_nonnull_rate: `0.3850522231558853`
- min_required_nonnull_rate: `0.0003906862819520144`

## Interpretation

ZZShare limit/sentiment candidates are visible in the mature shared pool and their required fields are present in the joined panel.
This is still a selector-pool preflight only; no replay or alpha-quality claim is made.

## Next

`run mature G2 selector-only on the ZZShare joined panel and frozen enriched pool`
