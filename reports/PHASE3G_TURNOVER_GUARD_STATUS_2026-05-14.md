# Phase3G Turnover Guard Status

## Decision

`PASS_TURNOVER_GUARD_SMOKE`.

The prior signal-vector selector fixed concentration but selected high-turnover formulas. The turnover-guard version keeps the anti-collapse benefit and materially reduces replay turnover.

## Key Results

| arm | deployable / audited | top cluster share | median turnover |
| --- | ---: | ---: | ---: |
| G0 E0 stable | 6 / 16 | 42.86% | 0.040182 |
| G1 E3 current proxy | 4 / 16 | 62.50% | 0.040182 |
| G2 signal-vector diversified + turnover guard | 9 / 16 | 6.67% | 0.148179 |
| G3 strong signal-vector proxy + turnover guard | 9 / 16 | 6.67% | 0.148179 |

Global aggregate:

- audited: `64`
- global deployable clusters: `9`
- new deployable clusters vs cumulative baseline: `6`
- global top cluster share: `30.00%`
- aggregate decision: `PASS_CONFIRM_PHASE3G`

## Interpretation

Compared with the first Phase3G smoke:

- G2/G3 concentration control remains effective: top cluster share stays near `6%`.
- G2/G3 deployable count declines from `11/10` to `9/9`, which is acceptable for the turnover reduction.
- Median turnover improves from roughly `0.33-0.37` to `0.148179`.
- G2/G3 still outperform G1 current proxy on deployable clusters.

The selector is still not a true book-marginal selector. It is a `signal_vector_diversified_proxy` with structure-level turnover guard.

## Implementation Change

Added `turnover_structure_risk`, a pre-replay expression-only heuristic. It penalizes:

- `Mom(...,1)` / `Mom(...,2)`
- `Delta(...,1)`
- second-difference structures
- short-window volatility transforms
- short-window correlation triggers
- short-horizon market-cap / amount / volume deltas

This avoids using replay turnover labels during selection.

## Next

Run official Phase3G:

```text
G0/G1/G2/G3 x seeds29-32 x 64 audited
```

Primary readout:

- G2/G3 deployable clusters vs G1/E0
- top cluster share
- cluster_001 / cluster_003 share
- median turnover
- new deployable clusters vs cumulative `134`
