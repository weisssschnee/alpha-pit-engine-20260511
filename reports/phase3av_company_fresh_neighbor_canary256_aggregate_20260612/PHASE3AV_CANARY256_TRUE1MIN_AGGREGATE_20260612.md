# Phase3AV Canary256 True 1min Aggregate
created_at: 2026-06-12T04:34:13.011659+00:00

## Decision
PHASE3AV_CANARY256_TRUE1MIN_AGGREGATED_RESEARCH_ONLY

## Run Status
- shards: 16/16
- unique candidates: 256
- candidate-horizon rows: 16384
- total errors: 0
- total memory hits: 0
- all shards evaluated 256: True
- data guard: true 1min Phase3AU shard panels only; no old 1D panel used.

## Main Finding
The strongest and most stable family is capacity-normalized minute flow: amount or amount_yuan divided by float_share. This is fresh relative to the Phase3AU memory filter in this canary, but it is still a research signal, not deployable alpha proof.

## Top Candidates By Horizon

### Horizon 1 min
| rank | candidate | factor_lane | fields | avg_abs_ic | avg_ic | sign_consistency | shards | avg_spread |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | phase3av_fresh_neighbor_00125 | av_capacity_normalized_flow | amount|float_share | 0.097275 | -0.017326 | 1.000 | 16 | -0.00000453 |
| 2 | phase3av_fresh_neighbor_00121 | av_capacity_normalized_flow | amount|float_share | 0.097023 | -0.017400 | 1.000 | 16 | -0.00000444 |
| 3 | phase3av_fresh_neighbor_00117 | av_capacity_normalized_flow | amount|float_share | 0.096660 | -0.017400 | 1.000 | 16 | -0.00000219 |
| 4 | phase3av_fresh_neighbor_00113 | av_capacity_normalized_flow | amount|float_share | 0.096101 | -0.017554 | 1.000 | 16 | -0.00000351 |
| 5 | phase3av_fresh_neighbor_00109 | av_capacity_normalized_flow | amount|float_share | 0.095631 | -0.017595 | 1.000 | 16 | -0.00000238 |
| 6 | phase3av_fresh_neighbor_00105 | av_capacity_normalized_flow | amount|float_share | 0.095158 | -0.017663 | 1.000 | 16 | -0.00000146 |
| 7 | phase3av_fresh_neighbor_00255 | av_capacity_normalized_flow | amount_yuan|float_share | 0.095158 | -0.017663 | 1.000 | 16 | -0.00000146 |
| 8 | phase3av_fresh_neighbor_00101 | av_capacity_normalized_flow | amount|float_share | 0.094840 | -0.017536 | 1.000 | 16 | -0.00000005 |
| 9 | phase3av_fresh_neighbor_00251 | av_capacity_normalized_flow | amount_yuan|float_share | 0.094840 | -0.017536 | 1.000 | 16 | -0.00000005 |
| 10 | phase3av_fresh_neighbor_00097 | av_capacity_normalized_flow | amount|float_share | 0.094349 | -0.017088 | 1.000 | 16 | 0.00000360 |

