# Phase3Z46 EventAlpha Canary

- decision: `HOLD_Z46_CANARY_NO_SMOKE_PASS`
- generated_count: `390`
- kept_after_memory_count: `390`
- selected_count: `64`
- frozen_queue_hash: `b5c7cec974c5b5a930bc8bf9b5ce18938c63ecee086c4171c6d3ed74d6ba92d8`
- evaluated_count: `64`
- unsupported_count: `0`
- passed_smoke_count: `0`
- promoted_to_full_history_review_count: `0`
- boundary: diagnostic only; no official object changes.

## Lane Summary

| lane | evaluated | pass smoke | promoted | best rank IC | best long sortino | mean turnover |
|---|---:|---:|---:|---:|---:|---:|
| challenger | 22 | 0 | 0 | 0.022277 | 0.243355 | 0.054884 |
| event_module | 33 | 0 | 0 | 0.026363 | 2.668087 | 0.06202 |
| veto_intensifier | 9 | 0 | 0 | 0.002038 | 0.494501 | 0.054648 |

## Top Candidates

- `z46_event_module_051` lane=`event_module` sortino=`2.668087` rank_ic=`-0.009606` pass=`False` expr=`CSRank(Mean(Delay($limit_up_streak_ge_8,1),5))`
- `z46_event_module_049` lane=`event_module` sortino=`2.001696` rank_ic=`-0.008427` pass=`False` expr=`CSRank(Mean(Delay($limit_up_streak_ge_8,1),3))`
- `z46_event_module_085` lane=`event_module` sortino=`0.605159` rank_ic=`-0.022277` pass=`False` expr=`CSRank(Mean(Delay($limit_up_touch_not_close,1),3))`
- `z46_event_module_047` lane=`event_module` sortino=`0.567481` rank_ic=`-0.002906` pass=`False` expr=`CSRank(Mean(Delay($limit_up_streak_ge_8,1),2))`
- `z46_veto_intensifier_088` lane=`veto_intensifier` sortino=`0.494501` rank_ic=`-0.000179` pass=`False` expr=`CSRank(Sub(Mean(Delay($limit_up_touch_not_close,1),2),Mean(Delay($limit_up_touch_not_close,1),8)))`
- `z46_event_module_042` lane=`event_module` sortino=`0.347282` rank_ic=`-0.001952` pass=`False` expr=`CSRank(Mean(Delay($limit_up_streak_ge_6,1),5))`
- `z46_event_module_083` lane=`event_module` sortino=`0.270194` rank_ic=`-0.018481` pass=`False` expr=`CSRank(Mean(Delay($limit_up_touch_not_close,1),2))`
- `z46_challenger_091` lane=`challenger` sortino=`0.243355` rank_ic=`0.007128` pass=`False` expr=`Neg(ZScore(Mean(Delay($limit_down_open_not_close,1),2)))`

## Interpretation

- This is a canary screen only; smoke pass requires strict replay and event validation.
- Overlay lane remains excluded because Z45b marginal audit rejected all overlay candidates.
- Search memory is active to avoid repeating Phase3R templates.
