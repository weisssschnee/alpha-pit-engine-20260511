# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T09:27:47.799702+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01']`
- attempt count: `2`
- candidate rows: `8696`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 2 | 0.135180 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 2 | 0.132960 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 2 | 0.129753 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 2 | 0.129243 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 2 | 0.128166 | `amount|final_float_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 2 | 0.126894 | `amount|final_float_market_cap` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 2 | 0.126273 | `amount|final_float_market_cap` |
| 8 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 2 | 0.126187 | `amount|final_total_market_cap` |
| 9 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 2 | 0.124351 | `amount|final_float_market_cap` |
| 10 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 2 | 0.123242 | `amount|final_total_market_cap` |
| 11 | `phase3ae_brepair_v1_00358` | 30 | 2 | 0.122547 | `ctx_holder_close_price` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 2 | 0.122411 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 2 | 0.122353 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 2 | 0.121211 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 2 | 0.120757 | `amount|final_total_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 2 | 0.119677 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 2 | 0.118932 | `amount|final_total_market_cap` |
| 18 | `phase3ae_brepair_v1_00372` | 30 | 2 | 0.118683 | `ctx_fund_cf_total_operate_inflow` |
| 19 | `phase3ae_brepair_v1_00373` | 30 | 2 | 0.118683 | `ctx_fund_cf_total_operate_inflow` |
| 20 | `cn_underutil_v1_capacity_residual_activity_0120` | 15 | 2 | 0.117052 | `amount|final_total_market_cap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00032` | 1 | 2 | 0.671003 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00074` | 1 | 2 | 0.671003 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 1 | 2 | 0.655529 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 1 | 2 | 0.655529 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00024` | 1 | 2 | 0.650833 | `evt_limit_fengdan_rate_last_by_1000` |
| 6 | `phase3ae_brepair_v1_00062` | 1 | 2 | 0.650833 | `evt_limit_fengdan_money_last_by_1000` |
| 7 | `phase3ae_brepair_v1_00022` | 1 | 2 | 0.650362 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00068` | 1 | 2 | 0.650362 | `evt_limit_fengdan_money_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00064` | 1 | 2 | 0.647303 | `evt_limit_fengdan_money_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00022` | 5 | 2 | 0.612040 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00068` | 5 | 2 | 0.612040 | `evt_limit_fengdan_money_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00024` | 5 | 2 | 0.609426 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00062` | 5 | 2 | 0.609426 | `evt_limit_fengdan_money_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00032` | 5 | 2 | 0.592894 | `evt_limit_fengdan_rate_last_by_1130` |
| 15 | `phase3ae_brepair_v1_00074` | 5 | 2 | 0.592894 | `evt_limit_fengdan_money_last_by_1130` |
| 16 | `phase3ae_brepair_v1_00024` | 30 | 2 | 0.570865 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00062` | 30 | 2 | 0.570865 | `evt_limit_fengdan_money_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00030` | 5 | 2 | 0.570701 | `evt_limit_fengdan_rate_last_by_1130` |
| 19 | `phase3ae_brepair_v1_00080` | 5 | 2 | 0.570701 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00013` | 15 | 2 | 0.559906 | `evt_limit_fengdan_rate_last_by_0935` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
