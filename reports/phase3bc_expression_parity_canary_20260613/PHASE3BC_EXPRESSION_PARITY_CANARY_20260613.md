# Phase3BC Expression Parity Canary

- decision: `HOLD_EXPRESSION_PARITY_FAILED`
- panel: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3at_company_slice24_dailyjoin2_20260610_pull\phase3ar_wide_sidecar\phase3ar_true_1min_sidecar_canary.parquet`
- candidates: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_fresh_top.csv`
- rows: `400000`
- codes: `24`
- date groups: `58563`
- trade_time groups: `58563`
- date equals trade_time: `True`
- pass: `0/16`

## Meaning

This is not a search result and not alpha proof. It is a backend safety check: fixed Phase3BA/BB expressions are evaluated by the existing pandas evaluator and a numba-backed evaluator on the same true-1min sidecar panel.

The existing evaluator groups `CSRank`, `ZScore`, and `CSResidual` by `frame['date']`. In this true-1min panel, `date` is equal to `trade_time`, so the cross-section is minute-level rather than old daily kline.

## Failure Reading

Strict expression parity failed. Nonfinite mismatches are zero, so this is not a missing-field, NaN, or old-1D-data problem. The observed pattern is finite-value rank divergence in nested `CSRank` expressions, likely from tiny floating-point differences in rolling/zscore subexpressions changing pandas exact-tie rank behavior. Phase3AS numba backend wiring remains blocked.

## Rows

| rank | candidate_id | horizon | pandas_s | numba_s | speedup | max_diff | nonfinite_mismatch | pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `phase3ba_focused_minute_expansion_00269` | 30 | 1.101997 | 2.011358 | 0.548 | 5.000e-01 | 0 | `False` |
| 2 | `phase3ba_focused_minute_expansion_00437` | 30 | 0.533681 | 0.153829 | 3.469 | 5.000e-01 | 0 | `False` |
| 3 | `phase3ba_focused_minute_expansion_00440` | 30 | 0.352337 | 0.108423 | 3.250 | 5.000e-01 | 0 | `False` |
| 4 | `phase3ba_focused_minute_expansion_00272` | 30 | 0.111195 | 0.043178 | 2.575 | 5.000e-01 | 0 | `False` |
| 5 | `phase3ba_focused_minute_expansion_00443` | 30 | 0.417817 | 0.253180 | 1.650 | 6.667e-01 | 0 | `False` |
| 6 | `phase3ba_focused_minute_expansion_00663` | 30 | 0.519398 | 0.122271 | 4.248 | 5.000e-01 | 0 | `False` |
| 7 | `phase3ba_focused_minute_expansion_00275` | 30 | 0.127810 | 0.069021 | 1.852 | 6.667e-01 | 0 | `False` |
| 8 | `phase3ba_focused_minute_expansion_00667` | 30 | 0.366131 | 0.103640 | 3.533 | 5.000e-01 | 0 | `False` |
| 9 | `phase3ba_focused_minute_expansion_00683` | 30 | 0.115135 | 0.049334 | 2.334 | 5.000e-01 | 0 | `False` |
| 10 | `phase3ba_focused_minute_expansion_00278` | 30 | 0.360512 | 0.432736 | 0.833 | 6.667e-01 | 0 | `False` |
| 11 | `phase3ba_focused_minute_expansion_00687` | 30 | 0.095549 | 0.041170 | 2.321 | 5.000e-01 | 0 | `False` |
| 12 | `phase3ba_focused_minute_expansion_00446` | 30 | 0.094603 | 0.043000 | 2.200 | 5.000e-01 | 0 | `False` |
| 13 | `phase3ba_focused_minute_expansion_00281` | 30 | 0.317165 | 0.104257 | 3.042 | 5.000e-01 | 0 | `False` |
| 14 | `phase3ba_focused_minute_expansion_00449` | 30 | 0.093316 | 0.042657 | 2.188 | 5.000e-01 | 0 | `False` |
| 15 | `phase3ba_focused_minute_expansion_00287` | 30 | 0.314179 | 0.119215 | 2.635 | 7.143e-01 | 0 | `False` |
| 16 | `phase3ba_focused_minute_expansion_00455` | 30 | 0.099685 | 0.043492 | 2.292 | 5.833e-01 | 0 | `False` |

## Next Contract

- If this canary passes, Phase3AS can receive an explicit `--evaluator-backend numba` flag.
- The default evaluator must remain pandas until a small replay metric-diff audit passes.
- X0/R3 and prior search decisions are unchanged.
