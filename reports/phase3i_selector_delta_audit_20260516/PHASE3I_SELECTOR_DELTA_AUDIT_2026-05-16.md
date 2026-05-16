# Phase3I Selector Delta Audit

- decision: `HOLD_SELECTOR_REPAIR_REQUIRED`
- run_root: `D:\p3i_selector_only_20260516\s41\selector`

## Findings

- I1_added_turnover_worse_than_removed: `True`
- I3_added_signal_corr_worse_than_removed: `True`
- I2_added_liquidity_better_than_removed: `True`

## Delta Summaries

### I1 vs I0 Turnover
```json
{
  "added": {
    "count": 12,
    "median_turnover_proxy": 0.076815,
    "p90_turnover_proxy": 0.203039,
    "max_turnover_proxy": 0.20474,
    "source_lane_counts": {
      "agnostic_freeform_ast": 4,
      "r0_cem_led": 6,
      "formula_gen_v2_repair_expansion": 2
    },
    "median_base_e3_score": -0.25034,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.745424,
    "median_final_score": -0.550876
  },
  "removed": {
    "count": 12,
    "median_turnover_proxy": 0.066093,
    "p90_turnover_proxy": 0.102174,
    "max_turnover_proxy": 0.107673,
    "source_lane_counts": {
      "agnostic_freeform_ast": 7,
      "formula_gen_v2_repair_expansion": 2,
      "r0_cem_led": 3
    },
    "median_base_e3_score": 0.583604,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.498125,
    "median_final_score": -0.17883
  },
  "overlap_count": 52,
  "base_selected_count": 64,
  "other_selected_count": 64
}
```

### I3 vs I0 Signal Correlation
```json
{
  "added": {
    "count": 9,
    "median_max_corr_to_selected_queue_signal": 0.721257,
    "p90_max_corr_to_selected_queue_signal": 1.0,
    "max_max_corr_to_selected_queue_signal": 1.0,
    "source_lane_counts": {
      "agnostic_freeform_ast": 4,
      "r0_cem_led": 4,
      "formula_gen_v2_repair_expansion": 1
    },
    "median_base_e3_score": 0.251955,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.721257,
    "median_final_score": -0.753579
  },
  "removed": {
    "count": 9,
    "median_max_corr_to_selected_queue_signal": 0.524696,
    "p90_max_corr_to_selected_queue_signal": 0.996507,
    "max_max_corr_to_selected_queue_signal": 0.996507,
    "source_lane_counts": {
      "r0_cem_led": 4,
      "formula_gen_v2_repair_expansion": 1,
      "agnostic_freeform_ast": 4
    },
    "median_base_e3_score": 0.270455,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.524696,
    "median_final_score": -0.306127
  },
  "overlap_count": 55,
  "base_selected_count": 64,
  "other_selected_count": 64
}
```

### I2 vs I0 Liquidity
```json
{
  "added": {
    "count": 5,
    "median_liquidity_proxy": 2222543352.974,
    "p90_liquidity_proxy": 2711980036.639523,
    "max_liquidity_proxy": 2711980036.639523,
    "source_lane_counts": {
      "agnostic_freeform_ast": 2,
      "r0_cem_led": 3
    },
    "median_base_e3_score": -0.304769,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.671999,
    "median_final_score": -0.492773
  },
  "removed": {
    "count": 5,
    "median_liquidity_proxy": 0.0,
    "p90_liquidity_proxy": 2605023106.285789,
    "max_liquidity_proxy": 2605023106.285789,
    "source_lane_counts": {
      "r0_cem_led": 3,
      "agnostic_freeform_ast": 2
    },
    "median_base_e3_score": -0.5568,
    "median_turnover_penalty": 0.0,
    "median_signal_corr_penalty": 0.0,
    "median_final_score": -0.1387
  },
  "overlap_count": 59,
  "base_selected_count": 64,
  "other_selected_count": 64
}
```
