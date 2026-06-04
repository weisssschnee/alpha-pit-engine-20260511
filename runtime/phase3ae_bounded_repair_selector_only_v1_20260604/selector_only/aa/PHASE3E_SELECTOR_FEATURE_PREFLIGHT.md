# Phase3E Selector Feature Preflight

- selector_profile: signal_vector_diversified_source_priority_proxy
- selector_version: phase3g-signal-vector-selector-v1-2026-05-14
- candidate_count: 379
- book_marginal_mode: signal_vector_proxy
- e2_minimum_requirement_pass: True
- e3_true_requirement_pass: False
- e3_proxy_requirement_pass: True

## Coverage

```json
{
  "turnover_proxy": 0.39314,
  "turnover_structure_risk": 1.0,
  "cost_adjusted_proxy": 0.39314,
  "liquidity_proxy": 0.39314,
  "capacity_proxy": 0.39314,
  "factor_exposure_proxy": 0.0,
  "sector_concentration_proxy": 0.0,
  "candidate_return_vector": 0.0,
  "registry_return_vectors": 0.0,
  "max_corr_to_103_proxy": 1.0,
  "signal_vector_ready": 1.0,
  "max_corr_to_134_signal_vector": 1.0,
  "mean_topk_corr_to_134_signal_vector": 1.0,
  "selected_queue_signal_corr": 1.0,
  "operator_pathology_flag": 1.0,
  "complexity_score": 1.0
}
```

## Thresholds

```json
{
  "turnover_p90": null,
  "complexity_p90": 15.225000000000005,
  "cost_adjusted_p10": null,
  "factor_exposure_p90": null,
  "sector_concentration_p90": null
}
```

## Leakage Guard

```json
{
  "forbidden_fields": [
    "cost_survives",
    "deployable",
    "global_signal_cluster_id",
    "portfolio_replay_avg_one_way_turnover",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_pass",
    "signal_cluster_id",
    "strict_cost_adjusted_sortino",
    "strict_mean_one_way_turnover",
    "strict_mean_rank_ic"
  ],
  "selector_uses_forbidden_fields": false
}
```
