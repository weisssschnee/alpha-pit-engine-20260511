# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.059135 | 0.110825 | 0.429 | 1960780948.543134 | 57605108303.12904 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.056112 | 0.090913 | 0.518595 | 1417424836.096977 | 59005356207.83682 |
| I3V2 | 64 | signal_vector_queue_diversity_v2 | 0.059228 | 0.110825 | 0.334803 | 1336222257.773896 | 42246439686.68956 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.765625 |
| I0_vs_I3V2 | 0.78125 |

## Fail Reasons

- none
