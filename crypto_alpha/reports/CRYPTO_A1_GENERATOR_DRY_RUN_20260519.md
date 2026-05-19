# Crypto A1 Generator Dry Run

- generated_at: `2026-05-19T06:05:41Z`
- decision: `PASS_A1_GENERATOR_DRY_RUN`
- candidates total: `235`
- accepted: `235`
- rejected: `0`
- candidate jsonl: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a1_generator_dry_run\crypto_a1_candidates_20260519.jsonl`

## Counts By Interval

- `1h`: 119
- `5m`: 116

## Counts By Motif

- `basis_funding_state`: 32
- `basis_premium_continuation`: 23
- `momentum_liquidity_state`: 16
- `momentum_taker_flow_diagnostic`: 4
- `momentum_volatility_state`: 32
- `price_basis_confirmation`: 48
- `price_funding_state`: 48
- `price_momentum_continuation`: 32

## Counts By Priority

- `diagnostic`: 20
- `high`: 52
- `low`: 32
- `medium`: 131

## Top Candidate Examples

| interval | horizon | motif | priority | expression |
|---|---:|---|---|---|
| `1h` | 1 | `price_momentum_continuation` | `medium` | `Rank(ret_3)` |
| `1h` | 1 | `price_momentum_continuation` | `medium` | `Rank(ret_24)` |
| `1h` | 1 | `price_momentum_continuation` | `medium` | `Rank(ret_6)` |
| `1h` | 1 | `price_momentum_continuation` | `medium` | `Rank(ret_12)` |
| `1h` | 1 | `basis_premium_continuation` | `medium` | `Rank(premium_index)` |
| `1h` | 1 | `basis_premium_continuation` | `medium` | `Rank(mark_minus_index)` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_3),Rank(premium_index))` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_3),Rank(mark_minus_index))` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_24),Rank(premium_index))` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_24),Rank(mark_minus_index))` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_6),Rank(premium_index))` |
| `1h` | 1 | `price_basis_confirmation` | `medium` | `Mul(Rank(ret_6),Rank(mark_minus_index))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_3),ZScore(latest_known_funding_rate))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_3),ZScore(funding_rate_persistence_3))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_24),ZScore(latest_known_funding_rate))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_24),ZScore(funding_rate_persistence_3))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_6),ZScore(latest_known_funding_rate))` |
| `1h` | 1 | `price_funding_state` | `medium` | `Mul(Rank(ret_6),ZScore(funding_rate_persistence_3))` |
| `1h` | 1 | `basis_funding_state` | `medium` | `Mul(Rank(premium_index),ZScore(latest_known_funding_rate))` |
| `1h` | 1 | `basis_funding_state` | `medium` | `Mul(Rank(premium_index),ZScore(funding_rate_persistence_3))` |
| `1h` | 1 | `basis_funding_state` | `medium` | `Mul(Rank(mark_minus_index),ZScore(latest_known_funding_rate))` |
| `1h` | 1 | `basis_funding_state` | `medium` | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` |
| `1h` | 1 | `momentum_volatility_state` | `low` | `Mul(Rank(ret_3),ZScore(realized_vol_6))` |
| `1h` | 1 | `momentum_volatility_state` | `low` | `Mul(Rank(ret_3),ZScore(realized_vol_12))` |
| `1h` | 1 | `momentum_volatility_state` | `low` | `Mul(Rank(ret_24),ZScore(realized_vol_6))` |
| `1h` | 1 | `momentum_volatility_state` | `low` | `Mul(Rank(ret_24),ZScore(realized_vol_12))` |
| `1h` | 1 | `momentum_liquidity_state` | `diagnostic` | `Mul(Rank(ret_3),ZScore(avg_trade_size_quote))` |
| `1h` | 1 | `momentum_liquidity_state` | `diagnostic` | `Mul(Rank(ret_24),ZScore(avg_trade_size_quote))` |
| `1h` | 3 | `price_momentum_continuation` | `medium` | `Rank(ret_24)` |
| `1h` | 3 | `price_momentum_continuation` | `medium` | `Rank(ret_3)` |

## Blockers

- none

## Boundary

- This is metadata-only candidate generation.
- No candidate is promoted by this dry run.
- A2 strict replay must evaluate candidates on fixed train/validation/recent-OOS windows.
- CN stock generator/reward/replay logic is not used.
