# Phase3H Selector-Only Dry Run Audit

- created_at: `2026-05-15T19:02:10+08:00`
- decision: `PASS_SELECTOR_ONLY_DRYRUN`
- run_root: `runtime\phase3h_shared_selector_dryrun_s33_20260515`

## Arm Metrics

| arm | selected | selector | median_turnover | median_turnover_structure | mean_signal_corr | agnostic | repair_expansion | metadata |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| H0 | 64 | standard_D3 | 0.056112 | 0.0 | 0.0 | 12 | 8 | DUAL_BASELINE_ACCEPTED |
| H1 | 64 | signal_vector_diversified_proxy | 0.057411 | 0.0 | 0.448196 | 16 | 8 | DUAL_BASELINE_ACCEPTED |
| H2 | 64 | signal_vector_turnover_calibrated_proxy | 0.056112 | 0.0 | 0.471939 | 14 | 8 | DUAL_BASELINE_ACCEPTED |
| H3 | 64 | signal_vector_diversified_proxy | 0.057411 | 0.0 | 0.448196 | 16 | 8 | DUAL_BASELINE_ACCEPTED |

## Queue Overlap

| pair | overlap | left | right |
| --- | ---: | ---: | ---: |
| H1_vs_H2 | 0.921875 | 64 | 64 |
| H1_vs_H3 | 1.0 | 64 | 64 |
| H0_vs_H1 | 0.396825 | 63 | 64 |

## Fail Reasons

- none

## Decision

Run Phase3H smoke only if decision is PASS_SELECTOR_ONLY_DRYRUN.
