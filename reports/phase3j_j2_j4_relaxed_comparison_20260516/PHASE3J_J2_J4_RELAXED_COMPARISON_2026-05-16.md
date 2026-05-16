# Phase3J J2 vs J4 Relaxed Comparison - 2026-05-16

Decision: `PASS_J4_RELAXED_STABLE_BOOK_CANDIDATE`

This is a no-run overlap, plateau, and book proxy audit. It does not run search or replay.

## Overlap

- J2 clusters: `23`
- J4 relaxed clusters: `22`
- overlap: `22`
- J2-only removed clusters: `1`
- J4-only added clusters: `0`

## Sensitivity Plateau

- pass variants: `129` / `216`
- local neighborhood variants: `18`
- local pass variants: `18`
- near-best variants: `24`

## Book Proxy

| metric | J2 | J4_relaxed |
| --- | ---: | ---: |
| cluster_count | 23 | 22 |
| retention_vs_j0 | 0.676471 | 0.647059 |
| p90_turnover | 0.276502 | 0.278967 |
| capacity_proxy_median | 23895134.562695 | 24333428.564258 |
| max_raw_share | 0.129032 | 0.133333 |
| source_lane_top_share | 0.521739 | 0.545455 |
| limit_suspension_loss_proxy | 0.024846 | 0.025427 |
| equal_book_ir_proxy | 1.609018 | 1.68038 |
| liquidity_adjusted_book_ir_proxy | 1.905661 | 1.918174 |
| liquidity_adjusted_max_cluster_weight | 0.165589 | 0.16696 |
| liquidity_adjusted_top_cluster_contribution | 0.213203 | 0.21323 |

## Interpretation

- J4_relaxed is almost a subset of J2, so it is a light cluster-level prune, not a new book construction.
- If plateau is broad, the light liquidity/capacity constraint is useful. If plateau is narrow, it is likely overfit.
- Production deployment remains unconfirmed; this is a book-readiness proxy only.
