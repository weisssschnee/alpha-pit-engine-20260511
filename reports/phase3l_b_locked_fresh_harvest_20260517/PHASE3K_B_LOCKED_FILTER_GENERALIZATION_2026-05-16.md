# Phase3K-B Locked Filter Generalization - 2026-05-16

Decision: `PASS_KB_J2_AND_J4_RELAXED_GENERALIZATION`

This aggregate applies locked J2/J4_relaxed rules to fresh G2 output. It does not tune thresholds and does not filter by old cluster IDs.

## Book Metrics

| book | clusters | retention | p90 turnover | max raw share | cap proxy median | equal score | equal IR | liq IR | source top |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| J0_fresh | 50 | 1.0 | 0.400547 | 0.0625 | 25480245.859375 | 1.988238 | 1.988238 | 2.194615 | 0.44 |
| J2_fresh | 35 | 0.7 | 0.204045 | 0.088889 | 25480245.859375 | 2.042773 | 2.042773 | 2.231355 | 0.485714 |
| J4_relaxed_fresh | 34 | 0.68 | 0.204322 | 0.090909 | 25480245.859375 | 2.092282 | 2.092282 | 2.258299 | 0.5 |

## Removed Cluster Diagnostics

- removed clusters: `1`
- removed bad-quality count: `1`
- removed bad-quality rate: `1.0`

## Scope

- Book-readiness validation only.
- No production deployment, live capacity, or fill model is confirmed.
- Full `new_vs_149_retained` requires a complete 149 representative registry; this artifact records the gap rather than fabricating the metric.
