# Phase3K-B Locked Filter Generalization - 2026-05-16

Decision: `HOLD_KB_LOCKED_FILTER_GENERALIZATION`

This aggregate applies locked J2/J4_relaxed rules to fresh G2 output. It does not tune thresholds and does not filter by old cluster IDs.

## Book Metrics

| book | clusters | retention | p90 turnover | max raw share | cap proxy median | equal score | equal IR | liq IR | source top |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| J0_fresh | 48 | 1.0 | 0.397096 | 0.067797 | 26112624.53916 | 2.280562 | 2.280562 | 2.290773 | 0.291667 |
| J2_fresh | 33 | 0.6875 | 0.238545 | 0.073171 | 32417481.550781 | 2.257039 | 2.257039 | 2.285613 | 0.333333 |
| J4_relaxed_fresh | 31 | 0.645833 | 0.227858 | 0.076923 | 32814617.294922 | 2.359585 | 2.359585 | 2.294168 | 0.290323 |

## Removed Cluster Diagnostics

- removed clusters: `2`
- removed bad-quality count: `2`
- removed bad-quality rate: `1.0`

## Scope

- Book-readiness validation only.
- No production deployment, live capacity, or fill model is confirmed.
- Full `new_vs_149_retained` requires a complete 149 representative registry; this artifact records the gap rather than fabricating the metric.
