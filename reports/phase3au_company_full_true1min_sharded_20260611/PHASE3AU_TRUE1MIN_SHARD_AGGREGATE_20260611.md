# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T10:51:00.248518+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03']`
- attempt count: `4`
- candidate rows: `17392`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 4 | 0.136920 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 4 | 0.134604 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 4 | 0.131417 | `amount|final_float_market_cap` |
| 4 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 4 | 0.131365 | `amount|final_float_market_cap` |
| 5 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 4 | 0.130593 | `amount|final_total_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 4 | 0.128646 | `amount|final_float_market_cap` |
| 7 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 4 | 0.127927 | `amount|final_float_market_cap` |
| 8 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 4 | 0.127654 | `amount|final_total_market_cap` |
| 9 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 4 | 0.126649 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 4 | 0.126232 | `amount|final_float_market_cap` |
| 11 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 4 | 0.126112 | `amount|final_float_market_cap` |
| 12 | `phase3ae_brepair_v1_00358` | 30 | 4 | 0.125621 | `ctx_holder_close_price` |
| 13 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 4 | 0.124122 | `amount|final_float_market_cap` |
| 14 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 4 | 0.123988 | `amount|final_float_market_cap` |
| 15 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 4 | 0.122384 | `amount|final_total_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 4 | 0.121548 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 4 | 0.120527 | `amount|final_total_market_cap` |
| 18 | `cn_underutil_v1_capacity_residual_activity_0120` | 15 | 4 | 0.119892 | `amount|final_total_market_cap` |
| 19 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 15 | 4 | 0.119702 | `amount|final_float_market_cap` |
| 20 | `phase3ae_brepair_v1_00372` | 30 | 4 | 0.116335 | `ctx_fund_cf_total_operate_inflow` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 4 | 0.663317 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 4 | 0.663317 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00032` | 1 | 4 | 0.655372 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00074` | 1 | 4 | 0.655372 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 5 | 4 | 0.558546 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 5 | 4 | 0.558546 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00030` | 15 | 4 | 0.534329 | `evt_limit_fengdan_rate_last_by_1130` |
| 8 | `phase3ae_brepair_v1_00080` | 15 | 4 | 0.534329 | `evt_limit_fengdan_money_last_by_1130` |
| 9 | `phase3ae_brepair_v1_00010` | 15 | 4 | 0.516270 | `evt_limit_fengdan_rate_last_by_0935` |
| 10 | `phase3ae_brepair_v1_00009` | 15 | 4 | 0.516270 | `evt_limit_fengdan_rate_last_by_0935` |
| 11 | `phase3ae_brepair_v1_00011` | 15 | 4 | 0.516270 | `evt_limit_fengdan_rate_last_by_0935` |
| 12 | `phase3ae_brepair_v1_00012` | 15 | 4 | 0.516270 | `evt_limit_fengdan_rate_last_by_0935` |
| 13 | `phase3ae_brepair_v1_00013` | 15 | 4 | 0.511527 | `evt_limit_fengdan_rate_last_by_0935` |
| 14 | `phase3ae_brepair_v1_00032` | 15 | 4 | 0.508911 | `evt_limit_fengdan_rate_last_by_1130` |
| 15 | `phase3ae_brepair_v1_00074` | 15 | 4 | 0.508911 | `evt_limit_fengdan_money_last_by_1130` |
| 16 | `phase3ae_brepair_v1_00009` | 30 | 4 | 0.505960 | `evt_limit_fengdan_rate_last_by_0935` |
| 17 | `phase3ae_brepair_v1_00011` | 30 | 4 | 0.505960 | `evt_limit_fengdan_rate_last_by_0935` |
| 18 | `phase3ae_brepair_v1_00012` | 30 | 4 | 0.505960 | `evt_limit_fengdan_rate_last_by_0935` |
| 19 | `phase3ae_brepair_v1_00010` | 30 | 4 | 0.505960 | `evt_limit_fengdan_rate_last_by_0935` |
| 20 | `phase3ae_brepair_v1_00013` | 30 | 4 | 0.501200 | `evt_limit_fengdan_rate_last_by_0935` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
