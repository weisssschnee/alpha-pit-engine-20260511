# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.057578 | 0.125155 | 0.427867 | 1725973266.170837 | 62421384509.57245 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.054404 | 0.09415 | 0.487025 | 1651686120.698951 | 67203745364.44206 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.765625 |

## Fail Reasons

- none
