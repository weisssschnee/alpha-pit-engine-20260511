# Phase3L-L Regime Proxy Audit

- generated_at: 2026-05-17T05:15:59+08:00
- decision: `PASS_PHASE3L_L_REGIME_PROXY_AUDIT_TRUE_REGIME_STILL_BLOCKED`
- scope: `daily_lagged_market_regime_proxy_not_true_regime_replay`
- survivor_count: 9
- proxy_pass_count: 9
- proxy_hold_count: 0
- axis_proxy_note: `PIT labels plus lagged trend/volatility/liquidity/limit-density quantile axes; proxy only, not true regime replay.`
- evaluation_window: 2025-07-01 to 2026-05-08

## Interpretation

- This is a lagged daily market-regime proxy audit, not true regime replay.
- Regime labels use market aggregates shifted by one trading day.
- A pass here can reduce concern about single-state dependence, but it does not clear the true regime replay blocker.

## Regime Coverage

| regime | days | mean_ew_return | mean_up_ratio | mean_liquidity_ratio | mean_limit_density |
| --- | ---: | ---: | ---: | ---: | ---: |
| limit_density_high | 171 | 0.000918 | 0.481844 | 0.993895 | 0.020363 |
| unknown_warmup | 9 | 0.00481 | 0.52794 | nan | 0.014794 |

## Cluster Summary

| global_cluster | source_cluster | decision | usable_axes | pass_axes | worst_regime | min_mean | dominant_share | expression |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| cluster_001 | s47_cluster_005 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 2 | volatility_lag_quantile:vol_mid | -0.00098084 | 0.833323 | `CSRank(ZScore(Mean(Abs(Delta($vwap,1)),21)))` |
| cluster_005 | s47_cluster_005 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 3 | trend_lag_quantile:trend_mid | -0.00096647 | 0.490701 | `CSRank(Mul(CSRank(Std($open,8)),ZScore(Mean(Abs(Delta($vwap,1)),21))))` |
| cluster_008 | s50_cluster_005 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 2 | volatility_lag_quantile:vol_mid | -0.00189504 | 0.689632 | `CSRank(Mul(CSRank(Mul(ZScore(Mean($amount,34)),ZScore(Mean($final_float_market_cap,8)))),ZScore(M...` |
| cluster_006 | s48_cluster_008 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 3 | volatility_lag_quantile:vol_low | -0.00187225 | 0.714057 | `CSRank(Mul(ZScore(Mean(Abs($close),8)),ZScore(Mean(Abs($amount),21))))` |
| cluster_009 | cluster_031 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 3 | volatility_lag_quantile:vol_low | -0.00113415 | 0.845243 | `CSRank(Mul(CSRank(CSResidual(CSRank(CSRank($close)),CSRank(Log($final_total_market_cap)))),ZScore...` |
| cluster_003 | s52_cluster_013 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 2 | volatility_lag_quantile:vol_mid | -0.00023922 | 0.854025 | `CSRank(CSResidual(ZScore(Mean(Abs(Delta($open,1)),34)),CSRank($high)))` |
| cluster_002 | cluster_017 | PASS_REGIME_PROXY_DIVERSIFIED | 5 | 3 | pit_regime_label:unknown_warmup | -0.00584672 | 0.975455 | `CSRank(Mul(CSRank($open),CSRank(Mean($amount,8))))` |
| cluster_007 | s53_cluster_002 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 2 | volatility_lag_quantile:vol_mid | -0.00251524 | 0.648357 | `CSRank(Add(Sign(Mom($final_total_market_cap,34)),CSRank(Mean(Abs(Delta($open,1)),34))))` |
| cluster_004 | cluster_014 | PASS_REGIME_PROXY_DIVERSIFIED | 4 | 2 | trend_lag_quantile:trend_mid | -0.00051325 | 0.519909 | `CSRank(Mul(ZScore(Mean($close,8)),ZScore(Mean($final_float_market_cap,34))))` |

## Remaining Blockers

- true_regime_bucket_replay_not_run
- minute_execution_capacity_not_run
- live_execution_not_confirmed
