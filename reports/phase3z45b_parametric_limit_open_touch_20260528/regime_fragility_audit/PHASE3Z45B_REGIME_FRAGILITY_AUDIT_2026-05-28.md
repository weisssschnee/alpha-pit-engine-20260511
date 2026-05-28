# Phase3Z45b Regime Fragility Audit

Decision: `HOLD_RESEARCH_REGIME_FRAGILITY_AUDIT_COMPLETE`.

This audit tests whether the best-looking OOS regime slices are stable enough to interpret.

| cluster | best slice | oos days | oos ann | train ann | top3 positive share | remove top1 ann | random p95 | beats random p95 | fragility |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| cluster_001 | limit_density_bucket:limit_density_low | 8 | 1.339791 | 0.615996 | 0.792622 | -0.113414 | 3.053138 | False | True small_oos_slice|top3_positive_concentrated|does_not_beat_random_p95 |
| cluster_002 | breadth_bucket:breadth_low | 10 | 4.454866 | 0.061513 | 0.730298 | 1.825995 | 4.257932 | True | True small_oos_slice|top3_positive_concentrated |
| cluster_007 | limit_density_bucket:limit_density_low | 8 | 3.262919 | 0.027518 | 0.756113 | 0.853988 | 6.933446 | False | True small_oos_slice|top3_positive_concentrated|does_not_beat_random_p95 |
| cluster_017 | limit_density_bucket:limit_density_low | 9 | 2.43732 | 0.491143 | 0.749341 | 0.545363 | 3.661829 | False | True small_oos_slice|top3_positive_concentrated|does_not_beat_random_p95 |
| cluster_030 | breadth_bucket:breadth_mid | 16 | 1.062222 | 0.724264 | 0.476476 | 0.669523 | 1.626839 | False | True does_not_beat_random_p95 |

## Interpretation

- Best slices were selected from OOS diagnostics, so this is not a promotion protocol.
- A slice is marked fragile if it is too small, top-day concentrated, train/OOS sign inconsistent, or fails same-active-count random p95.
- Passing this audit would still not promote a candidate; it would only justify a locked forward diagnostic.
