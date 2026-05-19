# Crypto A7C FundingCore Narrow Audit

- generated_at: `2026-05-19T12:18:23Z`
- decision: `HOLD_FUNDINGCORE_ALPHA_SHADOW_PROOF`
- status: `fundingcore_research_baseline_only`
- blockers: `['fresh_may_10bp_negative']`
- warnings: `['validation_drawdown_large', 'recent_oos_drawdown_large', 'fresh_may_drawdown_large', 'future_wrong_lag_diagnostic_stronger_than_live_lag']`
- risk_variant: `R3_vol_target_gross_0p5x_cap`
- purge_embargo_bars: `24`

## Candidate Factor Review

- factor_id: `FundingCore_v1`
- provenance: A7B simple baseline, not new search
- operator path: cross-sectional z-score/rank of latest-known funding rate and 3-step funding persistence; top/bottom 3 long-short basket; next-open execution proxy
- data source: Binance core12 futures 1h gold panel plus funding history
- feature family: funding/carry regime
- discovery status: diagnostic/reproduction of A7B baseline, no discovery credit

## FundingCore Fixed-Split Performance

| cost | split | ann mean | compounded DD | month pass | mean gross | mean turnover |
|---|---|---:|---:|---:|---:|---:|
| `normal_5bp` | `validation_2025H1` | 2.0989 | -0.3742 | 0.833 | 0.493 | 0.029 |
| `normal_5bp` | `recent_oos_2025H2_2026Apr` | 0.9238 | -0.6122 | 0.800 | 0.495 | 0.031 |
| `normal_5bp` | `fresh_forward_2026May` | -2.7136 | -0.1799 | 0.000 | 0.500 | 0.033 |
| `stress_10bp` | `validation_2025H1` | 1.9697 | -0.3767 | 0.833 | 0.493 | 0.029 |
| `stress_10bp` | `recent_oos_2025H2_2026Apr` | 0.7863 | -0.6195 | 0.800 | 0.495 | 0.031 |
| `stress_10bp` | `fresh_forward_2026May` | -2.8562 | -0.1808 | 0.000 | 0.500 | 0.033 |
| `severe_20bp` | `validation_2025H1` | 1.7112 | -0.3876 | 0.833 | 0.493 | 0.029 |
| `severe_20bp` | `recent_oos_2025H2_2026Apr` | 0.5113 | -0.6336 | 0.700 | 0.495 | 0.031 |
| `severe_20bp` | `fresh_forward_2026May` | -3.1414 | -0.1828 | 0.000 | 0.500 | 0.033 |

## Placebo / Wrong-Lag Audit

| object | split | ann mean | compounded DD | month pass |
|---|---|---:|---:|---:|
| `sign_flip` | `validation_2025H1` | -1.7387 | -0.7104 | 0.333 |
| `sign_flip` | `recent_oos_2025H2_2026Apr` | -1.6368 | -0.7906 | 0.100 |
| `sign_flip` | `fresh_forward_2026May` | 2.7199 | -0.1673 | 1.000 |
| `wrong_lag_stale_24h` | `validation_2025H1` | 0.5809 | -0.6265 | 0.667 |
| `wrong_lag_stale_24h` | `recent_oos_2025H2_2026Apr` | 0.1183 | -0.5334 | 0.500 |
| `wrong_lag_stale_24h` | `fresh_forward_2026May` | -5.3327 | -0.2207 | 0.000 |
| `wrong_lag_future_24h_diagnostic` | `validation_2025H1` | 8.9024 | -0.1035 | 1.000 |
| `wrong_lag_future_24h_diagnostic` | `recent_oos_2025H2_2026Apr` | 5.8932 | -0.1671 | 1.000 |
| `wrong_lag_future_24h_diagnostic` | `fresh_forward_2026May` | 7.8438 | -0.0224 | 1.000 |
| `row_shuffle` | `validation_2025H1` | -2.1003 | -0.6718 | 0.000 |
| `row_shuffle` | `recent_oos_2025H2_2026Apr` | -2.9617 | -0.9150 | 0.000 |
| `row_shuffle` | `fresh_forward_2026May` | -2.9637 | -0.1247 | 0.000 |
| `time_shuffle` | `validation_2025H1` | -2.4979 | -0.7135 | 0.000 |
| `time_shuffle` | `recent_oos_2025H2_2026Apr` | -2.6945 | -0.8936 | 0.000 |
| `time_shuffle` | `fresh_forward_2026May` | -2.9471 | -0.1245 | 0.000 |

## Component Standalone Audit

| component | split | ann mean | compounded DD | month pass |
|---|---|---:|---:|---:|
| `funding_rate_h6` | `validation_2025H1` | 1.2089 | -0.3652 | 0.667 |
| `funding_rate_h6` | `recent_oos_2025H2_2026Apr` | 0.8061 | -0.4763 | 0.700 |
| `funding_rate_h6` | `fresh_forward_2026May` | -2.0725 | -0.1211 | 0.000 |
| `funding_rate_h12` | `validation_2025H1` | 2.2611 | -0.5042 | 0.500 |
| `funding_rate_h12` | `recent_oos_2025H2_2026Apr` | 1.5673 | -0.6911 | 0.800 |
| `funding_rate_h12` | `fresh_forward_2026May` | -3.1757 | -0.2517 | 0.000 |
| `funding_persistence_h6` | `validation_2025H1` | 1.9063 | -0.3791 | 0.833 |
| `funding_persistence_h6` | `recent_oos_2025H2_2026Apr` | 0.1861 | -0.4573 | 0.600 |
| `funding_persistence_h6` | `fresh_forward_2026May` | -1.2750 | -0.1248 | 0.000 |
| `funding_persistence_h12` | `validation_2025H1` | 2.4392 | -0.5370 | 0.833 |
| `funding_persistence_h12` | `recent_oos_2025H2_2026Apr` | 0.7731 | -0.7293 | 0.600 |
| `funding_persistence_h12` | `fresh_forward_2026May` | -3.9913 | -0.2308 | 0.000 |

## May 2026 Failure Attribution

| object | May total | May ann proxy | worst hour | top3 loss sum | mean turnover |
|---|---:|---:|---:|---:|---:|
| `FundingCore` | -0.1066 | -2.1215 | -0.0081 | -0.0222 | 0.0331 |

## Symbol LOO Summary

- recent_oos_symbol_loo_positive_rate: `1.0`
- recent_oos_symbol_loo_min_ann: `1.692624937165766`

## Bias Audit Decision

- lookahead: latest-known funding only; A7.0 split/linkage ledger applies
- costs: 5/10/20bps included; 10bps is primary
- OOS: validation, recent OOS, fresh May, symbol LOO
- status: HOLD unless fresh-forward and drawdown issues are cleared

## Interpretation

- FundingCore is a necessary benchmark for crypto reward design.
- This audit does not search, tune, or promote paper/live trading.
- If FundingCore beats Core4 but fails fresh May or drawdown, it remains a research baseline, not an alpha shadow proof.
