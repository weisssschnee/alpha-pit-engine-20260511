# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T10:11:10.977427+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02']`
- attempt count: `3`
- candidate rows: `13044`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 3 | 0.136962 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 3 | 0.134468 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 3 | 0.130894 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 3 | 0.129913 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 3 | 0.128169 | `amount|final_float_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 3 | 0.128114 | `amount|final_float_market_cap` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 3 | 0.127345 | `amount|final_float_market_cap` |
| 8 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 3 | 0.126653 | `amount|final_total_market_cap` |
| 9 | `phase3ae_brepair_v1_00358` | 30 | 3 | 0.126438 | `ctx_holder_close_price` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 3 | 0.125638 | `amount|final_float_market_cap` |
| 11 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 3 | 0.123390 | `amount|final_float_market_cap` |
| 12 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 3 | 0.122912 | `amount|final_total_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 3 | 0.122544 | `amount|final_float_market_cap` |
| 14 | `phase3ae_brepair_v1_00372` | 30 | 3 | 0.122158 | `ctx_fund_cf_total_operate_inflow` |
| 15 | `phase3ae_brepair_v1_00373` | 30 | 3 | 0.122158 | `ctx_fund_cf_total_operate_inflow` |
| 16 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 3 | 0.121378 | `amount|final_total_market_cap` |
| 17 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 3 | 0.120536 | `amount|final_float_market_cap` |
| 18 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 3 | 0.120396 | `amount|final_float_market_cap` |
| 19 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 3 | 0.119442 | `amount|final_total_market_cap` |
| 20 | `phase3ae_brepair_v1_00376` | 30 | 3 | 0.118098 | `ctx_fund_cf_total_operate_outflow` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 3 | 0.693455 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 3 | 0.693455 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00032` | 1 | 3 | 0.692087 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00074` | 1 | 3 | 0.692087 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 5 | 3 | 0.605422 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 5 | 3 | 0.605422 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00030` | 15 | 3 | 0.580972 | `evt_limit_fengdan_rate_last_by_1130` |
| 8 | `phase3ae_brepair_v1_00080` | 15 | 3 | 0.580972 | `evt_limit_fengdan_money_last_by_1130` |
| 9 | `phase3ae_brepair_v1_00032` | 15 | 3 | 0.543471 | `evt_limit_fengdan_rate_last_by_1130` |
| 10 | `phase3ae_brepair_v1_00074` | 15 | 3 | 0.543471 | `evt_limit_fengdan_money_last_by_1130` |
| 11 | `phase3ae_brepair_v1_00010` | 15 | 3 | 0.529589 | `evt_limit_fengdan_rate_last_by_0935` |
| 12 | `phase3ae_brepair_v1_00009` | 15 | 3 | 0.529589 | `evt_limit_fengdan_rate_last_by_0935` |
| 13 | `phase3ae_brepair_v1_00011` | 15 | 3 | 0.529589 | `evt_limit_fengdan_rate_last_by_0935` |
| 14 | `phase3ae_brepair_v1_00012` | 15 | 3 | 0.529589 | `evt_limit_fengdan_rate_last_by_0935` |
| 15 | `phase3ae_brepair_v1_00013` | 15 | 3 | 0.527329 | `evt_limit_fengdan_rate_last_by_0935` |
| 16 | `phase3ae_brepair_v1_00009` | 30 | 3 | 0.511199 | `evt_limit_fengdan_rate_last_by_0935` |
| 17 | `phase3ae_brepair_v1_00011` | 30 | 3 | 0.511199 | `evt_limit_fengdan_rate_last_by_0935` |
| 18 | `phase3ae_brepair_v1_00012` | 30 | 3 | 0.511199 | `evt_limit_fengdan_rate_last_by_0935` |
| 19 | `phase3ae_brepair_v1_00010` | 30 | 3 | 0.511199 | `evt_limit_fengdan_rate_last_by_0935` |
| 20 | `phase3ae_brepair_v1_00075` | 30 | 3 | 0.498405 | `evt_limit_fengdan_money_last_by_1130` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
