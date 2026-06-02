# CN Underutilized Field Discovery Baseline 162 Promotion - 2026-06-01

decision: `PROMOTE_CANDIDATE_162_TO_DISCOVERY_BASELINE`

## Baseline

- baseline_name: `cn_discovery_baseline_162_20260601`
- status: `promoted_discovery_baseline_not_book_or_production`
- prior discovery baseline: `149`
- new discovery baseline: `162`
- added signal clusters: `13`
- stable hash excluding created_at: `0cbf6d81255a10b1de201328cb77c249586d59c61914329ae0010ef545bcffa5`

## Source Counts

- cn_underutilized_field_replay128_candidate_new: `13`
- phase3D_previous: `103`
- phase3E_new: `31`
- phase3H_new: `15`

## Evidence

- replay128 deployable survivor attribution
- signal-vector recluster vs frozen 149 registry
- global 149+13 integration with zero review/high-corr queued edges

## Explicit Boundary

This is a discovery baseline promotion only. It is not a production, execution, capacity, or book-readiness promotion.

Not confirmed:

- production_ready
- book_marginal_value
- minute_execution
- true_slippage
- true_capacity

## Artifacts

- baseline JSON: `runtime\baselines\cn_discovery_baseline_162_20260601.json`
- stable hash: `runtime\baselines\cn_discovery_baseline_162_20260601.sha256`
