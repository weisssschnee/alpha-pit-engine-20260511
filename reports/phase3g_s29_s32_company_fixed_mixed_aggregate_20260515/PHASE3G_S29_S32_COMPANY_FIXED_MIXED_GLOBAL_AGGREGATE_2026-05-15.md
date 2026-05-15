# Phase3G Global Aggregate Report

- created_at: `2026-05-15T14:27:18.852534+08:00`
- decision: `PASS_CONFIRM_PHASE3G`
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
    "cluster_009",
    "cluster_015",
    "cluster_039",
    "cluster_050",
    "cluster_053",
    "cluster_056",
    "cluster_062",
    "cluster_072",
    "cluster_093",
    "cluster_096",
    "cluster_106",
    "cluster_109",
    "cluster_143",
    "cluster_145"
  ],
  "ast_repair_new_deployable_clusters_vs_phase2_r0": 14,
  "ast_repair_new_cluster_ids_vs_phase2_r0": [
    "cluster_009",
    "cluster_015",
    "cluster_039",
    "cluster_050",
    "cluster_053",
    "cluster_056",
    "cluster_062",
    "cluster_072",
    "cluster_093",
    "cluster_096",
    "cluster_106",
    "cluster_109",
    "cluster_143",
    "cluster_145"
  ],
  "decision": "PASS_CONFIRM_PHASE3G"
}
```

## Global Union Metrics

```json
{
  "completed_phase3_seed_count": 4,
  "audited": 1024,
  "global_unique_return_corr_clusters": 291,
  "global_deployable_clusters": 144,
  "phase2_r0_baseline_deployable_clusters": 4,
  "global_new_clusters_vs_phase2_r0": 141,
  "global_new_cluster_ids_vs_phase2_r0": [
    "cluster_002",
    "cluster_004",
    "cluster_005",
    "cluster_006",
    "cluster_007",
    "cluster_008",
    "cluster_009",
    "cluster_010",
    "cluster_011",
    "cluster_012",
    "cluster_013",
    "cluster_014",
    "cluster_015",
    "cluster_016",
    "cluster_017",
    "cluster_018",
    "cluster_019",
    "cluster_020",
    "cluster_021",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_026",
    "cluster_027",
    "cluster_028",
    "cluster_029",
    "cluster_030",
    "cluster_031",
    "cluster_032",
    "cluster_033",
    "cluster_034",
    "cluster_035",
    "cluster_036",
    "cluster_037",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_041",
    "cluster_042",
    "cluster_043",
    "cluster_045",
    "cluster_046",
    "cluster_047",
    "cluster_048",
    "cluster_049",
    "cluster_050",
    "cluster_051",
    "cluster_052",
    "cluster_053",
    "cluster_055",
    "cluster_056",
    "cluster_057",
    "cluster_058",
    "cluster_059",
    "cluster_061",
    "cluster_062",
    "cluster_063",
    "cluster_064",
    "cluster_066",
    "cluster_067",
    "cluster_068",
    "cluster_070",
    "cluster_071",
    "cluster_072",
    "cluster_075",
    "cluster_076",
    "cluster_077",
    "cluster_078",
    "cluster_079",
    "cluster_080",
    "cluster_081",
    "cluster_083",
    "cluster_085",
    "cluster_086",
    "cluster_088",
    "cluster_089",
    "cluster_091",
    "cluster_092",
    "cluster_093",
    "cluster_095",
    "cluster_096",
    "cluster_098",
    "cluster_100",
    "cluster_106",
    "cluster_108",
    "cluster_109",
    "cluster_114",
    "cluster_115",
    "cluster_123",
    "cluster_125",
    "cluster_126",
    "cluster_130",
    "cluster_133",
    "cluster_137",
    "cluster_142",
    "cluster_143",
    "cluster_144",
    "cluster_145",
    "cluster_146",
    "cluster_147",
    "cluster_148",
    "cluster_152",
    "cluster_154",
    "cluster_155",
    "cluster_156",
    "cluster_158",
    "cluster_159",
    "cluster_160",
    "cluster_162",
    "cluster_163",
    "cluster_164",
    "cluster_165",
    "cluster_166",
    "cluster_169",
    "cluster_171",
    "cluster_172",
    "cluster_178",
    "cluster_179",
    "cluster_181",
    "cluster_183",
    "cluster_184",
    "cluster_185",
    "cluster_187",
    "cluster_191",
    "cluster_197",
    "cluster_199",
    "cluster_204",
    "cluster_205",
    "cluster_207",
    "cluster_209",
    "cluster_213",
    "cluster_217",
    "cluster_226",
    "cluster_228",
    "cluster_230",
    "cluster_234",
    "cluster_235",
    "cluster_240",
    "cluster_242",
    "cluster_259"
  ],
  "phase3b_union_baseline_deployable_clusters": 0,
  "new_deployable_clusters_vs_phase3B_union": null,
  "new_deployable_cluster_ids_vs_phase3B_union": [],
  "phase3_cumulative_baseline_deployable_clusters": 122,
  "phase3_cumulative_baseline_declared_clusters": 134,
  "new_deployable_clusters_vs_phase3_cumulative": 110,
  "new_deployable_cluster_ids_vs_phase3_cumulative": [
    "cluster_002",
    "cluster_004",
    "cluster_005",
    "cluster_006",
    "cluster_008",
    "cluster_009",
    "cluster_010",
    "cluster_011",
    "cluster_012",
    "cluster_014",
    "cluster_016",
    "cluster_019",
    "cluster_020",
    "cluster_021",
    "cluster_022",
    "cluster_023",
    "cluster_024",
    "cluster_025",
    "cluster_026",
    "cluster_027",
    "cluster_028",
    "cluster_030",
    "cluster_033",
    "cluster_034",
    "cluster_035",
    "cluster_036",
    "cluster_037",
    "cluster_038",
    "cluster_039",
    "cluster_040",
    "cluster_042",
    "cluster_043",
    "cluster_045",
    "cluster_047",
    "cluster_049",
    "cluster_051",
    "cluster_052",
    "cluster_055",
    "cluster_056",
    "cluster_058",
    "cluster_059",
    "cluster_061",
    "cluster_063",
    "cluster_064",
    "cluster_066",
    "cluster_067",
    "cluster_070",
    "cluster_071",
    "cluster_075",
    "cluster_077",
    "cluster_078",
    "cluster_079",
    "cluster_080",
    "cluster_081",
    "cluster_083",
    "cluster_085",
    "cluster_086",
    "cluster_088",
    "cluster_091",
    "cluster_092",
    "cluster_093",
    "cluster_095",
    "cluster_098",
    "cluster_100",
    "cluster_108",
    "cluster_109",
    "cluster_114",
    "cluster_115",
    "cluster_125",
    "cluster_126",
    "cluster_130",
    "cluster_133",
    "cluster_142",
    "cluster_143",
    "cluster_145",
    "cluster_146",
    "cluster_148",
    "cluster_152",
    "cluster_154",
    "cluster_155",
    "cluster_156",
    "cluster_158",
    "cluster_159",
    "cluster_160",
    "cluster_162",
    "cluster_163",
    "cluster_165",
    "cluster_169",
    "cluster_171",
    "cluster_172",
    "cluster_181",
    "cluster_184",
    "cluster_185",
    "cluster_187",
    "cluster_191",
    "cluster_199",
    "cluster_204",
    "cluster_205",
    "cluster_207",
    "cluster_209",
    "cluster_213",
    "cluster_217",
    "cluster_226",
    "cluster_228",
    "cluster_230",
    "cluster_234",
    "cluster_235",
    "cluster_240",
    "cluster_242",
    "cluster_259"
  ],
  "raw_non_gap_pass": 978,
  "global_top_cluster_id": "cluster_001",
  "global_top_cluster_share": 0.162577,
  "cluster_label_scope": "global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline",
  "seed_local_labels_ignored": true
}
```

## Per Seed Metrics

| run_id | seed | ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3G_G0_E0_stable::g0 | g0 | Phase3G_G0_E0_stable | 256 | 247 | 89 | 54 | cluster_001 | 0.182186 |
| Phase3G_G1_E3_current_proxy::g1 | g1 | Phase3G_G1_E3_current_proxy | 256 | 256 | 66 | 51 | cluster_001 | 0.363281 |
| Phase3G_G2_E3_signal_vector_diversified::g2 | g2 | Phase3G_G2_E3_signal_vector_diversified | 256 | 242 | 144 | 67 | cluster_001 | 0.049587 |
| Phase3G_G3_E3_strong_signal_vector_proxy::g3 | g3 | Phase3G_G3_E3_strong_signal_vector_proxy | 256 | 233 | 136 | 54 | cluster_009 | 0.038627 |

## Per Arm Metrics

| ablation_arm | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters | top_cluster_id | top_cluster_share | median_turnover | median_complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phase3G_G0_E0_stable | 256 | 247 | 89 | 54 | cluster_001 | 0.182186 | 0.178381 | 11.0 |
| Phase3G_G1_E3_current_proxy | 256 | 256 | 66 | 51 | cluster_001 | 0.363281 | 0.126914 | 12.0 |
| Phase3G_G2_E3_signal_vector_diversified | 256 | 242 | 144 | 67 | cluster_001 | 0.049587 | 0.21137 | 16.0 |
| Phase3G_G3_E3_strong_signal_vector_proxy | 256 | 233 | 136 | 54 | cluster_009 | 0.038627 | 0.222916 | 16.0 |

## Seed Overlap Matrix

| left_seed | right_seed | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3G_G0_E0_stable::g0 | Phase3G_G0_E0_stable::g0 | 54 | 54 | 1.0 | 89 | 89 |
| Phase3G_G0_E0_stable::g0 | Phase3G_G1_E3_current_proxy::g1 | 19 | 86 | 0.22093 | 26 | 129 |
| Phase3G_G0_E0_stable::g0 | Phase3G_G2_E3_signal_vector_diversified::g2 | 24 | 97 | 0.247423 | 43 | 190 |
| Phase3G_G0_E0_stable::g0 | Phase3G_G3_E3_strong_signal_vector_proxy::g3 | 27 | 81 | 0.333333 | 43 | 182 |
| Phase3G_G1_E3_current_proxy::g1 | Phase3G_G0_E0_stable::g0 | 19 | 86 | 0.22093 | 26 | 129 |
| Phase3G_G1_E3_current_proxy::g1 | Phase3G_G1_E3_current_proxy::g1 | 51 | 51 | 1.0 | 66 | 66 |
| Phase3G_G1_E3_current_proxy::g1 | Phase3G_G2_E3_signal_vector_diversified::g2 | 21 | 97 | 0.216495 | 36 | 174 |
| Phase3G_G1_E3_current_proxy::g1 | Phase3G_G3_E3_strong_signal_vector_proxy::g3 | 20 | 85 | 0.235294 | 28 | 174 |
| Phase3G_G2_E3_signal_vector_diversified::g2 | Phase3G_G0_E0_stable::g0 | 24 | 97 | 0.247423 | 43 | 190 |
| Phase3G_G2_E3_signal_vector_diversified::g2 | Phase3G_G1_E3_current_proxy::g1 | 21 | 97 | 0.216495 | 36 | 174 |
| Phase3G_G2_E3_signal_vector_diversified::g2 | Phase3G_G2_E3_signal_vector_diversified::g2 | 67 | 67 | 1.0 | 144 | 144 |
| Phase3G_G2_E3_signal_vector_diversified::g2 | Phase3G_G3_E3_strong_signal_vector_proxy::g3 | 23 | 98 | 0.234694 | 51 | 229 |
| Phase3G_G3_E3_strong_signal_vector_proxy::g3 | Phase3G_G0_E0_stable::g0 | 27 | 81 | 0.333333 | 43 | 182 |
| Phase3G_G3_E3_strong_signal_vector_proxy::g3 | Phase3G_G1_E3_current_proxy::g1 | 20 | 85 | 0.235294 | 28 | 174 |
| Phase3G_G3_E3_strong_signal_vector_proxy::g3 | Phase3G_G2_E3_signal_vector_diversified::g2 | 23 | 98 | 0.234694 | 51 | 229 |
| Phase3G_G3_E3_strong_signal_vector_proxy::g3 | Phase3G_G3_E3_strong_signal_vector_proxy::g3 | 54 | 54 | 1.0 | 136 | 136 |

## Arm Overlap Matrix

| left_arm | right_arm | deployable_overlap | deployable_union | deployable_jaccard | non_gap_cluster_overlap | non_gap_cluster_union |
| --- | --- | --- | --- | --- | --- | --- |
| Phase3G_G0_E0_stable | Phase3G_G0_E0_stable | 54 | 54 | 1.0 | 89 | 89 |
| Phase3G_G0_E0_stable | Phase3G_G1_E3_current_proxy | 19 | 86 | 0.22093 | 26 | 129 |
| Phase3G_G0_E0_stable | Phase3G_G2_E3_signal_vector_diversified | 24 | 97 | 0.247423 | 43 | 190 |
| Phase3G_G0_E0_stable | Phase3G_G3_E3_strong_signal_vector_proxy | 27 | 81 | 0.333333 | 43 | 182 |
| Phase3G_G1_E3_current_proxy | Phase3G_G0_E0_stable | 19 | 86 | 0.22093 | 26 | 129 |
| Phase3G_G1_E3_current_proxy | Phase3G_G1_E3_current_proxy | 51 | 51 | 1.0 | 66 | 66 |
| Phase3G_G1_E3_current_proxy | Phase3G_G2_E3_signal_vector_diversified | 21 | 97 | 0.216495 | 36 | 174 |
| Phase3G_G1_E3_current_proxy | Phase3G_G3_E3_strong_signal_vector_proxy | 20 | 85 | 0.235294 | 28 | 174 |
| Phase3G_G2_E3_signal_vector_diversified | Phase3G_G0_E0_stable | 24 | 97 | 0.247423 | 43 | 190 |
| Phase3G_G2_E3_signal_vector_diversified | Phase3G_G1_E3_current_proxy | 21 | 97 | 0.216495 | 36 | 174 |
| Phase3G_G2_E3_signal_vector_diversified | Phase3G_G2_E3_signal_vector_diversified | 67 | 67 | 1.0 | 144 | 144 |
| Phase3G_G2_E3_signal_vector_diversified | Phase3G_G3_E3_strong_signal_vector_proxy | 23 | 98 | 0.234694 | 51 | 229 |
| Phase3G_G3_E3_strong_signal_vector_proxy | Phase3G_G0_E0_stable | 27 | 81 | 0.333333 | 43 | 182 |
| Phase3G_G3_E3_strong_signal_vector_proxy | Phase3G_G1_E3_current_proxy | 20 | 85 | 0.235294 | 28 | 174 |
| Phase3G_G3_E3_strong_signal_vector_proxy | Phase3G_G2_E3_signal_vector_diversified | 23 | 98 | 0.234694 | 51 | 229 |
| Phase3G_G3_E3_strong_signal_vector_proxy | Phase3G_G3_E3_strong_signal_vector_proxy | 54 | 54 | 1.0 | 136 | 136 |

## Lane Attribution

| lane | audited | raw_non_gap_pass | unique_return_corr_clusters | deployable_clusters |
| --- | --- | --- | --- | --- |
| agnostic_freeform_ast | 230 | 223 | 148 | 79 |
| ast_failure_aware_repair | 146 | 146 | 34 | 15 |
| formula_gen_v2_repair_expansion | 132 | 132 | 26 | 16 |
| r0_cem_led | 496 | 457 | 113 | 56 |
| replay_aware_residual | 20 | 20 | 14 | 7 |

## Denominator Audit

| seed | generated | valid | candidate_pool | selected_for_audit | audited | replay_attempted | replay_pass | non_gap_replay_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| g0 | 816 | 816 | 585 | 64 | 256 | 256 | 255 | 247 |
| g1 | 816 | 816 | 579 | 64 | 256 | 256 | 256 | 256 |
| g2 | 816 | 816 | 578 | 64 | 256 | 256 | 242 | 242 |
| g3 | 816 | 816 | 584 | 64 | 256 | 256 | 233 | 233 |
| g0 | 816 | 816 | 578 | 64 | 256 | 256 | 255 | 247 |
| g1 | 816 | 816 | 580 | 64 | 256 | 256 | 256 | 256 |
| g2 | 816 | 816 | 581 | 64 | 256 | 256 | 242 | 242 |
| g3 | 816 | 816 | 587 | 64 | 256 | 256 | 233 | 233 |
| g0 | 816 | 816 | 583 | 64 | 256 | 256 | 255 | 247 |
| g1 | 816 | 816 | 580 | 64 | 256 | 256 | 256 | 256 |
| g2 | 816 | 816 | 575 | 64 | 256 | 256 | 242 | 242 |
| g3 | 816 | 816 | 583 | 64 | 256 | 256 | 233 | 233 |
| g0 | 816 | 816 | 580 | 64 | 256 | 256 | 255 | 247 |
| g1 | 816 | 816 | 587 | 64 | 256 | 256 | 256 | 256 |
| g2 | 816 | 816 | 588 | 64 | 256 | 256 | 242 | 242 |
| g3 | 816 | 816 | 585 | 64 | 256 | 256 | 233 | 233 |

## Bias Audit

- decision: `HOLD_RESEARCH`
- reason: Phase3G aggregate validates search mechanics and global cluster uniqueness, but sector neutralization/capacity/survivorship promotion-grade checks remain blockers.
- date alignment: true-limit after_open + T+1 contract inherited from strict rows.
- replay vs discovery: Phase3G repair is search-method evidence; not a commercial alpha promotion.

## Next Ablation

A. original R0/CEM-led baseline
B. R0/CEM-led + cluster quota
C. R0 + AST repair only
D. Phase3A full
