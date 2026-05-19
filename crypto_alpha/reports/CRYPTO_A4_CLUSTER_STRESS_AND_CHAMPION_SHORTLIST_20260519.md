# Crypto A4 Cluster Stress And Champion Shortlist

- generated_at: `2026-05-19T07:18:48Z`
- decision: `PASS_A4_CHAMPION_SHORTLIST_WITH_LIMITS`
- input A2.6 keep candidates: `19`
- signal clusters: `9`
- grade counts: `{'Grade_B': 5, 'Grade_A': 4}`
- champion shortlist count: `9`

## Interpretation

A4 is run only on A2.6 tradable candidates. The broad A2/A3 proxy pool is intentionally excluded from champion grading.

## Champion Shortlist

| grade | cluster | interval | members | horizon | motif | recent net 5bp | recent net 10bp | turnover | max symbol share | expression |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---|
| `Grade_A` | `crypto_a4_1h_001` | `1h` | 3 | 6 | `price_funding_state` | 0.5488 | 0.3087 | 0.3289 | 0.105 | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` |
| `Grade_A` | `crypto_a4_1h_002` | `1h` | 5 | 12 | `basis_funding_state` | 0.5363 | 0.3412 | 0.5344 | 0.120 | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` |
| `Grade_A` | `crypto_a4_1h_003` | `1h` | 1 | 6 | `basis_funding_state` | 0.4653 | 0.3325 | 0.1803 | 0.136 | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` |
| `Grade_A` | `crypto_a4_1h_004` | `1h` | 2 | 12 | `price_funding_state` | 0.3514 | 0.1787 | 0.4732 | 0.106 | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` |
| `Grade_B` | `crypto_a4_5m_001` | `5m` | 1 | 12 | `price_funding_state` | 0.3522 | -0.4510 | 0.1834 | 0.104 | `Mul(Rank(ret_24),ZScore(latest_known_funding_rate))` |
| `Grade_B` | `crypto_a4_1h_006` | `1h` | 2 | 12 | `basis_funding_state` | 0.3235 | 0.1205 | 0.5490 | 0.121 | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` |
| `Grade_B` | `crypto_a4_1h_005` | `1h` | 2 | 6 | `price_funding_state` | 0.2774 | 0.0647 | 0.2880 | 0.110 | `Mul(Rank(ret_12),ZScore(funding_rate_persistence_3))` |
| `Grade_B` | `crypto_a4_1h_008` | `1h` | 1 | 12 | `price_momentum_continuation` | 0.2675 | 0.1355 | 0.3617 | 0.112 | `Rank(ret_24)` |
| `Grade_B` | `crypto_a4_1h_007` | `1h` | 2 | 12 | `price_funding_state` | 0.2044 | 0.0198 | 0.4992 | 0.113 | `Mul(Rank(hl_range),ZScore(funding_rate_persistence_3))` |

## Boundary

- Grade A/B here means daily/1h research champion candidate after tradable proxy replay; it is not production alpha proof.
- Static core12 universe and real exchange slippage/capacity remain unresolved.
- If champions are dominated by funding motifs, the next stage should stress funding semantics and fee timing before expanding search.
