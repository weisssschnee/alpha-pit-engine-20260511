# Phase3I Selector-Only Dry Run Audit

- decision: `PASS_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.069322 | 0.12558 | 0.410715 | 2166644197.84933 | 55843522633.89121 |
| I1V2 | 64 | signal_vector_turnover_tail_guard_v2 | 0.064076 | 0.097957 | 0.477587 | 1739321367.834423 | 62315766030.842804 |
| I3V2 | 64 | signal_vector_queue_diversity_v2 | 0.074576 | 0.129724 | 0.359162 | 1655755660.289804 | 34881583998.79935 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1V2 | 0.703125 |
| I0_vs_I3V2 | 0.859375 |

## Fail Reasons

- none
