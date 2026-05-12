# Phase3A Global Aggregate Report

- created_at: `2026-05-12T09:53:08.239448+08:00`
- decision: `PASS_CONFIRM_PHASE3A`
- cluster_label_scope: `global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline`
- seed_local_labels_ignored: `True`

## Pass Criteria

```json
{
  "criteria": {
    "global_deployable_clusters_gt_phase2_reference_5": true,
    "global_deployable_clusters_gte_8": true,
    "top_cluster_share_lt_50pct": true,
    "ast_repair_new_deployable_clusters_vs_phase2_r0_gte_2": true,
    "local_and_company_runner_represented": true,
    "raw_pass_not_primary": true
  },
  "machine_sources": [
    "company",
    "local"
  ],
  "ast_repair_deployable_clusters": [
    "cluster_001",
    "cluster_005",
    "cluster_006",
    "cluster_010",
    "cluster_020",
    "cluster_024",
    "cluster_034",
    "cluster_035",
    "cluster_039"
  ],
  "ast_repair_new_deployable_clusters_vs_phase2_r0": 8,
  "ast_repair_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_005",
    "cluster_010",
    "cluster_020",
    "cluster_024",
    "cluster_034",
    "cluster_035",
    "cluster_039"
  ],
  "decision": "PASS_CONFIRM_PHASE3A"
}
```

## Global Union Metrics

```json
{
  "completed_phase3_seed_count": 4,
  "audited": 1280,
  "global_unique_return_corr_clusters": 62,
  "global_deployable_clusters": 36,
  "phase2_r0_baseline_deployable_clusters": 5,
  "global_new_clusters_vs_phase2_r0": 32,
  "global_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_004",
    "cluster_005",
    "cluster_007",
    "cluster_008",
    "cluster_009",
    "cluster_010",
    "cluster_011",
    "cluster_014",
    "cluster_018",
    "cluster_019",
    "cluster_020",
    "cluster_021",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_027",
    "cluster_033",
    "cluster_034",
    "cluster_035",
    "cluster_039",
    "cluster_040",
    "cluster_041",
    "cluster_042",
    "cluster_044",
    "cluster_047",
    "cluster_051",
    "cluster_052",
    "cluster_058",
    "cluster_059",
    "cluster_061"
  ],
  "raw_non_gap_pass": 423,
  "global_top_cluster_id": "cluster_006",
  "global_top_cluster_share": 0.397163,
  "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
  "seed_local_labels_ignored": true
}
```

## Per Seed Metrics

| run_id | seed | ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3A_full::seed5 | seed5 | Phase3A_full | 64 | 24 | 12 | 9 | cluster_006 | 0.458333 |
| Phase3A_full::seed6 | seed6 | Phase3A_full | 64 | 21 | 11 | 8 | cluster_006 | 0.428571 |
| Phase3A_full::seed7 | seed7 | Phase3A_full | 64 | 29 | 15 | 9 | cluster_006 | 0.37931 |
| Phase3A_full::seed8 | seed8 | Phase3A_full | 64 | 26 | 12 | 9 | cluster_006 | 0.384615 |
| R0_AST_repair_only::seed5 | seed5 | R0_AST_repair_only | 64 | 27 | 13 | 7 | cluster_006 | 0.518519 |
| R0_AST_repair_only::seed6 | seed6 | R0_AST_repair_only | 64 | 26 | 13 | 9 | cluster_006 | 0.5 |
| R0_AST_repair_only::seed7 | seed7 | R0_AST_repair_only | 64 | 31 | 15 | 8 | cluster_006 | 0.516129 |
| R0_AST_repair_only::seed8 | seed8 | R0_AST_repair_only | 64 | 31 | 14 | 7 | cluster_006 | 0.354839 |
| R0_cluster_quota_AST_repair_only::seed5 | seed5 | R0_cluster_quota_AST_repair_only | 64 | 21 | 12 | 7 | cluster_006 | 0.380952 |
| R0_cluster_quota_AST_repair_only::seed6 | seed6 | R0_cluster_quota_AST_repair_only | 64 | 24 | 14 | 9 | cluster_006 | 0.333333 |
| R0_cluster_quota_AST_repair_only::seed7 | seed7 | R0_cluster_quota_AST_repair_only | 64 | 25 | 13 | 9 | cluster_006 | 0.32 |
| R0_cluster_quota_AST_repair_only::seed8 | seed8 | R0_cluster_quota_AST_repair_only | 64 | 19 | 12 | 8 | cluster_006 | 0.368421 |
| R0_cluster_quota_only::seed5 | seed5 | R0_cluster_quota_only | 64 | 8 | 6 | 5 | cluster_006 | 0.375 |
| R0_cluster_quota_only::seed6 | seed6 | R0_cluster_quota_only | 64 | 11 | 7 | 5 | cluster_006 | 0.363636 |
| R0_cluster_quota_only::seed7 | seed7 | R0_cluster_quota_only | 64 | 18 | 11 | 9 | cluster_042 | 0.222222 |
| R0_cluster_quota_only::seed8 | seed8 | R0_cluster_quota_only | 64 | 12 | 9 | 7 | cluster_006 | 0.333333 |
| original_R0::seed5 | seed5 | original_R0 | 64 | 17 | 10 | 4 | cluster_006 | 0.411765 |
| original_R0::seed6 | seed6 | original_R0 | 64 | 17 | 8 | 6 | cluster_006 | 0.470588 |
| original_R0::seed7 | seed7 | original_R0 | 64 | 20 | 13 | 4 | cluster_006 | 0.35 |
| original_R0::seed8 | seed8 | original_R0 | 64 | 16 | 8 | 4 | cluster_006 | 0.375 |

## Per Arm Metrics

| ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share | median_turnover | median_complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3A_full | 256 | 100 | 30 | 20 | cluster_006 | 0.41 | 0.061575 | 11.0 |
| R0_AST_repair_only | 256 | 115 | 32 | 20 | cluster_006 | 0.469565 | 0.04526 | 11.0 |
| R0_cluster_quota_AST_repair_only | 256 | 89 | 25 | 16 | cluster_006 | 0.348315 | 0.037872 | 11.0 |
| R0_cluster_quota_only | 256 | 49 | 20 | 17 | cluster_006 | 0.285714 | 0.037872 | 10.0 |
| original_R0 | 256 | 70 | 26 | 11 | cluster_006 | 0.4 | 0.037872 | 14.0 |

## Seed Overlap Matrix

