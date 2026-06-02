# CN Public Enrichment Global Field Route v1

decision: `PASS_GLOBAL_FIELD_ROUTE_LEDGER_READY_FOR_BATCH_PANELIZATION_AND_FACTOR_PACK`
field_count: `2069`
bulk_transform_field_count: `1537`
high_value_unwired_count: `36`

## By Route

- `announcement_pit_feature`: `1408`
- `blocked_future_label`: `14`
- `event_cutoff_key`: `13`
- `index_minute_market_context`: `8`
- `join_key`: `108`
- `lagged_daily_context_feature`: `75`
- `manual_review_required`: `56`
- `metadata`: `50`
- `probe_only_candidate_source`: `250`
- `stock_minute_feature`: `10`
- `text_diagnostic`: `41`
- `timestamped_event_feature`: `36`

## By Family

- `capacity_size`: `82`
- `disclosure_event_flow`: `51`
- `flow_liquidity`: `94`
- `fundamental_quality_risk`: `415`
- `future_label`: `14`
- `group_market_context`: `42`
- `holder_corporate_action`: `52`
- `instrument_key`: `38`
- `leverage_flow`: `39`
- `limit_event_sentiment`: `40`
- `metadata`: `50`
- `other`: `333`
- `price_state`: `597`
- `text_or_description`: `41`
- `time_key_or_cutoff`: `83`
- `tradability_universe`: `98`

## Mature Chain Batch Plan

- `minute_stock_observed_window`: `10` fields, status `mature_chain_available`
- `minute_index_market_context`: `8` fields, status `needs_context_sidecar_before_factor_pack`
- `nonminute_lagged_daily_and_pit`: `1483` fields, status `mature_chain_available_for_panelized_fields`
- `timestamped_limit_event`: `36` fields, status `blocked_from_daily_replay_until_lag_or_event_time_path`
- `probe_to_silver`: `306` fields, status `data_engineering_backlog`
- `blocked_and_diagnostic`: `226` fields, status `not_direct_alpha_input`

## Critical Policy

- Stock 1min fields are usable only after the observed window closes.
- Index 1min fields are market context/regime inputs, not standalone stock ranking alpha.
- Timestamped limit/seal/auction event fields must use event-time evaluator or lag1 daily materialization.
- Probe-only ZZShare fields are not selector data until converted to silver/PIT panels.
- Future labels and `next_*` fields remain blocked.

## Next

- Use `bulk_transform_plan.csv` for mature integrated factor-pack expansion.
- Use `high_value_unwired_fields.csv` as the next data-engineering backlog.
- Do not bypass PIT routes by loading raw event fields into daily replay.

