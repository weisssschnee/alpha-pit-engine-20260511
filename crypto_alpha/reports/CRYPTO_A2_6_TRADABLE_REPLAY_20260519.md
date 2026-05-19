# Crypto A2.6 Tradable Replay

- generated_at: `2026-05-19T07:15:12Z`
- decision: `PASS_A2_6_TRADABLE_REPLAY_WITH_CANDIDATES`
- scope: next-bar tradable label, purge/embargo, funding-fee-adjusted target, cost stress, placebo gate, simple baseline ablation

## Executive Finding

A2.6 replaces the A2 close-to-close proxy with a next-open tradable proxy and applies stricter retention gates. This is still research replay, not production execution proof.

## Alignment Contract

| field | rule |
|---|---|
| feature_available_time | signal bar close |
| signal_time | signal bar close |
| execution_time | next bar open |
| label_start_time | next bar open |
| label_end_time | next bar open + horizon bars |
| funding adjustment | sum known funding events across holding window subtracted from long return |
| purge/embargo | `12` bars at split edges |

## Decision Counts

- total candidates: `235`
- counts by decision: `{'HOLD_RESEARCH': 201, 'KEEP_A2_6_TRADABLE_CANDIDATE': 19, 'HOLD_BASELINE_EXPLAINED': 9, 'HOLD_PLACEBO_FAIL': 6}`
- output csv: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_6_tradable_replay\crypto_a2_6_tradable_replay_20260519.csv`
- placebo csv: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_6_tradable_replay\crypto_a2_6_placebo_gate_20260519.csv`

## Cost Survival

| cost tier | positive recent count | positive recent rate | median recent net annualized |
|---|---:|---:|---:|
| `low_1bp` | 153 | 0.651 | 0.1970 |
| `normal_5bp` | 53 | 0.226 | -1.3504 |
| `stress_2x_10bp` | 27 | 0.115 | -3.3859 |
| `stress_5x_25bp` | 2 | 0.009 | -9.6386 |

## Top A2.6 Tradable Candidates

| interval | horizon | motif | expression | val net 5bp ann | recent net 5bp ann | recent turnover | ablation margin | score |
|---|---:|---|---|---:|---:|---:|---:|---:|
| `1h` | 6 | `price_funding_state` | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` | 0.7942 | 0.5488 | 0.3289 | 0.5048 | 0.4578 |
| `1h` | 12 | `basis_funding_state` | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` | 0.6792 | 0.5363 | 0.5344 | 0.7472 | 0.4454 |
| `1h` | 6 | `basis_funding_state` | `Mul(Rank(mark_minus_index),ZScore(latest_known_funding_rate))` | 0.6595 | 0.5452 | 0.2159 | 0.6547 | 0.4351 |
| `1h` | 12 | `basis_funding_state` | `Mul(Rank(premium_index),ZScore(latest_known_funding_rate))` | 0.6166 | 0.4429 | 0.5600 | 0.7170 | 0.4078 |
| `1h` | 12 | `price_funding_state` | `Mul(Rank(ret_24),ZScore(latest_known_funding_rate))` | 0.7263 | 0.4706 | 0.2774 | 0.2030 | 0.3920 |
| `1h` | 6 | `basis_funding_state` | `Mul(Rank(mark_index_ratio),ZScore(latest_known_funding_rate))` | 0.5968 | 0.3473 | 0.5343 | 0.9252 | 0.3730 |
| `1h` | 12 | `price_funding_state` | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` | 0.5375 | 0.3514 | 0.4732 | 0.3829 | 0.3613 |
| `1h` | 3 | `price_funding_state` | `Mul(Rank(ret_12),ZScore(latest_known_funding_rate))` | 0.4404 | 0.4010 | 0.3289 | 0.6298 | 0.3610 |
| `1h` | 3 | `basis_funding_state` | `Mul(Rank(mark_minus_index),ZScore(latest_known_funding_rate))` | 0.2304 | 0.5189 | 0.2159 | 0.6876 | 0.3572 |
| `1h` | 6 | `basis_funding_state` | `Mul(Rank(mark_minus_index),ZScore(funding_rate_persistence_3))` | 0.2575 | 0.4653 | 0.1803 | 0.5748 | 0.3552 |
| `1h` | 6 | `price_funding_state` | `Mul(Rank(ret_12),ZScore(funding_rate_persistence_3))` | 0.5319 | 0.2774 | 0.2880 | 0.2333 | 0.3241 |
| `1h` | 12 | `basis_funding_state` | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` | 0.1331 | 0.3235 | 0.5490 | 0.5344 | 0.2972 |
| `5m` | 12 | `price_funding_state` | `Mul(Rank(ret_24),ZScore(latest_known_funding_rate))` | 0.1953 | 0.3522 | 0.1834 | 0.6920 | 0.2935 |
| `1h` | 3 | `price_funding_state` | `Mul(Rank(ret_12),ZScore(funding_rate_persistence_3))` | 0.4032 | 0.1694 | 0.2880 | 0.3983 | 0.2820 |
| `1h` | 6 | `price_funding_state` | `Mul(Rank(hl_range),ZScore(latest_known_funding_rate))` | 0.3535 | 0.1886 | 0.4732 | 0.5876 | 0.2795 |
| `1h` | 6 | `basis_funding_state` | `Mul(Rank(mark_index_ratio),ZScore(funding_rate_persistence_3))` | 0.3105 | 0.1395 | 0.5489 | 0.7173 | 0.2661 |
| `1h` | 12 | `price_funding_state` | `Mul(Rank(hl_range),ZScore(funding_rate_persistence_3))` | 0.2664 | 0.2044 | 0.4992 | 0.2359 | 0.2494 |
| `1h` | 6 | `price_funding_state` | `Mul(Rank(hl_range),ZScore(funding_rate_persistence_3))` | 0.2174 | 0.0782 | 0.4991 | 0.4772 | 0.2182 |
| `1h` | 12 | `price_momentum_continuation` | `Rank(ret_24)` | 0.2227 | 0.2675 | 0.3617 | 0.0000 | 0.1248 |

## Gate Notes

- A candidate must have positive validation/recent IC, positive validation/recent net annualized under normal 5bp, pass placebo, and beat low-order components if composite.
- Static core12 universe remains a production blocker; A2.6 only addresses tradable label/cost/replay linkage.
- A4 champion shortlist remains blocked if keep count is too small or dominated by one motif/frequency.
