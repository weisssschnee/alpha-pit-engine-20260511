# CN Phase3AD Selected Sidecar v1

decision: `PASS_PHASE3AD_SELECTED_SIDECAR_BUILT`

## Counts

- rows: `988005`
- date_range: `2025-08-06 .. 2026-04-10`
- feature_count: `531`
- alias_count: `531`
- mean_feature_nonnull_rate: `0.319758`
- nonzero_feature_count: `426`
- zero_nonnull_feature_count: `105`
- lt_1pct_nonnull_feature_count: `212`
- lt_5pct_nonnull_feature_count: `277`

## Route Alias Counts

- `announcement_pit_feature`: `495`
- `lagged_market_regime_context`: `23`
- `lagged_stock_heat_context`: `5`
- `timestamped_stock_event_feature`: `8`

## Route Coverage

- `announcement_pit_feature`: features `495`, nonzero `390`, zero `105`, mean_nonnull `0.301594`
- `lagged_market_regime_context`: features `23`, nonzero `23`, zero `0`, mean_nonnull `0.890909`
- `lagged_stock_heat_context`: features `5`, nonzero `5`, zero `0`, mean_nonnull `0.001618`
- `timestamped_stock_event_feature`: features `8`, nonzero `8`, zero `0`, mean_nonnull `0.000409`

## PIT Policy

- `fundamental`: max(NOTICE_DATE, UPDATE_DATE) + 1 calendar day; no REPORT_DATE-only availability
- `uplimit_stock_event_day`: materialized as previous selected trading day for this daily sidecar
- `sentiment_hot/open_sentiment`: previous selected trading day market context
- `ths_hot_stock_day`: previous selected trading day stock heat context

## Boundary

This artifact only materializes selected-row sidecar fields. It does not validate formula performance.

## Output

`runtime\cn_phase3ad_full_index_sidecar_v1_20260603\phase3ad_selected_sidecar.parquet`
