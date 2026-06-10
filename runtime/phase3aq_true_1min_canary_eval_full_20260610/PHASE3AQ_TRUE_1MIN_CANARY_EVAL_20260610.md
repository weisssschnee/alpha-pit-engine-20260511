# Phase3AQ True 1min Canary Eval

decision: `PHASE3AQ_TRUE_1MIN_CANARY_EVAL_COMPLETE`

## Scope

- panel rows: `351137`
- codes: `6`
- trade_time_count: `58563`
- candidates: `97`
- errors: `0`

## Top IC By Horizon

### 1m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0143462 spread=3.31688e-05 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0138099 spread=2.63688e-05 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_flow_impulse_0011` ic=0.0106999 spread=5.91373e-05 expr=`CSRank(Delta($volume,5))`
- `cn_underutil_v1_flow_impulse_curve_0013` ic=0.0106999 spread=5.91373e-05 expr=`CSRank(Delta($volume,5))`
- `cn_flow_liq_v1_flow_impulse_0027` ic=0.0103127 spread=6.04803e-05 expr=`CSRank(Delta($amount,5))`

### 5m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0227987 spread=6.45044e-05 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.022477 spread=7.5109e-05 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_flow_impulse_0011` ic=0.0137411 spread=0.000114842 expr=`CSRank(Delta($volume,5))`
- `cn_underutil_v1_flow_impulse_curve_0013` ic=0.0137411 spread=0.000114842 expr=`CSRank(Delta($volume,5))`
- `cn_flow_liq_v1_flow_impulse_0027` ic=0.0136259 spread=0.000106059 expr=`CSRank(Delta($amount,5))`

### 15m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0326511 spread=0.000109862 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0314161 spread=5.99266e-05 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_price_flow_divergence_0067` ic=0.011297 spread=8.83639e-05 expr=`CSRank(Mul(ZScore(Delta($amount,5)),Neg(ZScore(Delta($close,5)))))`
- `cn_flow_liq_v1_price_flow_divergence_0075` ic=0.0107971 spread=8.70393e-05 expr=`CSRank(Mul(ZScore(Delta($volume,5)),Neg(ZScore(Delta($close,5)))))`
- `cn_flow_liq_v1_price_flow_divergence_0073` ic=0.00992004 spread=0.000106915 expr=`CSRank(Mul(ZScore(Delta($volume,3)),Neg(ZScore(Delta($close,3)))))`

### 30m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0340464 spread=0.000165078 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0291151 spread=1.3798e-05 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_price_flow_divergence_0071` ic=0.0123226 spread=0.000124489 expr=`CSRank(Mul(ZScore(Delta($amount,20)),Neg(ZScore(Delta($close,20)))))`
- `cn_flow_liq_v1_price_flow_divergence_0079` ic=0.011795 spread=0.000125478 expr=`CSRank(Mul(ZScore(Delta($volume,20)),Neg(ZScore(Delta($close,20)))))`
- `cn_flow_liq_v1_price_flow_divergence_0067` ic=0.0115186 spread=9.94815e-05 expr=`CSRank(Mul(ZScore(Delta($amount,5)),Neg(ZScore(Delta($close,5)))))`

