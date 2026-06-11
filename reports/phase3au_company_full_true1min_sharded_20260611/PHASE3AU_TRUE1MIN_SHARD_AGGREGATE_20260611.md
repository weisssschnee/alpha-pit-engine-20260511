# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T12:47:38.241346+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06']`
- attempt count: `7`
- candidate rows: `30436`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 7 | 0.135826 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 7 | 0.133635 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 7 | 0.130905 | `amount|final_float_market_cap` |
| 4 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 7 | 0.130256 | `amount|final_float_market_cap` |
| 5 | `phase3ae_brepair_v1_00358` | 30 | 7 | 0.129706 | `ctx_holder_close_price` |
| 6 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 7 | 0.129555 | `amount|final_total_market_cap` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 7 | 0.127745 | `amount|final_float_market_cap` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 7 | 0.126856 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 7 | 0.126488 | `amount|final_total_market_cap` |
| 10 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 7 | 0.125447 | `amount|final_total_market_cap` |
| 11 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 7 | 0.125203 | `amount|final_float_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 7 | 0.125138 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 7 | 0.123276 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 7 | 0.122770 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 7 | 0.121600 | `amount|final_total_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 7 | 0.120106 | `amount|final_float_market_cap` |
| 17 | `phase3ae_brepair_v1_00372` | 30 | 7 | 0.119530 | `ctx_fund_cf_total_operate_inflow` |
| 18 | `phase3ae_brepair_v1_00373` | 30 | 7 | 0.119530 | `ctx_fund_cf_total_operate_inflow` |
| 19 | `phase3ae_brepair_v1_00358` | 15 | 7 | 0.119390 | `ctx_holder_close_price` |
| 20 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 7 | 0.119372 | `amount|final_total_market_cap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 7 | 0.650900 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 7 | 0.650900 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 7 | 0.595747 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 7 | 0.595747 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 7 | 0.557672 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 7 | 0.557672 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00018` | 15 | 7 | 0.492784 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00017` | 15 | 7 | 0.492784 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00019` | 15 | 7 | 0.492784 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 15 | 7 | 0.492784 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 15 | 7 | 0.489136 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00017` | 30 | 7 | 0.488204 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00019` | 30 | 7 | 0.488204 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00020` | 30 | 7 | 0.488204 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00018` | 30 | 7 | 0.488204 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00021` | 30 | 7 | 0.484035 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00023` | 15 | 7 | 0.482733 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00075` | 30 | 7 | 0.479501 | `evt_limit_fengdan_money_last_by_1130` |
| 19 | `phase3ae_brepair_v1_00023` | 30 | 7 | 0.476567 | `evt_limit_fengdan_rate_last_by_1000` |
| 20 | `phase3ae_brepair_v1_00075` | 15 | 7 | 0.461241 | `evt_limit_fengdan_money_last_by_1130` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
