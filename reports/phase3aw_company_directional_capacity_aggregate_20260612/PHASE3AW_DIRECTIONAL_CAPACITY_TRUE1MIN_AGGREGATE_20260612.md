# Phase3AW Directional Capacity True 1min Aggregate

created_at: 2026-06-12T05:41:57.469204+00:00

## Decision

PHASE3AW_DIRECTIONAL_CAPACITY_TRUE1MIN_AGGREGATED_RESEARCH_ONLY

## Run Status

- shards: 16/16
- candidates: 96
- candidate-horizon rows: 6144
- total errors: 0
- total memory hits: 0
- data guard: true 1min Phase3AU shard panels only; no old 1D panel used.

## Main Finding

The Phase3AV negative capacity-flow family flips cleanly into positive IC after `Neg(...)`. The effect is strongest at 15-30 minute horizons, but this remains a canary result rather than replay/cost proof.

## Top Candidates By Horizon

### Horizon 1 min
| rank | candidate | fields | avg_ic | min_ic | sign_consistency | all_positive | avg_spread |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | phase3aw_directional_capacity_00024 | amount|final_float_market_cap | 0.018379 | 0.015923 | 1.000 | True | 0.00000344 |
| 2 | phase3aw_directional_capacity_00025 | amount_yuan|final_float_market_cap | 0.018379 | 0.015923 | 1.000 | True | 0.00000344 |
| 3 | phase3aw_directional_capacity_00027 | amount_yuan|final_float_market_cap | 0.018347 | 0.015916 | 1.000 | True | 0.00000261 |
| 4 | phase3aw_directional_capacity_00021 | amount|final_float_market_cap | 0.018282 | 0.015822 | 1.000 | True | 0.00000349 |
| 5 | phase3aw_directional_capacity_00022 | amount_yuan|final_float_market_cap | 0.018282 | 0.015822 | 1.000 | True | 0.00000349 |
| 6 | phase3aw_directional_capacity_00016 | amount|final_float_market_cap | 0.018238 | 0.015018 | 1.000 | True | 0.00000425 |
| 7 | phase3aw_directional_capacity_00017 | amount_yuan|final_float_market_cap | 0.018238 | 0.015018 | 1.000 | True | 0.00000425 |
| 8 | phase3aw_directional_capacity_00032 | amount|final_float_market_cap | 0.018227 | 0.016054 | 1.000 | True | 0.00000288 |
| 9 | phase3aw_directional_capacity_00033 | amount_yuan|final_float_market_cap | 0.018227 | 0.016054 | 1.000 | True | 0.00000288 |
| 10 | phase3aw_directional_capacity_00043 | amount|final_total_market_cap | 0.018156 | 0.015956 | 1.000 | True | 0.00000217 |

### Horizon 5 min
| rank | candidate | fields | avg_ic | min_ic | sign_consistency | all_positive | avg_spread |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | phase3aw_directional_capacity_00039 | amount_yuan|final_float_market_cap | 0.030831 | 0.027930 | 1.000 | True | 0.00003756 |
| 2 | phase3aw_directional_capacity_00027 | amount_yuan|final_float_market_cap | 0.030770 | 0.027611 | 1.000 | True | 0.00003216 |
| 3 | phase3aw_directional_capacity_00045 | amount|final_float_market_cap | 0.030684 | 0.027830 | 1.000 | True | 0.00004210 |
| 4 | phase3aw_directional_capacity_00058 | amount_yuan|final_float_market_cap | 0.030684 | 0.027830 | 1.000 | True | 0.00004210 |
| 5 | phase3aw_directional_capacity_00047 | amount_yuan|final_total_market_cap | 0.030656 | 0.027750 | 1.000 | True | 0.00002700 |
| 6 | phase3aw_directional_capacity_00054 | amount_yuan|final_total_market_cap | 0.030630 | 0.027675 | 1.000 | True | 0.00003103 |
| 7 | phase3aw_directional_capacity_00032 | amount|final_float_market_cap | 0.030542 | 0.027605 | 1.000 | True | 0.00003081 |
| 8 | phase3aw_directional_capacity_00033 | amount_yuan|final_float_market_cap | 0.030542 | 0.027605 | 1.000 | True | 0.00003081 |
| 9 | phase3aw_directional_capacity_00024 | amount|final_float_market_cap | 0.030516 | 0.027798 | 1.000 | True | 0.00003493 |
| 10 | phase3aw_directional_capacity_00025 | amount_yuan|final_float_market_cap | 0.030516 | 0.027798 | 1.000 | True | 0.00003493 |

