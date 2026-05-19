# Crypto A6.1 Core4 Curve Exposure Sanity

- generated_at: `2026-05-19T07:54:41Z`
- decision: `PASS_A6_1_CURVE_SANITY_RISK_SCALING_REQUIRED`
- locked object: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\baselines\crypto_core4_locked_research_book_v1.json`

## Split Summary

| split | ann mean | additive total | additive max DD | compounded total | compounded max DD | min hour | <=-10% bars | gross exposure mean | turnover mean | fee drag total | funding drag total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `train_2024` | 1.5365 | 1.5407 | -2.8566 | 1.4226 | -0.9460 | -0.0848 | 0 | 1.9287 | 0.3804 | 1.6707 | 0.1020 |
| `validation_2025H1` | 4.2300 | 2.0976 | -2.6730 | 5.0368 | -0.9413 | -0.1701 | 2 | 2.0000 | 0.3629 | 0.7883 | -0.0953 |
| `recent_oos_2025H2_2026` | 3.9461 | 3.2867 | -2.6663 | 19.4975 | -0.9334 | -0.0422 | 0 | 1.9899 | 0.3789 | 1.3821 | -0.0359 |

## Top Loss Hours

| timestamp | book net | gross | fee | funding | turnover | gross exposure | worst cluster | worst cluster ret |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| `2025-03-02 12:00:00+00:00` | -0.1701 | -0.1699 | 0.0001 | 0.0000 | 0.2500 | 2.0000 | `crypto_a4_1h_004` | -0.2232 |
| `2025-03-02 11:00:00+00:00` | -0.1643 | -0.1640 | 0.0002 | 0.0000 | 0.5000 | 2.0000 | `crypto_a4_1h_002` | -0.2232 |
| `2025-03-02 10:00:00+00:00` | -0.0859 | -0.0858 | 0.0002 | 0.0000 | 0.3333 | 2.0000 | `crypto_a4_1h_004` | -0.1546 |
| `2024-12-02 10:00:00+00:00` | -0.0848 | -0.0846 | 0.0000 | 0.0001 | 0.0833 | 1.5000 | `crypto_a4_1h_002` | -0.1160 |
| `2024-12-02 12:00:00+00:00` | -0.0792 | -0.0789 | 0.0000 | 0.0003 | 0.0833 | 1.5000 | `crypto_a4_1h_001` | -0.1282 |
| `2025-03-02 14:00:00+00:00` | -0.0688 | -0.0687 | 0.0002 | 0.0000 | 0.3333 | 2.0000 | `crypto_a4_1h_003` | -0.1567 |
| `2024-12-02 11:00:00+00:00` | -0.0674 | -0.0672 | 0.0001 | 0.0001 | 0.1667 | 1.5000 | `crypto_a4_1h_001` | -0.1036 |
| `2024-12-02 13:00:00+00:00` | -0.0669 | -0.0665 | 0.0001 | 0.0003 | 0.1667 | 1.5000 | `crypto_a4_1h_004` | -0.1060 |
| `2024-03-27 10:00:00+00:00` | -0.0643 | -0.0640 | 0.0001 | 0.0003 | 0.1667 | 1.5000 | `crypto_a4_1h_004` | -0.0915 |
| `2025-03-02 13:00:00+00:00` | -0.0612 | -0.0610 | 0.0002 | 0.0000 | 0.4167 | 2.0000 | `crypto_a4_1h_003` | -0.1492 |

## Recent Cluster Contribution

| cluster | net total | mean | worst hour | best hour | fee drag | funding drag | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|
| `crypto_a4_1h_001` | 2.5644 | 0.000351 | -0.0542 | 0.1044 | 1.1997 | -0.0283 | 0.3289 |
| `crypto_a4_1h_002` | 5.1276 | 0.000703 | -0.0598 | 0.1497 | 1.9467 | -0.0308 | 0.5336 |
| `crypto_a4_1h_003` | 2.1600 | 0.000296 | -0.0547 | 0.0918 | 0.6573 | -0.0217 | 0.1802 |
| `crypto_a4_1h_004` | 3.2946 | 0.000452 | -0.0706 | 0.1207 | 1.7248 | -0.0629 | 0.4728 |

## Interpretation

- No <= -100% hourly return bars means the -93% compounded drawdown is not an immediate unit bug.
- The drawdown is driven by repeated large unscaled hourly long-short losses and compounding at full notional.
- Core4 can proceed to A6.2 risk scaling only as a locked research object; it is not shadow/live-ready yet.
