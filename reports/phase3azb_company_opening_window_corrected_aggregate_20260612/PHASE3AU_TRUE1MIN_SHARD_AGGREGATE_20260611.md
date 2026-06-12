# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-12T11:14:36.216607+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `16`
- candidate rows: `9216`
- unique candidates: `144`
- unique expressions: `144`
- robust min ic_count: `450`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3azb_opening_window_corrected_00105` | 30 | 16 | 0.124034 | `m1_first30_amount` |
| 2 | `phase3azb_opening_window_corrected_00106` | 30 | 16 | 0.124034 | `m1_first30_amount` |
| 3 | `phase3azb_opening_window_corrected_00057` | 30 | 16 | 0.122667 | `m1_first15_amount` |
| 4 | `phase3azb_opening_window_corrected_00058` | 30 | 16 | 0.122667 | `m1_first15_amount` |
| 5 | `phase3azb_opening_window_corrected_00107` | 30 | 16 | 0.121915 | `m1_first30_high|m1_first30_low|open` |
| 6 | `phase3azb_opening_window_corrected_00108` | 30 | 16 | 0.121915 | `m1_first30_high|m1_first30_low|open` |
| 7 | `phase3azb_opening_window_corrected_00101` | 30 | 16 | 0.121782 | `m1_first30_range` |
| 8 | `phase3azb_opening_window_corrected_00102` | 30 | 16 | 0.121782 | `m1_first30_range` |
| 9 | `phase3azb_opening_window_corrected_00144` | 30 | 16 | 0.120143 | `m1_first30_range|volume` |
| 10 | `phase3azb_opening_window_corrected_00135` | 30 | 16 | 0.119968 | `m1_first30_range|m1_first30_vol` |
| 11 | `phase3azb_opening_window_corrected_00059` | 30 | 16 | 0.119543 | `m1_first15_high|m1_first15_low|open` |
| 12 | `phase3azb_opening_window_corrected_00060` | 30 | 16 | 0.119543 | `m1_first15_high|m1_first15_low|open` |
| 13 | `phase3azb_opening_window_corrected_00053` | 30 | 16 | 0.119294 | `m1_first15_range` |
| 14 | `phase3azb_opening_window_corrected_00054` | 30 | 16 | 0.119294 | `m1_first15_range` |
| 15 | `phase3azb_opening_window_corrected_00087` | 30 | 16 | 0.118178 | `m1_first15_range|m1_first15_vol` |
| 16 | `phase3azb_opening_window_corrected_00009` | 30 | 16 | 0.118105 | `m1_first5_amount` |
| 17 | `phase3azb_opening_window_corrected_00010` | 30 | 16 | 0.118105 | `m1_first5_amount` |
| 18 | `phase3azb_opening_window_corrected_00096` | 30 | 16 | 0.117944 | `m1_first15_range|volume` |
| 19 | `phase3azb_opening_window_corrected_00105` | 15 | 16 | 0.115530 | `m1_first30_amount` |
| 20 | `phase3azb_opening_window_corrected_00106` | 15 | 16 | 0.115530 | `m1_first30_amount` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3azb_company_opening_window_corrected_aggregate_20260612\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3azb_company_opening_window_corrected_aggregate_20260612\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3azb_company_opening_window_corrected_aggregate_20260612\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3azb_company_opening_window_corrected_aggregate_20260612\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3azb_company_opening_window_corrected_aggregate_20260612\phase3au_true1min_shard_source_attribution.csv`
