# CN New Data Asset Integration v1

decision: `PASS_NEW_DATA_ASSET_REGISTRY_READY_WITH_BLOCKERS`

## Counts

- asset_count: `10`
- field_route_count: `1376`
- accepted_selector_field_count: `531`
- blocked_or_backlog_field_count: `845`
- next_factor_pack_seed_axis_count: `531`

## Accepted Routes

- `announcement_pit_feature`: `495`
- `lagged_market_regime_context`: `23`
- `lagged_stock_heat_context`: `5`
- `timestamped_stock_event_feature`: `8`

## Blockers

- `fundamental_pit_silver/fundamental_cashflow_long`: `invalid_parquet_or_missing_pit_keys`; error=`ArrowInvalid: Parquet magic bytes not found in footer. Either the file is corrupted or this is not a parquet file.`

## Policy

- Fundamentals: use PIT silver only; `NOTICE_DATE`/`UPDATE_DATE` availability is mandatory.
- Limit stock events: same-day use requires event cutoff; otherwise materialize lag1 daily context.
- Daily sentiment/hotness: default T+1 until observable-time audit is stronger.
- Plate fund and advanced ZZShare probes remain data-engineering backlog, not selector inputs.
- `next_*` outcome fields are blocked.

## Next

- Use `next_factor_pack_seed_axes.csv` as the Phase3AD transform seed registry.
- Do not load probe CSVs or future labels into replay panels.
