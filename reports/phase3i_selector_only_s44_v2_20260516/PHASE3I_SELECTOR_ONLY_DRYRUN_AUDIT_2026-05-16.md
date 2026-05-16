# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.0681 | 0.120607 | 0.416291 | 2185264637.670897 | 59039243100.44362 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.053544 | 0.091129 | 0.494763 | 2635455773.272198 | 93061752986.522 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.75 |

## Fail Reasons

- none
