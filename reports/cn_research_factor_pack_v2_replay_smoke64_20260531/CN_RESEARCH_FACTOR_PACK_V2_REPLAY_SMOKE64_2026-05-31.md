# CN Research Factor Pack V2 Replay Smoke64

decision: `PASS_FROZEN_QUEUE_REPLAY_SMOKE_NO_PROMOTION`

## Scope

This is a frozen-queue replay smoke from the v2 selector output.

It does not regenerate candidates, does not tune selectors, and does not promote any alpha.

## Inputs

- selection root: `runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector`
- dataset: `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet`
- replay output: `runtime/cn_research_factor_pack_v2_replay_smoke64_20260531/aa`
- attribution output: `reports/cn_research_factor_pack_v2_replay_smoke64_20260531/cn_research_factor_pack_v2_replay_source_attribution.json`

## Main Smoke Result

- audited: 64
- raw non-gap replay pass: 62 / 64
- unique return-corr clusters: 45
- cost/turnover deployable unique clusters: 29
- top cluster raw-pass share: 12.9032%
- top cluster id: `cluster_003`
- median turnover proxy: 0.056195

## Source Attribution

Attribution was joined back from the frozen selection queue because strict rows do not preserve `source_lane` consistently.

By source lane:

- `cn_research_feature_layer_v2`: audited 24, raw pass 24, deployable-row proxy 12, unique clusters 20
- `agnostic_freeform_ast`: audited 10, raw pass 10, deployable-row proxy 9, unique clusters 8
- `formula_gen_v2_repair_expansion`: audited 10, raw pass 10, deployable-row proxy 8, unique clusters 8
- `r0_cem_led`: audited 10, raw pass 10, deployable-row proxy 8, unique clusters 8
- `ast_failure_aware_repair`: audited 8, raw pass 8, deployable-row proxy 6, unique clusters 8
- `event_derived_feature_layer`: audited 2, raw pass 0, deployable-row proxy 0, unique clusters 2

By fundamental exposure:

- `fundamental_expr`: audited 24, raw pass 24, deployable-row proxy 12, unique clusters 20
- `nonfund_expr`: audited 40, raw pass 38, deployable-row proxy 31, unique clusters 27

By factor lane among `fund_` expressions:

- `fundamental_x_event`: audited 10, raw pass 10, deployable-row proxy 5, unique clusters 6
- `fundamental_risk_inverse`: audited 5, raw pass 5, deployable-row proxy 2, unique clusters 5
- `fundamental_size_residual`: audited 5, raw pass 5, deployable-row proxy 3, unique clusters 5
- `fundamental_quality`: audited 4, raw pass 4, deployable-row proxy 2, unique clusters 4

## Interpretation

The v2 feature layer is now end-to-end evaluable:

- PIT fundamental fields can be loaded by the mature evaluator.
- Fundamental expressions can produce pre-replay signal vectors.
- Fundamental candidates enter the G2 frozen queue.
- A replay smoke can complete on the v2 dataset.

This is still only smoke evidence. The audited sample uses the recent replay window and is not an OOS promotion-grade test.

## Required Fix Before Large Search

`phase3e_selector_audit.csv` and strict replay rows should preserve:

- `source_lane`
- `source_generator`
- `factor_lane`
- `contains_fundamental_field`

Current source attribution is recoverable through `candidate_id`, but native preservation is required before large-scale source-credit decisions.

## Next Allowed Step

Run a larger selector-only or small replay matrix on company machine only after adding native source attribution preservation.

Do not launch full search from this smoke alone.
