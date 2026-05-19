# Crypto A2.5 Linkage And Placebo Audit

- generated_at: `2026-05-19T07:04:11Z`
- decision: `HOLD_ALPHA_PROOF_A2_5`
- scope: A2/A3 linkage, placebo, cost, ablation, and universe audit

## Executive Finding

A2/A3 remain valid as method/search pipeline checks, but they are not alpha proof yet.
The main blockers are execution alignment, missing purge/embargo, missing funding fees, and cost sensitivity of high-turnover 5m candidates.

## 1. Time Alignment

| field | current A2 proxy | audit result |
|---|---|---|
| feature_available_time | bar close for close-derived features | known only after bar close |
| signal_time | bar close proxy | acceptable for research signal |
| execution_time | not modeled | blocker |
| label_start_time | current close in close-to-close `fwd_ret_*` | not tradable if signal is after close |
| label_end_time | future close | proxy only |

Conclusion: A2 uses close-to-close proxy labels. A tradable replay must rebuild labels from next executable bar.

## 2. Premium / Basis Label-Source Audit

- median LS annualized by target: `{'perp_last_close': 1.0456439741928358, 'mark_close': 0.9432496327557551, 'index_close': 0.3755930990090274, 'spot_close_core6': nan}`
- detail: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_5_linkage_placebo_audit\crypto_a2_5_label_source_audit.csv`

If a basis cluster only works on mark/index labels and fails on perp-last labels, it should be downgraded. Current A2 used perp-last close labels; the table above checks alternate targets for top representatives.

## 3. Funding Semantics

| interval   |    rows |   funding_rows |   future_funding_rows |   exact_funding_time_rows |   min_lag_ms |   median_lag_ms |   max_lag_ms | funding_fee_included_in_return   |
|:-----------|--------:|---------------:|----------------------:|--------------------------:|-------------:|----------------:|-------------:|:---------------------------------|
| 5m         | 2941056 |        2941056 |                     0 |                     20388 |            0 |        1.44e+07 |     2.88e+07 | False                            |
| 1h         |  245088 |         245088 |                     0 |                     20388 |            0 |        1.44e+07 |     2.88e+07 | False                            |

Funding is asof/backward and not future-dated, but exact funding-time rows exist and funding fee is not included in returns. Funding candidates stay HOLD_ALPHA_PROOF until fee-adjusted replay.

## 4. Purged / Embargoed Split

- Current split is calendar split only.
- Maximum evaluated horizon is 12 bars.
- Required next replay: purge at least max horizon around split boundaries and embargo adjacent labels.

## 5. Cost Stress

- cost summary: `{'low_1bp': {'positive_count': 128, 'positive_rate': 0.6597938144329897, 'median_net': 0.22933630071059355}, 'normal_5bp': {'positive_count': 44, 'positive_rate': 0.2268041237113402, 'median_net': -1.5081306604129614}, 'stress_2x_10bp': {'positive_count': 24, 'positive_rate': 0.12371134020618557, 'median_net': -3.641425823189504}, 'stress_5x_25bp': {'positive_count': 2, 'positive_rate': 0.010309278350515464, 'median_net': -9.964536992711832}}`
- normal 5bp negative rate: `0.773`

| interval | horizon | motif | expression | gross | net 1bp | net 5bp | net 10bp | net 25bp | turnover |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(mark_index_ratio))` | 5.089 | -4.088 | -40.796 | -86.681 | -224.335 | 0.873 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(mark_index_ratio))` | 4.994 | -5.254 | -46.248 | -97.490 | -251.215 | 0.975 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_3),Rank(premium_index))` | 4.801 | -6.016 | -49.282 | -103.364 | -265.612 | 1.029 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 4.785 | -5.019 | -44.235 | -93.255 | -240.314 | 0.933 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_6)` | 4.584 | -2.319 | -29.929 | -64.442 | -167.981 | 0.657 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_1),Rank(mark_index_ratio))` | 4.430 | -9.094 | -63.188 | -130.805 | -333.658 | 1.286 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_3)` | 4.224 | -5.118 | -42.485 | -89.193 | -229.320 | 0.889 |
| `5m` | 1 | `price_basis_confirmation` | `Mul(Rank(ret_1),Rank(premium_index))` | 4.202 | -9.751 | -65.563 | -135.327 | -344.622 | 1.327 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_1)` | 3.404 | -12.268 | -74.958 | -153.321 | -388.410 | 1.491 |
| `5m` | 1 | `price_momentum_continuation` | `Rank(ret_12)` | 3.314 | -1.782 | -22.165 | -47.645 | -124.083 | 0.485 |
| `5m` | 3 | `price_momentum_continuation` | `Rank(ret_6)` | 3.152 | 0.851 | -8.352 | -19.857 | -54.369 | 0.657 |
| `5m` | 3 | `price_basis_confirmation` | `Mul(Rank(ret_6),Rank(premium_index))` | 3.032 | -0.236 | -13.308 | -29.647 | -78.666 | 0.933 |

## 6. Simple Baseline Ablation

- summary: `{'rows': 154, 'pass_count': 55, 'pass_rate': 0.35714285714285715, 'median_marginal_ls': -0.1284663503639084}`
- detail: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_5_linkage_placebo_audit\crypto_a2_5_simple_baseline_ablation.csv`

Composite candidates that do not beat their low-order components should not be treated as new alpha structure.

## 7. Placebo

- median LS annualized by placebo: `{'original': 2.0827492073741407, 'basis_shuffle': 0.6386476366097882, 'symbol_shuffle': 0.14986951376840357, 'label_shuffle': -0.0839845695073757, 'wrong_lag_funding_future_shift': -0.47861309590226425, 'time_shift': -0.945909253769737, 'sign_flip': -2.0827492073741407}`
- detail: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_5_linkage_placebo_audit\crypto_a2_5_placebo_audit.csv`

Required interpretation: sign flip should invert; label/symbol/time/basis shuffle should degrade materially. Any candidate surviving placebo needs manual review.

## 8. Universe / Survivorship

- detail: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a2_5_linkage_placebo_audit\crypto_a2_5_universe_audit.csv`
- core12 has continuous panel coverage in this dataset.
- However, core12 is a static selected universe, not a time-varying listed/tradable universe.
- This blocks production-style claims until a universe-at-time-t policy is defined.

## Decision

`HOLD_ALPHA_PROOF_A2_5`

A4 champion shortlist is blocked. The next valid step is A2.6 tradable replay: next-bar execution labels, purged/embargoed splits, fee/funding-adjusted returns, and placebo-gated candidate retention.

## Blockers

- current A2 label is close-to-close proxy; tradable next-bar execution label is not yet used
- no purged/embargo replay has been run
- funding fee is not included in return/cost
- cost stress materially reduces high-turnover 5m candidates
- universe is static core12, not time-varying tradable universe
