# Phase3I Official Global Aggregate - 2026-05-16

Decision: `KEEP_I0_G2_DISCOVERY_PRIMARY`

This aggregate reclusters all strict rows across seeds 43-46 and arms I0/I1_v2 before computing metrics.

## Arm Metrics

| arm | audited | raw non-gap | deployable clusters | top raw cluster share | median replay turnover | p90 replay turnover | median strict turnover | p90 strict turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| i0 | 256 | 75 | 34 | 0.16 | 0.312992 | 0.6821 | 0.300686 | 0.67796 |
| i1v2 | 256 | 73 | 29 | 0.205479 | 0.254162 | 0.592018 | 0.250169 | 0.592804 |

## Gate Result

- Deployable delta I1_v2 - I0: `-5`
- Strict turnover delta median / p90: `-0.050517` / `-0.085156`
- Replay turnover delta median / p90: `-0.05883` / `-0.090082`
- Gates: deployable `False`, top cluster `False`, strict turnover `True`, replay turnover `True`

## Scope

- This is a deployment-hardening selector test, not a true book-residual selector.
- `new_vs_149` is intentionally not asserted until a full 149 representative registry is available.
