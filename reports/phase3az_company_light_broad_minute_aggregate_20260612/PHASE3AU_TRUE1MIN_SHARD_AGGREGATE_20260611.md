# Phase3AU True 1min Shard Aggregate

decision: `PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH`

- generated_at: `2026-06-12T11:14:36.771603+00:00`
- version: `phase3au-shard-aggregate-v1-2026-06-11`
- completed shards: `['shard_00', 'shard_01', 'shard_02', 'shard_03', 'shard_04', 'shard_05', 'shard_06', 'shard_07', 'shard_08', 'shard_09', 'shard_10', 'shard_11', 'shard_12', 'shard_13', 'shard_14', 'shard_15']`
- attempt count: `16`
- candidate rows: `19072`
- unique candidates: `298`
- unique expressions: `298`
- robust min ic_count: `450`

## Interpretation

- This aggregate uses true `trade_time` 1min shard outputs only.
- Search-memory hits and fresh structures are separated.
- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.

## Fresh Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3az_light_broad_minute_00059` | 30 | 16 | 0.104432 | `vwap` |
| 2 | `phase3az_light_broad_minute_00060` | 30 | 16 | 0.104432 | `vwap` |
| 3 | `phase3az_light_broad_minute_00032` | 30 | 16 | 0.104219 | `low` |
| 4 | `phase3az_light_broad_minute_00031` | 30 | 16 | 0.104219 | `low` |
| 5 | `phase3az_light_broad_minute_00004` | 30 | 16 | 0.104063 | `open` |
| 6 | `phase3az_light_broad_minute_00003` | 30 | 16 | 0.104063 | `open` |
| 7 | `phase3az_light_broad_minute_00018` | 30 | 16 | 0.103884 | `high` |
| 8 | `phase3az_light_broad_minute_00017` | 30 | 16 | 0.103884 | `high` |
| 9 | `phase3az_light_broad_minute_00045` | 30 | 16 | 0.103687 | `close` |
| 10 | `phase3az_light_broad_minute_00046` | 30 | 16 | 0.103687 | `close` |
| 11 | `phase3az_light_broad_minute_00030` | 30 | 16 | 0.103448 | `low` |
| 12 | `phase3az_light_broad_minute_00029` | 30 | 16 | 0.103448 | `low` |
| 13 | `phase3az_light_broad_minute_00058` | 30 | 16 | 0.103166 | `vwap` |
| 14 | `phase3az_light_broad_minute_00057` | 30 | 16 | 0.103166 | `vwap` |
| 15 | `phase3az_light_broad_minute_00016` | 30 | 16 | 0.103127 | `high` |
| 16 | `phase3az_light_broad_minute_00015` | 30 | 16 | 0.103127 | `high` |
| 17 | `phase3az_light_broad_minute_00002` | 30 | 16 | 0.103060 | `open` |
| 18 | `phase3az_light_broad_minute_00001` | 30 | 16 | 0.103060 | `open` |
| 19 | `phase3az_light_broad_minute_00062` | 30 | 16 | 0.102917 | `vwap` |
| 20 | `phase3az_light_broad_minute_00061` | 30 | 16 | 0.102917 | `vwap` |

## Memory-Hit Robust Top

| rank | candidate | horizon | shards | mean abs IC | fields |
|---:|---|---:|---:|---:|---|
| 1 | `phase3az_light_broad_minute_00091` | 30 | 16 | 0.063390 | `volume` |
| 2 | `phase3az_light_broad_minute_00091` | 15 | 16 | 0.061499 | `volume` |
| 3 | `phase3az_light_broad_minute_00091` | 5 | 16 | 0.057799 | `volume` |
| 4 | `phase3az_light_broad_minute_00091` | 1 | 16 | 0.051879 | `volume` |

## Outputs

- summary JSON: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3az_company_light_broad_minute_aggregate_20260612\phase3au_true1min_shard_aggregate_summary.json`
- attempt status CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3az_company_light_broad_minute_aggregate_20260612\phase3au_true1min_shard_attempt_status.csv`
- fresh top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3az_company_light_broad_minute_aggregate_20260612\phase3au_true1min_shard_fresh_top.csv`
- memory-hit top CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3az_company_light_broad_minute_aggregate_20260612\phase3au_true1min_shard_memory_hit_top.csv`
- source attribution CSV: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3az_company_light_broad_minute_aggregate_20260612\phase3au_true1min_shard_source_attribution.csv`
