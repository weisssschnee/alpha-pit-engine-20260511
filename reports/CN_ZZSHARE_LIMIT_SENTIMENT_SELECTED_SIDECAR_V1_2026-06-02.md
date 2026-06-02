# CN ZZShare Limit/Sentiment Selected Sidecar v1

decision: `PASS_ZZSHARE_SELECTED_SIDECAR_V1`
rows: `859129`
feature_count: `40`
mean_feature_nonnull_rate: `0.524231`
date_range: `2025-08-06..2026-04-10`

## Table Coverage

- `market_daily`: `{'open_sentiment_daily': {'feature_count': 19, 'mean_nonnull_rate': 0.9940102126688771}, 'sentiment_hot_daily': {'feature_count': 5, 'mean_nonnull_rate': 0.4137364703088826}}`
- `uplimit_stock_event_day`: `{'feature_count': 11, 'mean_nonnull_rate': 0.000469291361578783, 'matched_rows': 413}`
- `ths_hot_stock_day`: `{'feature_count': 5, 'mean_nonnull_rate': 0.001842563805901093, 'matched_rows': 1583}`

## PIT Policy

- Every feature uses the previous selected trading date.
- Same-day `up_limit_time` minute-event usage is not included in this daily sidecar.
- `next_*` labels are absent.
