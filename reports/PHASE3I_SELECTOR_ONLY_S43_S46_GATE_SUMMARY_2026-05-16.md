# Phase3I Selector-Only S43-S46 Gate Summary

- decision: `PASS_SELECTOR_ONLY_GATE_FOR_OFFICIAL`
- seeds: `43,44,45,46`
- official replay arms allowed: `I0`, `I1_v2`
- blocked official arms: `I2`, `I3_v2`

## Results

| seed | I0 median turnover | I1_v2 median turnover | I0 p90 turnover | I1_v2 p90 turnover | I0 mean signal corr | I1_v2 mean signal corr | overlap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 43 | 0.056867 | 0.052381 | 0.102982 | 0.090568 | 0.422184 | 0.508318 | 0.734375 |
| 44 | 0.068100 | 0.053544 | 0.120607 | 0.091129 | 0.416291 | 0.494763 | 0.750000 |
| 45 | 0.057578 | 0.054404 | 0.125155 | 0.094150 | 0.427867 | 0.487025 | 0.765625 |
| 46 | 0.056712 | 0.055836 | 0.104613 | 0.086704 | 0.433891 | 0.494043 | 0.781250 |

## Interpretation

- `I1_v2` reduced p90 turnover on all four seeds.
- `I1_v2` reduced median turnover on all four seeds.
- `I1_v2` changes the queue materially: overlap with `I0` is `0.734375-0.78125`.
- `I1_v2` raises mean selected-queue signal corr versus `I0`; this is an accepted tradeoff for official replay because Phase3I is testing turnover hardening, not pure diversity.

## Gate

Proceed to official replay:

```text
I0 / I1_v2 x seeds43-46 x 64 audited
```

Execution must use:

```text
shared_candidate_pool -> frozen selection -> strict/replay/cluster
```

Do not use seed-local cluster labels in the global aggregate.
