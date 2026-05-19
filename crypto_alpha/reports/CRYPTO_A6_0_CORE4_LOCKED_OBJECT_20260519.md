# Crypto A6.0 Core4 Locked Object

- generated_at: `2026-05-19T07:52:32Z`
- decision: `FREEZE_CORE4_RESEARCH_OBJECT`
- object_id: `crypto_core4_locked_research_book_v1`
- object_hash: `f07b8a9387c1c80be70c29c06a22d3782710d5d46a074ece7d4a6e7c6175f33b`
- output: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\baselines\crypto_core4_locked_research_book_v1.json`

## Clusters

| cluster | horizon | motif | recent net 5bp | recent net 10bp | expression |
|---|---:|---|---:|---:|---|
| `crypto_a4_1h_001` | 6 | `price_funding_state` | 0.5389 | 0.2987 | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` |
| `crypto_a4_1h_002` | 12 | `basis_funding_state` | 0.5383 | 0.3432 | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` |
| `crypto_a4_1h_003` | 6 | `basis_funding_state` | 0.4606 | 0.3278 | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` |
| `crypto_a4_1h_004` | 12 | `price_funding_state` | 0.3514 | 0.1785 | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` |

## Boundary

- This freezes a research object only.
- It is not a production book and not live-ready.
- Next required gate: A6.1 curve/exposure sanity.
