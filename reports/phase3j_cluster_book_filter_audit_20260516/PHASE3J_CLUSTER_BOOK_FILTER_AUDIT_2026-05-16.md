# Phase3J Cluster Book Filter Audit - 2026-05-16

Decision: `PASS_CLUSTER_LEVEL_FILTER_DIRECTION`

This is a no-run cluster-level audit. It does not generate candidates and does not run replay.

## Book Metrics

| book | clusters | retention | median turnover | p90 turnover | max raw share | source top share | median cost proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| J0 | 34 | 1.0 | 0.203328 | 0.382188 | 0.210526 | 0.441176 | 2.130552 |
| J1 | 24 | 0.705882 | 0.174296 | 0.274037 | 0.27907 | 0.5 | 1.767554 |
| J2 | 23 | 0.676471 | 0.17779 | 0.276502 | 0.129032 | 0.521739 | 1.2677 |
| J3 | 16 | 0.470588 | 0.126317 | 0.254302 | 0.181818 | 0.4375 | 2.750344 |

## Interpretation

- J1 retention vs J0: `0.705882`.
- J1 p90 cluster turnover improves from `0.382188` to `0.274037`.
- J2 p90 cluster turnover is `0.276502` with source top share `0.521739`.
- J3 is diagnostic only because liquidity/capacity proxy coverage is not available in the Phase3I strict-row artifact.

## Bias / Promotion Scope

- Cost and turnover are present.
- Capacity/liquidity is missing, so no book is production-promotion grade.
- `new_vs_149` is not asserted until a full 149 registry mapping is available.
- Result supports post-discovery cluster filtering, not live deployment.
