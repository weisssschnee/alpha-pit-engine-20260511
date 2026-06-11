# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-11T14:36:59.960050+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11']`
- attempt count: `12`
- candidate rows: `52176`
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
| 1 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 30 | 12 | 0.137642 | `amount|final_float_market_cap` |
| 2 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 30 | 12 | 0.135479 | `amount|final_float_market_cap` |
| 3 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 30 | 12 | 0.132062 | `amount|final_float_market_cap` |
| 4 | `cn_underutil_v1_capacity_normalized_activity_0121` | 30 | 12 | 0.131340 | `amount|final_total_market_cap` |
| 5 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 30 | 12 | 0.130086 | `amount|final_float_market_cap` |
| 6 | `cn_flow_liq_v1_capacity_normalized_flow_0087` | 15 | 12 | 0.129501 | `amount|final_float_market_cap` |
| 7 | `phase3ae_brepair_v1_00358` | 30 | 12 | 0.129162 | `ctx_holder_close_price` |
| 8 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 30 | 12 | 0.128775 | `amount|final_float_market_cap` |
| 9 | `cn_underutil_v1_capacity_normalized_activity_0119` | 30 | 12 | 0.128217 | `amount|final_total_market_cap` |
| 10 | `cn_flow_liq_v1_capacity_normalized_flow_0085` | 15 | 12 | 0.127073 | `amount|final_float_market_cap` |
| 11 | `cn_underutil_v1_capacity_residual_activity_0120` | 30 | 12 | 0.125283 | `amount|final_total_market_cap` |
| 12 | `cn_flow_liq_v1_capacity_residual_flow_0082` | 30 | 12 | 0.124908 | `amount|final_float_market_cap` |
| 13 | `cn_flow_liq_v1_capacity_normalized_flow_0083` | 15 | 12 | 0.124531 | `amount|final_float_market_cap` |
| 14 | `cn_underutil_v1_capacity_normalized_activity_0121` | 15 | 12 | 0.123092 | `amount|final_total_market_cap` |
| 15 | `cn_flow_liq_v1_capacity_residual_flow_0086` | 15 | 12 | 0.122268 | `amount|final_float_market_cap` |
| 16 | `cn_flow_liq_v1_capacity_normalized_flow_0081` | 15 | 12 | 0.121855 | `amount|final_float_market_cap` |
| 17 | `cn_underutil_v1_capacity_normalized_activity_0119` | 15 | 12 | 0.120777 | `amount|final_total_market_cap` |
| 18 | `phase3ae_brepair_v1_00373` | 30 | 12 | 0.120522 | `ctx_fund_cf_total_operate_inflow` |
| 19 | `phase3ae_brepair_v1_00372` | 30 | 12 | 0.120488 | `ctx_fund_cf_total_operate_inflow` |
| 20 | `phase3ae_brepair_v1_00358` | 15 | 12 | 0.119001 | `ctx_holder_close_price` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3ae_brepair_v1_00030` | 1 | 12 | 0.655676 | `evt_limit_fengdan_rate_last_by_1130` |
| 2 | `phase3ae_brepair_v1_00080` | 1 | 12 | 0.655676 | `evt_limit_fengdan_money_last_by_1130` |
| 3 | `phase3ae_brepair_v1_00030` | 5 | 12 | 0.618395 | `evt_limit_fengdan_rate_last_by_1130` |
| 4 | `phase3ae_brepair_v1_00080` | 5 | 12 | 0.618395 | `evt_limit_fengdan_money_last_by_1130` |
| 5 | `phase3ae_brepair_v1_00030` | 15 | 12 | 0.519622 | `evt_limit_fengdan_rate_last_by_1130` |
| 6 | `phase3ae_brepair_v1_00080` | 15 | 12 | 0.519622 | `evt_limit_fengdan_money_last_by_1130` |
| 7 | `phase3ae_brepair_v1_00017` | 30 | 12 | 0.479545 | `evt_limit_fengdan_rate_last_by_1000` |
| 8 | `phase3ae_brepair_v1_00019` | 30 | 12 | 0.479545 | `evt_limit_fengdan_rate_last_by_1000` |
| 9 | `phase3ae_brepair_v1_00018` | 30 | 12 | 0.479545 | `evt_limit_fengdan_rate_last_by_1000` |
| 10 | `phase3ae_brepair_v1_00020` | 30 | 12 | 0.478868 | `evt_limit_fengdan_rate_last_by_1000` |
| 11 | `phase3ae_brepair_v1_00021` | 30 | 12 | 0.477960 | `evt_limit_fengdan_rate_last_by_1000` |
| 12 | `phase3ae_brepair_v1_00018` | 15 | 12 | 0.474172 | `evt_limit_fengdan_rate_last_by_1000` |
| 13 | `phase3ae_brepair_v1_00017` | 15 | 12 | 0.474172 | `evt_limit_fengdan_rate_last_by_1000` |
| 14 | `phase3ae_brepair_v1_00019` | 15 | 12 | 0.474172 | `evt_limit_fengdan_rate_last_by_1000` |
| 15 | `phase3ae_brepair_v1_00020` | 15 | 12 | 0.473459 | `evt_limit_fengdan_rate_last_by_1000` |
| 16 | `phase3ae_brepair_v1_00021` | 15 | 12 | 0.471493 | `evt_limit_fengdan_rate_last_by_1000` |
| 17 | `phase3ae_brepair_v1_00023` | 30 | 12 | 0.469147 | `evt_limit_fengdan_rate_last_by_1000` |
| 18 | `phase3ae_brepair_v1_00023` | 15 | 12 | 0.464381 | `evt_limit_fengdan_rate_last_by_1000` |
| 19 | `phase3ae_brepair_v1_00075` | 30 | 12 | 0.458980 | `evt_limit_fengdan_money_last_by_1130` |
| 20 | `phase3ae_brepair_v1_00057` | 30 | 12 | 0.454189 | `evt_limit_fengdan_money_last_by_1000` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3au_company_full_true1min_sharded_20260611\phase3au_true1min_shard_source_attribution.csv`
