# Phase2 TDXGP Limit Status Audit

## Summary

We found a real A-share limit-status source in the local TDXGP event table:

- source file: `tdxgp_gpjvalue_types_1-3-6-11-12-13-15-16_since_20250806.parquet`
- source field: `GPJYVALUE(15): limit-up/down status`
- mapping used for tradability:
  - `value1 == 2`: close locked limit-up, block long entry
  - `value1 == -2`: close locked limit-down, block short entry / sell exit
  - `value1 == 1/-1/0`: touched/opened/mixed limit states; useful as future microstructure features, not used as close locked tradability blocks in this daily proof path

The validator now prefers this source when the main panel's `is_limit_up/is_limit_down` fields are all null. If TDXGP status is not available, it still falls back to `rt_change_pct>=9.8` / `<=-9.8`.

## Field Quality

On `phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet` after stock-only loading:

| metric | value |
|---|---:|
| rows | 990549 |
| codes | 5775 |
| date range | 2025-08-06 to 2026-05-08 |
| TDXGP status non-null rows | 38882 |
| true close limit-up rows | 13846 |
| true close limit-down rows | 3201 |
| old 9.8 limit-up rows | 16460 |
| old 9.8 limit-down rows | 3685 |
| old 9.8 up but not TDXGP close-up | 4825 |
| TDXGP close-up but not old 9.8 up | 2211 |
| old 9.8 down but not TDXGP close-down | 1921 |
| TDXGP close-down but not old 9.8 down | 1437 |

Latest date `2026-05-08`:

| metric | value |
|---|---:|
| rows | 5490 |
| TDXGP status non-null rows | 287 |
| true close limit-up rows | 125 |
| true close limit-down rows | 33 |
| old 9.8 limit-up rows | 132 |
| old 9.8 limit-down rows | 10 |

## Opengap Re-Audit With True Limits

Factor: `CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1)))`

| case | RankIC | long return | long Sortino | spread Sortino | IC excluded |
|---|---:|---:|---:|---:|---:|
| pre_open, T+1 | 0.000803 | 0.000963 | 0.588699 | -0.279974 | 16694 |
| after_open, T+1 | 0.012394 | -0.000309 | 0.712445 | 0.363575 | 16694 |
| after_open, same-day close proxy | 0.009161 | -0.000196 | -0.257797 | 0.899381 | 16784 |

## Interpretation

- `opengap` is still not a future function under `after_open`, but its edge is much weaker under true close-limit tradability.
- The previous `rt_change_pct` fallback was directionally better than all-null flags, but it was still not precise enough for proof.
- Prior `limit-fallback-fixed` P0/P3 results are now an intermediate repair stage, not final promotion evidence.
- Search-space memory can remain, but reward memory and proof conclusions need a `pre_tdxgp_limit_status` tag unless rerun with this loader.

## Decision

HOLD_RESEARCH.

Next required action: rerun P0/P1/P2/P3 using the TDXGP true limit-status loader, then recalibrate reward against strict/replay. Large search should wait until that proof run confirms the new tradability baseline.
