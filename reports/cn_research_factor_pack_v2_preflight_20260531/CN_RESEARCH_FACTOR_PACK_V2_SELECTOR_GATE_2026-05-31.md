# CN Research Factor Pack V2 Selector Gate

decision: `PASS_SELECTOR_ONLY_GATE_NO_REPLAY`

## Scope

This gate validates that the event + PIT fundamental feature layer can enter the mature shared-pool / G2 selector route.

It is not replay, not deployability evidence, and does not change X0/R3.

## Inputs

- factor pack: `runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json`
- enriched pool: `runtime/cn_research_factor_pack_v2_phase3aa_preflight_20260531/shared_candidate_pool_event_fund_enriched.json`
- evaluator panel: `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet`
- selector output: `runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector/aa/phase3_selection_only_report.json`

## Preflight Result

- enriched pool rows: 1,631
- factor pack rows: 834
- factor pack rows in enriched pool: 834
- factor pack rows not in enriched pool: 0
- factor fields used: 107
- fields missing from derived panel: 0
- fields missing from mature signal-vector panel: 0

## Selector-Only Gate

- pool cap: 160
- selected queue: 64
- signal sample size: 384
- candidate source counts:
  - `cn_research_feature_layer_v2`: 49
  - `event_derived_feature_layer`: 18
  - `unknown`: 93
- selected source counts:
  - `cn_research_feature_layer_v2`: 24
  - `event_derived_feature_layer`: 2
  - `unknown`: 38
- event candidates in pool: 48
- event candidates selected: 12
- fundamental candidates in pool: 19
- fundamental candidates selected: 14

## Guards

- forbidden replay/deployable/final-cluster fields used by selector: false
- signal-vector proxy requirement: pass
- fundamental signal-vector smoke: 4/4 ready, 0 errors

## Findings

The first 80-row micro gate proved fundamental fields could be evaluated, but the old event/other prefilter starved pure `fund_` candidates.

The prefilter was upgraded to three buckets:

- event
- fundamental
- other mature sources

After this change, fundamental rows entered the selected queue without using replay labels.

## Known Gaps

- `phase3e_selector_audit.csv` does not preserve `factor_lane` consistently for all selected rows. Source lane and candidate id remain sufficient for this gate, but the audit schema should be extended before a larger replay.
- This gate only validates selector and feature integration. It does not prove fundamental alpha value.

## Next Allowed Step

Run one frozen-queue replay smoke on the 64 selected rows if the next goal is alpha value validation.

Recommended smoke:

- no new candidate generation
- replay only from `runtime/cn_research_factor_pack_v2_selector_gate_20260531/selector`
- global cluster and source attribution required
- report event/fundamental/interaction contribution separately

Do not launch a full large search until replay smoke confirms the v2 queue is evaluable end-to-end.
