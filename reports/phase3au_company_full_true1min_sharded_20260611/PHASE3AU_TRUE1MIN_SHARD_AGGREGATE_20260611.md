# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T14:11:01.540865+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10']`
- attempt count: `11`
- candidate rows: `47828`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 11 | 0.136256 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 11 | 0.134061 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 11 | 0.130642 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 11 | 0.130147 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 11 | 0.128742 | `amount|final_float_market_cap` |
| 6 | `phase3ae_brepair_v1_00358` | 30 | 11 | 0.128488 | `ctx_holder_close_price` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 11 | 0.128189 | `amount|final_float_market_cap` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 11 | 0.127372 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 11 | 0.126992 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 11 | 0.125783 | `amount|final_float_market_cap` |
| 11 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 11 | 0.124322 | `amount|final_total_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 11 | 0.123537 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 11 | 0.123251 | `amount|final_float_market_cap` |
| 14 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 11 | 0.122049 | `amount|final_total_market_cap` |
| 15 | `phase3ae_brepair_v1_00373` | 30 | 11 | 0.121278 | `ctx_fund_cf_total_operate_inflow` |
| 16 | `phase3ae_brepair_v1_00372` | 30 | 11 | 0.121241 | `ctx_fund_cf_total_operate_inflow` |
| 17 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 11 | 0.121093 | `amount|final_float_market_cap` |
| 18 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 11 | 0.120594 | `amount|final_float_market_cap` |
| 19 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 11 | 0.119703 | `amount|final_total_market_cap` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 11 | 0.118249 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 11 | 0.656609 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 11 | 0.656609 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 11 | 0.618657 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 11 | 0.618657 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 11 | 0.535150 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 11 | 0.535150 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00017` | 30 | 11 | 0.475329 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00019` | 30 | 11 | 0.475329 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00018` | 30 | 11 | 0.475329 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 30 | 11 | 0.474590 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 30 | 11 | 0.473813 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00018` | 15 | 11 | 0.471489 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00017` | 15 | 11 | 0.471489 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00019` | 15 | 11 | 0.471489 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00020` | 15 | 11 | 0.470712 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00021` | 15 | 11 | 0.469058 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00023` | 30 | 11 | 0.464038 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 15 | 11 | 0.461289 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00075` | 30 | 11 | 0.459143 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00057` | 30 | 11 | 0.448976 | `evt_limit_fengdan_money_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
