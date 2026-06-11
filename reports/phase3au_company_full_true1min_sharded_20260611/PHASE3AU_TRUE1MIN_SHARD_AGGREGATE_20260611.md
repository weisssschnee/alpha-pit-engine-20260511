# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T13:01:38.384754+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07']`
- attempt count: `8`
- candidate rows: `34784`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 8 | 0.136478 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 8 | 0.134354 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 8 | 0.130962 | `amount|final_float_market_cap` |
| 4 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 8 | 0.130758 | `amount|final_float_market_cap` |
| 5 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 8 | 0.130561 | `amount|final_total_market_cap` |
| 6 | `phase3ae_brepair_v1_00358` | 30 | 8 | 0.129787 | `ctx_holder_close_price` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 8 | 0.128351 | `amount|final_float_market_cap` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 8 | 0.127624 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 8 | 0.127461 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 8 | 0.125930 | `amount|final_float_market_cap` |
| 11 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 8 | 0.125506 | `amount|final_total_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 8 | 0.125114 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 8 | 0.123481 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 8 | 0.122971 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 8 | 0.122559 | `amount|final_total_market_cap` |
| 16 | `phase3ae_brepair_v1_00372` | 30 | 8 | 0.120952 | `ctx_fund_cf_total_operate_inflow` |
| 17 | `phase3ae_brepair_v1_00373` | 30 | 8 | 0.120952 | `ctx_fund_cf_total_operate_inflow` |
| 18 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 8 | 0.120878 | `amount|final_float_market_cap` |
| 19 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 8 | 0.120285 | `amount|final_total_market_cap` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 8 | 0.119333 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 8 | 0.646927 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 8 | 0.646927 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 8 | 0.592886 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 8 | 0.592886 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 8 | 0.550719 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 8 | 0.550719 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00018` | 15 | 8 | 0.489403 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00017` | 15 | 8 | 0.489403 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00019` | 15 | 8 | 0.489403 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 15 | 8 | 0.489403 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 15 | 8 | 0.485829 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00017` | 30 | 8 | 0.485059 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00019` | 30 | 8 | 0.485059 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00020` | 30 | 8 | 0.485059 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00018` | 30 | 8 | 0.485059 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00021` | 30 | 8 | 0.481587 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00023` | 15 | 8 | 0.478861 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 30 | 8 | 0.473380 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00075` | 30 | 8 | 0.469598 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00057` | 30 | 8 | 0.459437 | `evt_limit_fengdan_money_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
