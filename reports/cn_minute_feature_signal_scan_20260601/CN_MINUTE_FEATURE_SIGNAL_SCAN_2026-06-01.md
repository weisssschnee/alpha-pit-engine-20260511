# CN Minute Feature Signal Scan - 2026-06-01

decision: `PASS_MINUTE_FEATURE_SIGNAL_SCAN_DIAGNOSTIC`
rows: `345435`
days: `63`
r3_active_days: `24`

## Top Diagnostic Features

| rank | feature | sample | horizon | direction | ann | sharpe | maxDD |
|---:|---|---|---|---|---:|---:|---:|
| 1 | `m1_first30_last_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 375.377374 | 54.97072 | 0.0 |
| 2 | `m1_first30_last_return_vs_open` | all_days | 1000_to_close | high_minus_low | 438.48577 | 46.950042 | 0.0 |
| 3 | `m1_first5_last_return_vs_open` | all_days | 0935_to_close | high_minus_low | 71.716615 | 27.580452 | -0.01164496 |
| 4 | `m1_first30_vwap_return_vs_open` | all_days | 1000_to_close | high_minus_low | 28.447801 | 27.25916 | -0.00397096 |
| 5 | `m1_first15_last_return_vs_open` | all_days | 1000_to_close | high_minus_low | 22.787953 | 25.660803 | -0.00664905 |
| 6 | `m1_first30_vwap_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 21.636033 | 23.831106 | -0.00397096 |
| 7 | `m1_first5_last_return_vs_open` | R3_active | 0935_to_close | high_minus_low | 42.522731 | 21.386 | -0.01164496 |
| 8 | `m1_first15_last_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 18.695861 | 21.068426 | -0.00664905 |
| 9 | `m1_first5_vwap_return_vs_open` | all_days | 0935_to_close | high_minus_low | 14.282722 | 20.284203 | -0.01204162 |
| 10 | `m1_first5_vwap_return_vs_open` | R3_active | 0935_to_close | high_minus_low | 8.227002 | 14.275715 | -0.01204162 |
| 11 | `m1_first15_vwap_return_vs_open` | all_days | 1000_to_close | high_minus_low | 4.364985 | 13.822899 | -0.02186114 |
| 12 | `ctx_limit_up_streak_close` | R3_active | 1000_to_close | low_minus_high | 1.999269 | 12.559333 | -0.00575356 |
| 13 | `m1_first30_amount_vs_ctx_amount` | all_days | 1000_to_close | high_minus_low | 2.034465 | 11.796902 | -0.01207734 |
| 14 | `m1_first30_amount_vs_ctx_amount` | R3_active | 1000_to_close | high_minus_low | 1.42641 | 11.701622 | -0.00621795 |
| 15 | `ctx_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.298409 | 11.35952 | -0.00778643 |
| 16 | `ctx_final_total_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.400682 | 11.209622 | -0.00860916 |
| 17 | `ctx_float_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.130978 | 10.761771 | -0.00616772 |
| 18 | `ctx_final_float_market_cap` | R3_active | 1000_to_close | high_minus_low | 2.130978 | 10.761771 | -0.00616772 |
| 19 | `m1_first30_amount` | R3_active | 1000_to_close | high_minus_low | 2.07507 | 10.245706 | -0.00992693 |
| 20 | `m1_first15_vwap_return_vs_open` | R3_active | 1000_to_close | high_minus_low | 3.141157 | 9.254057 | -0.01630476 |

## Boundary

- This is diagnostic feature screening, not an alpha promotion.
- Top rows are not OOS-safe winners; they define minute-feature search axes that need locked replay.
- Label columns remain forbidden as selector inputs.
