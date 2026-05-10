# Phase2 Maxopt Reward/Generator Upgrade - 2026-05-10

## Data inspected

- Main fixed stock PIT panel:
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
  - rows: `1,090,783`
  - symbols: `6,333`
  - dates: `2025-08-06` to `2026-05-08`
  - columns: `46`
- Quality report:
  `phase2_stock_tdx_official_20250806_to_20260508_maxopt_report.json`
  - final total cap coverage rows: `90.81%`
  - final float cap coverage rows: `89.86%`
  - market-cap conflict >5%: `61,678` rows, `503` symbols
- Enhancement sources inspected:
  - `tdx_gbbq_capital_events_since_20200101.parquet`
  - `tdxgp_gpjvalue_types_1-3-6-11-12-13-15-16_since_20250806.parquet`
  - `phase2_stock_tdx_official_20250806_to_20260508_gbbq_cap_enriched_20200101_tdxgp_gpjvalue.parquet`

## Implemented

- Switched default stock-PIT data preference to the fixed `maxopt` panel, with legacy validation slice fallback.
- Added capacity/capital columns to the validation loader and marked them as full-day fields for `after_open`/`pre_open` lagging.
- Updated derived `turnover_rate` so panels with `float_share` use `volume / float_share`; the old rolling-volume proxy remains fallback only.
- Added signal-safe long-selection diagnostics to validation output:
  - selected long-side amount
  - selected long-side turnover rate
  - selected long-side final float/total market cap
  - selected long-side market-cap conflict rate
- Upgraded terminal reward proxy to include mild capacity/coverage terms and market-cap conflict penalty.
- Upgraded RX typed beam generator to open size/cap-normalized search space only when the dataset has cap fields.
- Added collinearity control: only one canonical field per semantic capacity family enters generation.
  Redundant same-source fields remain diagnostics only.
- Updated next-wave dry-run launcher to use the `maxopt` panel.

## Real smoke

Real smoke root:
`runtime\next_stage_artifacts\maxopt_reward_capacity_smoke_20260510`

- generated RX ledger records: `96`
- canonical generation fields:
  - float cap: `final_float_market_cap`
  - total cap: `final_total_market_cap`
- generated cap-aware expressions: `36`
- validation mode: `recent_2_quarter_multi_cycle_smoke`, `after_open`, T+1, `top_bottom_quantile=0.02`
- first 6 candidates all produced capacity diagnostics and cap field lags.

Example first-row smoke result:

- IC: `0.028931`
- long return: `0.003781`
- long sortino: `11.995197`
- selected amount: `1,215,834,679`
- selected float cap: `33,694,207,487`
- cap conflict rate: `0.044607`

This is a chain smoke, not a commercial edge claim.

## Verification

- `py_compile` passed for modified services.
- `pytest -q tests\test_phase2_v21_runtime.py -k "stock_pit"` passed:
  `20 passed, 165 deselected`
- launch dry-run passed:
  `launch_phase2_next_wave_pending_approval_20260509.ps1 -RunMode forward_first`
- `git diff --check` passed with only CRLF warnings.

## Next search implication

Next large search should use the `rx_typed_beam` path on `maxopt`, because that path now explores:

- price/open/limit/trend motifs from the existing system
- size and market-cap residual motifs
- cap-normalized amount/volume velocity motifs
- reward memory/UCB scheduling
- capacity-aware terminal reward proxy
- same T+1 and limit-up/down tradability contract

The old validation-slice roots should not be treated as directly comparable to this new maxopt-capacity run.
