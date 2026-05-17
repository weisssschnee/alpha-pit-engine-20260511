# Phase3P Historical Analog Regime Replay

- decision: `HOLD_R3_POST_2025_REGIME_ONLY`
- fixed_gate: `R3_liquidity_low`
- threshold: `0.9888283511695009`
- book: `candidate_book_6`

## Window Metrics

| window | calendar days | active days | active ratio | full ann | active ann | inactive ann | active sharpe | active max dd |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all_history_2020_2026 | 1525 | 790 | 0.518033 | -0.036693 | -0.069625 | -0.306419 | -0.373156 | -0.51253624 |
| historical_2020_2024 | 1204 | 625 | 0.519103 | -0.092528 | -0.170617 | -0.3375 | -0.992299 | -0.479147 |
| train_2025h2 | 126 | 42 | 0.333333 | 0.149494 | 0.518517 | 0.216182 | 1.839216 | -0.06434914 |
| recent_oos_2026 | 78 | 38 | 0.487179 | 1.175657 | 3.918442 | -0.361992 | 6.815622 | -0.03442312 |
| recent_2025h2_2026 | 204 | 80 | 0.392157 | 0.467349 | 1.655585 | -0.012133 | 4.18714 | -0.06434914 |

## Interpretation

- This replay applies the 2025H2 R3 threshold to earlier history without retuning.
- If historical analog states exist but do not work, R3 should be treated as a recent structural-regime gate, not a long-history universal regime.
- This is a regime explanation audit, not a new alpha search.
