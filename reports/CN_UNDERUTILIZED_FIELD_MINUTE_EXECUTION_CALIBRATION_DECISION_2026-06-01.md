# CN Minute Execution Calibration - 2026-06-01

decision: `PASS_MINUTE_EXECUTION_CALIBRATION_AVAILABLE`
minute_coverage: `20260105` to `20260410`
calendar_days: `63`
r3_active_days: `24`

## Metrics

| profile | exec | ann | sharpe | sortino | maxDD | total | median_amount30 | cap2pct30 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| B2_x0_plus_core6_R3 | open_to_close | 0.232112 | 4.054854 | 4.31543 | -0.0110294 | 0.05321986 | 95686500.0 | 1913730.0 |
| B2_x0_plus_core6_R3 | vwap5_to_close | 0.176144 | 3.452661 | 4.812985 | -0.00887563 | 0.04110737 | 95686500.0 | 1913730.0 |
| B2_x0_plus_core6_R3 | vwap30_to_close | 0.118685 | 2.838753 | 4.078282 | -0.00850139 | 0.02823512 | 95686500.0 | 1913730.0 |
| X0_official6_R3 | open_to_close | 0.1702 | 2.432366 | 2.280136 | -0.01740015 | 0.03953299 | 92659894.0 | 1853197.88 |
| X0_official6_R3 | vwap5_to_close | 0.161103 | 2.495095 | 4.147163 | -0.0149514 | 0.03758423 | 92659894.0 | 1853197.88 |
| X0_official6_R3 | vwap30_to_close | 0.101505 | 1.867344 | 2.625461 | -0.01448297 | 0.02412111 | 92659894.0 | 1853197.88 |

## Boundary

- This is minute execution calibration for available dates only.
- It does not cover 2026 after 2026-04-10 because minute files are missing there.
- It is not live, fill, or full capacity proof.
