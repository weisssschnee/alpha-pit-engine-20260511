# CN Controlled Data Smoke

Decision: `PASS_CN_CONTROLLED_DATA_SMOKE`

## Policy

- Daily/event fields are conservatively treated as next-trading-day inputs unless an intraday timestamp contract proves otherwise.
- 1min fields are observable only after the bar close; daily alpha use must explicitly aggregate and lag.
- `holder_num_detail` requires announcement-date PIT handling.
- `stock_calendar` is not a daily tradable-state input until standardized.

## Tables

| table | rows | date range | unique dates | unique codes | duplicate keys | role |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `hfq_daily_2026` | 443570 | 2026-01-05..2026-05-14 | 81 | 5521 | 0 | `daily_price_state_value` |
| `stock_1min_2026_manifest` | 63 | 2026-01-05..2026-04-10 | 63 |  | 0 | `minute_manifest` |
| `stock_1min_2026_sample_partition` | 1318029 | 2026-01-05..2026-01-05 | 1 | 5469 | 0 | `minute_price_sample_partition` |
| `review_uplimit_reason` | 168229 | 2024-01-02..2026-05-29 | 578 | 4655 | 128833 | `limit_event_close_reason` |
| `review_uplimit_reason_open` | 42673 | 2024-01-02..2026-05-29 | 578 | 4655 | 3277 | `limit_event_open_board_reason` |
| `updown_distribution` | 581 | 2024-01-02..2026-05-29 | 580 |  | 0 | `market_regime_distribution` |
| `uplimit_trend` | 49809 | 2024-01-02..2026-05-29 | 609 |  | 0 | `market_limit_trend_intraday_summary` |
| `rzrq_margin_xsection_daily` | 2359230 | 2024-01-02..2026-05-29 | 580 | 4655 | 0 | `margin_short_xsection_daily` |
| `billboard_details` | 49010 |  |  |  |  | `lhb_billboard_details` |
| `billboard_buy` | 244856 |  |  |  |  | `lhb_buy_departments` |
| `billboard_sell` | 244815 |  |  |  |  | `lhb_sell_departments` |
| `holder_num_detail` | 119933 |  |  |  |  | `holder_count_detail` |
| `stock_calendar` | 1243838 |  |  |  |  | `company_event_calendar` |

## Outputs

- `cn_controlled_data_smoke.json`
- `cn_controlled_data_sources.csv`
- `cn_controlled_field_inventory.csv`
- `runtime\field_registry\cn_alpha_field_registry_v1_20260531.json`