# Phase3E-Official-S21-S24 Global Aggregate Report

- created_at: `2026-05-14T16:31:37.249497+08:00`
- decision: `PASS_CONFIRM_PHASE3E-OFFICIAL-S21-S24`
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
    "cluster_002",
    "cluster_006",
    "cluster_012",
    "cluster_014",
    "cluster_056",
    "cluster_063"
  ],
  "ast_repair_new_deployable_clusters_vs_phase2_r0": 6,
  "ast_repair_new_cluster_ids_vs_phase2_r0": [
    "cluster_002",
    "cluster_006",
    "cluster_012",
    "cluster_014",
    "cluster_056",
    "cluster_063"
  ],
  "decision": "PASS_CONFIRM_PHASE3E-OFFICIAL-S21-S24"
}
```

## Global Union Metrics

```json
{
  "completed_phase3_seed_count": 4,
  "audited": 1024,
  "global_unique_return_corr_clusters": 93,
  "global_deployable_clusters": 65,
  "phase2_r0_baseline_deployable_clusters": 5,
  "global_new_clusters_vs_phase2_r0": 60,
  "global_new_cluster_ids_vs_phase2_r0": [
    "cluster_002",
    "cluster_004",
    "cluster_006",
    "cluster_009",
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
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_027",
    "cluster_028",
    "cluster_030",
    "cluster_031",
    "cluster_034",
    "cluster_035",
    "cluster_036",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_043",
    "cluster_044",
    "cluster_045",
    "cluster_046",
    "cluster_047",
    "cluster_048",
    "cluster_050",
    "cluster_051",
    "cluster_053",
    "cluster_055",
    "cluster_056",
    "cluster_057",
    "cluster_059",
    "cluster_060",
    "cluster_062",
    "cluster_063",
    "cluster_064",
    "cluster_065",
    "cluster_066",
    "cluster_067",
    "cluster_070",
    "cluster_073",
    "cluster_074",
    "cluster_075",
    "cluster_076",
    "cluster_078",
    "cluster_079",
    "cluster_082",
    "cluster_084",
    "cluster_088",
    "cluster_089",
    "cluster_090"
  ],
  "phase3b_union_baseline_deployable_clusters": 41,
  "new_deployable_clusters_vs_phase3B_union": 43,
  "new_deployable_cluster_ids_vs_phase3B_union": [
    "cluster_004",
    "cluster_010",
    "cluster_011",
    "cluster_013",
    "cluster_015",
    "cluster_016",
    "cluster_018",
    "cluster_019",
    "cluster_020",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_028",
    "cluster_030",
    "cluster_031",
    "cluster_034",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_043",
    "cluster_044",
    "cluster_045",
    "cluster_046",
    "cluster_048",
    "cluster_050",
    "cluster_051",
    "cluster_053",
    "cluster_054",
    "cluster_055",
    "cluster_057",
    "cluster_060",
    "cluster_062",
    "cluster_064",
    "cluster_065",
    "cluster_066",
    "cluster_067",
    "cluster_073",
    "cluster_074",
    "cluster_076",
    "cluster_078",
    "cluster_084",
    "cluster_089"
  ],
  "phase3_cumulative_baseline_deployable_clusters": 98,
  "phase3_cumulative_baseline_declared_clusters": 103,
  "new_deployable_clusters_vs_phase3_cumulative": 31,
  "new_deployable_cluster_ids_vs_phase3_cumulative": [
    "cluster_004",
    "cluster_011",
    "cluster_013",
    "cluster_016",
    "cluster_018",
    "cluster_020",
    "cluster_023",
    "cluster_030",
    "cluster_031",
    "cluster_034",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_043",
    "cluster_044",
    "cluster_048",
    "cluster_050",
    "cluster_051",
    "cluster_053",
    "cluster_054",
    "cluster_055",
    "cluster_057",
    "cluster_060",
    "cluster_062",
    "cluster_064",
    "cluster_065",
    "cluster_066",
    "cluster_067",
    "cluster_074",
    "cluster_078",
    "cluster_089"
  ],
  "raw_non_gap_pass": 615,
  "global_top_cluster_id": "cluster_001",
  "global_top_cluster_share": 0.478049,
  "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
  "seed_local_labels_ignored": true
}
```

## Per Seed Metrics

| run_id | seed | ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | Phase3E_E0_D3_primary | Phase3E_E0_D3_primary | 256 | 119 | 33 | 25 | cluster_001 | 0.361345 |
| Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E1_D3_plus_D2_sidecar | 256 | 166 | 38 | 26 | cluster_001 | 0.493976 |
| Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | Phase3E_E2_D3_deployability_hardened | Phase3E_E2_D3_deployability_hardened | 256 | 170 | 36 | 25 | cluster_001 | 0.476471 |
| Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | Phase3E_E3_D3_book_marginal | Phase3E_E3_D3_book_marginal | 256 | 160 | 43 | 30 | cluster_001 | 0.55 |

## Per Arm Metrics

| ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share | median_turnover | median_complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3E_E0_D3_primary | 256 | 119 | 33 | 25 | cluster_001 | 0.361345 | 0.093033 | 15.0 |
| Phase3E_E1_D3_plus_D2_sidecar | 256 | 166 | 38 | 26 | cluster_001 | 0.493976 | 0.061582 | 15.0 |
| Phase3E_E2_D3_deployability_hardened | 256 | 170 | 36 | 25 | cluster_001 | 0.476471 | 0.081835 | 12.0 |
| Phase3E_E3_D3_book_marginal | 256 | 160 | 43 | 30 | cluster_001 | 0.55 | 0.037872 | 13.0 |

## Seed Overlap Matrix

| left_seed | right_seed | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | 25 | 25 | 1.0 | 33 | 33 |
| Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | 11 | 40 | 0.275 | 16 | 55 |
| Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | 11 | 39 | 0.282051 | 14 | 55 |
| Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | 14 | 41 | 0.341463 | 17 | 59 |
| Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | 11 | 40 | 0.275 | 16 | 55 |
| Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | 26 | 26 | 1.0 | 38 | 38 |
| Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | 10 | 41 | 0.243902 | 14 | 60 |
| Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | 10 | 46 | 0.217391 | 16 | 65 |
| Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | 11 | 39 | 0.282051 | 14 | 55 |
| Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | 10 | 41 | 0.243902 | 14 | 60 |
| Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | 25 | 25 | 1.0 | 36 | 36 |
| Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | 10 | 45 | 0.222222 | 13 | 66 |
| Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | Phase3E_E0_D3_primary::Phase3E_E0_D3_primary | 14 | 41 | 0.341463 | 17 | 59 |
| Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | Phase3E_E1_D3_plus_D2_sidecar::Phase3E_E1_D3_plus_D2_sidecar | 10 | 46 | 0.217391 | 16 | 65 |
| Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | Phase3E_E2_D3_deployability_hardened::Phase3E_E2_D3_deployability_hardened | 10 | 45 | 0.222222 | 13 | 66 |
| Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | Phase3E_E3_D3_book_marginal::Phase3E_E3_D3_book_marginal | 30 | 30 | 1.0 | 43 | 43 |

## Arm Overlap Matrix

| left_arm | right_arm | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3E_E0_D3_primary | Phase3E_E0_D3_primary | 25 | 25 | 1.0 | 33 | 33 |
| Phase3E_E0_D3_primary | Phase3E_E1_D3_plus_D2_sidecar | 11 | 40 | 0.275 | 16 | 55 |
| Phase3E_E0_D3_primary | Phase3E_E2_D3_deployability_hardened | 11 | 39 | 0.282051 | 14 | 55 |
| Phase3E_E0_D3_primary | Phase3E_E3_D3_book_marginal | 14 | 41 | 0.341463 | 17 | 59 |
| Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E0_D3_primary | 11 | 40 | 0.275 | 16 | 55 |
| Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E1_D3_plus_D2_sidecar | 26 | 26 | 1.0 | 38 | 38 |
| Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E2_D3_deployability_hardened | 10 | 41 | 0.243902 | 14 | 60 |
| Phase3E_E1_D3_plus_D2_sidecar | Phase3E_E3_D3_book_marginal | 10 | 46 | 0.217391 | 16 | 65 |
| Phase3E_E2_D3_deployability_hardened | Phase3E_E0_D3_primary | 11 | 39 | 0.282051 | 14 | 55 |
| Phase3E_E2_D3_deployability_hardened | Phase3E_E1_D3_plus_D2_sidecar | 10 | 41 | 0.243902 | 14 | 60 |
| Phase3E_E2_D3_deployability_hardened | Phase3E_E2_D3_deployability_hardened | 25 | 25 | 1.0 | 36 | 36 |
| Phase3E_E2_D3_deployability_hardened | Phase3E_E3_D3_book_marginal | 10 | 45 | 0.222222 | 13 | 66 |
| Phase3E_E3_D3_book_marginal | Phase3E_E0_D3_primary | 14 | 41 | 0.341463 | 17 | 59 |
| Phase3E_E3_D3_book_marginal | Phase3E_E1_D3_plus_D2_sidecar | 10 | 46 | 0.217391 | 16 | 65 |
| Phase3E_E3_D3_book_marginal | Phase3E_E2_D3_deployability_hardened | 10 | 45 | 0.222222 | 13 | 66 |
| Phase3E_E3_D3_book_marginal | Phase3E_E3_D3_book_marginal | 30 | 30 | 1.0 | 43 | 43 |

## Lane Attribution

| lane | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters |
| --- | --- | --- | --- | --- |
| agnostic_freeform_ast | 197 | 150 | 45 | 35 |
| ast_failure_aware_repair | 162 | 160 | 8 | 7 |
| formula_gen_v2_repair_expansion | 145 | 115 | 14 | 9 |
| r0_cem_led | 504 | 182 | 38 | 24 |
| replay_aware_residual | 16 | 8 | 3 | 2 |

## Denominator Audit

| seed | generated | valid | candidate_pool | selected_for_audit | audited | replay_attempted | replay_pass | non_gap_replay_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3E_E0_D3_primary | 788 | 788 | 572 | 64 | 256 | 256 | 119 | 119 |
| Phase3E_E1_D3_plus_D2_sidecar | 788 | 788 | 575 | 64 | 256 | 256 | 166 | 166 |
| Phase3E_E2_D3_deployability_hardened | 788 | 788 | 577 | 64 | 256 | 256 | 170 | 170 |
| Phase3E_E3_D3_book_marginal | 788 | 788 | 578 | 64 | 256 | 256 | 160 | 160 |
| Phase3E_E0_D3_primary | 788 | 788 | 570 | 64 | 256 | 256 | 119 | 119 |
| Phase3E_E1_D3_plus_D2_sidecar | 788 | 788 | 583 | 64 | 256 | 256 | 166 | 166 |
| Phase3E_E2_D3_deployability_hardened | 788 | 788 | 574 | 64 | 256 | 256 | 170 | 170 |
| Phase3E_E3_D3_book_marginal | 788 | 788 | 577 | 64 | 256 | 256 | 160 | 160 |
| Phase3E_E0_D3_primary | 788 | 788 | 570 | 64 | 256 | 256 | 119 | 119 |
| Phase3E_E1_D3_plus_D2_sidecar | 788 | 788 | 569 | 64 | 256 | 256 | 166 | 166 |
| Phase3E_E2_D3_deployability_hardened | 788 | 788 | 572 | 64 | 256 | 256 | 170 | 170 |
| Phase3E_E3_D3_book_marginal | 788 | 788 | 577 | 64 | 256 | 256 | 160 | 160 |
| Phase3E_E0_D3_primary | 788 | 788 | 578 | 64 | 256 | 256 | 119 | 119 |
| Phase3E_E1_D3_plus_D2_sidecar | 788 | 788 | 577 | 64 | 256 | 256 | 166 | 166 |
| Phase3E_E2_D3_deployability_hardened | 788 | 788 | 575 | 64 | 256 | 256 | 170 | 170 |
| Phase3E_E3_D3_book_marginal | 788 | 788 | 579 | 64 | 256 | 256 | 160 | 160 |

## Bias Audit

- decision: `HOLD_RESEARCH`
- reason: Phase3E-Official-S21-S24 aggregate validates search mechanics and global cluster uniqueness, but sector neutralization/capacity/survivorship promotion-grade checks remain blockers.
- date alignment: true-limit after_open + T+1 contract inherited from strict rows.
- replay vs discovery: Phase3E-Official-S21-S24 repair is search-method evidence; not a commercial alpha promotion.

## Next Ablation

A. original R0/CEM-led baseline
B. R0/CEM-led + cluster quota
C. R0 + AST repair only
D. Phase3A full
