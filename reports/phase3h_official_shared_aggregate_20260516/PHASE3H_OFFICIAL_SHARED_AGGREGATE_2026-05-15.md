# Phase3H Official Shared Aggregate

- created_at: 2026-05-15T19:01:09+00:00
- run_root: `D:\p3h_official_20260516`
- seeds: [33, 34, 35, 36]
- aggregate_scope: arm_level_shared_official_not_cross_seed_global_recluster
- decision: **HOLD_G2_PROMOTION**

## Arm Metrics

| arm | audited | deployable_sum | raw_non_gap | raw/deployable | top_share_max | cluster001 | cluster003 | replay_turnover | queue_corr | reports |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H0_G0_stable | 256 | 43 | 114 | 2.6512 | 0.5200 | 0.0439 | 0.2304 | 0.351537 | 0.000000 | 4 |
| H1_G2_signal_vector_control | 256 | 45 | 70 | 1.5556 | 0.1250 | 0.0576 | 0.0701 | 0.380784 | 0.397084 | 4 |
| H2_G2_turnover_calibrated | 256 | 43 | 73 | 1.6977 | 0.2105 | 0.0695 | 0.1189 | 0.365893 | 0.407544 | 4 |

## Selector Parity

- H1/H2 overlap mean: 0.91796875
- H1/H3 overlap mean: 1.0
- H2 turnover proxy advantage mean: 0.001849499999999997

## Notes

- This is a shared-pool official execution aggregate.
- H3 is expected to be selector-only parity unless replay reports are present.
- `new_vs_134` requires cross-seed registry/global reclustering and is marked unavailable here when absent.
- Cross-seed promotion-grade global reclustering remains a separate accounting step.