### Horizon 15 min
| rank | candidate | fields | avg_ic | min_ic | sign_consistency | all_positive | avg_spread |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | phase3aw_directional_capacity_00039 | amount_yuan|final_float_market_cap | 0.042318 | 0.040427 | 1.000 | True | 0.00006803 |
| 2 | phase3aw_directional_capacity_00054 | amount_yuan|final_total_market_cap | 0.042053 | 0.040428 | 1.000 | True | 0.00005875 |
| 3 | phase3aw_directional_capacity_00045 | amount|final_float_market_cap | 0.041838 | 0.039651 | 1.000 | True | 0.00007913 |
| 4 | phase3aw_directional_capacity_00058 | amount_yuan|final_float_market_cap | 0.041838 | 0.039651 | 1.000 | True | 0.00007913 |
| 5 | phase3aw_directional_capacity_00032 | amount|final_float_market_cap | 0.041714 | 0.039735 | 1.000 | True | 0.00006440 |
| 6 | phase3aw_directional_capacity_00033 | amount_yuan|final_float_market_cap | 0.041714 | 0.039735 | 1.000 | True | 0.00006440 |
| 7 | phase3aw_directional_capacity_00056 | amount|final_total_market_cap | 0.041500 | 0.039624 | 1.000 | True | 0.00006761 |
| 8 | phase3aw_directional_capacity_00069 | amount_yuan|final_total_market_cap | 0.041500 | 0.039624 | 1.000 | True | 0.00006761 |
| 9 | phase3aw_directional_capacity_00062 | amount_yuan|final_float_market_cap | 0.041470 | 0.039580 | 1.000 | True | 0.00008201 |
| 10 | phase3aw_directional_capacity_00050 | amount|final_total_market_cap | 0.041417 | 0.039749 | 1.000 | True | 0.00005635 |

### Horizon 30 min
| rank | candidate | fields | avg_ic | min_ic | sign_consistency | all_positive | avg_spread |
|---:|---|---|---:|---:|---:|---|---:|
| 1 | phase3aw_directional_capacity_00039 | amount_yuan|final_float_market_cap | 0.051090 | 0.048323 | 1.000 | True | 0.00012896 |
| 2 | phase3aw_directional_capacity_00054 | amount_yuan|final_total_market_cap | 0.051048 | 0.049088 | 1.000 | True | 0.00012284 |
| 3 | phase3aw_directional_capacity_00045 | amount|final_float_market_cap | 0.050737 | 0.048054 | 1.000 | True | 0.00015296 |
| 4 | phase3aw_directional_capacity_00058 | amount_yuan|final_float_market_cap | 0.050737 | 0.048054 | 1.000 | True | 0.00015296 |
| 5 | phase3aw_directional_capacity_00056 | amount|final_total_market_cap | 0.050629 | 0.048157 | 1.000 | True | 0.00014506 |
| 6 | phase3aw_directional_capacity_00069 | amount_yuan|final_total_market_cap | 0.050629 | 0.048157 | 1.000 | True | 0.00014506 |
| 7 | phase3aw_directional_capacity_00062 | amount_yuan|final_float_market_cap | 0.050266 | 0.047542 | 1.000 | True | 0.00016666 |
| 8 | phase3aw_directional_capacity_00032 | amount|final_float_market_cap | 0.050104 | 0.047532 | 1.000 | True | 0.00011276 |
| 9 | phase3aw_directional_capacity_00033 | amount_yuan|final_float_market_cap | 0.050104 | 0.047532 | 1.000 | True | 0.00011276 |
| 10 | phase3aw_directional_capacity_00050 | amount|final_total_market_cap | 0.050075 | 0.047896 | 1.000 | True | 0.00010941 |

## Limits

- research-only canary, not alpha proof
- direction-corrected IC is not replay/cost proof
- requires turnover, cost, placebo, and new-vs-149 checks
- X0/R3 read-only
