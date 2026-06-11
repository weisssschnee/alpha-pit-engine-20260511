# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T11:56:40.675936+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05']`
- attempt count: `6`
- candidate rows: `26088`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 6 | 0.136333 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 6 | 0.134093 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 6 | 0.131000 | `amount|final_float_market_cap` |
| 4 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 6 | 0.130710 | `amount|final_float_market_cap` |
| 5 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 6 | 0.129959 | `amount|final_total_market_cap` |
| 6 | `phase3ae_brepair_v1_00358` | 30 | 6 | 0.129325 | `ctx_holder_close_price` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 6 | 0.128237 | `amount|final_float_market_cap` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 6 | 0.127346 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 6 | 0.126916 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 6 | 0.125710 | `amount|final_float_market_cap` |
| 11 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 6 | 0.125265 | `amount|final_float_market_cap` |
| 12 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 6 | 0.125158 | `amount|final_total_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 6 | 0.123505 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 6 | 0.123413 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 6 | 0.121997 | `amount|final_total_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 6 | 0.120805 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 6 | 0.119935 | `amount|final_total_market_cap` |
| 18 | `phase3ae_brepair_v1_00358` | 15 | 6 | 0.119186 | `ctx_holder_close_price` |
| 19 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 15 | 6 | 0.118984 | `amount|final_float_market_cap` |
| 20 | `cn_underutil_v1_capacity_residual_activity_0120` | 15 | 6 | 0.118635 | `amount|final_total_market_cap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 6 | 0.660350 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 6 | 0.660350 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 6 | 0.619168 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 6 | 0.619168 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 6 | 0.546502 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 6 | 0.546502 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00018` | 15 | 6 | 0.495338 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00017` | 15 | 6 | 0.495338 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00019` | 15 | 6 | 0.495338 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 15 | 6 | 0.495338 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00017` | 30 | 6 | 0.492382 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00019` | 30 | 6 | 0.492382 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00020` | 30 | 6 | 0.492382 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00018` | 30 | 6 | 0.492382 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00021` | 15 | 6 | 0.491124 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00021` | 30 | 6 | 0.489027 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00023` | 15 | 6 | 0.483283 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 30 | 6 | 0.481080 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00075` | 30 | 6 | 0.478344 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00030` | 30 | 6 | 0.477040 | `evt_limit_fengdan_rate_last_by_1130` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
