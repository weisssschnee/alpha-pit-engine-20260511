# CN Underutilized Field Registry Recluster - 2026-06-01

decision: `PASS_SIGNAL_VECTOR_REGISTRY_RECLUSTER_AUDIT`

## Scope

posthoc signal-vector comparison of replay128 deployable survivor representatives vs frozen 149 registry; no selection or replay rerun

## Counts

- survivor_representatives: `14`
- survivor_vector_ready: `14`
- survivor_zero_vector_count: `0`
- registry_rows: `149`
- registry_vector_ready: `149`
- registry_zero_vector_count: `0`
- known_or_duplicate_signal_cluster: `1`
- registry_similarity_review: `0`
- provisional_new_signal_space: `13`
- internal_corr_pairs_ge_review_threshold: `0`
- internal_corr_pairs_ge_high_threshold: `0`
- internal_multi_cluster_components: `0`

## Interpretation

- `known_or_duplicate_signal_cluster`: survivor is high-correlation to a frozen 149 registry representative.
- `registry_similarity_review`: survivor is not a high-confidence duplicate but is close enough to require review.
- `provisional_new_signal_space`: survivor is not close to the 149 registry under this sampled signal-vector proxy.

This is still a pre-replay signal-vector proxy audit. It is stronger than symbolic matching, but it is not a new official baseline update by itself.

## Survivor Review Rows

| tier | cluster | source_lane | factor_lane | max_corr_to_149 | nearest_registry | expression |
|---|---|---|---|---:|---|---|
| known_or_duplicate_signal_cluster | cluster_070 | cn_underutilized_field_feature_layer | capacity_residual_activity | 0.835079 | registry_147 | `CSRank(CSResidual(ZScore(Mean($amount,20)),ZScore(Mean($final_total_market_cap,20))))` |
| provisional_new_signal_space | cluster_011 | cn_research_feature_layer_v2 | fundamental_risk_inverse | 0.102343 | registry_047 | `Neg(CSRank($fund_debt_to_assets))` |
| provisional_new_signal_space | cluster_084 | cn_flow_liquidity_feature_layer | fundamental_x_flow | 0.095402 | registry_040 | `CSRank(Mul(ZScore($fund_cash_to_assets),ZScore(Div(Mean($turnover_ratio,5),Add(Abs(Mean...` |
| provisional_new_signal_space | cluster_028 | cn_research_feature_layer_v2 | fundamental_quality | 0.088342 | registry_040 | `CSRank(Delta($fund_float_share_ratio_cninfo,20))` |
| provisional_new_signal_space | cluster_088 | cn_underutilized_field_feature_layer | fundamental_x_activity | 0.081113 | registry_049 | `CSRank(Mul(ZScore($fund_current_ratio),ZScore(Div(Mean($turnover_ratio,5),Add(Abs(Mean(...` |
| provisional_new_signal_space | cluster_091 | cn_flow_liquidity_feature_layer | fundamental_x_flow | 0.071708 | registry_102 | `Neg(CSRank(Mul(ZScore($fund_debt_to_assets),ZScore(Div(Mean($turnover_ratio,5),Add(Abs(...` |
| provisional_new_signal_space | cluster_039 | cn_research_feature_layer_v2 | fundamental_size_residual | 0.070544 | registry_049 | `CSRank(CSResidual(Log($fund_netcash_operate),Log($fund_total_assets)))` |
| provisional_new_signal_space | cluster_031 | cn_research_feature_layer_v2 | fundamental_risk_inverse | 0.069401 | registry_122 | `Neg(CSRank(Delta($fund_goodwill_to_assets,20)))` |
| provisional_new_signal_space | cluster_089 | cn_underutilized_field_feature_layer | fundamental_x_activity | 0.061327 | registry_020 | `Neg(CSRank(Mul(ZScore($fund_inventory_to_assets),ZScore(Div(Mean($volume,5),Add(Abs(Mea...` |
| provisional_new_signal_space | cluster_029 | cn_research_feature_layer_v2 | fundamental_risk_inverse | 0.059199 | registry_034 | `Neg(CSRank(Delta($fund_debt_to_assets,20)))` |
| provisional_new_signal_space | cluster_086 | cn_underutilized_field_feature_layer | fundamental_x_activity | 0.052572 | registry_057 | `CSRank(Mul(ZScore($fund_top10_holder_pct),ZScore(Div(Mean($amount,5),Add(Abs(Mean($amou...` |
| provisional_new_signal_space | cluster_038 | cn_research_feature_layer_v2 | fundamental_size_residual | 0.052428 | registry_057 | `CSRank(CSResidual(Log($fund_total_assets),Log($fund_total_assets)))` |
| provisional_new_signal_space | cluster_090 | cn_underutilized_field_feature_layer | fundamental_x_activity | 0.038844 | registry_113 | `CSRank(Mul(ZScore($fund_top1_holder_pct),ZScore(Div(Mean($turnover_ratio,5),Add(Abs(Mea...` |
| provisional_new_signal_space | cluster_024 | cn_research_feature_layer_v2 | fundamental_quality | 0.031658 | registry_020 | `CSRank(Delta($fund_top1_holder_pct,20))` |

## Outputs

- review_rows_csv: `reports\cn_underutilized_field_registry_recluster_20260601\recluster_review_rows.csv`
- top3_csv: `reports\cn_underutilized_field_registry_recluster_20260601\recluster_top3_registry_matches.csv`
- internal_pairs_csv: `reports\cn_underutilized_field_registry_recluster_20260601\survivor_internal_signal_corr_pairs.csv`
- internal_components_csv: `reports\cn_underutilized_field_registry_recluster_20260601\survivor_internal_components.csv`
