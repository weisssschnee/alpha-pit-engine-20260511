# Phase3I Selector-Only Dry Run Audit

- decision: `HOLD_PHASE3I_SELECTOR_ONLY_DRYRUN`
- i2_status: `promotion_eligible`

## Arm Metrics

| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| I0 | 64 | signal_vector_diversified_proxy | 0.066093 | 0.117566 | 0.440209 | 1913217745.897954 | 51015548379.971985 |
| I1 | 64 | signal_vector_cost_turnover_constrained_proxy | 0.068233 | 0.127073 | 0.487729 | 1655755660.289804 | 30799375798.52569 |
| I2 | 64 | signal_vector_capacity_liquidity_proxy | 0.066728 | 0.120072 | 0.477701 | 2186034128.797088 | 55583275995.87944 |
| I3 | 64 | signal_vector_book_proxy_hardened | 0.06725 | 0.12558 | 0.457424 | 1723591733.287664 | 41705483098.647995 |

## Queue Overlap

| pair | overlap |
| --- | ---: |
| I0_vs_I1 | 0.8125 |
| I0_vs_I3 | 0.859375 |
| I0_vs_I2 | 0.921875 |

## Fail Reasons

- `I1_p90_turnover_not_below_I0`
- `I3_selected_queue_signal_corr_not_below_I0`
