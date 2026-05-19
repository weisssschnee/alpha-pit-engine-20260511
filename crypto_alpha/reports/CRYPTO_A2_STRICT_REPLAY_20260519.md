# Crypto A2 Strict Replay

- started_at: `2026-05-19T06:12:32Z`
- finished_at: `2026-05-19T06:15:03Z`
- decision: `PASS_A2_STRICT_REPLAY`
- candidates evaluated: `235`
- counts by decision: `{'KEEP_REPLAY_CANDIDATE': 194, 'HOLD_RESEARCH': 41}`
- output csv: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_strict_replay\crypto_a2_strict_replay_20260519.csv`

## Top KEEP Candidates

| interval | horizon | motif | expression | val IC | recent IC | val LS ann | recent LS ann | turnover recent | score proxy |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 0.0323 | 0.0289 | 7.5136 | 4.7849 | 0.9326 | 0.4169 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(premium_index))` | 0.0310 | 0.0289 | 7.2576 | 4.8010 | 1.0290 | 0.4150 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(mark_index_ratio))` | 0.0301 | 0.0301 | 6.9733 | 5.0887 | 0.8730 | 0.4145 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(mark_index_ratio))` | 0.0294 | 0.0296 | 7.0057 | 4.9940 | 0.9749 | 0.4139 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_1),Rank(premium_index))` | 0.0309 | 0.0263 | 8.3843 | 4.2023 | 1.3273 | 0.4128 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_1),Rank(mark_index_ratio))` | 0.0305 | 0.0278 | 7.7018 | 4.4298 | 1.2865 | 0.4103 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 0.0308 | 0.0331 | 4.0247 | 3.0317 | 0.9326 | 0.4090 |
| `5m` | 1 | `basis_premium_continuation` | `Rank(mark_index_ratio)` | 0.0236 | 0.0183 | 6.7934 | 2.6549 | 0.8461 | 0.4048 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(premium_index))` | 0.0278 | 0.0317 | 3.3268 | 2.9056 | 1.0289 | 0.4047 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_12),Rank(premium_index))` | 0.0277 | 0.0311 | 3.2501 | 2.8432 | 0.8688 | 0.4025 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(mark_index_ratio))` | 0.0279 | 0.0333 | 3.3554 | 3.0232 | 0.8730 | 0.4011 |
| `5m` | 1 | `basis_premium_continuation` | `Rank(premium_index)` | 0.0240 | 0.0177 | 6.9754 | 2.5863 | 0.9458 | 0.3994 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_6)` | 0.0245 | 0.0273 | 3.3344 | 4.5841 | 0.6566 | 0.3983 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_3)` | 0.0246 | 0.0280 | 3.6199 | 4.2240 | 0.8887 | 0.3956 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(mark_index_ratio))` | 0.0259 | 0.0320 | 2.9520 | 2.8627 | 0.9749 | 0.3953 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_12),Rank(mark_index_ratio))` | 0.0256 | 0.0310 | 2.7396 | 2.7339 | 0.8015 | 0.3903 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_1)` | 0.0248 | 0.0252 | 5.4240 | 3.4044 | 1.4909 | 0.3885 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 0.0291 | 0.0317 | 3.0475 | 1.8707 | 0.9326 | 0.3767 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_12),Rank(premium_index))` | 0.0249 | 0.0324 | 2.4089 | 1.9299 | 0.8688 | 0.3738 |
| `5m` | 3 | `price_momentum_continuation` | `Rank(ret_6)` | 0.0278 | 0.0369 | 2.1586 | 3.1519 | 0.6566 | 0.3728 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(premium_index))` | 0.0247 | 0.0297 | 2.5899 | 1.7875 | 1.0289 | 0.3686 |
| `5m` | 3 | `basis_premium_continuation` | `Rank(mark_index_ratio)` | 0.0167 | 0.0148 | 2.6241 | 1.5125 | 0.8460 | 0.3655 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_12)` | 0.0221 | 0.0232 | 2.4223 | 3.3142 | 0.4848 | 0.3648 |
| `5m` | 3 | `basis_premium_continuation` | `Rank(premium_index)` | 0.0198 | 0.0146 | 3.2065 | 1.2921 | 0.9458 | 0.3631 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(mark_index_ratio))` | 0.0257 | 0.0327 | 2.4850 | 1.8745 | 0.8729 | 0.3627 |
| `5m` | 3 | `price_momentum_continuation` | `Rank(ret_1)` | 0.0243 | 0.0268 | 2.6041 | 2.3154 | 1.4909 | 0.3619 |
| `5m` | 1 | `momentum_liquidity_state` | `Mul(Rank(ret_3),ZScore(avg_trade_size_quote))` | 0.0174 | 0.0142 | 2.1996 | 1.5792 | 0.4697 | 0.3587 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_12),Rank(mark_index_ratio))` | 0.0227 | 0.0328 | 1.9998 | 1.8612 | 0.8015 | 0.3564 |
| `5m` | 6 | `price_momentum_continuation` | `Rank(ret_6)` | 0.0332 | 0.0377 | 2.3836 | 2.1198 | 0.6566 | 0.3559 |
| `5m` | 1 | `momentum_liquidity_state` | `Mul(Rank(ret_6),ZScore(avg_trade_size_quote))` | 0.0165 | 0.0144 | 1.8965 | 1.5091 | 0.3980 | 0.3556 |
| `5m` | 3 | `price_momentum_continuation` | `Rank(ret_3)` | 0.0252 | 0.0356 | 1.7961 | 2.7857 | 0.8886 | 0.3541 |
| `5m` | 6 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(mark_index_ratio))` | 0.0223 | 0.0306 | 2.0878 | 1.7780 | 0.9749 | 0.3518 |
| `5m` | 3 | `price_momentum_continuation` | `Rank(ret_12)` | 0.0230 | 0.0335 | 1.8313 | 2.3799 | 0.4848 | 0.3374 |
| `5m` | 6 | `price_momentum_continuation` | `Rank(ret_3)` | 0.0272 | 0.0351 | 1.7466 | 1.8457 | 0.8886 | 0.3240 |
| `5m` | 1 | `price_funding_state` | `Mul(Rank(ret_6),ZScore(latest_known_funding_rate))` | 0.0084 | 0.0077 | 1.7196 | 1.2440 | 0.3079 | 0.3237 |
| `5m` | 6 | `price_momentum_continuation` | `Rank(ret_12)` | 0.0268 | 0.0378 | 1.7057 | 1.7709 | 0.4847 | 0.3168 |
| `5m` | 3 | `momentum_liquidity_state` | `Mul(Rank(ret_6),ZScore(avg_trade_size_quote))` | 0.0214 | 0.0219 | 1.2689 | 1.1894 | 0.3979 | 0.3140 |
| `5m` | 12 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 0.0208 | 0.0290 | 1.5731 | 1.0868 | 0.9325 | 0.3097 |
| `5m` | 1 | `price_funding_state` | `Mul(Rank(ret_6),ZScore(funding_rate_persistence_3))` | 0.0057 | 0.0064 | 1.1752 | 1.1677 | 0.3299 | 0.3086 |
| `5m` | 3 | `price_funding_state` | `Mul(Rank(ret_6),ZScore(latest_known_funding_rate))` | 0.0115 | 0.0117 | 1.1929 | 1.2728 | 0.3079 | 0.3078 |

## Decision Counts By Motif

| motif | HOLD_RESEARCH | KEEP_REPLAY_CANDIDATE |
|---|---:|---:|
| `basis_funding_state` | 1 | 31 |
| `basis_premium_continuation` | 4 | 19 |
| `momentum_liquidity_state` | 3 | 13 |
| `momentum_taker_flow_diagnostic` | 4 | 0 |
| `momentum_volatility_state` | 14 | 18 |
| `price_basis_confirmation` | 3 | 45 |
| `price_funding_state` | 1 | 47 |
| `price_momentum_continuation` | 11 | 21 |

## Bias / Scope Notes

- Candidate direction is selected only from the train window.
- Validation and recent-OOS use fixed train orientation.
- No recent-only positioning fields are evaluated.
- `fwd_ret_*` columns are labels only.
- This is strict replay for A1 candidates, not cluster-level alpha proof.
