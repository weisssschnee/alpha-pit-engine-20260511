# Phase2 Opengap Timestamp And Tradability Audit

## Bias Audit

- Factor: `CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1)))`
- Run/experiment_id: `phase2-opengap-timestamp-tradability-audit-20260510-rerun-limit-fallback`
- Data source and universe: `phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`, stock-only loader
- Frequency and horizon: daily, horizon 1
- OOS/sample window used here: 2026-01-01 to 2026-05-08
- Cost model: not applied in this simple validation table; tradability filters are applied
- Discovery status: replay/audit of known winner family

### Findings

- Look-ahead:
  - `pre_open`: current `open_t` is not available; validator lags `open` and full-day fields by one session.
  - `after_open`: current `open_t` is available; `close/high/low/amount/volume/limit` fields are lagged by one session.
  - Therefore opengap is valid only as an after-open state factor, not as a pre-open prediction factor.
- Date alignment:
  - Current proof setting is signal after open T, execute T+1 close, exit T+2 close.
  - Same-day execution in the current daily engine is only a same-day close-entry proxy, not real open-price execution.
- Tradability:
  - Found and fixed a bug: `is_limit_up/is_limit_down` existed but were all null, so validation failed to fall back to `rt_change_pct`.
  - After fix, limit flags are derived from `rt_change_pct>=9.8` and `rt_change_pct<=-9.8`.
  - In the audit window, 9541 rows are excluded from IC under T+1 execution due to entry limit-up/limit-down.

### Results

| case | signal clock | execution | RankIC | long return | long Sortino | spread Sortino | IC excluded |
|---|---|---|---:|---:|---:|---:|---:|
| pre_open_exec_t_plus_1 | pre_open | T+1 close | -0.007030 | 0.002018 | 1.190268 | 0.323199 | 9541 |
| after_open_exec_t_plus_1_current_proof | after_open | T+1 close | 0.028443 | 0.001206 | 2.905181 | 2.765401 | 9541 |
| after_open_exec_same_day_close_proxy | after_open | same-day close proxy | 0.008098 | 0.001730 | 0.760249 | 2.548138 | 9752 |
| after_close_exec_t_plus_1 | after_close | T+1 close | 0.028443 | 0.001206 | 2.905181 | 2.765401 | 9541 |

### Decision

HOLD_RESEARCH.

The opengap family is not proven to be a future function under `after_open`, but it is not a pre-open factor. Its previously reported strength was overstated because limit-up/down filtering was not active on `maxopt` due to all-null limit flag columns. All stock-only P0/P3 proof results produced before this fix must be treated as pre-fix evidence and rerun.

### Required Next Action

- Re-sync the limit fallback fix to the company runner.
- Rerun stock-only P0/P1/P2/P3 with active `rt_change_pct` limit filtering.
- Add a separate pre-open-only search universe that rejects current `open_t`.
