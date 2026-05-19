# Crypto A5.1 Book Curve Sanity

- generated_at: `2026-05-19T07:42:35Z`
- decision: `PASS_A5_1_BOOK_CURVE_SANITY_WITH_DRAWDOWN_WARNING`

## Summary

| book | split | clusters | ann mean | additive total | compounded total | additive max DD | compounded max DD | worst day | top3 day contribution |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `Core4` | `train_2024` | 4 | 2.6992 | 2.7062 | 5.8201 | -2.8240 | -0.9470 | -0.6225 | 2.2293 |
| `Core4` | `validation_2025H1` | 4 | 4.5453 | 2.2539 | 6.0587 | -2.6016 | -0.9369 | -0.8690 | 1.0419 |
| `Core4` | `recent_oos_2025H2_2026` | 4 | 4.2409 | 3.5288 | 25.0201 | -2.6511 | -0.9325 | -0.4527 | 1.6544 |
| `CoreSupport8` | `train_2024` | 8 | 0.0607 | 0.0609 | -0.4314 | -4.1128 | -0.9861 | -0.7680 | 1.7517 |
| `CoreSupport8` | `validation_2025H1` | 8 | 3.4275 | 1.6997 | 3.2394 | -2.4797 | -0.9267 | -0.9452 | 1.0638 |
| `CoreSupport8` | `recent_oos_2025H2_2026` | 8 | 3.4767 | 2.8929 | 13.4568 | -2.5636 | -0.9262 | -0.4814 | 1.2547 |
| `All9` | `train_2024` | 9 | -0.8662 | -10.4209 | -1.0000 | -16.5663 | -1.0000 | -2.2128 | 3.9004 |
| `All9` | `validation_2025H1` | 9 | 0.4752 | 2.8279 | 6.5304 | -5.2053 | -0.9967 | -2.1884 | 2.3611 |
| `All9` | `recent_oos_2025H2_2026` | 9 | 0.6043 | 6.0389 | 180.4547 | -5.6902 | -0.9970 | -0.9519 | 3.4465 |

## Interpretation

- The Core4 mean signal is strong, but drawdown is not acceptable for production claims.
- A5 remains research proof. The next step is locked shadow with risk scaling and execution calibration, not live trading.
