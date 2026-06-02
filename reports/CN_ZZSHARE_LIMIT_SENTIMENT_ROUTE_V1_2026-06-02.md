# CN ZZShare Limit/Sentiment Route V1

- decision: `PASS_ZZSHARE_LIMIT_SENTIMENT_ROUTE_V1`
- field_count: `79`
- candidate_transform_count: `205`

## Route Counts
- blocked_future_label: `7`
- diagnostic_context: `4`
- key_or_timestamp: `9`
- lagged_daily_context: `23`
- lagged_daily_stock_context: `5`
- metadata: `18`
- minute_event_cutoff: `1`
- minute_event_or_tplus1: `12`

## Coverage
- uplimit_stocks: rows=`8062`, date=`2024-01-02..2026-05-28`, stock_count=`1200`
- open_sentiment_data: rows=`184631`, date=`2024-01-02..2026-06-02`
- sentiment_hot_day: rows=`63000`, date=`2025-12-26..2026-06-01`
- ths_hot_top: rows=`6300`, date=`2024-01-01..2026-05-29`, stock_count=`928`

## PIT Boundary

- `uplimit_stocks.up_limit_time` is a timestamped event key. It is usable only after the event timestamp for minute decisions.
- `open_sentiment_data`, `sentiment_hot_day`, and `ths_hot_top` are T+1 lagged context until observable intraday timestamp is proven.
- `next_*` fields are blocked as future labels and must not enter selector/replay expressions.

## Next Action

Build a dedicated ZZShare event/context candidate pack v1 from `candidate_transform_plan.csv`, then run selector-only before replay.
