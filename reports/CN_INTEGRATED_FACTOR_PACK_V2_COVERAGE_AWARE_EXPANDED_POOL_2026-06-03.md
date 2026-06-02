# CN Integrated Factor Pack V2 Coverage-Aware Expanded Pool Canary

Date: 2026-06-03

## Decision

`HOLD_EXPANDED_POOL_NOT_BETTER_THAN_COVERAGE_AWARE_BASE`

The expanded-pool canary increased the selector-visible pool from 360 to 682
rows, exposing all 294 coverage-aware integrated candidates. This produced a
meaningfully different integrated-feature queue, but replay quality weakened.

## Selector Delta

| metric | base coverage-aware | expanded pool |
| --- | ---: | ---: |
| visible integrated candidates | 108 | 294 |
| selected integrated candidates | 19 | 21 |
| selected fundamental candidates | 0 | 2 |
| queue overlap with base | n/a | 15 / 25 union |
| integrated queue jaccard | n/a | 0.6000 |

Expanded-pool-only candidates included quality direct, quality size residual,
quality x RZRQ, and quality x minute-pressure candidates.

## Replay Result

| metric | base coverage-aware | expanded pool |
| --- | ---: | ---: |
| audited | 19 | 21 |
| raw non-gap replay pass | 16 | 14 |
| cost survive | 12 | 12 |
| deployable clusters | 10 | 7 |
| top cluster share | 6.25% | 7.14% |
| median replay sortino | -0.126466 | -0.469631 |
| median turnover | 0.573237 | 0.525000 |

## Lane Attribution

| factor lane | audited | raw pass | cost survive | median replay sortino |
| --- | ---: | ---: | ---: | ---: |
| rzrq_size_normalized | 14 | 12 | 9 | -0.130480 |
| quality_direct_control | 2 | 0 | 2 | -0.626437 |
| quality_x_rzrq_flow | 2 | 1 | 1 | 1.874831 |
| minute_amount_share_daily | 1 | 1 | 0 | -8.939376 |
| quality_size_residual | 1 | 0 | 0 | -1.186533 |
| quality_x_minute_pressure | 1 | 0 | 0 | -3.138533 |

## Interpretation

Coverage-aware gating improved the v2 pack, but simply exposing the full v2
candidate pool is not beneficial. The expanded pool admits sparse or weak
quality/minute variants that dilute the RZRQ-normalized core. The strongest
validated axis remains:

- RZRQ flow normalized by amount or float market cap;
- quality x RZRQ flow as a secondary lane;
- direct quality and minute amount-share direct candidates remain weak.

## Next Gate

Do not promote expanded-pool selection. The next validation should preserve the
coverage-aware base pool discipline and test fresh candidate generation or
fresh dates, not merely widen selector visibility.
