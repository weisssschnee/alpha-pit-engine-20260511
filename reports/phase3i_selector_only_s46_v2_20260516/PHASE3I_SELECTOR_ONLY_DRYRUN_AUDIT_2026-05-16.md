# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.056712 | 0.104613 | 0.433891 | 2076135657.909206 | 53124242826.75514 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.055836 | 0.086704 | 0.494043 | 2039982444.626827 | 70076470422.1604 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.78125 |

## Fail Reasons

- none
