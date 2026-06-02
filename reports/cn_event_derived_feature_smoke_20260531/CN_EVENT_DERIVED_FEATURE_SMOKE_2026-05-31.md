# CN Event Derived Feature Smoke

Decision: `PASS_CN_EVENT_DERIVED_FEATURE_SMOKE`

## Output

- feature_path: `runtime\derived_features\cn_event_daily_features_v1_20260531.parquet`
- rows: `443570`
- date_range: `2026-01-05..2026-05-14`
- code_count: `5521`

## Critical Distinctions

- `limit_up_open_not_close`: opened at limit proxy but did not close limit.
- `limit_up_touch_not_close`: touched limit intraday but did not close limit.
- `limit_up_close_not_open`: closed limit but was not locked at open.
- `limit_up_*_count_tN`: rolling N-session event counts generated for N=2..max_window_n, not hard-coded to 2/3/4.
- All close/touch/reason fields are marked next-trading-day conservative for daily selection.

## Selected Coverage

| field | positive_ratio | max |
| --- | ---: | ---: |
| `reason_record_exists` | 0.012492 | 1.0 |
| `open_board_record` | 0.012492 | 1.0 |
| `limit_up_open_not_close` | 0.001695 | 1.0 |
| `limit_up_touch_not_close` | 0.018581 | 1.0 |
| `limit_up_close_not_open` | 0.011035 | 1.0 |
| `close_limit_without_reason_record` | 7.9e-05 | 1.0 |
| `reason_record_without_close_limit` | 8.1e-05 | 1.0 |
| `limit_up_close_count_t2` | 0.022544 | 2.0 |
| `limit_up_open_not_close_count_t2` | 0.002448 | 2.0 |
| `limit_up_close_not_open_count_t2` | 0.0207 | 2.0 |
| `limit_up_close_count_t3` | 0.031857 | 3.0 |
| `limit_up_open_not_close_count_t3` | 0.00319 | 3.0 |
| `limit_up_close_not_open_count_t3` | 0.029682 | 3.0 |
| `limit_up_close_count_t4` | 0.040512 | 4.0 |
| `limit_up_open_not_close_count_t4` | 0.003916 | 3.0 |
| `limit_up_close_not_open_count_t4` | 0.037978 | 4.0 |
| `limit_up_close_count_t5` | 0.048549 | 5.0 |
| `limit_up_open_not_close_count_t5` | 0.004631 | 3.0 |
| `limit_up_close_not_open_count_t5` | 0.045713 | 5.0 |
| `limit_up_close_count_t10` | 0.082916 | 10.0 |
| `limit_up_open_not_close_count_t10` | 0.008111 | 3.0 |
| `limit_up_close_not_open_count_t10` | 0.078799 | 7.0 |