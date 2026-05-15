# Phase3G Registry QA

- created_at: `2026-05-15T15:17:53+08:00`
- decision: `HOLD_METADATA_ONLY`
- declared_cluster_count: `134`
- representative_count: `129`
- aggregate_unique_cluster_count: `122`
- missing_declared_without_representative_count: `5`
- recluster_collision_group_count: `6`
- recluster_collision_duplicate_loss: `7`
- declared_vs_aggregate_unique_gap: `12`

## Interpretation

The 134 vs 122 gap is metadata/registry accounting, not a new search result: 5 declared clusters lack representative rows and 7 representative rows collapse under Phase3G reclustering.

## Collision Groups

| aggregate_global_cluster_id | registry_cluster_ids |
| --- | --- |
| cluster_007 | cluster_011, cluster_030 |
| cluster_017 | cluster_001, cluster_021, cluster_062 |
| cluster_068 | cluster_057, cluster_117 |
| cluster_072 | cluster_043, cluster_090 |
| cluster_137 | cluster_027, cluster_097 |
| cluster_304 | cluster_038, cluster_142 |

## Required Follow-Up

- Do not update the future cumulative baseline until representative coverage and recluster collision accounting are explicitly accepted or repaired.
- If the declared count remains 134, store the five missing representative rows or mark them as non-vector-matchable baseline members.
- If recluster collisions are expected, report both `declared_baseline_count` and `vector_matchable_unique_baseline_count` in Phase3H.

Detailed row-level diagnostics are in `phase3g_registry_qa_rows.csv`.
