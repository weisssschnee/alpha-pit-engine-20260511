# Crypto A5 Champion Deep Audit

- generated_at: `2026-05-19T07:40:13Z`
- decision: `PASS_A5_DAILY_RESEARCH_PROOF_PACK`
- input champions: `9`
- final role counts: `{'Core': 4, 'Support': 4, 'Watch': 1}`

## Alpha Cards

| role | grade | cluster | interval | horizon | motif | recent net 5bp | recent net 10bp | month pass | symbol LOO pass | funding fee impact | expression |
|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| `Core` | `Grade_A` | `crypto_a4_1h_001` | `1h` | 6 | `price_funding_state` | 0.5389 | 0.2987 | 0.800 | 1.000 | 0.0308 | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` |
| `Core` | `Grade_A` | `crypto_a4_1h_002` | `1h` | 12 | `basis_funding_state` | 0.5383 | 0.3432 | 0.900 | 1.000 | 0.0274 | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` |
| `Core` | `Grade_A` | `crypto_a4_1h_003` | `1h` | 6 | `basis_funding_state` | 0.4606 | 0.3278 | 0.700 | 1.000 | 0.0251 | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` |
| `Core` | `Grade_A` | `crypto_a4_1h_004` | `1h` | 12 | `price_funding_state` | 0.3514 | 0.1785 | 0.800 | 1.000 | 0.0274 | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` |
| `Support` | `Grade_B` | `crypto_a4_1h_006` | `1h` | 12 | `basis_funding_state` | 0.3142 | 0.1111 | 0.800 | 1.000 | 0.0224 | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` |
| `Support` | `Grade_B` | `crypto_a4_1h_008` | `1h` | 12 | `price_momentum_continuation` | 0.2649 | 0.1330 | 0.500 | 1.000 | 0.0130 | `Rank(ret_24)` |
| `Support` | `Grade_B` | `crypto_a4_1h_005` | `1h` | 6 | `price_funding_state` | 0.2629 | 0.0503 | 0.400 | 1.000 | 0.0266 | `Mul(Rank(ret_12),ZScore(funding_rate_persistence_3))` |
| `Support` | `Grade_B` | `crypto_a4_1h_007` | `1h` | 12 | `price_funding_state` | 0.1936 | 0.0088 | 0.700 | 1.000 | 0.0241 | `Mul(Rank(hl_range),ZScore(funding_rate_persistence_3))` |
| `Watch` | `Grade_B` | `crypto_a4_5m_001` | `5m` | 12 | `price_funding_state` | 0.3427 | -0.4606 | 0.800 | 1.000 | 0.0299 | `Mul(Rank(ret_24),ZScore(latest_known_funding_rate))` |

## Book Proxy

| book | split | clusters | annualized | sharpe | sortino | max DD | mean corr | max corr |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `Grade_A_equal_weight` | `train_2024` | 4 | 2.6992 | 2.155 | 3.070 | -0.9470 | 0.440 | 0.659 |
| `A4_champion_equal_weight` | `train_2024` | 9 | -0.8662 | -1.521 | -1.955 | -1.0000 | 0.258 | 0.659 |
| `Core_equal_weight` | `train_2024` | 4 | 2.6992 | 2.155 | 3.070 | -0.9470 | 0.440 | 0.659 |
| `Grade_A_equal_weight` | `validation_2025H1` | 4 | 4.5453 | 4.167 | 5.069 | -0.9369 | 0.507 | 0.720 |
| `A4_champion_equal_weight` | `validation_2025H1` | 9 | 0.4752 | 0.915 | 1.104 | -0.9967 | 0.328 | 0.720 |
| `Core_equal_weight` | `validation_2025H1` | 4 | 4.5453 | 4.167 | 5.069 | -0.9369 | 0.507 | 0.720 |
| `Grade_A_equal_weight` | `recent_oos_2025H2_2026` | 4 | 4.2409 | 5.257 | 8.182 | -0.9325 | 0.512 | 0.735 |
| `A4_champion_equal_weight` | `recent_oos_2025H2_2026` | 9 | 0.6043 | 1.463 | 2.085 | -0.9970 | 0.330 | 0.735 |
| `Core_equal_weight` | `recent_oos_2025H2_2026` | 4 | 4.2409 | 5.257 | 8.182 | -0.9325 | 0.512 | 0.735 |

## Decision Boundary

- This is a research proof pack after next-bar proxy execution, 5bp/10bp cost stress, funding fee adjustment, placebo, ablation, month stability, and symbol leave-one-out.
- It is not production proof: no order book slippage, no live forward, no time-varying universe beyond static core12.
- Next valid step is locked forward/shadow or exchange-execution calibration, not broader formula search.
