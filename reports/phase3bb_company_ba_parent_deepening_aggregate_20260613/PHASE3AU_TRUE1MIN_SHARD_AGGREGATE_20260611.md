# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-13T05:16:29.672800+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `16`
- candidate rows: `49152`
- unique candidates: `768`
- unique expressions: `768`
- robust min ic_count: `450`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ba_focused_minute_expansion_00269` | 30 | 16 | 0.171219 | `amount|final_total_market_cap|float_share|vwap` |
| 2 | `phase3ba_focused_minute_expansion_00437` | 30 | 16 | 0.170803 | `amount|final_total_market_cap|float_share|vwap` |
| 3 | `phase3ba_focused_minute_expansion_00440` | 30 | 16 | 0.170710 | `amount|final_total_market_cap|float_share|vwap` |
| 4 | `phase3ba_focused_minute_expansion_00272` | 30 | 16 | 0.170628 | `amount|final_total_market_cap|float_share|vwap` |
| 5 | `phase3ba_focused_minute_expansion_00443` | 30 | 16 | 0.168307 | `amount|final_total_market_cap|float_share|vwap` |
| 6 | `phase3ba_focused_minute_expansion_00663` | 30 | 16 | 0.168294 | `amount|final_total_market_cap|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 7 | `phase3ba_focused_minute_expansion_00275` | 30 | 16 | 0.168255 | `amount|final_total_market_cap|float_share|vwap` |
| 8 | `phase3ba_focused_minute_expansion_00667` | 30 | 16 | 0.168222 | `amount|final_total_market_cap|float_share|m1_first30_range|vwap` |
| 9 | `phase3ba_focused_minute_expansion_00683` | 30 | 16 | 0.167754 | `amount|final_total_market_cap|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 10 | `phase3ba_focused_minute_expansion_00278` | 30 | 16 | 0.167741 | `amount|final_total_market_cap|float_share|vwap` |
| 11 | `phase3ba_focused_minute_expansion_00687` | 30 | 16 | 0.167673 | `amount|final_total_market_cap|float_share|m1_first30_range|vwap` |
| 12 | `phase3ba_focused_minute_expansion_00446` | 30 | 16 | 0.167314 | `amount|final_total_market_cap|float_share|vwap` |
| 13 | `phase3ba_focused_minute_expansion_00281` | 30 | 16 | 0.167244 | `amount|final_total_market_cap|float_share|vwap` |
| 14 | `phase3ba_focused_minute_expansion_00449` | 30 | 16 | 0.167174 | `amount|final_total_market_cap|float_share|vwap` |
| 15 | `phase3ba_focused_minute_expansion_00287` | 30 | 16 | 0.166603 | `amount|final_float_market_cap|final_total_market_cap|vwap` |
| 16 | `phase3ba_focused_minute_expansion_00455` | 30 | 16 | 0.166269 | `amount|final_float_market_cap|final_total_market_cap|vwap` |
| 17 | `phase3ba_focused_minute_expansion_00458` | 30 | 16 | 0.166146 | `amount|final_float_market_cap|final_total_market_cap|vwap` |
| 18 | `phase3ba_focused_minute_expansion_00290` | 30 | 16 | 0.165933 | `amount|final_float_market_cap|final_total_market_cap|vwap` |
| 19 | `phase3ba_focused_minute_expansion_00723` | 30 | 16 | 0.165651 | `amount|final_total_market_cap|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 20 | `phase3ba_focused_minute_expansion_00727` | 30 | 16 | 0.165566 | `amount|final_total_market_cap|float_share|m1_first30_range|vwap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_source_attribution.csv`
