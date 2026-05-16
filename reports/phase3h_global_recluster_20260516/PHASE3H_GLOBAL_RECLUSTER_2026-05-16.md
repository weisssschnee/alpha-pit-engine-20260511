# Phase3H Global Aggregate Report

- created_at: `2026-05-16T03:26:18.395492+08:00`
- decision: `PASS_CONFIRM_PHASE3H`
- metadata_gate_decision: `HOLD_METADATA_ONLY`
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
    "raw_pass_not_primary": true,
    "local_and_company_runner_represented": false
  },
  "algorithm_criteria": {
    "global_deployable_clusters_gt_phase2_reference_5": true,
    "global_deployable_clusters_gte_8": true,
    "top_cluster_share_lt_50pct": true,
    "ast_repair_new_deployable_clusters_vs_phase2_r0_gte_2": true,
    "raw_pass_not_primary": true
  },
  "metadata_criteria": {
    "local_and_company_runner_represented": false
  },
  "metadata_gate_decision": "HOLD_METADATA_ONLY",
  "require_local_and_company": false,
  "machine_sources": [
    "company"
  ],
  "ast_repair_deployable_clusters": [
    "cluster_001",
    "cluster_006",
    "cluster_007",
    "cluster_011",
    "cluster_013",
    "cluster_036",
    "cluster_039",
    "cluster_044",
    "cluster_045"
  ],
  "ast_repair_new_deployable_clusters_vs_phase2_r0": 9,
  "ast_repair_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_006",
    "cluster_007",
    "cluster_011",
    "cluster_013",
    "cluster_036",
    "cluster_039",
    "cluster_044",
    "cluster_045"
  ],
  "decision": "PASS_CONFIRM_PHASE3H"
}
```

## Global Union Metrics

```json
{
  "completed_phase3_seed_count": 12,
  "audited": 768,
  "global_unique_return_corr_clusters": 55,
  "global_deployable_clusters": 37,
  "phase2_r0_baseline_deployable_clusters": 0,
  "global_new_clusters_vs_phase2_r0": 37,
  "global_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_002",
    "cluster_004",
    "cluster_005",
    "cluster_006",
    "cluster_007",
    "cluster_008",
    "cluster_010",
    "cluster_011",
    "cluster_012",
    "cluster_013",
    "cluster_014",
    "cluster_015",
    "cluster_016",
    "cluster_018",
    "cluster_019",
    "cluster_020",
    "cluster_021",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_026",
    "cluster_028",
    "cluster_029",
    "cluster_031",
    "cluster_034",
    "cluster_036",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_041",
    "cluster_044",
    "cluster_045",
    "cluster_046",
    "cluster_049",
    "cluster_051"
  ],
  "phase3b_union_baseline_deployable_clusters": 0,
  "new_deployable_clusters_vs_phase3B_union": null,
  "new_deployable_cluster_ids_vs_phase3B_union": [],
  "phase3_cumulative_baseline_deployable_clusters": 124,
  "phase3_cumulative_baseline_declared_clusters": 134,
  "new_deployable_clusters_vs_phase3_cumulative": 15,
  "new_deployable_cluster_ids_vs_phase3_cumulative": [
    "cluster_004",
    "cluster_015",
    "cluster_018",
    "cluster_019",
    "cluster_020",
    "cluster_021",
    "cluster_025",
    "cluster_026",
    "cluster_028",
    "cluster_034",
    "cluster_038",
    "cluster_039",
    "cluster_045",
    "cluster_046",
    "cluster_049"
  ],
  "raw_non_gap_pass": 257,
  "global_top_cluster_id": "cluster_006",
  "global_top_cluster_share": 0.252918,
  "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
  "seed_local_labels_ignored": true
}
```

## Per Seed Metrics

| run_id | seed | ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3H_H0_G0_stable::s33_h0 | s33_h0 | Phase3H_H0_G0_stable | 64 | 30 | 18 | 15 | cluster_006 | 0.366667 |
| Phase3H_H0_G0_stable::s34_h0 | s34_h0 | Phase3H_H0_G0_stable | 64 | 29 | 13 | 9 | cluster_006 | 0.448276 |
| Phase3H_H0_G0_stable::s35_h0 | s35_h0 | Phase3H_H0_G0_stable | 64 | 30 | 17 | 11 | cluster_006 | 0.366667 |
| Phase3H_H0_G0_stable::s36_h0 | s36_h0 | Phase3H_H0_G0_stable | 64 | 25 | 13 | 10 | cluster_006 | 0.52 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | s33_h1 | Phase3H_H1_G2_signal_vector_control | 64 | 16 | 15 | 12 | cluster_006 | 0.125 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | s34_h1 | Phase3H_H1_G2_signal_vector_control | 64 | 18 | 18 | 12 | cluster_006 | 0.055556 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | s35_h1 | Phase3H_H1_G2_signal_vector_control | 64 | 16 | 15 | 9 | cluster_009 | 0.125 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | s36_h1 | Phase3H_H1_G2_signal_vector_control | 64 | 20 | 18 | 12 | cluster_006 | 0.1 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | s33_h2 | Phase3H_H2_G2_turnover_calibrated | 64 | 15 | 14 | 12 | cluster_006 | 0.133333 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | s34_h2 | Phase3H_H2_G2_turnover_calibrated | 64 | 18 | 16 | 11 | cluster_006 | 0.111111 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | s35_h2 | Phase3H_H2_G2_turnover_calibrated | 64 | 19 | 15 | 9 | cluster_006 | 0.210526 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | s36_h2 | Phase3H_H2_G2_turnover_calibrated | 64 | 21 | 17 | 12 | cluster_006 | 0.142857 |

## Per Arm Metrics

| ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share | median_turnover | median_complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3H_H0_G0_stable | 256 | 114 | 39 | 29 | cluster_006 | 0.421053 | 0.081663 | 11.0 |
| Phase3H_H1_G2_signal_vector_control | 256 | 70 | 50 | 34 | cluster_006 | 0.085714 | 0.137688 | 16.0 |
| Phase3H_H2_G2_turnover_calibrated | 256 | 73 | 48 | 33 | cluster_006 | 0.150685 | 0.140328 | 17.0 |

## Seed Overlap Matrix

| left_seed | right_seed | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H0_G0_stable::s33_h0 | 15 | 15 | 1.0 | 18 | 18 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H0_G0_stable::s34_h0 | 3 | 21 | 0.142857 | 5 | 26 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H0_G0_stable::s35_h0 | 5 | 21 | 0.238095 | 7 | 28 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H0_G0_stable::s36_h0 | 7 | 18 | 0.388889 | 8 | 23 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 9 | 18 | 0.5 | 11 | 22 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 5 | 22 | 0.227273 | 7 | 29 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 2 | 22 | 0.090909 | 4 | 29 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 5 | 22 | 0.227273 | 6 | 30 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 8 | 19 | 0.421053 | 9 | 23 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 4 | 22 | 0.181818 | 6 | 28 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 2 | 22 | 0.090909 | 4 | 29 |
| Phase3H_H0_G0_stable::s33_h0 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 5 | 22 | 0.227273 | 5 | 30 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H0_G0_stable::s33_h0 | 3 | 21 | 0.142857 | 5 | 26 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H0_G0_stable::s34_h0 | 9 | 9 | 1.0 | 13 | 13 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H0_G0_stable::s35_h0 | 3 | 17 | 0.176471 | 4 | 26 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H0_G0_stable::s36_h0 | 3 | 16 | 0.1875 | 4 | 22 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 3 | 18 | 0.166667 | 4 | 24 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 9 | 12 | 0.75 | 12 | 19 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 1 | 17 | 0.058824 | 2 | 26 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 2 | 19 | 0.105263 | 3 | 28 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 18 | 0.166667 | 3 | 24 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 9 | 11 | 0.818182 | 12 | 17 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 1 | 17 | 0.058824 | 2 | 26 |
| Phase3H_H0_G0_stable::s34_h0 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 2 | 19 | 0.105263 | 2 | 28 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H0_G0_stable::s33_h0 | 5 | 21 | 0.238095 | 7 | 28 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H0_G0_stable::s34_h0 | 3 | 17 | 0.176471 | 4 | 26 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H0_G0_stable::s35_h0 | 11 | 11 | 1.0 | 17 | 17 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H0_G0_stable::s36_h0 | 6 | 15 | 0.4 | 8 | 22 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 3 | 20 | 0.15 | 3 | 29 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 3 | 20 | 0.15 | 4 | 31 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 6 | 14 | 0.428571 | 10 | 22 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 20 | 0.15 | 5 | 30 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 4 | 19 | 0.210526 | 4 | 27 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 3 | 19 | 0.157895 | 4 | 29 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 6 | 14 | 0.428571 | 10 | 22 |
| Phase3H_H0_G0_stable::s35_h0 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 20 | 0.15 | 5 | 29 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H0_G0_stable::s33_h0 | 7 | 18 | 0.388889 | 8 | 23 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H0_G0_stable::s34_h0 | 3 | 16 | 0.1875 | 4 | 22 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H0_G0_stable::s35_h0 | 6 | 15 | 0.4 | 8 | 22 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H0_G0_stable::s36_h0 | 10 | 10 | 1.0 | 13 | 13 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 3 | 19 | 0.157895 | 3 | 25 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 4 | 18 | 0.222222 | 5 | 26 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 3 | 16 | 0.1875 | 4 | 24 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 7 | 15 | 0.466667 | 9 | 22 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 19 | 0.157895 | 3 | 24 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 4 | 17 | 0.235294 | 5 | 24 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 3 | 16 | 0.1875 | 4 | 24 |
| Phase3H_H0_G0_stable::s36_h0 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 7 | 15 | 0.466667 | 9 | 21 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H0_G0_stable::s33_h0 | 9 | 18 | 0.5 | 11 | 22 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H0_G0_stable::s34_h0 | 3 | 18 | 0.166667 | 4 | 24 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H0_G0_stable::s35_h0 | 3 | 20 | 0.15 | 3 | 29 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H0_G0_stable::s36_h0 | 3 | 19 | 0.157895 | 3 | 25 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 12 | 12 | 1.0 | 15 | 15 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 5 | 19 | 0.263158 | 6 | 27 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 2 | 19 | 0.105263 | 3 | 27 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 21 | 0.142857 | 4 | 29 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 11 | 13 | 0.846154 | 13 | 16 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 4 | 19 | 0.210526 | 5 | 26 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 2 | 19 | 0.105263 | 3 | 27 |
| Phase3H_H1_G2_signal_vector_control::s33_h1 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 21 | 0.142857 | 3 | 29 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H0_G0_stable::s33_h0 | 5 | 22 | 0.227273 | 7 | 29 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H0_G0_stable::s34_h0 | 9 | 12 | 0.75 | 12 | 19 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H0_G0_stable::s35_h0 | 3 | 20 | 0.15 | 4 | 31 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H0_G0_stable::s36_h0 | 4 | 18 | 0.222222 | 5 | 26 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 5 | 19 | 0.263158 | 6 | 27 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 12 | 12 | 1.0 | 18 | 18 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 2 | 19 | 0.105263 | 3 | 30 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 21 | 0.142857 | 4 | 32 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 5 | 19 | 0.263158 | 5 | 27 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 11 | 12 | 0.916667 | 16 | 18 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 2 | 19 | 0.105263 | 3 | 30 |
| Phase3H_H1_G2_signal_vector_control::s34_h1 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 21 | 0.142857 | 3 | 32 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H0_G0_stable::s33_h0 | 2 | 22 | 0.090909 | 4 | 29 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H0_G0_stable::s34_h0 | 1 | 17 | 0.058824 | 2 | 26 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H0_G0_stable::s35_h0 | 6 | 14 | 0.428571 | 10 | 22 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H0_G0_stable::s36_h0 | 3 | 16 | 0.1875 | 4 | 24 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 2 | 19 | 0.105263 | 3 | 27 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 2 | 19 | 0.105263 | 3 | 30 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 9 | 9 | 1.0 | 15 | 15 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 18 | 0.166667 | 6 | 27 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 18 | 0.166667 | 3 | 26 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 2 | 18 | 0.111111 | 3 | 28 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 9 | 9 | 1.0 | 15 | 15 |
| Phase3H_H1_G2_signal_vector_control::s35_h1 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 18 | 0.166667 | 5 | 27 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H0_G0_stable::s33_h0 | 5 | 22 | 0.227273 | 6 | 30 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H0_G0_stable::s34_h0 | 2 | 19 | 0.105263 | 3 | 28 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H0_G0_stable::s35_h0 | 3 | 20 | 0.15 | 5 | 30 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H0_G0_stable::s36_h0 | 7 | 15 | 0.466667 | 9 | 22 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 3 | 21 | 0.142857 | 4 | 29 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 3 | 21 | 0.142857 | 4 | 32 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 3 | 18 | 0.166667 | 6 | 27 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 12 | 12 | 1.0 | 18 | 18 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 21 | 0.142857 | 3 | 29 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 3 | 20 | 0.15 | 4 | 30 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 3 | 18 | 0.166667 | 6 | 27 |
| Phase3H_H1_G2_signal_vector_control::s36_h1 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 12 | 12 | 1.0 | 17 | 18 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H0_G0_stable::s33_h0 | 8 | 19 | 0.421053 | 9 | 23 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H0_G0_stable::s34_h0 | 3 | 18 | 0.166667 | 3 | 24 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H0_G0_stable::s35_h0 | 4 | 19 | 0.210526 | 4 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H0_G0_stable::s36_h0 | 3 | 19 | 0.157895 | 3 | 24 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 11 | 13 | 0.846154 | 13 | 16 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 5 | 19 | 0.263158 | 5 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 3 | 18 | 0.166667 | 3 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 21 | 0.142857 | 3 | 29 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 12 | 12 | 1.0 | 14 | 14 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 4 | 19 | 0.210526 | 4 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 3 | 18 | 0.166667 | 3 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s33_h2 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 21 | 0.142857 | 3 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H0_G0_stable::s33_h0 | 4 | 22 | 0.181818 | 6 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H0_G0_stable::s34_h0 | 9 | 11 | 0.818182 | 12 | 17 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H0_G0_stable::s35_h0 | 3 | 19 | 0.157895 | 4 | 29 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H0_G0_stable::s36_h0 | 4 | 17 | 0.235294 | 5 | 24 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 4 | 19 | 0.210526 | 5 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 11 | 12 | 0.916667 | 16 | 18 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 2 | 18 | 0.111111 | 3 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 20 | 0.15 | 4 | 30 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 4 | 19 | 0.210526 | 4 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 11 | 11 | 1.0 | 16 | 16 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 2 | 18 | 0.111111 | 3 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s34_h2 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 20 | 0.15 | 3 | 30 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H0_G0_stable::s33_h0 | 2 | 22 | 0.090909 | 4 | 29 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H0_G0_stable::s34_h0 | 1 | 17 | 0.058824 | 2 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H0_G0_stable::s35_h0 | 6 | 14 | 0.428571 | 10 | 22 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H0_G0_stable::s36_h0 | 3 | 16 | 0.1875 | 4 | 24 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 2 | 19 | 0.105263 | 3 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 2 | 19 | 0.105263 | 3 | 30 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 9 | 9 | 1.0 | 15 | 15 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 3 | 18 | 0.166667 | 6 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 18 | 0.166667 | 3 | 26 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 2 | 18 | 0.111111 | 3 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 9 | 9 | 1.0 | 15 | 15 |
| Phase3H_H2_G2_turnover_calibrated::s35_h2 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 3 | 18 | 0.166667 | 5 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H0_G0_stable::s33_h0 | 5 | 22 | 0.227273 | 5 | 30 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H0_G0_stable::s34_h0 | 2 | 19 | 0.105263 | 2 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H0_G0_stable::s35_h0 | 3 | 20 | 0.15 | 5 | 29 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H0_G0_stable::s36_h0 | 7 | 15 | 0.466667 | 9 | 21 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H1_G2_signal_vector_control::s33_h1 | 3 | 21 | 0.142857 | 3 | 29 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H1_G2_signal_vector_control::s34_h1 | 3 | 21 | 0.142857 | 3 | 32 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H1_G2_signal_vector_control::s35_h1 | 3 | 18 | 0.166667 | 5 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H1_G2_signal_vector_control::s36_h1 | 12 | 12 | 1.0 | 17 | 18 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H2_G2_turnover_calibrated::s33_h2 | 3 | 21 | 0.142857 | 3 | 28 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H2_G2_turnover_calibrated::s34_h2 | 3 | 20 | 0.15 | 3 | 30 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H2_G2_turnover_calibrated::s35_h2 | 3 | 18 | 0.166667 | 5 | 27 |
| Phase3H_H2_G2_turnover_calibrated::s36_h2 | Phase3H_H2_G2_turnover_calibrated::s36_h2 | 12 | 12 | 1.0 | 17 | 17 |

## Arm Overlap Matrix

| left_arm | right_arm | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3H_H0_G0_stable | Phase3H_H0_G0_stable | 29 | 29 | 1.0 | 39 | 39 |
| Phase3H_H0_G0_stable | Phase3H_H1_G2_signal_vector_control | 26 | 37 | 0.702703 | 34 | 55 |
| Phase3H_H0_G0_stable | Phase3H_H2_G2_turnover_calibrated | 25 | 37 | 0.675676 | 33 | 54 |
| Phase3H_H1_G2_signal_vector_control | Phase3H_H0_G0_stable | 26 | 37 | 0.702703 | 34 | 55 |
| Phase3H_H1_G2_signal_vector_control | Phase3H_H1_G2_signal_vector_control | 34 | 34 | 1.0 | 50 | 50 |
| Phase3H_H1_G2_signal_vector_control | Phase3H_H2_G2_turnover_calibrated | 33 | 34 | 0.970588 | 48 | 50 |
| Phase3H_H2_G2_turnover_calibrated | Phase3H_H0_G0_stable | 25 | 37 | 0.675676 | 33 | 54 |
| Phase3H_H2_G2_turnover_calibrated | Phase3H_H1_G2_signal_vector_control | 33 | 34 | 0.970588 | 48 | 50 |
| Phase3H_H2_G2_turnover_calibrated | Phase3H_H2_G2_turnover_calibrated | 33 | 33 | 1.0 | 48 | 48 |

## Lane Attribution

| lane | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters |
| --- | --- | --- | --- | --- |
| agnostic_freeform_ast | 176 | 67 | 25 | 19 |
| ast_failure_aware_repair | 108 | 57 | 11 | 9 |
| formula_gen_v2_repair_expansion | 96 | 56 | 15 | 9 |
| r0_cem_led | 372 | 69 | 16 | 10 |
| replay_aware_residual | 16 | 8 | 5 | 4 |

## Denominator Audit

| seed | generated | valid | candidate_pool | selected_for_audit | audited | replay_attempted | replay_pass | non_gap_replay_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s33_h0 | 0 | 0 | 0 | 0 | 64 | 64 | 30 | 30 |
| s33_h1 | 0 | 0 | 0 | 0 | 64 | 64 | 16 | 16 |
| s33_h2 | 0 | 0 | 0 | 0 | 64 | 64 | 15 | 15 |
| s34_h0 | 0 | 0 | 0 | 0 | 64 | 64 | 29 | 29 |
| s34_h1 | 0 | 0 | 0 | 0 | 64 | 64 | 18 | 18 |
| s34_h2 | 0 | 0 | 0 | 0 | 64 | 64 | 18 | 18 |
| s35_h0 | 0 | 0 | 0 | 0 | 64 | 64 | 30 | 30 |
| s35_h1 | 0 | 0 | 0 | 0 | 64 | 64 | 16 | 16 |
| s35_h2 | 0 | 0 | 0 | 0 | 64 | 64 | 19 | 19 |
| s36_h0 | 0 | 0 | 0 | 0 | 64 | 64 | 25 | 25 |
| s36_h1 | 0 | 0 | 0 | 0 | 64 | 64 | 20 | 20 |
| s36_h2 | 0 | 0 | 0 | 0 | 64 | 64 | 21 | 21 |

## Bias Audit

- decision: `HOLD_RESEARCH`
- reason: Phase3H aggregate validates search mechanics and global cluster uniqueness, but sector neutralization/capacity/survivorship promotion-grade checks remain blockers.
- date alignment: true-limit after_open + T+1 contract inherited from strict rows.
- replay vs discovery: Phase3H repair is search-method evidence; not a commercial alpha promotion.

## Next Ablation

A. original R0/CEM-led baseline
B. R0/CEM-led + cluster quota
C. R0 + AST repair only
D. Phase3A full
