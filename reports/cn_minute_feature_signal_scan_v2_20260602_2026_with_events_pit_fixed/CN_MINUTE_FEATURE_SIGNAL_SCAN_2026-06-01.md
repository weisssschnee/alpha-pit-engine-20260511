# CN Minute Feature Signal Scan - 2026-06-01

decision: `PASS_MINUTE_FEATURE_SIGNAL_SCAN_DIAGNOSTIC`
rows: `339966`
days: `62`
r3_active_days: `23`

## Top Diagnostic Features

| rank | feature | sample | horizon | direction | ann | sharpe | maxDD |
|---:|---|---|---|---|---:|---:|---:|
| 1 | `m1_first30_last_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 365.687916 | 53.720734 | 0.0 |
| 2 | `m1_first30_last_return_vs_open` | all_days | 1000_to_close | high_minus_low | 435.346152 | 46.538342 | 0.0 |
| 3 | `m1_first5_last_return_vs_open` | all_days | 0935_to_close | high_minus_low | 69.710921 | 27.291448 | -0.01164496 |
| 4 | `m1_first30_vwap_return_vs_open` | all_days | 1000_to_close | high_minus_low | 27.861244 | 26.96856 | -0.00397096 |
| 5 | `m1_first15_last_return_vs_open` | all_days | 1000_to_close | high_minus_low | 22.415219 | 25.380428 | -0.00664905 |
| 6 | `m1_first30_vwap_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 20.195746 | 23.105488 | -0.00397096 |
| 7 | `m1_first5_last_return_vs_open` | R3_active | 0935_to_close | high_minus_low | 38.46358 | 20.685595 | -0.01164496 |
| 8 | `m1_first15_last_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 17.719948 | 20.392975 | -0.00664905 |
| 9 | `m1_first5_vwap_return_vs_open` | all_days | 0935_to_close | high_minus_low | 13.885884 | 20.022969 | -0.01204162 |
| 10 | `ctx_aug_limit_up_open_count_t10` | R3_active | 1000_to_close | low_minus_high | 1.577481 | 15.963252 | -0.00367564 |
| 11 | `m1_first5_vwap_return_vs_open` | R3_active | 0935_to_close | high_minus_low | 7.407269 | 13.613236 | -0.01204162 |
| 12 | `m1_first15_vwap_return_vs_open` | all_days | 1000_to_close | high_minus_low | 4.251412 | 13.589784 | -0.02186114 |
| 13 | `ctx_aug_limit_up_streak_close` | R3_active | 1000_to_close | low_minus_high | 1.999269 | 12.559333 | -0.00575356 |
| 14 | `m1_first30_amount_vs_ctx_amount` | all_days | 1000_to_close | high_minus_low | 1.94212 | 11.506083 | -0.01207734 |
| 15 | `ctx_aug_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.394832 | 11.428974 | -0.00778643 |
| 16 | `ctx_hfq_market_cap_yuan` | R3_active | 1000_to_close | high_minus_low | 2.529049 | 11.420292 | -0.00857793 |
| 17 | `ctx_aug_final_total_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.539025 | 11.401961 | -0.00860916 |
| 18 | `ctx_aug_float_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.29007 | 11.105532 | -0.00616772 |
| 19 | `ctx_aug_final_float_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.29007 | 11.105532 | -0.00616772 |
| 20 | `m1_first30_amount_vs_ctx_amount` | R3_active | 1000_to_close | high_minus_low | 1.211514 | 10.953497 | -0.00638449 |

## Boundary

- This is diagnostic feature screening, not an alpha promotion.
- Top rows are not OOS-safe winners; they define minute-feature search axes that need locked replay.
- Label columns remain forbidden as selector inputs.
