# Phase3G Seed29 Official Gate

- created_at: 2026-05-15T08:11:13+08:00
- experiment_id: 20260515_phase3g_seed29_official_gate
- status: PASS
- reason: at least one of G2/G3 satisfies seed29 official gate
- run_root: `reports\phase3g_seed29_company_s29_20260515\s29`
- clustered_rows_path: `reports\phase3g_seed29_company_aggregate_20260515\s29_aggregate\phase3g_seed29_company_global_clustered_rows.json`

## Arm Metrics

| arm | deployable | top_share | c001 | c003 | turnover | new_vs_134 |
|---|---:|---:|---:|---:|---:|---:|
| Phase3G_G0_E0_stable | 19 | 0.180328 | 0.18032786885245902 | 0.01639344262295082 | 0.134632 | 21 |
| Phase3G_G1_E3_current_proxy | 20 | 0.34375 | 0.34375 | 0.0625 | 0.133268 | 15 |
| Phase3G_G2_E3_signal_vector_diversified | 22 | 0.15625 | 0.15625 | 0.03125 | 0.14452 | 16 |
| Phase3G_G3_E3_strong_signal_vector_proxy | 24 | 0.125 | 0.109375 | 0.015625 | 0.177579 | 21 |

## Target Arm Decisions

- Phase3G_G2_E3_signal_vector_diversified: {'passes_seed29_gate': True, 'pass_blockers': [], 'triggers_fail_condition': False, 'fail_reasons': []}
- Phase3G_G3_E3_strong_signal_vector_proxy: {'passes_seed29_gate': True, 'pass_blockers': [], 'triggers_fail_condition': False, 'fail_reasons': []}

## Queue Overlap

{
  "G1_vs_G2": {
    "left_count": 64,
    "right_count": 64,
    "intersection_count": 5,
    "overlap_ratio_min_denom": 0.078125
  },
  "G1_vs_G3": {
    "left_count": 64,
    "right_count": 64,
    "intersection_count": 6,
    "overlap_ratio_min_denom": 0.09375
  },
  "G2_vs_G3": {
    "left_count": 64,
    "right_count": 64,
    "intersection_count": 11,
    "overlap_ratio_min_denom": 0.171875
  }
}
