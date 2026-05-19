# Crypto A6.3 Core4 Conservative Dry Shadow Replay

- generated_at: `2026-05-19T08:24:26Z`
- decision: `PASS_A6_3_CONSERVATIVE_DRY_SHADOW_REPLAY_WITH_WARNINGS`
- dry_shadow_object_hash: `5336e046183b3cfcd2f4ae07695761ef4ce74cf0aed550d4b43239e299d38895`
- gross_cap: `0.2`
- warnings: `['validation_month_pass_rate_below_70pct']`

## Summary

| split | cost | ann mean | compounded max DD | additive max DD | month pass | sharpe | min hour |
|---|---|---:|---:|---:|---:|---:|---:|
| `train_2024` | `stress_10bp` | -0.0263 | -0.2744 | -0.3188 | 0.417 | -0.210 | -0.0113 |
| `validation_2025H1` | `stress_10bp` | 0.2640 | -0.2575 | -0.2961 | 0.500 | 2.420 | -0.0170 |
| `recent_oos_2025H2_2026` | `stress_10bp` | 0.2359 | -0.2496 | -0.2867 | 0.700 | 2.924 | -0.0042 |
| `train_2024` | `severe_20bp` | -0.3737 | -0.4671 | -0.6224 | 0.250 | -2.980 | -0.0113 |
| `validation_2025H1` | `severe_20bp` | -0.0539 | -0.3037 | -0.3602 | 0.500 | -0.493 | -0.0170 |
| `recent_oos_2025H2_2026` | `severe_20bp` | -0.0981 | -0.2892 | -0.3405 | 0.400 | -1.213 | -0.0043 |

## Boundary

- This is a dry-shadow replay only. It does not place orders and does not authorize live trading.
- The gross cap is a conservative risk budget candidate, not alpha optimization.
- Validation month pass is weak; forward shadow requires append-only observation before any deployment discussion.
