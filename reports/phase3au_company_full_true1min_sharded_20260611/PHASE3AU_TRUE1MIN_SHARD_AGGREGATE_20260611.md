# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T15:50:37.105124+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12']`
- attempt count: `13`
- candidate rows: `56524`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 13 | 0.138256 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 13 | 0.136049 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 13 | 0.132621 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 13 | 0.131777 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 13 | 0.130335 | `amount|final_float_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 13 | 0.130197 | `amount|final_float_market_cap` |
| 7 | `phase3ae_brepair_v1_00358` | 30 | 13 | 0.129691 | `ctx_holder_close_price` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 13 | 0.129295 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 13 | 0.128627 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 13 | 0.127774 | `amount|final_float_market_cap` |
| 11 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 13 | 0.125510 | `amount|final_total_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 13 | 0.125191 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 13 | 0.125143 | `amount|final_float_market_cap` |
| 14 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 13 | 0.123651 | `amount|final_total_market_cap` |
| 15 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 13 | 0.122684 | `amount|final_float_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 13 | 0.122495 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 13 | 0.121304 | `amount|final_total_market_cap` |
| 18 | `phase3ae_brepair_v1_00373` | 30 | 13 | 0.120657 | `ctx_fund_cf_total_operate_inflow` |
| 19 | `phase3ae_brepair_v1_00372` | 30 | 13 | 0.120626 | `ctx_fund_cf_total_operate_inflow` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 13 | 0.119559 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 13 | 0.660650 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 13 | 0.660650 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 13 | 0.603898 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 13 | 0.603898 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 13 | 0.524248 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 13 | 0.524248 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00017` | 30 | 13 | 0.483089 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00019` | 30 | 13 | 0.483089 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00018` | 30 | 13 | 0.483089 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 30 | 13 | 0.482464 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 30 | 13 | 0.480942 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00018` | 15 | 13 | 0.473212 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00017` | 15 | 13 | 0.473212 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00019` | 15 | 13 | 0.473212 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00023` | 30 | 13 | 0.472735 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00020` | 15 | 13 | 0.472554 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00021` | 15 | 13 | 0.469477 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 15 | 13 | 0.463269 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00075` | 30 | 13 | 0.458755 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00057` | 30 | 13 | 0.454876 | `evt_limit_fengdan_money_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