| left_seed | right_seed | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3A_full::seed5 | Phase3A_full::seed5 | 9 | 9 | 1.0 | 12 | 12 |
| Phase3A_full::seed5 | Phase3A_full::seed6 | 4 | 13 | 0.307692 | 5 | 18 |
| Phase3A_full::seed5 | Phase3A_full::seed7 | 4 | 14 | 0.285714 | 6 | 21 |
| Phase3A_full::seed5 | Phase3A_full::seed8 | 3 | 15 | 0.2 | 4 | 20 |
| Phase3A_full::seed5 | R0_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 4 | 21 |
| Phase3A_full::seed5 | R0_AST_repair_only::seed6 | 5 | 13 | 0.384615 | 5 | 20 |
| Phase3A_full::seed5 | R0_AST_repair_only::seed7 | 3 | 14 | 0.214286 | 5 | 22 |
| Phase3A_full::seed5 | R0_AST_repair_only::seed8 | 3 | 13 | 0.230769 | 5 | 21 |
| Phase3A_full::seed5 | R0_cluster_quota_AST_repair_only::seed5 | 5 | 11 | 0.454545 | 6 | 18 |
| Phase3A_full::seed5 | R0_cluster_quota_AST_repair_only::seed6 | 6 | 12 | 0.5 | 8 | 18 |
| Phase3A_full::seed5 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 14 | 0.285714 | 5 | 20 |
| Phase3A_full::seed5 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 15 | 0.133333 | 3 | 21 |
| Phase3A_full::seed5 | R0_cluster_quota_only::seed5 | 1 | 13 | 0.076923 | 1 | 17 |
| Phase3A_full::seed5 | R0_cluster_quota_only::seed6 | 2 | 12 | 0.166667 | 2 | 17 |
| Phase3A_full::seed5 | R0_cluster_quota_only::seed7 | 4 | 14 | 0.285714 | 4 | 19 |
| Phase3A_full::seed5 | R0_cluster_quota_only::seed8 | 3 | 13 | 0.230769 | 3 | 18 |
| Phase3A_full::seed5 | original_R0::seed5 | 1 | 12 | 0.083333 | 1 | 21 |
| Phase3A_full::seed5 | original_R0::seed6 | 3 | 12 | 0.25 | 4 | 16 |
| Phase3A_full::seed5 | original_R0::seed7 | 1 | 12 | 0.083333 | 2 | 23 |
| Phase3A_full::seed5 | original_R0::seed8 | 1 | 12 | 0.083333 | 2 | 18 |
| Phase3A_full::seed6 | Phase3A_full::seed5 | 4 | 13 | 0.307692 | 5 | 18 |
| Phase3A_full::seed6 | Phase3A_full::seed6 | 8 | 8 | 1.0 | 11 | 11 |
| Phase3A_full::seed6 | Phase3A_full::seed7 | 3 | 14 | 0.214286 | 5 | 21 |
| Phase3A_full::seed6 | Phase3A_full::seed8 | 4 | 13 | 0.307692 | 6 | 17 |
| Phase3A_full::seed6 | R0_AST_repair_only::seed5 | 2 | 13 | 0.153846 | 3 | 21 |
| Phase3A_full::seed6 | R0_AST_repair_only::seed6 | 4 | 13 | 0.307692 | 4 | 20 |
| Phase3A_full::seed6 | R0_AST_repair_only::seed7 | 3 | 13 | 0.230769 | 4 | 22 |
| Phase3A_full::seed6 | R0_AST_repair_only::seed8 | 3 | 12 | 0.25 | 5 | 20 |
| Phase3A_full::seed6 | R0_cluster_quota_AST_repair_only::seed5 | 3 | 12 | 0.25 | 5 | 18 |
| Phase3A_full::seed6 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 13 | 0.307692 | 6 | 19 |
| Phase3A_full::seed6 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 13 | 0.307692 | 5 | 19 |
| Phase3A_full::seed6 | R0_cluster_quota_AST_repair_only::seed8 | 3 | 13 | 0.230769 | 4 | 19 |
| Phase3A_full::seed6 | R0_cluster_quota_only::seed5 | 2 | 11 | 0.181818 | 3 | 14 |
| Phase3A_full::seed6 | R0_cluster_quota_only::seed6 | 2 | 11 | 0.181818 | 3 | 15 |
| Phase3A_full::seed6 | R0_cluster_quota_only::seed7 | 5 | 12 | 0.416667 | 6 | 16 |
| Phase3A_full::seed6 | R0_cluster_quota_only::seed8 | 2 | 13 | 0.153846 | 3 | 17 |
| Phase3A_full::seed6 | original_R0::seed5 | 2 | 10 | 0.2 | 2 | 19 |
| Phase3A_full::seed6 | original_R0::seed6 | 2 | 12 | 0.166667 | 3 | 16 |
| Phase3A_full::seed6 | original_R0::seed7 | 2 | 10 | 0.2 | 2 | 22 |
| Phase3A_full::seed6 | original_R0::seed8 | 1 | 11 | 0.090909 | 2 | 17 |
| Phase3A_full::seed7 | Phase3A_full::seed5 | 4 | 14 | 0.285714 | 6 | 21 |
| Phase3A_full::seed7 | Phase3A_full::seed6 | 3 | 14 | 0.214286 | 5 | 21 |
| Phase3A_full::seed7 | Phase3A_full::seed7 | 9 | 9 | 1.0 | 15 | 15 |
| Phase3A_full::seed7 | Phase3A_full::seed8 | 6 | 12 | 0.5 | 7 | 20 |
| Phase3A_full::seed7 | R0_AST_repair_only::seed5 | 4 | 12 | 0.333333 | 7 | 21 |
| Phase3A_full::seed7 | R0_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 5 | 23 |
| Phase3A_full::seed7 | R0_AST_repair_only::seed7 | 3 | 14 | 0.214286 | 6 | 24 |
| Phase3A_full::seed7 | R0_AST_repair_only::seed8 | 3 | 13 | 0.230769 | 5 | 24 |
| Phase3A_full::seed7 | R0_cluster_quota_AST_repair_only::seed5 | 3 | 13 | 0.230769 | 7 | 20 |
| Phase3A_full::seed7 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 8 | 21 |
| Phase3A_full::seed7 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 15 | 0.2 | 5 | 23 |
| Phase3A_full::seed7 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 15 | 0.133333 | 6 | 21 |
| Phase3A_full::seed7 | R0_cluster_quota_only::seed5 | 2 | 12 | 0.166667 | 3 | 18 |
| Phase3A_full::seed7 | R0_cluster_quota_only::seed6 | 2 | 12 | 0.166667 | 3 | 19 |
| Phase3A_full::seed7 | R0_cluster_quota_only::seed7 | 3 | 15 | 0.2 | 5 | 21 |
| Phase3A_full::seed7 | R0_cluster_quota_only::seed8 | 1 | 15 | 0.066667 | 2 | 22 |
| Phase3A_full::seed7 | original_R0::seed5 | 1 | 12 | 0.083333 | 4 | 21 |
| Phase3A_full::seed7 | original_R0::seed6 | 2 | 13 | 0.153846 | 3 | 20 |
| Phase3A_full::seed7 | original_R0::seed7 | 2 | 11 | 0.181818 | 5 | 23 |
| Phase3A_full::seed7 | original_R0::seed8 | 2 | 11 | 0.181818 | 4 | 19 |
| Phase3A_full::seed8 | Phase3A_full::seed5 | 3 | 15 | 0.2 | 4 | 20 |
| Phase3A_full::seed8 | Phase3A_full::seed6 | 4 | 13 | 0.307692 | 6 | 17 |
| Phase3A_full::seed8 | Phase3A_full::seed7 | 6 | 12 | 0.5 | 7 | 20 |
| Phase3A_full::seed8 | Phase3A_full::seed8 | 9 | 9 | 1.0 | 12 | 12 |
| Phase3A_full::seed8 | R0_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 4 | 21 |
| Phase3A_full::seed8 | R0_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 4 | 21 |
| Phase3A_full::seed8 | R0_AST_repair_only::seed7 | 6 | 11 | 0.545455 | 7 | 20 |
| Phase3A_full::seed8 | R0_AST_repair_only::seed8 | 4 | 12 | 0.333333 | 6 | 20 |
| Phase3A_full::seed8 | R0_cluster_quota_AST_repair_only::seed5 | 4 | 12 | 0.333333 | 6 | 18 |
| Phase3A_full::seed8 | R0_cluster_quota_AST_repair_only::seed6 | 5 | 13 | 0.384615 | 7 | 19 |
| Phase3A_full::seed8 | R0_cluster_quota_AST_repair_only::seed7 | 5 | 13 | 0.384615 | 6 | 19 |
| Phase3A_full::seed8 | R0_cluster_quota_AST_repair_only::seed8 | 4 | 13 | 0.307692 | 5 | 19 |
| Phase3A_full::seed8 | R0_cluster_quota_only::seed5 | 3 | 11 | 0.272727 | 4 | 14 |
| Phase3A_full::seed8 | R0_cluster_quota_only::seed6 | 2 | 12 | 0.166667 | 3 | 16 |
| Phase3A_full::seed8 | R0_cluster_quota_only::seed7 | 3 | 15 | 0.2 | 4 | 19 |
| Phase3A_full::seed8 | R0_cluster_quota_only::seed8 | 2 | 14 | 0.142857 | 3 | 18 |
| Phase3A_full::seed8 | original_R0::seed5 | 3 | 10 | 0.3 | 3 | 19 |
| Phase3A_full::seed8 | original_R0::seed6 | 2 | 13 | 0.153846 | 4 | 16 |
| Phase3A_full::seed8 | original_R0::seed7 | 2 | 11 | 0.181818 | 2 | 23 |
| Phase3A_full::seed8 | original_R0::seed8 | 2 | 11 | 0.181818 | 3 | 17 |
| R0_AST_repair_only::seed5 | Phase3A_full::seed5 | 2 | 14 | 0.142857 | 4 | 21 |
| R0_AST_repair_only::seed5 | Phase3A_full::seed6 | 2 | 13 | 0.153846 | 3 | 21 |
| R0_AST_repair_only::seed5 | Phase3A_full::seed7 | 4 | 12 | 0.333333 | 7 | 21 |
| R0_AST_repair_only::seed5 | Phase3A_full::seed8 | 2 | 14 | 0.142857 | 4 | 21 |
| R0_AST_repair_only::seed5 | R0_AST_repair_only::seed5 | 7 | 7 | 1.0 | 13 | 13 |
| R0_AST_repair_only::seed5 | R0_AST_repair_only::seed6 | 3 | 13 | 0.230769 | 4 | 22 |
| R0_AST_repair_only::seed5 | R0_AST_repair_only::seed7 | 2 | 13 | 0.153846 | 7 | 21 |
| R0_AST_repair_only::seed5 | R0_AST_repair_only::seed8 | 2 | 12 | 0.166667 | 5 | 22 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed5 | 2 | 12 | 0.166667 | 7 | 18 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed6 | 2 | 14 | 0.142857 | 6 | 21 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed7 | 2 | 14 | 0.142857 | 3 | 23 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed8 | 1 | 14 | 0.071429 | 4 | 21 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_only::seed5 | 3 | 9 | 0.333333 | 4 | 15 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_only::seed6 | 1 | 11 | 0.090909 | 2 | 18 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_only::seed7 | 2 | 14 | 0.142857 | 3 | 21 |
| R0_AST_repair_only::seed5 | R0_cluster_quota_only::seed8 | 1 | 13 | 0.076923 | 3 | 19 |
| R0_AST_repair_only::seed5 | original_R0::seed5 | 1 | 10 | 0.1 | 2 | 21 |
| R0_AST_repair_only::seed5 | original_R0::seed6 | 1 | 12 | 0.083333 | 3 | 18 |
| R0_AST_repair_only::seed5 | original_R0::seed7 | 2 | 9 | 0.222222 | 4 | 22 |
| R0_AST_repair_only::seed5 | original_R0::seed8 | 1 | 10 | 0.1 | 4 | 17 |
| R0_AST_repair_only::seed6 | Phase3A_full::seed5 | 5 | 13 | 0.384615 | 5 | 20 |
| R0_AST_repair_only::seed6 | Phase3A_full::seed6 | 4 | 13 | 0.307692 | 4 | 20 |
| R0_AST_repair_only::seed6 | Phase3A_full::seed7 | 4 | 14 | 0.285714 | 5 | 23 |
| R0_AST_repair_only::seed6 | Phase3A_full::seed8 | 4 | 14 | 0.285714 | 4 | 21 |
| R0_AST_repair_only::seed6 | R0_AST_repair_only::seed5 | 3 | 13 | 0.230769 | 4 | 22 |
| R0_AST_repair_only::seed6 | R0_AST_repair_only::seed6 | 9 | 9 | 1.0 | 13 | 13 |
| R0_AST_repair_only::seed6 | R0_AST_repair_only::seed7 | 3 | 14 | 0.214286 | 5 | 23 |
| R0_AST_repair_only::seed6 | R0_AST_repair_only::seed8 | 4 | 12 | 0.333333 | 6 | 21 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed5 | 4 | 12 | 0.333333 | 4 | 21 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 6 | 21 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed7 | 5 | 13 | 0.384615 | 6 | 20 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed8 | 4 | 13 | 0.307692 | 5 | 20 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_only::seed5 | 3 | 11 | 0.272727 | 3 | 16 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_only::seed6 | 2 | 12 | 0.166667 | 2 | 18 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_only::seed7 | 4 | 14 | 0.285714 | 5 | 19 |
| R0_AST_repair_only::seed6 | R0_cluster_quota_only::seed8 | 2 | 14 | 0.142857 | 3 | 19 |
| R0_AST_repair_only::seed6 | original_R0::seed5 | 2 | 11 | 0.181818 | 5 | 18 |
| R0_AST_repair_only::seed6 | original_R0::seed6 | 2 | 13 | 0.153846 | 2 | 19 |
| R0_AST_repair_only::seed6 | original_R0::seed7 | 2 | 11 | 0.181818 | 4 | 22 |
| R0_AST_repair_only::seed6 | original_R0::seed8 | 2 | 11 | 0.181818 | 3 | 18 |
| R0_AST_repair_only::seed7 | Phase3A_full::seed5 | 3 | 14 | 0.214286 | 5 | 22 |
| R0_AST_repair_only::seed7 | Phase3A_full::seed6 | 3 | 13 | 0.230769 | 4 | 22 |
| R0_AST_repair_only::seed7 | Phase3A_full::seed7 | 3 | 14 | 0.214286 | 6 | 24 |
| R0_AST_repair_only::seed7 | Phase3A_full::seed8 | 6 | 11 | 0.545455 | 7 | 20 |
| R0_AST_repair_only::seed7 | R0_AST_repair_only::seed5 | 2 | 13 | 0.153846 | 7 | 21 |
| R0_AST_repair_only::seed7 | R0_AST_repair_only::seed6 | 3 | 14 | 0.214286 | 5 | 23 |
| R0_AST_repair_only::seed7 | R0_AST_repair_only::seed7 | 8 | 8 | 1.0 | 15 | 15 |
| R0_AST_repair_only::seed7 | R0_AST_repair_only::seed8 | 4 | 11 | 0.363636 | 8 | 21 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed5 | 5 | 10 | 0.5 | 8 | 19 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 13 | 0.307692 | 8 | 21 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 13 | 0.307692 | 7 | 21 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed8 | 4 | 12 | 0.333333 | 7 | 20 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_only::seed5 | 3 | 10 | 0.3 | 4 | 17 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_only::seed6 | 3 | 10 | 0.3 | 3 | 19 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_only::seed7 | 3 | 14 | 0.214286 | 4 | 22 |
| R0_AST_repair_only::seed7 | R0_cluster_quota_only::seed8 | 3 | 12 | 0.25 | 5 | 19 |
| R0_AST_repair_only::seed7 | original_R0::seed5 | 3 | 9 | 0.333333 | 4 | 21 |
| R0_AST_repair_only::seed7 | original_R0::seed6 | 4 | 10 | 0.4 | 6 | 17 |
| R0_AST_repair_only::seed7 | original_R0::seed7 | 2 | 10 | 0.2 | 4 | 24 |
| R0_AST_repair_only::seed7 | original_R0::seed8 | 2 | 10 | 0.2 | 3 | 20 |
| R0_AST_repair_only::seed8 | Phase3A_full::seed5 | 3 | 13 | 0.230769 | 5 | 21 |
| R0_AST_repair_only::seed8 | Phase3A_full::seed6 | 3 | 12 | 0.25 | 5 | 20 |
| R0_AST_repair_only::seed8 | Phase3A_full::seed7 | 3 | 13 | 0.230769 | 5 | 24 |
| R0_AST_repair_only::seed8 | Phase3A_full::seed8 | 4 | 12 | 0.333333 | 6 | 20 |
| R0_AST_repair_only::seed8 | R0_AST_repair_only::seed5 | 2 | 12 | 0.166667 | 5 | 22 |
| R0_AST_repair_only::seed8 | R0_AST_repair_only::seed6 | 4 | 12 | 0.333333 | 6 | 21 |
| R0_AST_repair_only::seed8 | R0_AST_repair_only::seed7 | 4 | 11 | 0.363636 | 8 | 21 |
| R0_AST_repair_only::seed8 | R0_AST_repair_only::seed8 | 7 | 7 | 1.0 | 14 | 14 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed5 | 3 | 11 | 0.272727 | 6 | 20 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 12 | 0.333333 | 7 | 21 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 12 | 0.333333 | 6 | 21 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed8 | 3 | 12 | 0.25 | 5 | 21 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_only::seed5 | 2 | 10 | 0.2 | 3 | 17 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_only::seed6 | 2 | 10 | 0.2 | 3 | 18 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_only::seed7 | 3 | 13 | 0.230769 | 5 | 20 |
| R0_AST_repair_only::seed8 | R0_cluster_quota_only::seed8 | 2 | 12 | 0.166667 | 4 | 19 |
| R0_AST_repair_only::seed8 | original_R0::seed5 | 2 | 9 | 0.222222 | 3 | 21 |
| R0_AST_repair_only::seed8 | original_R0::seed6 | 3 | 10 | 0.3 | 5 | 17 |
| R0_AST_repair_only::seed8 | original_R0::seed7 | 2 | 9 | 0.222222 | 4 | 23 |
| R0_AST_repair_only::seed8 | original_R0::seed8 | 1 | 10 | 0.1 | 4 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | Phase3A_full::seed5 | 5 | 11 | 0.454545 | 6 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | Phase3A_full::seed6 | 3 | 12 | 0.25 | 5 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | Phase3A_full::seed7 | 3 | 13 | 0.230769 | 7 | 20 |
| R0_cluster_quota_AST_repair_only::seed5 | Phase3A_full::seed8 | 4 | 12 | 0.333333 | 6 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_AST_repair_only::seed5 | 2 | 12 | 0.166667 | 7 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_AST_repair_only::seed6 | 4 | 12 | 0.333333 | 4 | 21 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_AST_repair_only::seed7 | 5 | 10 | 0.5 | 8 | 19 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_AST_repair_only::seed8 | 3 | 11 | 0.272727 | 6 | 20 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed5 | 7 | 7 | 1.0 | 12 | 12 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed6 | 6 | 10 | 0.6 | 10 | 16 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 12 | 0.333333 | 5 | 20 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_AST_repair_only::seed8 | 4 | 11 | 0.363636 | 6 | 18 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_only::seed5 | 2 | 10 | 0.2 | 3 | 15 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_only::seed6 | 1 | 11 | 0.090909 | 2 | 17 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_only::seed7 | 2 | 14 | 0.142857 | 3 | 20 |
| R0_cluster_quota_AST_repair_only::seed5 | R0_cluster_quota_only::seed8 | 4 | 10 | 0.4 | 5 | 16 |
| R0_cluster_quota_AST_repair_only::seed5 | original_R0::seed5 | 2 | 9 | 0.222222 | 2 | 20 |
| R0_cluster_quota_AST_repair_only::seed5 | original_R0::seed6 | 2 | 11 | 0.181818 | 3 | 17 |
| R0_cluster_quota_AST_repair_only::seed5 | original_R0::seed7 | 1 | 10 | 0.1 | 2 | 23 |
| R0_cluster_quota_AST_repair_only::seed5 | original_R0::seed8 | 1 | 10 | 0.1 | 3 | 17 |
| R0_cluster_quota_AST_repair_only::seed6 | Phase3A_full::seed5 | 6 | 12 | 0.5 | 8 | 18 |
| R0_cluster_quota_AST_repair_only::seed6 | Phase3A_full::seed6 | 4 | 13 | 0.307692 | 6 | 19 |
| R0_cluster_quota_AST_repair_only::seed6 | Phase3A_full::seed7 | 4 | 14 | 0.285714 | 8 | 21 |
| R0_cluster_quota_AST_repair_only::seed6 | Phase3A_full::seed8 | 5 | 13 | 0.384615 | 7 | 19 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 6 | 21 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 6 | 21 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_AST_repair_only::seed7 | 4 | 13 | 0.307692 | 8 | 21 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_AST_repair_only::seed8 | 4 | 12 | 0.333333 | 7 | 21 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed5 | 6 | 10 | 0.6 | 10 | 16 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed6 | 9 | 9 | 1.0 | 14 | 14 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed7 | 5 | 13 | 0.384615 | 7 | 20 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_AST_repair_only::seed8 | 3 | 14 | 0.214286 | 6 | 20 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_only::seed5 | 2 | 12 | 0.166667 | 3 | 17 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_only::seed6 | 1 | 13 | 0.076923 | 2 | 19 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_only::seed7 | 3 | 15 | 0.2 | 6 | 19 |
| R0_cluster_quota_AST_repair_only::seed6 | R0_cluster_quota_only::seed8 | 4 | 12 | 0.333333 | 6 | 17 |
| R0_cluster_quota_AST_repair_only::seed6 | original_R0::seed5 | 2 | 11 | 0.181818 | 2 | 22 |
| R0_cluster_quota_AST_repair_only::seed6 | original_R0::seed6 | 2 | 13 | 0.153846 | 3 | 19 |
| R0_cluster_quota_AST_repair_only::seed6 | original_R0::seed7 | 1 | 12 | 0.083333 | 2 | 25 |
| R0_cluster_quota_AST_repair_only::seed6 | original_R0::seed8 | 1 | 12 | 0.083333 | 2 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | Phase3A_full::seed5 | 4 | 14 | 0.285714 | 5 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | Phase3A_full::seed6 | 4 | 13 | 0.307692 | 5 | 19 |
| R0_cluster_quota_AST_repair_only::seed7 | Phase3A_full::seed7 | 3 | 15 | 0.2 | 5 | 23 |
| R0_cluster_quota_AST_repair_only::seed7 | Phase3A_full::seed8 | 5 | 13 | 0.384615 | 6 | 19 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 3 | 23 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_AST_repair_only::seed6 | 5 | 13 | 0.384615 | 6 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_AST_repair_only::seed7 | 4 | 13 | 0.307692 | 7 | 21 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_AST_repair_only::seed8 | 4 | 12 | 0.333333 | 6 | 21 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed5 | 4 | 12 | 0.333333 | 5 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed6 | 5 | 13 | 0.384615 | 7 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed7 | 9 | 9 | 1.0 | 13 | 13 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_AST_repair_only::seed8 | 4 | 13 | 0.307692 | 6 | 19 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_only::seed5 | 3 | 11 | 0.272727 | 3 | 16 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_only::seed6 | 3 | 11 | 0.272727 | 3 | 17 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_only::seed7 | 3 | 15 | 0.2 | 4 | 20 |
| R0_cluster_quota_AST_repair_only::seed7 | R0_cluster_quota_only::seed8 | 3 | 13 | 0.230769 | 4 | 18 |
| R0_cluster_quota_AST_repair_only::seed7 | original_R0::seed5 | 4 | 9 | 0.444444 | 6 | 17 |
| R0_cluster_quota_AST_repair_only::seed7 | original_R0::seed6 | 3 | 12 | 0.25 | 3 | 18 |
| R0_cluster_quota_AST_repair_only::seed7 | original_R0::seed7 | 2 | 11 | 0.181818 | 4 | 22 |
| R0_cluster_quota_AST_repair_only::seed7 | original_R0::seed8 | 1 | 12 | 0.083333 | 1 | 20 |
| R0_cluster_quota_AST_repair_only::seed8 | Phase3A_full::seed5 | 2 | 15 | 0.133333 | 3 | 21 |
| R0_cluster_quota_AST_repair_only::seed8 | Phase3A_full::seed6 | 3 | 13 | 0.230769 | 4 | 19 |
| R0_cluster_quota_AST_repair_only::seed8 | Phase3A_full::seed7 | 2 | 15 | 0.133333 | 6 | 21 |
| R0_cluster_quota_AST_repair_only::seed8 | Phase3A_full::seed8 | 4 | 13 | 0.307692 | 5 | 19 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_AST_repair_only::seed5 | 1 | 14 | 0.071429 | 4 | 21 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_AST_repair_only::seed6 | 4 | 13 | 0.307692 | 5 | 20 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_AST_repair_only::seed7 | 4 | 12 | 0.333333 | 7 | 20 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_AST_repair_only::seed8 | 3 | 12 | 0.25 | 5 | 21 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed5 | 4 | 11 | 0.363636 | 6 | 18 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed6 | 3 | 14 | 0.214286 | 6 | 20 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 13 | 0.307692 | 6 | 19 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_AST_repair_only::seed8 | 8 | 8 | 1.0 | 12 | 12 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_only::seed5 | 3 | 10 | 0.3 | 4 | 14 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_only::seed6 | 2 | 11 | 0.181818 | 2 | 17 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_only::seed7 | 2 | 15 | 0.133333 | 3 | 20 |
| R0_cluster_quota_AST_repair_only::seed8 | R0_cluster_quota_only::seed8 | 2 | 13 | 0.153846 | 2 | 19 |
| R0_cluster_quota_AST_repair_only::seed8 | original_R0::seed5 | 3 | 9 | 0.333333 | 5 | 17 |
| R0_cluster_quota_AST_repair_only::seed8 | original_R0::seed6 | 2 | 12 | 0.166667 | 2 | 18 |
| R0_cluster_quota_AST_repair_only::seed8 | original_R0::seed7 | 2 | 10 | 0.2 | 4 | 21 |
| R0_cluster_quota_AST_repair_only::seed8 | original_R0::seed8 | 1 | 11 | 0.090909 | 1 | 19 |
| R0_cluster_quota_only::seed5 | Phase3A_full::seed5 | 1 | 13 | 0.076923 | 1 | 17 |
| R0_cluster_quota_only::seed5 | Phase3A_full::seed6 | 2 | 11 | 0.181818 | 3 | 14 |
| R0_cluster_quota_only::seed5 | Phase3A_full::seed7 | 2 | 12 | 0.166667 | 3 | 18 |
| R0_cluster_quota_only::seed5 | Phase3A_full::seed8 | 3 | 11 | 0.272727 | 4 | 14 |
| R0_cluster_quota_only::seed5 | R0_AST_repair_only::seed5 | 3 | 9 | 0.333333 | 4 | 15 |
| R0_cluster_quota_only::seed5 | R0_AST_repair_only::seed6 | 3 | 11 | 0.272727 | 3 | 16 |
| R0_cluster_quota_only::seed5 | R0_AST_repair_only::seed7 | 3 | 10 | 0.3 | 4 | 17 |
| R0_cluster_quota_only::seed5 | R0_AST_repair_only::seed8 | 2 | 10 | 0.2 | 3 | 17 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_AST_repair_only::seed5 | 2 | 10 | 0.2 | 3 | 15 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_AST_repair_only::seed6 | 2 | 12 | 0.166667 | 3 | 17 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 11 | 0.272727 | 3 | 16 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_AST_repair_only::seed8 | 3 | 10 | 0.3 | 4 | 14 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_only::seed5 | 5 | 5 | 1.0 | 6 | 6 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_only::seed6 | 2 | 8 | 0.25 | 3 | 10 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_only::seed7 | 3 | 11 | 0.272727 | 4 | 13 |
| R0_cluster_quota_only::seed5 | R0_cluster_quota_only::seed8 | 2 | 10 | 0.2 | 3 | 12 |
| R0_cluster_quota_only::seed5 | original_R0::seed5 | 3 | 6 | 0.5 | 4 | 12 |
| R0_cluster_quota_only::seed5 | original_R0::seed6 | 2 | 9 | 0.222222 | 3 | 11 |
| R0_cluster_quota_only::seed5 | original_R0::seed7 | 2 | 7 | 0.285714 | 3 | 16 |
| R0_cluster_quota_only::seed5 | original_R0::seed8 | 1 | 8 | 0.125 | 2 | 12 |
| R0_cluster_quota_only::seed6 | Phase3A_full::seed5 | 2 | 12 | 0.166667 | 2 | 17 |
| R0_cluster_quota_only::seed6 | Phase3A_full::seed6 | 2 | 11 | 0.181818 | 3 | 15 |
| R0_cluster_quota_only::seed6 | Phase3A_full::seed7 | 2 | 12 | 0.166667 | 3 | 19 |
| R0_cluster_quota_only::seed6 | Phase3A_full::seed8 | 2 | 12 | 0.166667 | 3 | 16 |
| R0_cluster_quota_only::seed6 | R0_AST_repair_only::seed5 | 1 | 11 | 0.090909 | 2 | 18 |
| R0_cluster_quota_only::seed6 | R0_AST_repair_only::seed6 | 2 | 12 | 0.166667 | 2 | 18 |
| R0_cluster_quota_only::seed6 | R0_AST_repair_only::seed7 | 3 | 10 | 0.3 | 3 | 19 |
| R0_cluster_quota_only::seed6 | R0_AST_repair_only::seed8 | 2 | 10 | 0.2 | 3 | 18 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_AST_repair_only::seed5 | 1 | 11 | 0.090909 | 2 | 17 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_AST_repair_only::seed6 | 1 | 13 | 0.076923 | 2 | 19 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 11 | 0.272727 | 3 | 17 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 11 | 0.181818 | 2 | 17 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_only::seed5 | 2 | 8 | 0.25 | 3 | 10 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_only::seed6 | 5 | 5 | 1.0 | 7 | 7 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_only::seed7 | 2 | 12 | 0.166667 | 3 | 15 |
| R0_cluster_quota_only::seed6 | R0_cluster_quota_only::seed8 | 1 | 11 | 0.090909 | 2 | 14 |
| R0_cluster_quota_only::seed6 | original_R0::seed5 | 3 | 6 | 0.5 | 3 | 14 |
| R0_cluster_quota_only::seed6 | original_R0::seed6 | 5 | 6 | 0.833333 | 5 | 10 |
| R0_cluster_quota_only::seed6 | original_R0::seed7 | 2 | 7 | 0.285714 | 2 | 18 |
| R0_cluster_quota_only::seed6 | original_R0::seed8 | 2 | 7 | 0.285714 | 2 | 13 |
| R0_cluster_quota_only::seed7 | Phase3A_full::seed5 | 4 | 14 | 0.285714 | 4 | 19 |
| R0_cluster_quota_only::seed7 | Phase3A_full::seed6 | 5 | 12 | 0.416667 | 6 | 16 |
| R0_cluster_quota_only::seed7 | Phase3A_full::seed7 | 3 | 15 | 0.2 | 5 | 21 |
| R0_cluster_quota_only::seed7 | Phase3A_full::seed8 | 3 | 15 | 0.2 | 4 | 19 |
| R0_cluster_quota_only::seed7 | R0_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 3 | 21 |
| R0_cluster_quota_only::seed7 | R0_AST_repair_only::seed6 | 4 | 14 | 0.285714 | 5 | 19 |
| R0_cluster_quota_only::seed7 | R0_AST_repair_only::seed7 | 3 | 14 | 0.214286 | 4 | 22 |
| R0_cluster_quota_only::seed7 | R0_AST_repair_only::seed8 | 3 | 13 | 0.230769 | 5 | 20 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_AST_repair_only::seed5 | 2 | 14 | 0.142857 | 3 | 20 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_AST_repair_only::seed6 | 3 | 15 | 0.2 | 6 | 19 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 15 | 0.2 | 4 | 20 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 15 | 0.133333 | 3 | 20 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_only::seed5 | 3 | 11 | 0.272727 | 4 | 13 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_only::seed6 | 2 | 12 | 0.166667 | 3 | 15 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_only::seed7 | 9 | 9 | 1.0 | 11 | 11 |
| R0_cluster_quota_only::seed7 | R0_cluster_quota_only::seed8 | 3 | 13 | 0.230769 | 5 | 15 |
| R0_cluster_quota_only::seed7 | original_R0::seed5 | 2 | 11 | 0.181818 | 3 | 18 |
| R0_cluster_quota_only::seed7 | original_R0::seed6 | 3 | 12 | 0.25 | 4 | 15 |
| R0_cluster_quota_only::seed7 | original_R0::seed7 | 2 | 11 | 0.181818 | 4 | 20 |
| R0_cluster_quota_only::seed7 | original_R0::seed8 | 1 | 12 | 0.083333 | 2 | 17 |
| R0_cluster_quota_only::seed8 | Phase3A_full::seed5 | 3 | 13 | 0.230769 | 3 | 18 |
| R0_cluster_quota_only::seed8 | Phase3A_full::seed6 | 2 | 13 | 0.153846 | 3 | 17 |
| R0_cluster_quota_only::seed8 | Phase3A_full::seed7 | 1 | 15 | 0.066667 | 2 | 22 |
| R0_cluster_quota_only::seed8 | Phase3A_full::seed8 | 2 | 14 | 0.142857 | 3 | 18 |
| R0_cluster_quota_only::seed8 | R0_AST_repair_only::seed5 | 1 | 13 | 0.076923 | 3 | 19 |
| R0_cluster_quota_only::seed8 | R0_AST_repair_only::seed6 | 2 | 14 | 0.142857 | 3 | 19 |
| R0_cluster_quota_only::seed8 | R0_AST_repair_only::seed7 | 3 | 12 | 0.25 | 5 | 19 |
| R0_cluster_quota_only::seed8 | R0_AST_repair_only::seed8 | 2 | 12 | 0.166667 | 4 | 19 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_AST_repair_only::seed5 | 4 | 10 | 0.4 | 5 | 16 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_AST_repair_only::seed6 | 4 | 12 | 0.333333 | 6 | 17 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 13 | 0.230769 | 4 | 18 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 13 | 0.153846 | 2 | 19 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_only::seed5 | 2 | 10 | 0.2 | 3 | 12 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_only::seed6 | 1 | 11 | 0.090909 | 2 | 14 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_only::seed7 | 3 | 13 | 0.230769 | 5 | 15 |
| R0_cluster_quota_only::seed8 | R0_cluster_quota_only::seed8 | 7 | 7 | 1.0 | 9 | 9 |
| R0_cluster_quota_only::seed8 | original_R0::seed5 | 2 | 9 | 0.222222 | 2 | 17 |
| R0_cluster_quota_only::seed8 | original_R0::seed6 | 2 | 11 | 0.181818 | 3 | 14 |
| R0_cluster_quota_only::seed8 | original_R0::seed7 | 1 | 10 | 0.1 | 2 | 20 |
| R0_cluster_quota_only::seed8 | original_R0::seed8 | 1 | 10 | 0.1 | 2 | 15 |
| original_R0::seed5 | Phase3A_full::seed5 | 1 | 12 | 0.083333 | 1 | 21 |
| original_R0::seed5 | Phase3A_full::seed6 | 2 | 10 | 0.2 | 2 | 19 |
| original_R0::seed5 | Phase3A_full::seed7 | 1 | 12 | 0.083333 | 4 | 21 |
| original_R0::seed5 | Phase3A_full::seed8 | 3 | 10 | 0.3 | 3 | 19 |
| original_R0::seed5 | R0_AST_repair_only::seed5 | 1 | 10 | 0.1 | 2 | 21 |
| original_R0::seed5 | R0_AST_repair_only::seed6 | 2 | 11 | 0.181818 | 5 | 18 |
| original_R0::seed5 | R0_AST_repair_only::seed7 | 3 | 9 | 0.333333 | 4 | 21 |
| original_R0::seed5 | R0_AST_repair_only::seed8 | 2 | 9 | 0.222222 | 3 | 21 |
| original_R0::seed5 | R0_cluster_quota_AST_repair_only::seed5 | 2 | 9 | 0.222222 | 2 | 20 |
| original_R0::seed5 | R0_cluster_quota_AST_repair_only::seed6 | 2 | 11 | 0.181818 | 2 | 22 |
| original_R0::seed5 | R0_cluster_quota_AST_repair_only::seed7 | 4 | 9 | 0.444444 | 6 | 17 |
| original_R0::seed5 | R0_cluster_quota_AST_repair_only::seed8 | 3 | 9 | 0.333333 | 5 | 17 |
| original_R0::seed5 | R0_cluster_quota_only::seed5 | 3 | 6 | 0.5 | 4 | 12 |
| original_R0::seed5 | R0_cluster_quota_only::seed6 | 3 | 6 | 0.5 | 3 | 14 |
| original_R0::seed5 | R0_cluster_quota_only::seed7 | 2 | 11 | 0.181818 | 3 | 18 |
| original_R0::seed5 | R0_cluster_quota_only::seed8 | 2 | 9 | 0.222222 | 2 | 17 |
| original_R0::seed5 | original_R0::seed5 | 4 | 4 | 1.0 | 10 | 10 |
| original_R0::seed5 | original_R0::seed6 | 3 | 7 | 0.428571 | 3 | 15 |
| original_R0::seed5 | original_R0::seed7 | 2 | 6 | 0.333333 | 4 | 19 |
| original_R0::seed5 | original_R0::seed8 | 1 | 7 | 0.142857 | 2 | 16 |
| original_R0::seed6 | Phase3A_full::seed5 | 3 | 12 | 0.25 | 4 | 16 |
| original_R0::seed6 | Phase3A_full::seed6 | 2 | 12 | 0.166667 | 3 | 16 |
| original_R0::seed6 | Phase3A_full::seed7 | 2 | 13 | 0.153846 | 3 | 20 |
| original_R0::seed6 | Phase3A_full::seed8 | 2 | 13 | 0.153846 | 4 | 16 |
| original_R0::seed6 | R0_AST_repair_only::seed5 | 1 | 12 | 0.083333 | 3 | 18 |
| original_R0::seed6 | R0_AST_repair_only::seed6 | 2 | 13 | 0.153846 | 2 | 19 |
| original_R0::seed6 | R0_AST_repair_only::seed7 | 4 | 10 | 0.4 | 6 | 17 |
| original_R0::seed6 | R0_AST_repair_only::seed8 | 3 | 10 | 0.3 | 5 | 17 |
| original_R0::seed6 | R0_cluster_quota_AST_repair_only::seed5 | 2 | 11 | 0.181818 | 3 | 17 |
| original_R0::seed6 | R0_cluster_quota_AST_repair_only::seed6 | 2 | 13 | 0.153846 | 3 | 19 |
| original_R0::seed6 | R0_cluster_quota_AST_repair_only::seed7 | 3 | 12 | 0.25 | 3 | 18 |
| original_R0::seed6 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 12 | 0.166667 | 2 | 18 |
| original_R0::seed6 | R0_cluster_quota_only::seed5 | 2 | 9 | 0.222222 | 3 | 11 |
| original_R0::seed6 | R0_cluster_quota_only::seed6 | 5 | 6 | 0.833333 | 5 | 10 |
| original_R0::seed6 | R0_cluster_quota_only::seed7 | 3 | 12 | 0.25 | 4 | 15 |
| original_R0::seed6 | R0_cluster_quota_only::seed8 | 2 | 11 | 0.181818 | 3 | 14 |
| original_R0::seed6 | original_R0::seed5 | 3 | 7 | 0.428571 | 3 | 15 |
| original_R0::seed6 | original_R0::seed6 | 6 | 6 | 1.0 | 8 | 8 |
| original_R0::seed6 | original_R0::seed7 | 2 | 8 | 0.25 | 3 | 18 |
| original_R0::seed6 | original_R0::seed8 | 2 | 8 | 0.25 | 3 | 13 |
| original_R0::seed7 | Phase3A_full::seed5 | 1 | 12 | 0.083333 | 2 | 23 |
| original_R0::seed7 | Phase3A_full::seed6 | 2 | 10 | 0.2 | 2 | 22 |
| original_R0::seed7 | Phase3A_full::seed7 | 2 | 11 | 0.181818 | 5 | 23 |
| original_R0::seed7 | Phase3A_full::seed8 | 2 | 11 | 0.181818 | 2 | 23 |
| original_R0::seed7 | R0_AST_repair_only::seed5 | 2 | 9 | 0.222222 | 4 | 22 |
| original_R0::seed7 | R0_AST_repair_only::seed6 | 2 | 11 | 0.181818 | 4 | 22 |
| original_R0::seed7 | R0_AST_repair_only::seed7 | 2 | 10 | 0.2 | 4 | 24 |
| original_R0::seed7 | R0_AST_repair_only::seed8 | 2 | 9 | 0.222222 | 4 | 23 |
| original_R0::seed7 | R0_cluster_quota_AST_repair_only::seed5 | 1 | 10 | 0.1 | 2 | 23 |
| original_R0::seed7 | R0_cluster_quota_AST_repair_only::seed6 | 1 | 12 | 0.083333 | 2 | 25 |
| original_R0::seed7 | R0_cluster_quota_AST_repair_only::seed7 | 2 | 11 | 0.181818 | 4 | 22 |
| original_R0::seed7 | R0_cluster_quota_AST_repair_only::seed8 | 2 | 10 | 0.2 | 4 | 21 |
| original_R0::seed7 | R0_cluster_quota_only::seed5 | 2 | 7 | 0.285714 | 3 | 16 |
| original_R0::seed7 | R0_cluster_quota_only::seed6 | 2 | 7 | 0.285714 | 2 | 18 |
| original_R0::seed7 | R0_cluster_quota_only::seed7 | 2 | 11 | 0.181818 | 4 | 20 |
| original_R0::seed7 | R0_cluster_quota_only::seed8 | 1 | 10 | 0.1 | 2 | 20 |
| original_R0::seed7 | original_R0::seed5 | 2 | 6 | 0.333333 | 4 | 19 |
| original_R0::seed7 | original_R0::seed6 | 2 | 8 | 0.25 | 3 | 18 |
| original_R0::seed7 | original_R0::seed7 | 4 | 4 | 1.0 | 13 | 13 |
| original_R0::seed7 | original_R0::seed8 | 1 | 7 | 0.142857 | 3 | 18 |
| original_R0::seed8 | Phase3A_full::seed5 | 1 | 12 | 0.083333 | 2 | 18 |
| original_R0::seed8 | Phase3A_full::seed6 | 1 | 11 | 0.090909 | 2 | 17 |
| original_R0::seed8 | Phase3A_full::seed7 | 2 | 11 | 0.181818 | 4 | 19 |
| original_R0::seed8 | Phase3A_full::seed8 | 2 | 11 | 0.181818 | 3 | 17 |
| original_R0::seed8 | R0_AST_repair_only::seed5 | 1 | 10 | 0.1 | 4 | 17 |
| original_R0::seed8 | R0_AST_repair_only::seed6 | 2 | 11 | 0.181818 | 3 | 18 |
| original_R0::seed8 | R0_AST_repair_only::seed7 | 2 | 10 | 0.2 | 3 | 20 |
| original_R0::seed8 | R0_AST_repair_only::seed8 | 1 | 10 | 0.1 | 4 | 18 |
| original_R0::seed8 | R0_cluster_quota_AST_repair_only::seed5 | 1 | 10 | 0.1 | 3 | 17 |
| original_R0::seed8 | R0_cluster_quota_AST_repair_only::seed6 | 1 | 12 | 0.083333 | 2 | 20 |
| original_R0::seed8 | R0_cluster_quota_AST_repair_only::seed7 | 1 | 12 | 0.083333 | 1 | 20 |
| original_R0::seed8 | R0_cluster_quota_AST_repair_only::seed8 | 1 | 11 | 0.090909 | 1 | 19 |
| original_R0::seed8 | R0_cluster_quota_only::seed5 | 1 | 8 | 0.125 | 2 | 12 |
| original_R0::seed8 | R0_cluster_quota_only::seed6 | 2 | 7 | 0.285714 | 2 | 13 |
| original_R0::seed8 | R0_cluster_quota_only::seed7 | 1 | 12 | 0.083333 | 2 | 17 |
| original_R0::seed8 | R0_cluster_quota_only::seed8 | 1 | 10 | 0.1 | 2 | 15 |
| original_R0::seed8 | original_R0::seed5 | 1 | 7 | 0.142857 | 2 | 16 |
| original_R0::seed8 | original_R0::seed6 | 2 | 8 | 0.25 | 3 | 13 |
| original_R0::seed8 | original_R0::seed7 | 1 | 7 | 0.142857 | 3 | 18 |
| original_R0::seed8 | original_R0::seed8 | 4 | 4 | 1.0 | 8 | 8 |

