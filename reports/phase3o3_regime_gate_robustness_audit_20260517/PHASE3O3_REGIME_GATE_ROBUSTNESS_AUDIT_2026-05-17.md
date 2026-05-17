# Phase3O3 Regime Gate Robustness Audit

- decision: `PASS_STRICT_REGIME_GATE_ROBUSTNESS`
- primary_pass_gates: `R3_liquidity_low,R5_vol_or_trendlow_or_liqlow,R6_at_least_2_of_vol_trend_liq`
- random_draws: `1000`
- block_draws: `1000`

## Robustness Summary

| gate | true ann | active ratio | random p95 | block p95 | circular p95 | inverted ann | pass count | decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| R3_liquidity_low | 1.175657 | 0.487179 | 0.933008 | 0.9983 | 1.098173 | -0.205755 | 3 | PASS_STRICT_GATE_ROBUSTNESS |
| R5_vol_or_trendlow_or_liqlow | 1.12819 | 0.666667 | 0.998501 | 0.942271 | 1.112831 | -0.18797 | 3 | PASS_STRICT_GATE_ROBUSTNESS |
| R6_at_least_2_of_vol_trend_liq | 0.983379 | 0.551282 | 0.932219 | 0.970535 | 1.119395 | -0.128464 | 2 | PASS_STRICT_GATE_ROBUSTNESS |
| R1_volatility_high | 0.936759 | 0.602564 | 1.002085 | 0.895563 | 1.097095 | -0.107418 | 1 | HOLD_STRICT_GATE_ROBUSTNESS |
| R2_trend_low | 0.590611 | 0.448718 | 0.807392 | 0.91899 | 1.017133 | 0.087316 | 0 | HOLD_STRICT_GATE_ROBUSTNESS |
| F1_breadth_low_failed_control | -0.011777 | 0.371795 | 0.774509 | 0.741615 | 0.829881 | 0.749793 | 0 | HOLD_STRICT_GATE_ROBUSTNESS |
| F2_trend_high_failed_control | -0.011854 | 0.307692 | 0.645939 | 0.728816 | 0.769324 | 0.749928 | 0 | HOLD_STRICT_GATE_ROBUSTNESS |
| F3_liquidity_high_failed_control | -0.060578 | 0.205128 | 0.490547 | 0.559761 | 0.558409 | 0.840462 | 0 | HOLD_STRICT_GATE_ROBUSTNESS |

## Interpretation

- Random active-day placebo tests whether the gate beats random days with the same active count.
- Block-run placebo preserves active run lengths but randomizes their position.
- Circular shift preserves the full active/inactive sequence and tests timing alignment within 2026.
- A gate can be useful even if it fails circular-shift p95, but then the evidence is weaker and should be called timing-sensitive.
