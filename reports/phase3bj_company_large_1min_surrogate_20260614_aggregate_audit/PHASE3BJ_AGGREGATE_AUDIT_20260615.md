# Phase3BJ Aggregate Audit 2026-06-15

## Decision

`PHASE3BJ_AGGREGATE_AUDIT_COMPLETE_DIAGNOSTIC_ONLY`

Phase3BJ finished the broad true-1min surrogate evaluation and this audit aggregates all chunk-level rows by `expression_hash + horizon_min`.

This is not an X0/R3 promotion decision. The next valid step is Phase3BK strict replay / recluster / memory audit on a small selected subset.

## Coverage

- chunk summary files: 1024
- row CSV files: 1024
- raw metric rows: 524288
- unique expression hashes: 8192
- expression-horizon rows: 32768
- duplicate expression hashes: 0
- fresh non-memory expression-horizon rows: 32640
- memory-hit expression-horizon rows: 128

## Top Fresh Directional Candidates

| rank | horizon | factor_lane | fields | robust_score | median_ic | dir_share | spread_mean | expression |
|---:|---:|---|---|---:|---:|---:|---:|---|
| 1 | 1 | pure_fresh_cross | close|volume|vwap | 0.0941374 | -0.0941374 | 1.00 | -0.000310213 | `CSRank(Sub(ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($vwap,15)))),ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($close,15))))))` |
| 2 | 5 | pure_fresh_cross | close|volume|vwap | 0.0724934 | -0.0724934 | 1.00 | -0.000353841 | `CSRank(Sub(ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($vwap,15)))),ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($close,15))))))` |
| 3 | 1 | pure_fresh_cross | close|volume|vwap | 0.0618205 | 0.0618205 | 1.00 | 0.000279954 | `CSRank(Div(ZScore(Sub(ZScore(Delta($volume,10)),ZScore(Delta($close,10)))),Add(Abs(ZScore(Sub(ZScore(Delta($volume,10)),ZScore(Delta($vwap,10))))),0.000001)))` |
| 4 | 30 | pure_fresh_cross | close|m1_first30_vwap|vwap | 0.0563756 | -0.0563756 | 1.00 | -0.000162866 | `CSRank(Sub(ZScore(Div(Std($close,20),Add(Abs(Mean($close,20)),0.000001))),ZScore(Div(Sub($m1_first30_vwap,$vwap),Add(Abs($vwap),0.000001)))))` |
| 5 | 5 | opening_vwap_residual | close|m1_first30_vwap | 0.0556099 | 0.0556099 | 1.00 | 0.000216752 | `CSRank(Div(Sub($m1_first30_vwap,$close),Add(Abs($close),0.000001)))` |
| 6 | 5 | pure_fresh_cross | amount|close|m1_first30_vwap | 0.0532237 | 0.0532237 | 1.00 | 0.00021658 | `CSRank(Div(ZScore(Div(Sub($m1_first30_vwap,$close),Add(Abs($close),0.000001))),Add(Abs(ZScore(Div(Delta($amount,5),Add(Abs(Add(Std($close,5),0.000001)),0.000001)))),0.000001)))` |
| 7 | 5 | pure_fresh_cross | close|volume|vwap | 0.0525064 | 0.0525064 | 1.00 | 0.000322689 | `CSRank(Div(ZScore(Sub(ZScore(Delta($volume,10)),ZScore(Delta($close,10)))),Add(Abs(ZScore(Sub(ZScore(Delta($volume,10)),ZScore(Delta($vwap,10))))),0.000001)))` |
| 8 | 5 | opening_vwap_residual | close|m1_first15_vwap | 0.0525033 | 0.0525033 | 1.00 | 0.000210042 | `CSRank(Div(Sub($m1_first15_vwap,$close),Add(Abs($close),0.000001)))` |
| 9 | 5 | pure_fresh_cross | amount|close|m1_first15_vwap|vwap | 0.0519831 | 0.0519831 | 1.00 | 0.00020961 | `CSRank(Add(ZScore(Div(Sub($m1_first15_vwap,$close),Add(Abs($close),0.000001))),ZScore(Mul(ZScore(Delta($amount,2)),Neg(ZScore(Delta($vwap,2)))))))` |
| 10 | 5 | pure_fresh_cross | amount|close|m1_first15_vwap|vwap | 0.0519126 | 0.0519126 | 1.00 | 0.000219647 | `CSRank(Add(ZScore(Div(Sub($m1_first15_vwap,$close),Add(Abs($close),0.000001))),ZScore(Mul(ZScore(Delta($amount,10)),Neg(ZScore(Delta($vwap,10)))))))` |
| 11 | 15 | pure_fresh_cross | close|volume|vwap | 0.0517002 | -0.0517002 | 1.00 | -0.000340558 | `CSRank(Sub(ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($vwap,15)))),ZScore(Sub(ZScore(Delta($volume,15)),ZScore(Delta($close,15))))))` |
| 12 | 30 | pure_fresh_cross | amount|close|m1_first15_vwap|m1_first5_amount | 0.0515324 | -0.0515324 | 1.00 | -0.000273814 | `CSRank(Sub(ZScore(Div($m1_first5_amount,Add(Abs(Mean($amount,30)),0.000001))),ZScore(Div(Sub($m1_first15_vwap,$close),Add(Abs($close),0.000001)))))` |

## Factor Lane Summary

See `phase3bj_factor_lane_summary.csv`.

## Files

- `phase3bj_aggregate_audit_summary.json`
- `phase3bj_aggregate_by_expression_horizon.csv`
- `phase3bj_top_fresh_directional.csv`
- `phase3bj_top_all_directional.csv`
- `phase3bj_top_memory_hits_directional.csv`
- `phase3bj_duplicate_expression_hashes.csv`
- `phase3bj_factor_lane_summary.csv`
- `phase3bj_field_summary.csv`
- `phase3bj_phase3bk_shortlist_top64.csv`
- `phase3bj_phase3bk_shortlist_top64.json`

## Interpretation Boundary

- Directional consistency matters more than `ic_abs_mean`.
- Memory hits are diagnostic anchors, not fresh alpha.
- Repeated expression hashes are collapsed before top selection.
- Any selected BJ candidate must go through Phase3BK cross-shard strict replay and new-vs-existing signal-vector audit.
