# CN ZZShare Limit/Sentiment Canonical V1

decision: `PASS_ZZSHARE_CANONICAL_V1_WITH_GRAIN_FIXES`

## Tables

- `uplimit_stock_event_day`: raw_rows=`8062`, canonical_rows=`1668`, output=`G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602\canonical_v1\uplimit_stock_event_day.parquet`
- `open_sentiment_daily`: raw_rows=`184631`, canonical_rows=`582`, output=`G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602\canonical_v1\open_sentiment_daily.parquet`
- `sentiment_hot_daily`: raw_rows=`63000`, canonical_rows=`100`, output=`G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602\canonical_v1\sentiment_hot_daily.parquet`
- `ths_hot_stock_day`: raw_rows=`6300`, canonical_rows=`6300`, output=`G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602\canonical_v1\ths_hot_stock_day.parquet`

## Grain Fixes

- `open_sentiment_data` and `sentiment_hot_day` are compressed to one canonical row per date.
- `uplimit_stocks` is compressed to stock-date event rows; repeated plate/theme rows are retained as joined lists.
- `next_*` fields are excluded from the feature table and remain labels/audit only.
- All market sentiment and hot-rank outputs are T+1 context until observable timestamps are proven.
