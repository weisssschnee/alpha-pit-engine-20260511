# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-12T11:14:37.134636+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `16`
- candidate rows: `24576`
- unique candidates: `384`
- unique expressions: `384`
- robust min ic_count: `450`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ax_capacity_refine_00325` | 30 | 16 | 0.159701 | `amount|float_share` |
| 2 | `phase3ax_capacity_refine_00317` | 30 | 16 | 0.159314 | `amount|float_share` |
| 3 | `phase3ax_capacity_refine_00279` | 30 | 16 | 0.153964 | `amount|float_share` |
| 4 | `phase3ax_capacity_refine_00326` | 30 | 16 | 0.152287 | `amount|float_share` |
| 5 | `phase3ax_capacity_refine_00318` | 30 | 16 | 0.151663 | `amount|float_share` |
| 6 | `phase3ax_capacity_refine_00317` | 15 | 16 | 0.149810 | `amount|float_share` |
| 7 | `phase3ax_capacity_refine_00325` | 15 | 16 | 0.149641 | `amount|float_share` |
| 8 | `phase3ax_capacity_refine_00280` | 30 | 16 | 0.145133 | `amount|float_share` |
| 9 | `phase3ax_capacity_refine_00279` | 15 | 16 | 0.144760 | `amount|float_share` |
| 10 | `phase3ax_capacity_refine_00095` | 30 | 16 | 0.143108 | `amount|final_float_market_cap` |
| 11 | `phase3ax_capacity_refine_00326` | 15 | 16 | 0.142768 | `amount|float_share` |
| 12 | `phase3ax_capacity_refine_00318` | 15 | 16 | 0.142712 | `amount|float_share` |
| 13 | `phase3ax_capacity_refine_00087` | 30 | 16 | 0.142631 | `amount|final_float_market_cap` |
| 14 | `phase3ax_capacity_refine_00327` | 30 | 16 | 0.139017 | `amount|close|float_share` |
| 15 | `phase3ax_capacity_refine_00216` | 30 | 16 | 0.138688 | `amount|final_total_market_cap` |
| 16 | `phase3ax_capacity_refine_00319` | 30 | 16 | 0.138480 | `amount|close|float_share` |
| 17 | `phase3ax_capacity_refine_00208` | 30 | 16 | 0.138192 | `amount|final_total_market_cap` |
| 18 | `phase3ax_capacity_refine_00062` | 30 | 16 | 0.138029 | `amount|final_float_market_cap` |
| 19 | `phase3ax_capacity_refine_00311` | 30 | 16 | 0.136954 | `amount|close|float_share` |
| 20 | `phase3ax_capacity_refine_00047` | 30 | 16 | 0.136464 | `amount|final_float_market_cap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ax_company_capacity_flow_refinement_aggregate_20260612\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ax_company_capacity_flow_refinement_aggregate_20260612\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ax_company_capacity_flow_refinement_aggregate_20260612\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ax_company_capacity_flow_refinement_aggregate_20260612\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ax_company_capacity_flow_refinement_aggregate_20260612\phase3au_true1min_shard_source_attribution.csv`
