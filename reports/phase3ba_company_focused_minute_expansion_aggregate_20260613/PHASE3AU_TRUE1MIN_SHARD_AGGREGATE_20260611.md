# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-12T18:55:22.912882+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `112`
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
| 1 | `phase3ba_focused_minute_expansion_00296` | 30 | 16 | 0.171042 | `amount|final_total_market_cap|vwap` |
| 2 | `phase3ba_focused_minute_expansion_00302` | 30 | 16 | 0.170684 | `amount|final_total_market_cap|vwap` |
| 3 | `phase3ba_focused_minute_expansion_00287` | 30 | 16 | 0.170444 | `amount|final_float_market_cap|vwap` |
| 4 | `phase3ba_focused_minute_expansion_00290` | 30 | 16 | 0.170138 | `amount|final_float_market_cap|vwap` |
| 5 | `phase3ba_focused_minute_expansion_00359` | 30 | 16 | 0.167885 | `amount|close|final_total_market_cap|vwap` |
| 6 | `phase3ba_focused_minute_expansion_00317` | 30 | 16 | 0.167230 | `amount|close|final_float_market_cap|vwap` |
| 7 | `phase3ba_focused_minute_expansion_00323` | 30 | 16 | 0.167033 | `amount|close|final_float_market_cap|vwap` |
| 8 | `phase3ba_focused_minute_expansion_00329` | 30 | 16 | 0.166175 | `amount|close|final_float_market_cap|vwap` |
| 9 | `phase3ba_focused_minute_expansion_00341` | 30 | 16 | 0.165988 | `amount|final_total_market_cap|vwap` |
| 10 | `phase3ba_focused_minute_expansion_00305` | 30 | 16 | 0.165771 | `amount|final_float_market_cap|vwap` |
| 11 | `phase3ba_focused_minute_expansion_00338` | 30 | 16 | 0.165710 | `amount|close|final_float_market_cap|vwap` |
| 12 | `phase3ba_focused_minute_expansion_00356` | 30 | 16 | 0.165407 | `amount|final_total_market_cap|vwap` |
| 13 | `phase3ba_focused_minute_expansion_00311` | 30 | 16 | 0.165214 | `amount|final_float_market_cap|vwap` |
| 14 | `phase3ba_focused_minute_expansion_00320` | 30 | 16 | 0.165045 | `amount|final_float_market_cap|vwap` |
| 15 | `phase3ba_focused_minute_expansion_00350` | 30 | 16 | 0.164824 | `amount|close|final_float_market_cap|vwap` |
| 16 | `phase3ba_focused_minute_expansion_00353` | 30 | 16 | 0.164351 | `amount|final_float_market_cap|vwap` |
| 17 | `phase3ba_focused_minute_expansion_00269` | 30 | 16 | 0.164252 | `amount|float_share|vwap` |
| 18 | `phase3ba_focused_minute_expansion_00272` | 30 | 16 | 0.164127 | `amount|float_share|vwap` |
| 19 | `phase3ba_focused_minute_expansion_00663` | 30 | 16 | 0.163647 | `amount|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 20 | `phase3ba_focused_minute_expansion_00667` | 30 | 16 | 0.163578 | `amount|float_share|m1_first30_range|vwap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ba_company_focused_minute_expansion_aggregate_20260613\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ba_company_focused_minute_expansion_aggregate_20260613\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ba_company_focused_minute_expansion_aggregate_20260613\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ba_company_focused_minute_expansion_aggregate_20260613\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ba_company_focused_minute_expansion_aggregate_20260613\phase3au_true1min_shard_source_attribution.csv`