### Horizon 5 min
| rank | candidate | factor_lane | fields | avg_abs_ic | avg_ic | sign_consistency | shards | avg_spread |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | phase3av_fresh_neighbor_00125 | av_capacity_normalized_flow | amount|float_share | 0.132547 | -0.027537 | 1.000 | 16 | -0.00003268 |
| 2 | phase3av_fresh_neighbor_00121 | av_capacity_normalized_flow | amount|float_share | 0.132020 | -0.027670 | 1.000 | 16 | -0.00003076 |
| 3 | phase3av_fresh_neighbor_00117 | av_capacity_normalized_flow | amount|float_share | 0.131359 | -0.028329 | 1.000 | 16 | -0.00003520 |
| 4 | phase3av_fresh_neighbor_00113 | av_capacity_normalized_flow | amount|float_share | 0.130440 | -0.028804 | 1.000 | 16 | -0.00003741 |
| 5 | phase3av_fresh_neighbor_00109 | av_capacity_normalized_flow | amount|float_share | 0.129894 | -0.028811 | 1.000 | 16 | -0.00003383 |
| 6 | phase3av_fresh_neighbor_00105 | av_capacity_normalized_flow | amount|float_share | 0.128961 | -0.029116 | 1.000 | 16 | -0.00003798 |
| 7 | phase3av_fresh_neighbor_00255 | av_capacity_normalized_flow | amount_yuan|float_share | 0.128961 | -0.029116 | 1.000 | 16 | -0.00003798 |
| 8 | phase3av_fresh_neighbor_00101 | av_capacity_normalized_flow | amount|float_share | 0.128680 | -0.029163 | 1.000 | 16 | -0.00003929 |
| 9 | phase3av_fresh_neighbor_00251 | av_capacity_normalized_flow | amount_yuan|float_share | 0.128680 | -0.029163 | 1.000 | 16 | -0.00003929 |
| 10 | phase3av_fresh_neighbor_00097 | av_capacity_normalized_flow | amount|float_share | 0.128240 | -0.028909 | 1.000 | 16 | -0.00003598 |

### Horizon 15 min
| rank | candidate | factor_lane | fields | avg_abs_ic | avg_ic | sign_consistency | shards | avg_spread |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | phase3av_fresh_neighbor_00125 | av_capacity_normalized_flow | amount|float_share | 0.148850 | -0.037601 | 1.000 | 16 | -0.00005011 |
| 2 | phase3av_fresh_neighbor_00121 | av_capacity_normalized_flow | amount|float_share | 0.148324 | -0.037965 | 1.000 | 16 | -0.00004595 |
| 3 | phase3av_fresh_neighbor_00117 | av_capacity_normalized_flow | amount|float_share | 0.147058 | -0.038732 | 1.000 | 16 | -0.00005021 |
| 4 | phase3av_fresh_neighbor_00113 | av_capacity_normalized_flow | amount|float_share | 0.145960 | -0.039640 | 1.000 | 16 | -0.00005830 |
| 5 | phase3av_fresh_neighbor_00109 | av_capacity_normalized_flow | amount|float_share | 0.145242 | -0.040082 | 1.000 | 16 | -0.00005639 |
| 6 | phase3av_fresh_neighbor_00105 | av_capacity_normalized_flow | amount|float_share | 0.144394 | -0.040668 | 1.000 | 16 | -0.00006522 |
| 7 | phase3av_fresh_neighbor_00255 | av_capacity_normalized_flow | amount_yuan|float_share | 0.144394 | -0.040668 | 1.000 | 16 | -0.00006522 |
| 8 | phase3av_fresh_neighbor_00101 | av_capacity_normalized_flow | amount|float_share | 0.143923 | -0.040553 | 1.000 | 16 | -0.00006754 |
| 9 | phase3av_fresh_neighbor_00251 | av_capacity_normalized_flow | amount_yuan|float_share | 0.143923 | -0.040553 | 1.000 | 16 | -0.00006754 |
| 10 | phase3av_fresh_neighbor_00097 | av_capacity_normalized_flow | amount|float_share | 0.142835 | -0.040590 | 1.000 | 16 | -0.00006930 |

