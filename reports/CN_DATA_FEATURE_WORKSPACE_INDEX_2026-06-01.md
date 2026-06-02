# CN Data Feature Workspace Index - 2026-06-01

## Workspace Identity

- branch: `feature/data-feature-workspace-20260531`
- head: `c47d107`
- primary goal: integrate public enrichment, event-derived fields, fundamental PIT fields, flow/liquidity fields, and underutilized daily fields into the mature G2 shared-pool selector path.

## Data Layer

Current key panel:

- `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet`

Current fundamental field registry:

- `runtime/field_registry/cn_fundamental_field_registry_v1_20260531.json`

Current source package noted by the user:

- `G:\Project_V7_Rotation\data\cn_public_enrichment\cn_fundamental_akshare_batch_v1_20260531\aggregated_v1\aggregation_report.json`

Important PIT boundary:

- Public financial datasets are controlled smoke assets, not PIT-proof production data until NOTICE_DATE, REPORT_DATE, announcement dates, and conservative lag rules are enforced per field family.

## Feature And Factor Packs

Research/fundamental pack:

- `runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json`
- `reports/cn_research_factor_pack_v2_replay_smoke64_20260531/CN_RESEARCH_FACTOR_PACK_V2_REPLAY_SMOKE64_2026-05-31.md`

Flow/liquidity pack:

- `runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json`
- candidate count: `306`
- decision: `reports/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_PREFLIGHT_DECISION_2026-06-01.md`

Underutilized field pack:

- `runtime/factor_packs/cn_underutilized_field_factor_candidate_pack_v1_20260601.json`
- candidate count: `344`
- covered axes: flow relative activity, price-flow divergence, capacity-normalized activity, capacity residual activity, Amihud-style liquidity cost, limit seal flow, event x seal-flow, event x flow-liquidity, theme activity, fundamental x activity, and fundamental capacity value.

## Mature Chain Integration

Key integration points:

- `candidate_pool_priority` gives positive priority to research/fundamental, flow/liquidity, and underutilized field candidates.
- `real_market_validation` can evaluate added fields including `daily_ret`, `turnover_ratio`, `turnover_ratio_real`, `seal_money`, `seal_rate`, `seal_circulation_rate`, and `actual_circulation_value`.
- `phase3g_signal_vector_store` now has runtime disk cache support for expression vectors.
- `phase3aa_enrich_shared_candidate_pool` supports research, event, fundamental, flow, and underutilized factor rows.
- `phase3aa_apply_mature_g2_selector` supports research share and signal runtime cache routing.

## Validation Results

Flow/liquidity selector-only gate:

- selected total: `64`
- selected from `cn_flow_liquidity_feature_layer`: `32`
- research bucket selected: `19`
- selected signal-vector errors: `0`
- forbidden replay-label usage: `false`

Underutilized field family smoke:

- sampled rows: `232`
- vector ok: `232`
- operator pathology rows: `0`
- factor lanes sampled: `23`
- decision: `PASS_FIELD_FAMILY_SIGNAL_VECTOR_SMOKE`

Underutilized selector128:

- selected total: `128`
- selected from `cn_flow_liquidity_feature_layer`: `41`
- selected from `cn_underutilized_field_feature_layer`: `21`
- mature/legacy selected: `66`
- event bucket selected: `38`
- research bucket selected: `24`
- forbidden replay-label usage: `false`

Batched selector256:

- combined selected rows: `256`
- unique selected rows: `215`
- selected by source:
  - `cn_flow_liquidity_feature_layer`: `89`
  - `cn_underutilized_field_feature_layer`: `73`
  - `cn_research_feature_layer_v2`: `47`
  - `event_derived_feature_layer`: `6`
- decision: `PASS_UNDERUTILIZED_FIELD_SYSTEM_SMOKE_NO_REPLAY`

Frozen replay smoke48:

- source unique rows: `215`
- frozen queue rows: `48`
- selected factor lanes: `23`
- forbidden replay-field hits in selection: `0`
- raw pass: `5 / 48`
- portfolio replay pass: `16 / 48`
- cost survive: `12 / 48`
- deployable clusters: `5`
- top cluster share: `6.25%`
- decision: `reports/CN_UNDERUTILIZED_FIELD_REPLAY_SMOKE_DECISION_2026-06-01.md`