## Arm Overlap Matrix

| left_arm | right_arm | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3A_full | Phase3A_full | 20 | 20 | 1.0 | 30 | 30 |
| Phase3A_full | R0_AST_repair_only | 14 | 26 | 0.538462 | 19 | 43 |
| Phase3A_full | R0_cluster_quota_AST_repair_only | 10 | 26 | 0.384615 | 16 | 39 |
| Phase3A_full | R0_cluster_quota_only | 11 | 26 | 0.423077 | 12 | 38 |
| Phase3A_full | original_R0 | 7 | 24 | 0.291667 | 14 | 42 |
| R0_AST_repair_only | Phase3A_full | 14 | 26 | 0.538462 | 19 | 43 |
| R0_AST_repair_only | R0_AST_repair_only | 20 | 20 | 1.0 | 32 | 32 |
| R0_AST_repair_only | R0_cluster_quota_AST_repair_only | 10 | 26 | 0.384615 | 17 | 40 |
| R0_AST_repair_only | R0_cluster_quota_only | 9 | 28 | 0.321429 | 10 | 42 |
| R0_AST_repair_only | original_R0 | 7 | 24 | 0.291667 | 14 | 44 |
| R0_cluster_quota_AST_repair_only | Phase3A_full | 10 | 26 | 0.384615 | 16 | 39 |
| R0_cluster_quota_AST_repair_only | R0_AST_repair_only | 10 | 26 | 0.384615 | 17 | 40 |
| R0_cluster_quota_AST_repair_only | R0_cluster_quota_AST_repair_only | 16 | 16 | 1.0 | 25 | 25 |
| R0_cluster_quota_AST_repair_only | R0_cluster_quota_only | 7 | 26 | 0.269231 | 11 | 34 |
| R0_cluster_quota_AST_repair_only | original_R0 | 5 | 22 | 0.227273 | 11 | 40 |
| R0_cluster_quota_only | Phase3A_full | 11 | 26 | 0.423077 | 12 | 38 |
| R0_cluster_quota_only | R0_AST_repair_only | 9 | 28 | 0.321429 | 10 | 42 |
| R0_cluster_quota_only | R0_cluster_quota_AST_repair_only | 7 | 26 | 0.269231 | 11 | 34 |
| R0_cluster_quota_only | R0_cluster_quota_only | 17 | 17 | 1.0 | 20 | 20 |
| R0_cluster_quota_only | original_R0 | 7 | 21 | 0.333333 | 9 | 37 |
| original_R0 | Phase3A_full | 7 | 24 | 0.291667 | 14 | 42 |
| original_R0 | R0_AST_repair_only | 7 | 24 | 0.291667 | 14 | 44 |
| original_R0 | R0_cluster_quota_AST_repair_only | 5 | 22 | 0.227273 | 11 | 40 |
| original_R0 | R0_cluster_quota_only | 7 | 21 | 0.333333 | 9 | 37 |
| original_R0 | original_R0 | 11 | 11 | 1.0 | 26 | 26 |

