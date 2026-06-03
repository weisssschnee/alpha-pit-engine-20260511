# CN Integrated Factor Pack V2 Decision Record

Date: 2026-06-03

## Decision

```text
data_chain_decision: PASS_INTEGRATED_FACTOR_V2_CHAIN
novelty_decision: PASS_SIGNAL_VECTOR_NOVELTY_PROXY
x0_shadow_decision: HOLD_NO_X0_R3_PROMOTION
expanded_pool_decision: HOLD_EXPANDED_POOL_DILUTION
polarity_regime_rescue: HOLD_NO_POLARITY_OR_REGIME_RESCUE
```

The integrated data/feature chain is useful as a research and discovery asset.
It is not approved as an X0/R3 shadow component.

## Confirmed

- Integrated 1min-derived daily context, non-1min PIT context, RZRQ, and fundamental fields can be routed through the mature candidate/replay path.
- Coverage-aware filtering removes sparse and unusable candidates before replay.
- True mature-chain fresh-pool injection works without replacing the G2/X0 official objects.
- Signal-vector novelty audit found 7 deployable-proxy rows that are exact-new and signal-new versus the 149 registry proxy.
- The validated new axis is concentrated in `rzrq_size_normalized`; this is a real diagnostic discovery axis, not a direct X0/R3 overlay.

## Not Confirmed

- No evidence that integrated factor V2 improves locked X0/R3.
- No evidence that polarity reversal rescues the RZRQ-size normalized candidates.
- No evidence that these candidates should enter the official shadow book.
- No production readiness, minute execution readiness, or capacity validation.

## Key Evidence

### Coverage-aware pack

```text
raw_v2_candidates: 355
coverage_aware_candidates: 294
dropped_too_sparse: 61
```

### Base coverage-aware replay

```text
selected_integrated_candidates: 19
audited: 19
raw_pass: 16
cost_survive: 12
deployable_clusters: 10
top_cluster_share: 6.25%
main_lane: rzrq_size_normalized
```

### True fresh-pool seed36 canary

```text
raw_mature_pool: 484
enriched_pool_after_integrated_injection: 778
selected_integrated_candidates: 19
fresh_only_vs_base: 7
audited: 19
raw_pass: 14
cost_survive: 10
deployable_clusters: 8
top_cluster_share: 7.14%
```

Decision:

```text
PASS_TRUE_FRESH_POOL_CANARY_HOLD_PROMOTION
```

### Signal novelty versus 149

```text
registry_vectors_ready: 149 / 149
candidate_vectors_ready: 19 / 19
deployable_proxy_count: 7
exact_duplicates_vs_149: 0
signal_duplicates_vs_149_proxy: 0
signal_new_vs_149_proxy: 7
max_deployable_nearest_corr_to_149: 0.3823
```

Decision:

```text
PASS_SIGNAL_VECTOR_NOVELTY_PROXY_HOLD_FINAL_RECLUSTER
```

### X0/R3 marginal audit

```text
B0_x0_r3:
  annualized: 44.20%
  sortino: 2.8210
  max_drawdown: -2.66%

I0_integrated_signal_new_r3_equal:
  annualized: -21.71%
  sortino: -1.2682
  max_drawdown: -11.23%

best_overlay_10pct:
  annualized: 35.66%
  sortino: 2.3279
  delta_ann_vs_x0: -8.53%
  delta_sortino_vs_x0: -0.4931
```

Decision:

```text
HOLD_NO_CLEAR_X0_R3_MARGINAL_OVERLAY
```

### Polarity / regime rescue audit

```text
original_signal_new_r3_equal:
  annualized: -21.71%
  sortino: -1.2682

reversed_signal_new_r3_equal:
  annualized: -21.92%
  sortino: -1.3327

best_reversed_overlay_10pct:
  annualized: 35.63%
  sortino: 2.3549
  delta_ann_vs_x0: -8.57%
```

Decision:

```text
HOLD_NO_POLARITY_OR_REGIME_RESCUE
```

## Interpretation

RZRQ-size normalized formulas are not useless. They are signal-new and can pass replay/cost in the integrated panel. The problem is that their marginal behavior is incompatible with the locked X0/R3 book in the tested 2026 OOS slice.

Within R3, the candidates are consistently weak. Outside R3, a few candidates show positive diagnostic behavior, but that does not justify changing the locked R3 object.

## Locked Policy

```text
Do not add integrated factor V2 candidates to X0/R3.
Do not promote RZRQ-size normalized candidates as official shadow components.
Do not expand the integrated pool by simple pool widening.
Retain integrated factor V2 as a diagnostic discovery lane and search-prior source.
```

## Next Allowed Work

Only two follow-ups are allowed without reopening promotion:

1. Non-R3 diagnostic lane:
   Test whether RZRQ-size normalized structures have a separate challenger role outside R3.

2. Longer-data / true 1min alignment:
   Re-evaluate the same family after the integrated panel spans a broader history and minute-derived fields have been fully aligned.

Neither follow-up may modify X0/R3 without a fresh locked gate and placebo audit.
