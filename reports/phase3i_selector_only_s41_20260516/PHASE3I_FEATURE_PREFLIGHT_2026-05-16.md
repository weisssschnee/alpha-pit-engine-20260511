# Phase3I Feature Preflight

- decision: `PASS_PHASE3I_FEATURE_PREFLIGHT`
- candidate_count: `324`
- I1_minimum_pass: `True`
- I2_status: `promotion_eligible`
- I3_minimum_pass: `True`

## Coverage

| feature | coverage |
| --- | ---: |
| cluster_turnover | 0.950617 |
| p90_turnover | 0.950617 |
| source_lane_turnover | 1.0 |
| cost_proxy | 1.0 |
| liquidity_proxy | 0.950617 |
| capacity_proxy | 0.950617 |
| corr_to_149_registry_proxy | 1.0 |
| selected_queue_signal_corr | 1.0 |
| signal_vector_ready | 1.0 |
| operator_pathology_flag | 1.0 |
| complexity_score | 1.0 |

## Interpretation

- I1 can proceed only if turnover and source-lane turnover are available.
- I2 is promotion-eligible only if liquidity or capacity proxy coverage is sufficient; otherwise it remains diagnostic-only.
- I3 remains `book-proxy hardened`, not true book residual.
