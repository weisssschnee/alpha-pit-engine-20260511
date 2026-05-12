# Phase3A Global Aggregate Report

- created_at: `2026-05-11T20:37:34.188034+08:00`
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
    "cluster_008",
    "cluster_010",
    "cluster_013",
    "cluster_014",
    "cluster_017",
    "cluster_019"
  ],
  "ast_repair_new_deployable_clusters_vs_phase2_r0": 8,
  "ast_repair_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_005",
    "cluster_008",
    "cluster_010",
    "cluster_013",
    "cluster_014",
    "cluster_017",
    "cluster_019"
  ],
  "decision": "PASS_CONFIRM_PHASE3A"
}
```

## Global Union Metrics

```json
{
  "completed_phase3_seed_count": 4,
  "audited": 256,
  "global_unique_return_corr_clusters": 28,
  "global_deployable_clusters": 23,
  "phase2_r0_baseline_deployable_clusters": 5,
  "global_new_clusters_vs_phase2_r0": 19,
  "global_new_cluster_ids_vs_phase2_r0": [
    "cluster_001",
    "cluster_003",
    "cluster_005",
    "cluster_007",
    "cluster_008",
    "cluster_010",
    "cluster_011",
    "cluster_012",
    "cluster_013",
    "cluster_014",
    "cluster_016",
    "cluster_017",
    "cluster_018",
    "cluster_019",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_026",
    "cluster_028"
  ],
  "raw_non_gap_pass": 101,
  "global_top_cluster_id": "cluster_006",
  "global_top_cluster_share": 0.415842,
  "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
  "seed_local_labels_ignored": true
}
```

## Per Seed Metrics

| seed | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share |
| --- | --- | --- | --- | --- | --- | --- |
| seed1 | 64 | 26 | 12 | 7 | cluster_006 | 0.384615 |
| seed2 | 64 | 25 | 11 | 8 | cluster_006 | 0.44 |
| seed3 | 64 | 23 | 13 | 11 | cluster_006 | 0.434783 |
| seed4 | 64 | 27 | 15 | 13 | cluster_006 | 0.407407 |

## Seed Overlap Matrix

| left_seed | right_seed | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| seed1 | seed1 | 7 | 7 | 1.0 | 12 | 12 |
| seed1 | seed2 | 3 | 12 | 0.25 | 6 | 17 |
| seed1 | seed3 | 3 | 15 | 0.2 | 7 | 18 |
| seed1 | seed4 | 6 | 14 | 0.428571 | 9 | 18 |
| seed2 | seed1 | 3 | 12 | 0.25 | 6 | 17 |
| seed2 | seed2 | 8 | 8 | 1.0 | 11 | 11 |
| seed2 | seed3 | 4 | 15 | 0.266667 | 5 | 19 |
| seed2 | seed4 | 3 | 18 | 0.166667 | 5 | 21 |
| seed3 | seed1 | 3 | 15 | 0.2 | 7 | 18 |
| seed3 | seed2 | 4 | 15 | 0.266667 | 5 | 19 |
| seed3 | seed3 | 11 | 11 | 1.0 | 13 | 13 |
| seed3 | seed4 | 5 | 19 | 0.263158 | 6 | 22 |
| seed4 | seed1 | 6 | 14 | 0.428571 | 9 | 18 |
| seed4 | seed2 | 3 | 18 | 0.166667 | 5 | 21 |
| seed4 | seed3 | 5 | 19 | 0.263158 | 6 | 22 |
| seed4 | seed4 | 13 | 13 | 1.0 | 15 | 15 |

## Lane Attribution

| lane | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters |
| --- | --- | --- | --- | --- |
| ast_failure_aware_repair | 52 | 43 | 10 | 9 |
| novelty_diagnostic | 28 | 0 | 0 | 0 |
| r0_cem_led | 152 | 46 | 20 | 16 |
| replay_aware_residual | 24 | 12 | 3 | 2 |

## Denominator Audit

| seed | generated | valid | candidate_pool | selected_for_audit | audited | replay_attempted | replay_pass | non_gap_replay_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seed1 | 704 | 704 | 519 | 64 | 64 | 64 | 26 | 26 |
| seed2 | 704 | 704 | 513 | 64 | 64 | 64 | 25 | 25 |
| seed3 | 704 | 704 | 515 | 64 | 64 | 64 | 23 | 23 |
| seed4 | 704 | 704 | 515 | 64 | 64 | 64 | 27 | 27 |

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
