# Crypto Alpha Smoke v0

- generated_at: `2026-05-19T05:00:46Z`
- decision: `PASS_CRYPTO_ALPHA_SMOKE_V0`
- universe: `core12 futures`
- splits: `2024 train / 2025H1 validation / 2025H2-2026-04 recent OOS`
- method: cross-sectional Spearman IC and train-sign oriented top/bottom basket
- warning: this is feature smoke, not deployable alpha proof

## Top Recent-OOS Feature/Horizon Rows

| interval | horizon | feature | family | train IC | val IC | recent IC | recent LS ann | recent LS sharpe |
|---|---:|---|---|---:|---:|---:|---:|---:|
| `5m` | 1 | `ret_6` | `price` | 0.0271 | 0.0245 | 0.0273 | 4.5909 | 5.658 |
| `5m` | 1 | `ret_3` | `price` | 0.0306 | 0.0246 | 0.0280 | 4.2295 | 5.075 |
| `5m` | 1 | `ret_1` | `price` | 0.0301 | 0.0248 | 0.0252 | 3.4237 | 4.373 |
| `5m` | 1 | `ret_12` | `price` | 0.0234 | 0.0221 | 0.0232 | 3.3185 | 4.069 |
| `5m` | 3 | `ret_6` | `price` | 0.0302 | 0.0278 | 0.0369 | 3.1528 | 4.411 |
| `5m` | 1 | `ret_24` | `price` | 0.0221 | 0.0194 | 0.0227 | 2.8248 | 3.472 |
| `5m` | 3 | `ret_3` | `price` | 0.0298 | 0.0252 | 0.0356 | 2.7859 | 3.920 |
| `5m` | 1 | `mark_index_ratio` | `basis` | 0.0239 | 0.0236 | 0.0183 | 2.6549 | 6.288 |
| `5m` | 1 | `premium_index` | `basis` | 0.0270 | 0.0240 | 0.0177 | 2.5658 | 5.423 |
| `5m` | 3 | `ret_12` | `price` | 0.0267 | 0.0230 | 0.0335 | 2.3806 | 3.363 |
| `5m` | 3 | `ret_1` | `price` | 0.0298 | 0.0243 | 0.0268 | 2.3271 | 3.618 |
| `5m` | 6 | `ret_6` | `price` | 0.0282 | 0.0332 | 0.0377 | 2.1210 | 3.307 |
| `5m` | 3 | `ret_24` | `price` | 0.0242 | 0.0191 | 0.0315 | 2.0449 | 2.878 |
| `5m` | 6 | `ret_3` | `price` | 0.0284 | 0.0272 | 0.0351 | 1.8435 | 2.869 |
| `5m` | 6 | `ret_12` | `price` | 0.0282 | 0.0268 | 0.0378 | 1.7714 | 2.753 |
| `5m` | 6 | `ret_24` | `price` | 0.0252 | 0.0212 | 0.0366 | 1.6627 | 2.586 |
| `5m` | 3 | `mark_index_ratio` | `basis` | 0.0210 | 0.0167 | 0.0148 | 1.5125 | 3.749 |
| `5m` | 6 | `ret_1` | `price` | 0.0245 | 0.0216 | 0.0257 | 1.4034 | 2.332 |
| `5m` | 12 | `ret_6` | `price` | 0.0255 | 0.0267 | 0.0362 | 1.3042 | 2.518 |
| `5m` | 12 | `ret_24` | `price` | 0.0230 | 0.0197 | 0.0405 | 1.2620 | 2.426 |
| `5m` | 3 | `premium_index` | `basis` | 0.0232 | 0.0198 | 0.0146 | 1.2517 | 3.368 |
| `5m` | 12 | `latest_known_funding_rate` | `funding` | 0.0052 | 0.0135 | 0.0143 | 1.1672 | 3.251 |
| `5m` | 6 | `latest_known_funding_rate` | `funding` | 0.0037 | 0.0095 | 0.0109 | 1.1263 | 2.745 |
| `1h` | 1 | `latest_known_funding_rate` | `funding` | 0.0080 | 0.0107 | 0.0124 | 1.0991 | 3.529 |
| `5m` | 3 | `latest_known_funding_rate` | `funding` | 0.0032 | 0.0073 | 0.0074 | 1.0890 | 2.609 |
| `1h` | 1 | `ret_3` | `price` | 0.0263 | 0.0232 | 0.0412 | 1.0681 | 2.818 |
| `5m` | 12 | `ret_3` | `price` | 0.0227 | 0.0216 | 0.0302 | 1.0640 | 2.061 |
| `1h` | 1 | `ret_24` | `price` | 0.0140 | 0.0232 | 0.0346 | 1.0232 | 2.680 |
| `5m` | 12 | `ret_12` | `price` | 0.0279 | 0.0251 | 0.0393 | 1.0153 | 1.948 |
| `5m` | 1 | `latest_known_funding_rate` | `funding` | 0.0016 | 0.0044 | 0.0048 | 1.0002 | 2.270 |