### Horizon 30 min
| rank | candidate | factor_lane | fields | avg_abs_ic | avg_ic | sign_consistency | shards | avg_spread |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | phase3av_fresh_neighbor_00125 | av_capacity_normalized_flow | amount|float_share | 0.158024 | -0.043942 | 1.000 | 16 | -0.00006484 |
| 2 | phase3av_fresh_neighbor_00121 | av_capacity_normalized_flow | amount|float_share | 0.157497 | -0.044444 | 1.000 | 16 | -0.00006122 |
| 3 | phase3av_fresh_neighbor_00117 | av_capacity_normalized_flow | amount|float_share | 0.156284 | -0.045199 | 1.000 | 16 | -0.00006463 |
| 4 | phase3av_fresh_neighbor_00113 | av_capacity_normalized_flow | amount|float_share | 0.155201 | -0.046364 | 1.000 | 16 | -0.00008173 |
| 5 | phase3av_fresh_neighbor_00109 | av_capacity_normalized_flow | amount|float_share | 0.154434 | -0.046986 | 1.000 | 16 | -0.00008306 |
| 6 | phase3av_fresh_neighbor_00105 | av_capacity_normalized_flow | amount|float_share | 0.153523 | -0.047908 | 1.000 | 16 | -0.00010087 |
| 7 | phase3av_fresh_neighbor_00255 | av_capacity_normalized_flow | amount_yuan|float_share | 0.153523 | -0.047908 | 1.000 | 16 | -0.00010087 |
| 8 | phase3av_fresh_neighbor_00101 | av_capacity_normalized_flow | amount|float_share | 0.152857 | -0.047839 | 1.000 | 16 | -0.00011022 |
| 9 | phase3av_fresh_neighbor_00251 | av_capacity_normalized_flow | amount_yuan|float_share | 0.152857 | -0.047839 | 1.000 | 16 | -0.00011022 |
| 10 | phase3av_fresh_neighbor_00097 | av_capacity_normalized_flow | amount|float_share | 0.151618 | -0.047921 | 1.000 | 16 | -0.00011949 |

## Field Family Concentration

### Horizon 1 min
| rank | fields | candidates | avg_abs_ic | median_abs_ic |
|---:|---|---:|---:|---:|
| 1 | amount_yuan|float_share | 22 | 0.081415 | 0.084281 |
| 2 | amount|float_share | 50 | 0.079103 | 0.084589 |
| 3 | amount_yuan|final_float_market_cap | 50 | 0.070156 | 0.072415 |
| 4 | amount_yuan|final_total_market_cap | 50 | 0.068981 | 0.070733 |
| 5 | amount|final_float_market_cap | 42 | 0.068228 | 0.068649 |
| 6 | amount|final_total_market_cap | 42 | 0.067133 | 0.066937 |

### Horizon 5 min
| rank | fields | candidates | avg_abs_ic | median_abs_ic |
|---:|---|---:|---:|---:|
| 1 | amount_yuan|float_share | 22 | 0.106486 | 0.112074 |
| 2 | amount|float_share | 50 | 0.102824 | 0.111938 |
| 3 | amount_yuan|final_float_market_cap | 50 | 0.092400 | 0.099103 |
| 4 | amount_yuan|final_total_market_cap | 50 | 0.090277 | 0.096784 |
| 5 | amount|final_float_market_cap | 42 | 0.088988 | 0.094797 |
| 6 | amount|final_total_market_cap | 42 | 0.086998 | 0.092143 |

### Horizon 15 min
| rank | fields | candidates | avg_abs_ic | median_abs_ic |
|---:|---|---:|---:|---:|
| 1 | amount_yuan|float_share | 22 | 0.117740 | 0.124726 |
| 2 | amount|float_share | 50 | 0.113675 | 0.125339 |
| 3 | amount_yuan|final_float_market_cap | 50 | 0.103208 | 0.112592 |
| 4 | amount_yuan|final_total_market_cap | 50 | 0.100708 | 0.109673 |
| 5 | amount|final_float_market_cap | 42 | 0.099131 | 0.107724 |
| 6 | amount|final_total_market_cap | 42 | 0.096772 | 0.104889 |

### Horizon 30 min
| rank | fields | candidates | avg_abs_ic | median_abs_ic |
|---:|---|---:|---:|---:|
| 1 | amount_yuan|float_share | 22 | 0.124102 | 0.132684 |
| 2 | amount|float_share | 50 | 0.119847 | 0.132928 |
| 3 | amount_yuan|final_float_market_cap | 50 | 0.108431 | 0.119279 |
| 4 | amount_yuan|final_total_market_cap | 50 | 0.105826 | 0.116405 |
| 5 | amount|final_float_market_cap | 42 | 0.103927 | 0.113933 |
| 6 | amount|final_total_market_cap | 42 | 0.101482 | 0.110942 |

## Limits
- This is still canary evaluation, not replay/cost proof.
- The signal family is concentrated, so next work must test variants against placebo, cost, turnover, and new-vs-149 clustering.
- X0/R3 remains read-only.
