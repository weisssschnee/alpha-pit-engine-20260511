# CN Underutilized Field Book Readiness - 2026-06-01

decision: `PASS_BOOK_READINESS_AUDIT_READY`

## Counts

- new_clusters: `13`
- audit_rows: `13`
- errors: `0`
- book_readiness_candidate: `6`
- watch_candidate: `7`
- research_only_high_risk: `0`
- diagnostic_missing_replay_metric: `0`

## Metric Summary

- median_strict_turnover: `0.136363`
- p90_strict_turnover: `0.288182`
- median_strict_cost_adjusted_sortino: `1.389663`
- median_long_selected_amount: `3061652736.0`
- median_long_selected_float_mcap: `83793072585.9375`
- median_limit_or_susp_rate: `0.0`

## Rows

| grade | cluster | factor_lane | turnover | sortino | median_amount | limit_or_susp | expression |
|---|---|---|---:|---:|---:|---:|---|
| book_readiness_candidate | cluster_090 | fundamental_x_activity | 0.125682 | 5.429641 | 2799436032.0 | 0.0 | `CSRank(Mul(ZScore($fund_top1_holder_pct),ZScore(Div(Mean($turnover_ratio,5),A...` |
| book_readiness_candidate | cluster_011 | fundamental_risk_inverse | 0.064204 | 3.895127 | 2671507328.0 | 0.0 | `Neg(CSRank($fund_debt_to_assets))` |
| book_readiness_candidate | cluster_024 | fundamental_quality | 0.117614 | 2.672103 | 4343486464.0 | 0.0 | `CSRank(Delta($fund_top1_holder_pct,20))` |
| book_readiness_candidate | cluster_031 | fundamental_risk_inverse | 0.167749 | 2.439269 | 4036027136.0 | 0.0 | `Neg(CSRank(Delta($fund_goodwill_to_assets,20)))` |
| book_readiness_candidate | cluster_029 | fundamental_risk_inverse | 0.136363 | 1.994263 | 4183781632.0 | 0.0 | `Neg(CSRank(Delta($fund_debt_to_assets,20)))` |
| book_readiness_candidate | cluster_028 | fundamental_quality | 0.152841 | 1.389663 | 3061652736.0 | 0.0 | `CSRank(Delta($fund_float_share_ratio_cninfo,20))` |
| watch_candidate | cluster_089 | fundamental_x_activity | 0.297727 | 1.395528 | 2708709504.0 | 0.0 | `Neg(CSRank(Mul(ZScore($fund_inventory_to_assets),ZScore(Div(Mean($volume,5),A...` |
| watch_candidate | cluster_038 | fundamental_size_residual | 0.315258 | 1.182619 | 3738267904.0 | 0.0 | `CSRank(CSResidual(Log($fund_total_assets),Log($fund_total_assets)))` |
| watch_candidate | cluster_088 | fundamental_x_activity | 0.108978 | 0.914001 | 2451447296.0 | 0.0 | `CSRank(Mul(ZScore($fund_current_ratio),ZScore(Div(Mean($turnover_ratio,5),Add...` |
| watch_candidate | cluster_086 | fundamental_x_activity | 0.089773 | 0.374979 | 2760739200.0 | 0.0 | `CSRank(Mul(ZScore($fund_top10_holder_pct),ZScore(Div(Mean($amount,5),Add(Abs(...` |
| watch_candidate | cluster_084 | fundamental_x_flow | 0.220588 | 0.267397 | 3179633408.0 | 0.0 | `CSRank(Mul(ZScore($fund_cash_to_assets),ZScore(Div(Mean($turnover_ratio,5),Ad...` |
| watch_candidate | cluster_039 | fundamental_size_residual | 0.103977 | 0.245227 | 3281578752.0 | 0.0 | `CSRank(CSResidual(Log($fund_netcash_operate),Log($fund_total_assets)))` |
| watch_candidate | cluster_091 | fundamental_x_flow | 0.25 | 0.139265 | 2777379072.0 | 0.0 | `Neg(CSRank(Mul(ZScore($fund_debt_to_assets),ZScore(Div(Mean($turnover_ratio,5...` |

## Boundary

This is a no-replay book-readiness screen. It does not prove production readiness or true capacity.
