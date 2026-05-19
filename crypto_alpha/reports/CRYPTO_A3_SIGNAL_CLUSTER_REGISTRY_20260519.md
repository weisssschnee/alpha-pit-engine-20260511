# Crypto A3 Signal Cluster Registry

- generated_at: `2026-05-19T06:18:04Z`
- decision: `PASS_A3_SIGNAL_CLUSTER_REGISTRY`
- input KEEP candidates: `194`
- signal clusters: `53`
- cluster corr threshold: `0.85`
- clusters by interval: `{'1h': 31, '5m': 22}`

## Top Cluster Representatives

| cluster | interval | members | horizon | motif | score | expression |
|---|---|---:|---:|---|---:|---|
| `crypto_a3_5m_001` | `5m` | 8 | 1 | `price_basis_confirmation` | 0.4169 | `Mul(Rank(ret_6),Rank(premium_index))` |
| `crypto_a3_5m_002` | `5m` | 8 | 1 | `price_basis_confirmation` | 0.4150 | `Mul(Rank(ret_3),Rank(premium_index))` |
| `crypto_a3_5m_003` | `5m` | 2 | 1 | `price_basis_confirmation` | 0.4128 | `Mul(Rank(ret_1),Rank(premium_index))` |
| `crypto_a3_5m_004` | `5m` | 4 | 1 | `basis_premium_continuation` | 0.4048 | `Rank(mark_index_ratio)` |
| `crypto_a3_5m_005` | `5m` | 4 | 3 | `price_basis_confirmation` | 0.4025 | `Mul(Rank(ret_12),Rank(premium_index))` |
| `crypto_a3_5m_006` | `5m` | 4 | 1 | `basis_premium_continuation` | 0.3994 | `Rank(premium_index)` |
| `crypto_a3_5m_007` | `5m` | 4 | 1 | `price_momentum_continuation` | 0.3983 | `Rank(ret_6)` |
| `crypto_a3_5m_008` | `5m` | 4 | 1 | `price_momentum_continuation` | 0.3956 | `Rank(ret_3)` |
| `crypto_a3_5m_009` | `5m` | 2 | 1 | `price_momentum_continuation` | 0.3885 | `Rank(ret_1)` |
| `crypto_a3_5m_010` | `5m` | 4 | 1 | `price_momentum_continuation` | 0.3648 | `Rank(ret_12)` |
| `crypto_a3_5m_011` | `5m` | 8 | 1 | `momentum_liquidity_state` | 0.3587 | `Mul(Rank(ret_3),ZScore(avg_trade_size_quote))` |
| `crypto_a3_5m_012` | `5m` | 11 | 1 | `price_funding_state` | 0.3237 | `Mul(Rank(ret_6),ZScore(latest_known_funding_rate))` |
| `crypto_a3_5m_013` | `5m` | 11 | 1 | `price_funding_state` | 0.3086 | `Mul(Rank(ret_6),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_5m_014` | `5m` | 2 | 6 | `momentum_volatility_state` | 0.3011 | `Mul(Rank(ret_6),ZScore(quote_volume_mean_24))` |
| `crypto_a3_5m_015` | `5m` | 1 | 1 | `price_funding_state` | 0.2824 | `Mul(Rank(ret_1),ZScore(latest_known_funding_rate))` |
| `crypto_a3_1h_001` | `1h` | 10 | 6 | `price_funding_state` | 0.2586 | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` |
| `crypto_a3_5m_016` | `5m` | 8 | 1 | `basis_funding_state` | 0.2480 | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` |
| `crypto_a3_1h_002` | `1h` | 7 | 6 | `basis_funding_state` | 0.2476 | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` |
| `crypto_a3_1h_003` | `1h` | 9 | 1 | `price_funding_state` | 0.2444 | `Mul(Rank(ret_6),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_5m_017` | `5m` | 2 | 12 | `price_basis_confirmation` | 0.2365 | `Mul(Rank(ret_24),Rank(premium_index))` |
| `crypto_a3_1h_004` | `1h` | 2 | 1 | `price_basis_confirmation` | 0.2316 | `Mul(Rank(ret_24),Rank(mark_minus_index))` |
| `crypto_a3_1h_005` | `1h` | 3 | 1 | `basis_funding_state` | 0.2270 | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_1h_006` | `1h` | 1 | 1 | `price_basis_confirmation` | 0.2185 | `Mul(Rank(ret_6),Rank(mark_minus_index))` |
| `crypto_a3_1h_007` | `1h` | 1 | 1 | `price_momentum_continuation` | 0.2138 | `Rank(ret_3)` |
| `crypto_a3_1h_008` | `1h` | 5 | 3 | `price_basis_confirmation` | 0.2131 | `Mul(Rank(ret_24),Rank(mark_index_ratio))` |
| `crypto_a3_1h_009` | `1h` | 2 | 1 | `price_momentum_continuation` | 0.2084 | `Rank(ret_24)` |
| `crypto_a3_1h_010` | `1h` | 5 | 3 | `basis_funding_state` | 0.2069 | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_5m_018` | `5m` | 1 | 1 | `price_funding_state` | 0.2019 | `Mul(Rank(ret_1),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_5m_019` | `5m` | 8 | 1 | `basis_funding_state` | 0.2008 | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_1h_011` | `1h` | 2 | 12 | `price_funding_state` | 0.1938 | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` |
| `crypto_a3_5m_020` | `5m` | 4 | 1 | `basis_premium_continuation` | 0.1935 | `Rank(mark_minus_index)` |
| `crypto_a3_1h_012` | `1h` | 1 | 1 | `price_basis_confirmation` | 0.1883 | `Mul(Rank(ret_6),Rank(premium_index))` |
| `crypto_a3_1h_013` | `1h` | 4 | 1 | `price_basis_confirmation` | 0.1849 | `Mul(Rank(ret_3),Rank(premium_index))` |
| `crypto_a3_1h_014` | `1h` | 2 | 3 | `price_basis_confirmation` | 0.1808 | `Mul(Rank(ret_12),Rank(mark_minus_index))` |
| `crypto_a3_1h_015` | `1h` | 4 | 1 | `momentum_volatility_state` | 0.1661 | `Mul(Rank(ret_24),ZScore(realized_vol_6))` |
| `crypto_a3_1h_016` | `1h` | 2 | 3 | `price_basis_confirmation` | 0.1578 | `Mul(Rank(ret_12),Rank(mark_index_ratio))` |
| `crypto_a3_1h_017` | `1h` | 4 | 12 | `momentum_liquidity_state` | 0.1547 | `Mul(Rank(ret_24),ZScore(avg_trade_size_quote))` |
| `crypto_a3_1h_018` | `1h` | 2 | 6 | `price_basis_confirmation` | 0.1536 | `Mul(Rank(hl_range),Rank(mark_index_ratio))` |
| `crypto_a3_1h_019` | `1h` | 2 | 6 | `price_funding_state` | 0.1530 | `Mul(Rank(hl_range),ZScore(funding_rate_persistence_3))` |
| `crypto_a3_1h_020` | `1h` | 1 | 12 | `price_basis_confirmation` | 0.1446 | `Mul(Rank(hl_range),Rank(premium_index))` |

## Representative Motif Counts

- `basis_funding_state`: 5
- `basis_premium_continuation`: 6
- `momentum_liquidity_state`: 3
- `momentum_volatility_state`: 7
- `price_basis_confirmation`: 15
- `price_funding_state`: 8
- `price_momentum_continuation`: 9

## Boundary

- A3 clusters are signal-correlation clusters over recent-OOS sampled vectors.
- This prevents counting many near-duplicate replay candidates as independent alpha.
- This is still not production alpha proof; next step is cluster-level holdout/stress and cost-aware book construction.
