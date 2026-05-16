# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.056867 | 0.102982 | 0.422184 | 1777839710.243464 | 50712848244.672226 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.052381 | 0.090568 | 0.508318 | 1618128666.484868 | 56157533202.04907 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.734375 |

## Fail Reasons

- none
