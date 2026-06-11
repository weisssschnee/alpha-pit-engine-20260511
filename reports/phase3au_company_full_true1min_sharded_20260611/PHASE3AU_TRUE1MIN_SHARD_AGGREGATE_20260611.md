# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T11:26:09.037738+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04']`
- attempt count: `5`
- candidate rows: `21740`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 5 | 0.135951 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 5 | 0.133695 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 5 | 0.131178 | `amount|final_float_market_cap` |
| 4 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 5 | 0.130297 | `amount|final_float_market_cap` |
| 5 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 5 | 0.130074 | `amount|final_total_market_cap` |
| 6 | `phase3ae_brepair_v1_00358` | 30 | 5 | 0.128993 | `ctx_holder_close_price` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 5 | 0.127841 | `amount|final_float_market_cap` |
| 8 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 5 | 0.126994 | `amount|final_total_market_cap` |
| 9 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 5 | 0.126958 | `amount|final_float_market_cap` |
| 10 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 5 | 0.125759 | `amount|final_total_market_cap` |
| 11 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 5 | 0.125424 | `amount|final_float_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 5 | 0.125293 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 5 | 0.123634 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 5 | 0.123290 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 5 | 0.122057 | `amount|final_total_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 5 | 0.120672 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 5 | 0.120173 | `amount|final_total_market_cap` |
| 18 | `cn_underutil_v1_capacity_residual_activity_0120` | 15 | 5 | 0.119283 | `amount|final_total_market_cap` |
| 19 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 15 | 5 | 0.119122 | `amount|final_float_market_cap` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 5 | 0.118755 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 5 | 0.659423 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 5 | 0.659423 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 5 | 0.599988 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 5 | 0.599988 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 5 | 0.549035 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 5 | 0.549035 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00032` | 15 | 5 | 0.525161 | `evt_limit_fengdan_rate_last_by_1130` |
| 8 | `phase3ae_brepair_v1_00074` | 15 | 5 | 0.525161 | `evt_limit_fengdan_money_last_by_1130` |
| 9 | `phase3ae_brepair_v1_00017` | 15 | 5 | 0.490558 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00019` | 15 | 5 | 0.490558 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00020` | 15 | 5 | 0.490558 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00018` | 15 | 5 | 0.490558 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00017` | 30 | 5 | 0.488540 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00019` | 30 | 5 | 0.488540 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00020` | 30 | 5 | 0.488540 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00018` | 30 | 5 | 0.488540 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00075` | 30 | 5 | 0.486759 | `evt_limit_fengdan_money_last_by_1130` |
| 18 | `phase3ae_brepair_v1_00021` | 30 | 5 | 0.485350 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00021` | 15 | 5 | 0.482827 | `evt_limit_fengdan_rate_last_by_1000` |
| 20 | `phase3ae_brepair_v1_00023` | 30 | 5 | 0.477487 | `evt_limit_fengdan_rate_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
