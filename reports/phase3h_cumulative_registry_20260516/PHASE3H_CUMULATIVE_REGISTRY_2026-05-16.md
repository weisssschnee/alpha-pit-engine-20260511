# Phase3H Cumulative Registry

- decision: `PASS_DISCOVERY_BASELINE_UPDATE_WITH_DUAL_BASELINE`
- discovery_baseline_declared_clusters: `149`
- representative_rows: `144`
- previous_selector_vector_baseline: `122`
- new_phase3H_vector_matchable_clusters: `15`
- selector_vector_baseline_estimate: `137`
- missing_representatives_carried_forward: `5`

## Policy

Use discovery_baseline=149 for cumulative discovery accounting. Use the prior selector-vector baseline plus the 15 Phase3H vector-matchable additions until the next official selector-vector canonicalization run.

## New Representatives

| declared_cluster_id | source_global_signal_cluster_id | source_arm | source_lane | turnover |
| --- | --- | --- | --- | ---: |
| cluster_135 | cluster_004 | Phase3H_H0_G0_stable | agnostic_freeform_ast | 0.342091 |
| cluster_136 | cluster_015 | Phase3H_H0_G0_stable | formula_gen_v2_repair_expansion | 0.356734 |
| cluster_137 | cluster_018 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.232384 |
| cluster_138 | cluster_019 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.625144 |
| cluster_139 | cluster_020 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.391989 |
| cluster_140 | cluster_021 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.127749 |
| cluster_141 | cluster_025 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.111955 |
| cluster_142 | cluster_026 | Phase3H_H0_G0_stable | agnostic_freeform_ast | 0.10336 |
| cluster_143 | cluster_028 | Phase3H_H0_G0_stable | replay_aware_residual | 0.154218 |
| cluster_144 | cluster_034 | Phase3H_H0_G0_stable | agnostic_freeform_ast | 0.376419 |
| cluster_145 | cluster_038 | Phase3H_H0_G0_stable | replay_aware_residual | 0.412346 |
| cluster_146 | cluster_039 | Phase3H_H0_G0_stable | ast_failure_aware_repair | 0.162536 |
| cluster_147 | cluster_045 | Phase3H_H0_G0_stable | r0_cem_led | 0.081663 |
| cluster_148 | cluster_046 | Phase3H_H0_G0_stable | r0_cem_led | 0.61568 |
| cluster_149 | cluster_049 | Phase3H_H1_G2_signal_vector_control | agnostic_freeform_ast | 0.255658 |

## Outputs

- `src\our_system_phase2\runtime\baselines\phase3H_cumulative_deployable_clusters_20260515.json`
- `phase3h_cumulative_registry_summary.json`
- `phase3h_new_cluster_representatives.csv`
