# Phase3AQ True 1min Acceptance

decision: `PHASE3AQ_TRUE_1MIN_ROUTE_ACCEPTED_FOR_NEXT_FULL_UNIVERSE_PREP`

## What Is Now Fixed

- This line uses real `trade_time`; `date` is only a mature-evaluator compatibility key equal to `trade_time`.
- `exec_date` is only the trading-day key for lagged context joins.
- `daily_ret` is blocked, not silently mapped to `ret_1m`.
- `first5/15/30` are opening-window feature summaries, not 5/15/30 minute data segmentation.
- X0/R3 remains read-only.

## Full Canary

- rows: `351137`
- codes: `6`
- trade_time: `58563`
- candidates: `97`
- evaluated: `97`
- errors: `0`
- sampled: `None`

## Field Preservation

- direct true 1min formulas: `84`
- opening-window true 1min formulas: `13`
- blocked but preserved for sidecar/event/context lanes: `1273`

- `lagged_fundamental_context_sidecar`: 776
- `lagged_sentiment_market_context_sidecar`: 204
- `lagged_billboard_context_sidecar`: 151
- `lagged_rzrq_context_sidecar`: 138
- `event_state_observable_time_adapter`: 131
- `lagged_cap_float_share_sidecar`: 62
- `lagged_holder_context_sidecar`: 41
- `blocked_legacy_daily_ret_requires_explicit_lagged_daily_context`: 32
- `minute_derived_missing_materialization`: 5

## Leading Canary Families

### 1m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0143462 t=7.095 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0138099 t=7.088 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_flow_impulse_0011` ic=0.0106999 t=5.696 expr=`CSRank(Delta($volume,5))`
- `cn_underutil_v1_flow_impulse_curve_0013` ic=0.0106999 t=5.696 expr=`CSRank(Delta($volume,5))`
- `cn_flow_liq_v1_flow_impulse_0027` ic=0.0103127 t=5.565 expr=`CSRank(Delta($amount,5))`

### 15m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0326511 t=16.13 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0314161 t=14.99 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_price_flow_divergence_0067` ic=0.011297 t=6.034 expr=`CSRank(Mul(ZScore(Delta($amount,5)),Neg(ZScore(Delta($close,5)))))`
- `cn_flow_liq_v1_price_flow_divergence_0075` ic=0.0107971 t=5.761 expr=`CSRank(Mul(ZScore(Delta($volume,5)),Neg(ZScore(Delta($close,5)))))`
- `cn_flow_liq_v1_price_flow_divergence_0073` ic=0.00992004 t=5.295 expr=`CSRank(Mul(ZScore(Delta($volume,3)),Neg(ZScore(Delta($close,3)))))`

### 30m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0340464 t=16.62 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.0291151 t=13.71 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_price_flow_divergence_0071` ic=0.0123226 t=6.613 expr=`CSRank(Mul(ZScore(Delta($amount,20)),Neg(ZScore(Delta($close,20)))))`
- `cn_flow_liq_v1_price_flow_divergence_0079` ic=0.011795 t=6.317 expr=`CSRank(Mul(ZScore(Delta($volume,20)),Neg(ZScore(Delta($close,20)))))`
- `cn_flow_liq_v1_price_flow_divergence_0067` ic=0.0115186 t=6.17 expr=`CSRank(Mul(ZScore(Delta($amount,5)),Neg(ZScore(Delta($close,5)))))`

### 5m
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00347` ic=0.0227987 t=11.44 expr=`CSRank(Sub(ZScore($m1_first15_vwap),ZScore($vwap)))`
- `cn_integrated_v2_minute_vs_daily_vwap_residual_00353` ic=0.022477 t=10.9 expr=`CSRank(Sub(ZScore($m1_first30_vwap),ZScore($vwap)))`
- `cn_flow_liq_v1_flow_impulse_0011` ic=0.0137411 t=7.474 expr=`CSRank(Delta($volume,5))`
- `cn_underutil_v1_flow_impulse_curve_0013` ic=0.0137411 t=7.474 expr=`CSRank(Delta($volume,5))`
- `cn_flow_liq_v1_flow_impulse_0027` ic=0.0136259 t=7.469 expr=`CSRank(Delta($amount,5))`

## Next Gate

Do not call this production alpha. The next correct step is full-universe true 1min panelization plus sidecar/event adapters, then memory-filtered large search.
