# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-12T13:55:58.092656+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `28`
- candidate rows: `28160`
- unique candidates: `512`
- unique expressions: `512`
- robust min ic_count: `450`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ay_x0_minute_transfer_00499` | 30 | 16 | 0.147071 | `amount|close|final_float_market_cap|float_share` |
| 2 | `phase3ay_x0_minute_transfer_00473` | 30 | 16 | 0.137626 | `amount|volume` |
| 3 | `phase3ay_x0_minute_transfer_00475` | 30 | 16 | 0.137626 | `amount_yuan|volume` |
| 4 | `phase3ay_x0_minute_transfer_00474` | 30 | 16 | 0.137626 | `amount|volume` |
| 5 | `phase3ay_x0_minute_transfer_00499` | 15 | 16 | 0.136741 | `amount|close|final_float_market_cap|float_share` |
| 6 | `phase3ay_x0_minute_transfer_00496` | 30 | 16 | 0.129554 | `amount_yuan|close|final_float_market_cap` |
| 7 | `phase3ay_x0_minute_transfer_00501` | 30 | 16 | 0.129374 | `amount|close|final_float_market_cap|float_share` |
| 8 | `phase3ay_x0_minute_transfer_00488` | 30 | 16 | 0.129091 | `close|final_float_market_cap` |
| 9 | `phase3ay_x0_minute_transfer_00489` | 30 | 16 | 0.129091 | `close|final_float_market_cap` |
| 10 | `phase3ay_x0_minute_transfer_00493` | 30 | 16 | 0.127942 | `amount_yuan|close|final_float_market_cap` |
| 11 | `phase3ay_x0_minute_transfer_00473` | 15 | 16 | 0.127912 | `amount|volume` |
| 12 | `phase3ay_x0_minute_transfer_00474` | 15 | 16 | 0.127912 | `amount|volume` |
| 13 | `phase3ay_x0_minute_transfer_00475` | 15 | 16 | 0.127912 | `amount_yuan|volume` |
| 14 | `phase3ay_x0_minute_transfer_00490` | 30 | 16 | 0.126816 | `amount_yuan|close|final_float_market_cap` |
| 15 | `phase3ay_x0_minute_transfer_00478` | 30 | 16 | 0.125913 | `amount|amount_yuan|final_float_market_cap|volume` |
| 16 | `phase3ay_x0_minute_transfer_00481` | 30 | 16 | 0.125640 | `amount|amount_yuan|final_float_market_cap|volume` |
| 17 | `phase3ay_x0_minute_transfer_00484` | 30 | 16 | 0.125380 | `amount|amount_yuan|final_float_market_cap|volume` |
| 18 | `phase3ay_x0_minute_transfer_00492` | 30 | 16 | 0.124966 | `amount_yuan|close|final_float_market_cap` |
| 19 | `phase3ay_x0_minute_transfer_00495` | 30 | 16 | 0.124714 | `amount_yuan|close|final_float_market_cap` |
| 20 | `phase3ay_x0_minute_transfer_00498` | 30 | 16 | 0.124305 | `amount_yuan|close|final_float_market_cap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ay_company_x0_minute_transfer_aggregate_20260612\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ay_company_x0_minute_transfer_aggregate_20260612\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ay_company_x0_minute_transfer_aggregate_20260612\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ay_company_x0_minute_transfer_aggregate_20260612\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ay_company_x0_minute_transfer_aggregate_20260612\phase3au_true1min_shard_source_attribution.csv`
