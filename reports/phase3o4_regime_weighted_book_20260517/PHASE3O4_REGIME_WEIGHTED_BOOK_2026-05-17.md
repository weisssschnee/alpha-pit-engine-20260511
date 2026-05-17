# Phase3O4 Regime Weighted Book Diagnostic

- decision: `PASS_REGIME_WEIGHTED_DIAGNOSTIC_COMPLETED`
- scope: `fixed_regime_gates_non_oracle_variants_walk_forward_weighting_diagnostic`
- train_window: `2025-07-01` to `2025-12-31`
- oos_window: `2026-01-01` to `2026-05-08`

## Top Equal-Weight Gated Variants

| variant | gate | ann | sharpe | sortino | max dd | active ratio | total return |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| X1_research_9 | R3_liquidity_low | 1.272218 | 4.491351 | 5.515173 | -0.03901198 | 0.487179 | 0.282624 |
| X1_research_9 | R5_vol_or_trendlow_or_liqlow | 1.241418 | 3.828726 | 6.735137 | -0.05255119 | 0.666667 | 0.275048 |
| X4_official_6_plus_003_minus_002 | R3_liquidity_low | 1.233439 | 4.654946 | 6.009817 | -0.03200173 | 0.487179 | 0.276518 |
| X2_official_6_plus_003 | R3_liquidity_low | 1.232187 | 4.600898 | 5.871958 | -0.03557461 | 0.487179 | 0.276165 |
| X2_official_6_plus_003 | R5_vol_or_trendlow_or_liqlow | 1.203128 | 3.933869 | 7.199791 | -0.04481682 | 0.666667 | 0.269071 |
| X4_official_6_plus_003_minus_002 | R5_vol_or_trendlow_or_liqlow | 1.191343 | 3.957584 | 7.268331 | -0.04254272 | 0.666667 | 0.267166 |
| X0_official_6 | R3_liquidity_low | 1.175657 | 4.547115 | 6.085254 | -0.03442312 | 0.487179 | 0.266314 |
| X3_official_6_minus_002 | R3_liquidity_low | 1.165981 | 4.600731 | 6.134402 | -0.02990281 | 0.487179 | 0.264765 |
| X0_official_6 | R5_vol_or_trendlow_or_liqlow | 1.128189 | 3.827856 | 7.265461 | -0.04184402 | 0.666667 | 0.255818 |
| X3_official_6_minus_002 | R5_vol_or_trendlow_or_liqlow | 1.099947 | 3.833085 | 6.976988 | -0.03851379 | 0.666667 | 0.250918 |
| X2_official_6_plus_003 | R6_at_least_2_of_vol_trend_liq | 1.020856 | 3.859625 | 5.847291 | -0.04907499 | 0.551282 | 0.23695 |
| X4_official_6_plus_003_minus_002 | R6_at_least_2_of_vol_trend_liq | 1.017561 | 3.885428 | 5.969975 | -0.04665385 | 0.551282 | 0.236439 |
| X1_research_9 | R6_at_least_2_of_vol_trend_liq | 1.012706 | 3.647691 | 5.280076 | -0.05723822 | 0.551282 | 0.234727 |
| X0_official_6 | R6_at_least_2_of_vol_trend_liq | 0.983379 | 3.842269 | 6.113946 | -0.0466799 | 0.551282 | 0.23008 |
| X3_official_6_minus_002 | R6_at_least_2_of_vol_trend_liq | 0.972102 | 3.870404 | 6.053715 | -0.04328902 | 0.551282 | 0.228098 |

## Top Walk-Forward Weighted Gated Variants

| variant | gate | lookback | ann | sharpe | sortino | max dd | active ratio | total return |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| X1_research_9 | R3_liquidity_low | 120 | 1.268388 | 4.401581 | 5.187846 | -0.03925991 | 0.487179 | 0.281712 |
| X2_official_6_plus_003 | R3_liquidity_low | 120 | 1.237842 | 4.463512 | 5.29192 | -0.03701894 | 0.487179 | 0.276751 |
| X1_research_9 | R5_vol_or_trendlow_or_liqlow | 120 | 1.237762 | 3.830322 | 6.417864 | -0.0527007 | 0.666667 | 0.274445 |
| X4_official_6_plus_003_minus_002 | R3_liquidity_low | 120 | 1.235599 | 4.495288 | 5.603248 | -0.03465216 | 0.487179 | 0.276462 |
| X1_research_9 | R3_liquidity_low | 90 | 1.221756 | 4.308907 | 5.079161 | -0.04373415 | 0.487179 | 0.273551 |
| X2_official_6_plus_003 | R5_vol_or_trendlow_or_liqlow | 120 | 1.20479 | 3.89218 | 6.498523 | -0.04691783 | 0.666667 | 0.269182 |
| X4_official_6_plus_003_minus_002 | R5_vol_or_trendlow_or_liqlow | 120 | 1.197576 | 3.911173 | 6.921268 | -0.04539747 | 0.666667 | 0.26804 |
| X1_research_9 | R5_vol_or_trendlow_or_liqlow | 90 | 1.188949 | 3.665046 | 6.309413 | -0.05797634 | 0.666667 | 0.265485 |
| X4_official_6_plus_003_minus_002 | R3_liquidity_low | 90 | 1.188737 | 4.380025 | 5.292813 | -0.04048133 | 0.487179 | 0.268122 |
| X2_official_6_plus_003 | R3_liquidity_low | 90 | 1.182658 | 4.351566 | 5.168211 | -0.04234575 | 0.487179 | 0.266992 |
| X0_official_6 | R3_liquidity_low | 90 | 1.151711 | 4.44893 | 5.856593 | -0.0345351 | 0.487179 | 0.261897 |
| X3_official_6_minus_002 | R3_liquidity_low | 90 | 1.15066 | 4.511792 | 5.997035 | -0.03007583 | 0.487179 | 0.261876 |
| X2_official_6_plus_003 | R5_vol_or_trendlow_or_liqlow | 90 | 1.147427 | 3.700164 | 6.391828 | -0.05337325 | 0.666667 | 0.258592 |
| X4_official_6_plus_003_minus_002 | R5_vol_or_trendlow_or_liqlow | 90 | 1.145979 | 3.713426 | 6.58345 | -0.0525867 | 0.666667 | 0.258404 |
| X4_official_6_plus_003_minus_002 | R3_liquidity_low | 60 | 1.142927 | 4.494618 | 5.78512 | -0.03038465 | 0.487179 | 0.260476 |
| X1_research_9 | R3_liquidity_low | 60 | 1.142056 | 4.232103 | 5.009258 | -0.04064608 | 0.487179 | 0.259604 |
| X3_official_6_minus_002 | R3_liquidity_low | 120 | 1.130426 | 4.53865 | 6.412526 | -0.02952443 | 0.487179 | 0.25839 |
| X0_official_6 | R3_liquidity_low | 120 | 1.124646 | 4.456963 | 6.050358 | -0.03277922 | 0.487179 | 0.257171 |
| X2_official_6_plus_003 | R3_liquidity_low | 60 | 1.123648 | 4.393668 | 5.556985 | -0.0346796 | 0.487179 | 0.256832 |
| X1_research_9 | R5_vol_or_trendlow_or_liqlow | 60 | 1.097932 | 3.535279 | 6.058593 | -0.05691611 | 0.666667 | 0.249296 |

## Boundaries

- This is diagnostic only. It does not promote cluster_003 or weighting rules into the formal proof book.
- Walk-forward weights use only prior cluster returns, max 30% per cluster, 50% shrinkage to equal weight.
- No formula, gate threshold, or cluster expression was tuned in this run.
