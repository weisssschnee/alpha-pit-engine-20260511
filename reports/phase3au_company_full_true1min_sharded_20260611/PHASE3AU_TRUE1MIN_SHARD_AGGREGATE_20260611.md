# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T16:17:59.789365+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13']`
- attempt count: `14`
- candidate rows: `60872`
- unique candidates: `1087`
- unique expressions: `1075`
- robust min ic_count: `20`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 14 | 0.138873 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 14 | 0.136625 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 14 | 0.133170 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 14 | 0.132151 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 14 | 0.131032 | `amount|final_float_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 14 | 0.130833 | `amount|final_float_market_cap` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 14 | 0.129787 | `amount|final_float_market_cap` |
| 8 | `phase3ae_brepair_v1_00358` | 30 | 14 | 0.129528 | `ctx_holder_close_price` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 14 | 0.128980 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 14 | 0.128385 | `amount|final_float_market_cap` |
| 11 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 14 | 0.125823 | `amount|final_total_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 14 | 0.125776 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 14 | 0.125627 | `amount|final_float_market_cap` |
| 14 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 14 | 0.124128 | `amount|final_total_market_cap` |
| 15 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 14 | 0.123339 | `amount|final_float_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 14 | 0.123016 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 14 | 0.121756 | `amount|final_total_market_cap` |
| 18 | `phase3ae_brepair_v1_00373` | 30 | 14 | 0.120992 | `ctx_fund_cf_total_operate_inflow` |
| 19 | `phase3ae_brepair_v1_00372` | 30 | 14 | 0.120962 | `ctx_fund_cf_total_operate_inflow` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 14 | 0.119457 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 14 | 0.647401 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 14 | 0.647401 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 14 | 0.593216 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 14 | 0.593216 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 14 | 0.505252 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 14 | 0.505252 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00017` | 30 | 14 | 0.485280 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00019` | 30 | 14 | 0.485280 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00018` | 30 | 14 | 0.485280 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 30 | 14 | 0.484699 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 30 | 14 | 0.483929 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00023` | 30 | 14 | 0.476519 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00018` | 15 | 14 | 0.474650 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00017` | 15 | 14 | 0.474650 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00019` | 15 | 14 | 0.474650 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00020` | 15 | 14 | 0.474039 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00021` | 15 | 14 | 0.471068 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 15 | 14 | 0.464551 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00057` | 30 | 14 | 0.454996 | `evt_limit_fengdan_money_last_by_1000` |
| 20 | `phase3ae_brepair_v1_00059` | 30 | 14 | 0.454996 | `evt_limit_fengdan_money_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
