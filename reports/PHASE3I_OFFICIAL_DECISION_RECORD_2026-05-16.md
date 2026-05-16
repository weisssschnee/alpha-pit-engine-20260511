# Phase3I Official Decision Record - 2026-05-16

Decision: `KEEP_I0_G2_DISCOVERY_PRIMARY`

## Scope

This decision uses the Phase3I official replay matrix:

- `I0`: G2 discovery primary control
- `I1_v2`: G2 turnover tail guard
- Seeds: 43, 44, 45, 46
- Audited: 64 per arm per seed
- Total: 512 audited rows

The aggregate reclustered all rows globally across seeds and arms using the Phase3G signal-vector proxy. It does not use seed-local cluster labels.

## Result

| arm | audited | raw non-gap | deployable clusters | top raw cluster share | median replay turnover | p90 replay turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| I0 | 256 | 75 | 34 | 0.160000 | 0.312992 | 0.682100 |
| I1_v2 | 256 | 73 | 29 | 0.205479 | 0.254162 | 0.592018 |

I1_v2 achieved the intended turnover reduction:

- Median replay turnover improved by `-0.058830`.
- P90 replay turnover improved by `-0.090082`.
- Median strict turnover improved by `-0.050517`.
- P90 strict turnover improved by `-0.085156`.

But it failed the promotion gates:

- Deployable unique clusters fell by `5`.
- Top raw cluster share rose from `16.00%` to `20.55%`.
- The top-cluster gate target was `<= 15%`.

## Decision

`I1_v2` is not promoted to G2 deployment-hardened candidate.

Current status:

- `I0 / G2` remains the discovery primary.
- `I1_v2` is retained as a diagnostic tail-turnover variant.
- Deployment hardening returns to offline research.

## Notes

- `new_vs_149` is not asserted in this record because the full 149 representative registry is not present in this artifact set.
- Exact proof-suite global reclustering was attempted separately but was too slow for this execution window; the accepted aggregate uses signal-vector global clustering, which matches the G2 selector representation and is still cross-seed/global rather than seed-local.