## Stable Positive-IC Rows Across All Splits

| interval | horizon | feature | family | train IC | val IC | recent IC | recent LS ann |
|---|---:|---|---|---:|---:|---:|---:|
| `5m` | 1 | `ret_6` | `price` | 0.0271 | 0.0245 | 0.0273 | 4.5909 |
| `5m` | 1 | `ret_3` | `price` | 0.0306 | 0.0246 | 0.0280 | 4.2295 |
| `5m` | 1 | `ret_1` | `price` | 0.0301 | 0.0248 | 0.0252 | 3.4237 |
| `5m` | 1 | `ret_12` | `price` | 0.0234 | 0.0221 | 0.0232 | 3.3185 |
| `5m` | 3 | `ret_6` | `price` | 0.0302 | 0.0278 | 0.0369 | 3.1528 |
| `5m` | 1 | `ret_24` | `price` | 0.0221 | 0.0194 | 0.0227 | 2.8248 |
| `5m` | 3 | `ret_3` | `price` | 0.0298 | 0.0252 | 0.0356 | 2.7859 |
| `5m` | 1 | `mark_index_ratio` | `basis` | 0.0239 | 0.0236 | 0.0183 | 2.6549 |
| `5m` | 1 | `premium_index` | `basis` | 0.0270 | 0.0240 | 0.0177 | 2.5658 |
| `5m` | 3 | `ret_12` | `price` | 0.0267 | 0.0230 | 0.0335 | 2.3806 |
| `5m` | 3 | `ret_1` | `price` | 0.0298 | 0.0243 | 0.0268 | 2.3271 |
| `5m` | 6 | `ret_6` | `price` | 0.0282 | 0.0332 | 0.0377 | 2.1210 |
| `5m` | 3 | `ret_24` | `price` | 0.0242 | 0.0191 | 0.0315 | 2.0449 |
| `5m` | 6 | `ret_3` | `price` | 0.0284 | 0.0272 | 0.0351 | 1.8435 |
| `5m` | 6 | `ret_12` | `price` | 0.0282 | 0.0268 | 0.0378 | 1.7714 |
| `5m` | 6 | `ret_24` | `price` | 0.0252 | 0.0212 | 0.0366 | 1.6627 |
| `5m` | 3 | `mark_index_ratio` | `basis` | 0.0210 | 0.0167 | 0.0148 | 1.5125 |
| `5m` | 6 | `ret_1` | `price` | 0.0245 | 0.0216 | 0.0257 | 1.4034 |
| `5m` | 12 | `ret_6` | `price` | 0.0255 | 0.0267 | 0.0362 | 1.3042 |
| `5m` | 12 | `ret_24` | `price` | 0.0230 | 0.0197 | 0.0405 | 1.2620 |

## Family Summary By Recent-OOS LS Annualized

| interval | family | count | median | max |
|---|---|---:|---:|---:|
| `1h` | `funding` | 12 | 0.4909 | 1.0991 |
| `1h` | `price` | 28 | 0.3422 | 1.0681 |
| `1h` | `volatility` | 28 | -0.0547 | 0.5636 |
| `1h` | `basis` | 12 | 0.0639 | 0.3108 |
| `1h` | `liquidity` | 4 | 0.2010 | 0.2167 |
| `1h` | `flow` | 8 | -0.1642 | 0.1216 |
| `5m` | `price` | 28 | 1.5331 | 4.5909 |
| `5m` | `basis` | 12 | 0.5616 | 2.6549 |
| `5m` | `funding` | 12 | 0.3861 | 1.1672 |
| `5m` | `volatility` | 28 | -0.1351 | 0.1266 |
| `5m` | `liquidity` | 4 | -0.0580 | 0.0356 |
| `5m` | `flow` | 8 | -0.8423 | -0.6539 |

## Boundary

- Forward-return columns are labels and must not enter formula generation.
- This smoke does not use recent-only positioning.
- Results are priors for motif/search allocation, not a final alpha book.
