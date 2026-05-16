# Phase3J J4 Filter Sensitivity - 2026-05-16

Decision: `PASS_RELAXED_J4_CANDIDATE`

This is a no-run sensitivity audit over cluster-level filters. It does not run search or replay.

## Baselines

| book | clusters | retention | p90 turnover | capacity median | max raw share | score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| J0 | 34 | 1.0 | 0.382188 | 23524393.039062 | 0.210526 | 1.758429 |
| J2 | 23 | 0.676471 | 0.276502 | 23895134.562695 | 0.129032 | 1.75884 |
| J4_original | 15 | 0.441176 | 0.213655 | 46935603.134766 | 0.173913 | 1.92226 |

## Best Relaxed J4

- name: `J4_relaxed_a0.05_c0.05_and_l0.2`
- pass: `True`
- clusters: `22`
- p90 turnover: `0.278967`
- capacity proxy median: `24333428.564258`
- max raw share: `0.133333`
- equal cost-adjusted score: `1.840207`
- filter: amount_q `0.05`, capacity_q `0.05`, mode `and`, limit_max `0.2`, susp_max `0.01`

## Interpretation

- If the best variant passes, use it as the next J4 candidate for a proper book replay/check.
- If it does not pass, keep J2 as book-readiness candidate and treat liquidity/capacity filtering as offline research.