## Lane Attribution

| lane | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters |
| --- | --- | --- | --- | --- |
| ast_failure_aware_repair | 156 | 139 | 11 | 9 |
| novelty_diagnostic | 28 | 0 | 0 | 0 |
| r0_cem_led | 1072 | 272 | 55 | 30 |
| replay_aware_residual | 24 | 12 | 1 | 1 |

## Denominator Audit

| seed | generated | valid | candidate_pool | selected_for_audit | audited | replay_attempted | replay_pass | non_gap_replay_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed7 | 640 | 640 | 455 | 64 | 64 | 64 | 20 | 20 |
| seed8 | 640 | 640 | 458 | 64 | 64 | 64 | 16 | 16 |
| seed7 | 704 | 704 | 514 | 64 | 64 | 64 | 29 | 29 |
| seed8 | 704 | 704 | 520 | 64 | 64 | 64 | 26 | 26 |
| seed7 | 704 | 704 | 522 | 64 | 64 | 64 | 31 | 31 |
| seed8 | 704 | 704 | 522 | 64 | 64 | 64 | 31 | 31 |
| seed7 | 704 | 704 | 524 | 64 | 64 | 64 | 25 | 25 |
| seed8 | 704 | 704 | 519 | 64 | 64 | 64 | 19 | 19 |
| seed7 | 640 | 640 | 450 | 64 | 64 | 64 | 18 | 18 |
| seed8 | 640 | 640 | 456 | 64 | 64 | 64 | 12 | 12 |
| seed5 | 640 | 640 | 452 | 64 | 64 | 64 | 17 | 17 |
| seed6 | 640 | 640 | 455 | 64 | 64 | 64 | 17 | 17 |
| seed5 | 704 | 704 | 515 | 64 | 64 | 64 | 24 | 24 |
| seed6 | 704 | 704 | 517 | 64 | 64 | 64 | 21 | 21 |
| seed5 | 704 | 704 | 520 | 64 | 64 | 64 | 27 | 27 |
| seed6 | 704 | 704 | 506 | 64 | 64 | 64 | 26 | 26 |
| seed5 | 704 | 704 | 513 | 64 | 64 | 64 | 21 | 21 |
| seed6 | 704 | 704 | 514 | 64 | 64 | 64 | 24 | 24 |
| seed5 | 640 | 640 | 457 | 64 | 64 | 64 | 8 | 8 |
| seed6 | 640 | 640 | 458 | 64 | 64 | 64 | 11 | 11 |

## Bias Audit

- decision: `HOLD_RESEARCH`
- reason: Phase3A aggregate validates search mechanics and global cluster uniqueness, but sector neutralization/capacity/survivorship promotion-grade checks remain blockers.
- date alignment: true-limit after_open + T+1 contract inherited from strict rows.
- replay vs discovery: Phase3A repair is search-method evidence; not a commercial alpha promotion.

## Next Ablation

A. original R0/CEM-led baseline
B. R0/CEM-led + cluster quota
C. R0 + AST repair only
D. Phase3A full
