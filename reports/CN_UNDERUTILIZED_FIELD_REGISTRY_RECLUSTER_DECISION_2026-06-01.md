# CN Underutilized Field Registry Recluster Decision - 2026-06-01

decision: `PASS_SIGNAL_VECTOR_REGISTRY_RECLUSTER_AUDIT`

## Scope

Posthoc audit only. This compares the `14` deployable representatives from the underutilized-field replay128 smoke against the frozen `149` cumulative deployable registry with sampled pre-replay signal vectors.

No selection, strict replay, or cluster replay was rerun.

## Inputs

- survivor representatives: `reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv`
- frozen registry: `runtime/baselines/phase3K_complete_149_representative_registry_20260517.json`
- dataset: `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet`
- runtime vector cache: `runtime/phase3g_signal_vectors/runtime_eval_cache/underutilized_recluster_20260601`

## Result

- survivor representatives: `14`
- survivor vector ready: `14`
- survivor zero vector count: `0`
- registry rows: `149`
- registry vector ready: `149`
- registry zero vector count: `0`
- high-correlation duplicate vs 149: `1`
- review-band similarity vs 149: `0`
- provisional new signal space: `13`
- internal survivor pairs above review threshold: `0`
- internal survivor pairs above duplicate threshold: `0`

## Interpretation

The replay128 survivor set is not just symbolic novelty. Under the sampled signal-vector proxy, `13 / 14` deployable representatives are not close to the frozen `149` registry, and no survivor-survivor internal collision is detected at the review threshold.

One representative is a likely known/duplicate signal cluster:

- `cluster_070`
- lane: `cn_underutilized_field_feature_layer`
- factor lane: `capacity_residual_activity`
- expression: `CSRank(CSResidual(ZScore(Mean($amount,20)),ZScore(Mean($final_total_market_cap,20))))`
- nearest registry entry: `registry_147`
- max abs signal-vector corr: `0.835079`

The remaining `13` representatives should be treated as provisional new signal-space candidates, pending full global replay/cluster integration.

## Confirmed

- all registry representatives were vector-matchable;
- all replay128 deployable representatives were vector-matchable;
- zero-vector artifacts did not drive the novelty result;
- symbolic-only registry comparison was too conservative; signal-vector comparison supports substantial novelty;
- direct baseline update is still not automatic because this was a posthoc proxy audit, not a full official global aggregate.

## Not Confirmed

- official new deployable baseline increment;
- book-level marginal value;
- production deployability;
- true execution / capacity / minute slippage.

## Next Gate

Promote these results only after a full global integration step that:

1. imports the `13` provisional-new representatives into a candidate registry review queue;
2. reruns global signal clustering with the existing `149` registry plus the new representatives;
3. applies duplicate-family and book-readiness checks;
4. emits a formal baseline update only for clusters that remain distinct.

## Artifacts

- `reports/cn_underutilized_field_registry_recluster_20260601/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_2026-06-01.md`
- `reports/cn_underutilized_field_registry_recluster_20260601/cn_underutilized_field_registry_recluster.json`
- `reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/recluster_top3_registry_matches.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_signal_corr_pairs.csv`
- `reports/cn_underutilized_field_registry_recluster_20260601/survivor_internal_components.csv`