Frozen replay smoke128:

- source unique rows: `215`
- frozen queue rows: `128`
- selected factor lanes: `23`
- forbidden replay-field hits in selection: `0`
- strict proxy pass: `12 / 128`
- raw non-gap replay pass: `42 / 128`
- portfolio replay pass: `42 / 128`
- cost survive: `27 / 128`
- deployable clusters: `14`
- top cluster share: `4.76%`
- decision: `reports/CN_UNDERUTILIZED_FIELD_REPLAY128_DECISION_2026-06-01.md`

Survivor attribution:

- survivor rows: `54`
- deployable representatives: `14`
- registry exact representative matches: `0 / 14`
- registry skeleton matches: `2 / 14`
- strongest deployable source lanes: `cn_research_feature_layer_v2` with `7`, `cn_underutilized_field_feature_layer` with `5`
- strongest deployable factor lane: `fundamental_x_activity` with `4`
- decision: `reports/CN_UNDERUTILIZED_FIELD_SURVIVOR_ATTRIBUTION_DECISION_2026-06-01.md`

Signal-vector recluster vs 149 registry:

- survivor representatives: `14`
- survivor vector ready: `14`
- registry vector ready: `149 / 149`
- zero vector artifacts: `0`
- high-correlation duplicate vs 149: `1`
- provisional new signal-space candidates: `13`
- internal survivor collision pairs: `0`
- decision: `reports/CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_DECISION_2026-06-01.md`

Registry review queue:

- queued provisional-new representatives: `13`
- duplicate holdout: `1`
- review-band holdout: `0`
- canonical hits in 149 registry: `0`
- candidate discovery baseline if all queue survives full integration: `162`
- queue JSON: `runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json`

Candidate 162 global integration:

- existing registry: `149`
- queued new representatives: `13`
- accepted new signal clusters: `13`
- review/reject queued representatives: `0`
- candidate registry count: `162`
- queued edges above review threshold: `0`
- queued edges above duplicate threshold: `0`
- zero vector count: `0`
- candidate registry: `runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json`
- decision: `reports/CN_UNDERUTILIZED_FIELD_CANDIDATE_162_DECISION_2026-06-01.md`

Discovery baseline 162 promotion:

- decision: `PROMOTE_CANDIDATE_162_TO_DISCOVERY_BASELINE`
- status: `promoted_discovery_baseline_not_book_or_production`
- added signal clusters: `13`
- baseline JSON: `runtime/baselines/cn_discovery_baseline_162_20260601.json`
- stable hash: `runtime/baselines/cn_discovery_baseline_162_20260601.sha256`
- promotion report: `reports/CN_UNDERUTILIZED_FIELD_DISCOVERY_BASELINE_162_PROMOTION_2026-06-01.md`

Book-readiness audit for 13 new clusters:

- book-readiness candidates: `6`
- watch candidates: `7`
- research-only high risk: `0`
- median strict turnover: `0.136363`
- p90 strict turnover: `0.288182`
- median strict cost-adjusted sortino: `1.389663`
- median long-selected amount: `3,061,652,736`
- median long-selected float mcap: `83,793,072,586`
- median limit/susp rate: `0.0`
- decision: `reports/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_DECISION_2026-06-01.md`

## Cleanup State

Cleanup report:

- `reports/CN_WORKSPACE_CLEANUP_ARCHIVE_2026-06-01.md`

Key artifact manifest:

- `runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json`

Cleanup result:

- archived stale runtime directories under `archive/workspace_cleanup_20260601/`
- removed only cache directories
- key artifact missing count: `0`

## Current Boundary

Confirmed:

- The feature generation and shared-pool selector path can ingest the new field families.
- Signal-vector pre-replay selection does not require replay labels.
- Batched selector mode prevents a monolithic selector256 timeout from blocking progress.

Not confirmed:

- Replay performance of the selected underutilized field candidates.
- Production PIT safety of all public enrichment fields.
- True execution, minute slippage, and capacity.

## Next Gate

Recommended next gate:

1. Attribute replay128 survivors by source lane, factor lane, formula skeleton, and field family.
2. Recluster replay128 survivors against the current discovery registry.
3. Decide whether to replay the remaining unique selected rows or launch a larger shared-pool search.
