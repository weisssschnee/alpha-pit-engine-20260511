# Phase3J Decision Record - 2026-05-16

Decision: `PASS_PHASE3J_CLUSTER_LEVEL_FILTER_AUDIT`

## Confirmed

- G2 discovery primary should not be pre-filtered by a candidate-level turnover tail guard.
- Cluster-level filtering can reduce turnover while retaining most deployable clusters.
- `J2_balanced` is the current book-readiness candidate.

## Not Confirmed

- Capacity.
- Liquidity.
- True execution feasibility.
- Production deployment.
- `J3` as a capacity book.

## Primary Candidate

`J2_balanced`

- Clusters: `23`
- Retention vs G2/J0: `67.65%`
- p90 cluster replay turnover: `0.2765`
- max raw share: `12.90%`

## Required Next Gate

Phase3J-2 must add liquidity/capacity coverage and cluster-level book replay proxy before any deployment claim.

Required checks:

- `amount` / `volume` coverage.
- `susp` / `is_limit_up` / `is_limit_down` coverage.
- `float_share` or market-cap coverage.
- cluster-level liquidity/capacity metrics.
- J4 liquidity-aware balanced book.
- J0/J1/J2/J3/J4 book replay proxy comparison.

## Bias Scope

This is post-discovery filtering. It does not change candidate generation and does not prove live deployability. Capacity and execution remain `HOLD_RESEARCH` until liquidity/capacity metrics and limit/suspension feasibility are validated.
