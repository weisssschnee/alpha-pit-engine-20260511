# Phase3 Event Derived Feature Audit

Decision: `PASS_EVENT_DERIVED_FEATURE_LAYER_SMOKE`

## Dataset

- path: `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- rows: `50000`
- code_count: `501`
- date_min: `2025-08-06`
- date_max: `2026-05-08`

## Source Report

- has_tdxgp_limit_status: `True`
- has_exact_up_limit_price: `False`
- has_exact_down_limit_price: `False`
- has_open_high_low: `True`
- has_rt_change_pct: `True`
- price_touch_mode: `exact_limit_price_if_available_else_prev_close_pct_proxy`

## Key Coverage

| field | present | non_null | positive |
| --- | --- | ---: | ---: |
| `limit_up_close_event` | `True` | 1.0 | 0.00246 |
| `limit_up_open_event` | `True` | 1.0 | 0.00172 |
| `limit_up_touch_event` | `True` | 1.0 | 0.03234 |
| `limit_up_touch_not_close` | `True` | 1.0 | 0.02988 |
| `limit_up_open_not_close` | `True` | 1.0 | 0.0014 |
| `limit_up_streak_close` | `True` | 1.0 | 0.00246 |
| `limit_up_streak_ge_2` | `True` | 1.0 | 0.00044 |
| `limit_up_streak_ge_3` | `True` | 1.0 | 0.0001 |
| `market_high_board` | `True` | 1.0 | 0.3678 |
| `is_market_high_board` | `True` | 1.0 | 0.00176 |
| `post_market_high_board_tplus_1` | `True` | 1.0 | 0.00174 |
| `break_after_high_board_tplus_1` | `True` | 1.0 | 0.00138 |

## Policy

- This layer is a feature adapter, not an alpha promotion.
- Same-day close/touch/high-board fields must be lagged for after-open selection.
- Open-print fields may be used only after open and remain subject to tradability masks.
- Promotion still requires frozen selection, strict replay, global clustering, OOS/regime/marginal audit, and chain-lock update.