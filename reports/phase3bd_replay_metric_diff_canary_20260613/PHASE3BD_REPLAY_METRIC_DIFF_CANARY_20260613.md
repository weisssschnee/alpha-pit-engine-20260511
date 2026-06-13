# Phase3BD Replay Metric-Diff Canary

- decision: `HOLD_REPLAY_METRIC_DIFF_CANARY`
- panel: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3at_company_slice24_dailyjoin2_20260610_pull\phase3ar_wide_sidecar\phase3ar_true_1min_sidecar_canary.parquet`
- candidates: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3bb_company_ba_parent_deepening_aggregate_20260613\phase3au_true1min_shard_fresh_top.csv`
- rows: `1306461`
- codes: `24`
- date groups: `58563`
- trade_time groups: `58563`
- date equals trade_time: `True`
- candidates: `16`
- horizons: `1,5,15,30`
- max metric abs diff: `0.00033895113454474046`
- max abs diff by metric: `{'ic_mean': 3.494869850998589e-05, 'ic_abs_mean': 3.8629149698099496e-05, 'spread_mean': 3.2595703779211133e-06, 'spread_abs_mean': 2.6568936529348247e-06, 'spread_hit_rate': 0.00033895113454474046}`
- metric tolerance: `0.0001`
- ranking pass: `True`
- pandas eval seconds: `18.867718199999672`
- numba-hybrid eval seconds: `3.6971495999996478`
- eval speedup: `5.103314780662775`

## Meaning

This is not alpha proof and not a new search. It compares replay metrics from the existing pandas signal evaluator against the Phase3BC numba-hybrid signal evaluator on the same true-1min sidecar panel and the same Phase3BA/BB candidate expressions.

Phase3BC strict element parity remains the stricter gate. Phase3BD only answers whether the observed signal-level differences materially change Phase3AS-style IC/spread metrics.

## Ranking Diff

| horizon | top1_same | overlap | required | pass |
| ---: | --- | ---: | ---: | --- |
| 1 | `True` | 5 | 5 | `True` |
| 5 | `True` | 5 | 5 | `True` |
| 15 | `True` | 5 | 5 | `True` |
| 30 | `True` | 5 | 5 | `True` |

## Largest Metric Diffs

| candidate_id | horizon | abs_diff_ic_abs | abs_diff_ic_mean | abs_diff_spread_abs | abs_diff_spread_mean | abs_diff_spread_hit_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `phase3ba_focused_minute_expansion_00272` | 15 | 1.0840287709895646e-05 | 1.7475002431745212e-05 | 1.2562931426410642e-06 | 3.2595703779211133e-06 | 0.00033895113454474046 |
| `phase3ba_focused_minute_expansion_00269` | 15 | 1.5198125664389606e-05 | 5.426774031702664e-06 | 1.6148685585398032e-06 | 2.3460468906731825e-06 | 0.00020713680444406357 |
| `phase3ba_focused_minute_expansion_00281` | 30 | 3.0562965165070732e-06 | 1.7782522396814215e-05 | 1.0121247334534886e-06 | 2.5957272788905514e-06 | 0.00018835938971550892 |
| `phase3ba_focused_minute_expansion_00443` | 1 | 1.4648941976364016e-05 | 1.1139075777620577e-05 | 2.536664626252936e-07 | 4.090511330073818e-07 | 0.00018815383457515544 |
| `phase3ba_focused_minute_expansion_00272` | 30 | 6.9897007685670864e-06 | 3.1360939698882317e-06 | 1.5689320615507388e-06 | 1.9113699917952336e-06 | 0.00016952345074394692 |
| `phase3ba_focused_minute_expansion_00272` | 5 | 5.9915108768238134e-06 | 1.1952123691788552e-05 | 3.810936434912177e-09 | 1.2171778081721899e-06 | 0.00016944365998305955 |
| `phase3ba_focused_minute_expansion_00443` | 5 | 1.908188662247401e-06 | 3.494869850998589e-05 | 9.240797088031633e-09 | 1.03874240436355e-06 | 0.00016934801016088574 |
| `phase3ba_focused_minute_expansion_00667` | 15 | 2.6822976118251463e-05 | 4.804410414845084e-06 | 1.6779897317135278e-06 | 1.4976058796421277e-06 | 0.0001570875959706619 |
| `phase3ba_focused_minute_expansion_00437` | 5 | 5.412184246822438e-06 | 3.5939303663704014e-06 | 6.263881354487931e-07 | 6.815504863913704e-07 | 0.00015061658665160849 |
| `phase3ba_focused_minute_expansion_00446` | 15 | 1.1394777599260664e-05 | 1.652978008717665e-05 | 1.0891374489672631e-06 | 1.5887941769400981e-06 | 0.0001318143301006769 |
| `phase3ba_focused_minute_expansion_00281` | 5 | 1.3636678519252099e-05 | 2.1596986327129808e-05 | 4.40404345102962e-07 | 8.045975874082289e-07 | 0.00013178951332015743 |
| `phase3ba_focused_minute_expansion_00663` | 15 | 2.5397290259215888e-05 | 2.205707853128458e-06 | 1.669140951879658e-06 | 1.5300450319242012e-06 | 0.00011781569697810745 |
| `phase3ba_focused_minute_expansion_00275` | 5 | 2.5080611612771087e-05 | 2.904948695488241e-06 | 1.0646295547402096e-08 | 5.467659857557924e-07 | 0.00011296243998870636 |
| `phase3ba_focused_minute_expansion_00275` | 1 | 2.010160713764031e-05 | 1.0309802178313371e-05 | 7.34517310763301e-08 | 1.6522451630793387e-07 | 0.00011295606009265047 |
| `phase3ba_focused_minute_expansion_00281` | 1 | 2.454501800697173e-06 | 1.2989167762558762e-06 | 1.7138077131571838e-07 | 2.3788155331116198e-08 | 0.00011295606009265047 |
| `phase3ba_focused_minute_expansion_00449` | 1 | 6.4355644893987485e-06 | 1.3355241403313622e-05 | 1.567754741283421e-07 | 1.0775640819143845e-07 | 0.00011289230074507106 |
| `phase3ba_focused_minute_expansion_00667` | 30 | 3.958263357251024e-06 | 1.2748383353952675e-05 | 1.8623583614412603e-07 | 8.941500377819848e-07 | 9.820867379006781e-05 |
| `phase3ba_focused_minute_expansion_00287` | 15 | 6.029978791288748e-08 | 1.2594108433419682e-05 | 9.741508732018928e-07 | 4.1719827495405163e-07 | 9.415309292915008e-05 |
| `phase3ba_focused_minute_expansion_00446` | 5 | 9.130421169456504e-06 | 4.286263922216593e-06 | 1.994516761662929e-07 | 2.1909348533989074e-07 | 9.41353666572553e-05 |
| `phase3ba_focused_minute_expansion_00683` | 30 | 1.2877584004922227e-05 | 9.043222396379336e-06 | 9.789367539109889e-07 | 6.015476137268558e-08 | 7.856693903207645e-05 |

## Launch Contract

- Do not make numba the default proof evaluator.
- If this canary passes, a future change may add an explicit `--evaluator-backend numba_hybrid` flag for diagnostic replay only.
- X0/R3 and prior search decisions are unchanged.
