# Phase3AE Structured Large-Search Prelaunch

decision: `PASS_PHASE3AE_STRUCTURED_LARGE_SEARCH_PRELAUNCH`

## Evidence

- searcher adaptation: `PASS_SEARCHER_ADAPTATION_CLASSIFICATION_WITH_REPAIR_QUEUE`
- direct formula-ready fields: `1774`
- formula repair queue fields: `1416`
- event-state fields: `256`
- regime/gate fields: `395`
- blocked/key/cutoff fields: `491`
- replay128 survivors: `14`
- replay128 provisional new-vs-149 signal-space survivors: `13`
- replay128 known/duplicate signal survivors: `1`

## Matrix

| arm | lane | selector-only | replay canary | role |
|---|---|---:|---:|---|
| `AE0_mature_G2_baseline` | `baseline` | 256 | 64 | control |
| `AE1_direct_lagged_formula` | `direct_lagged_formula` | 256 | 64 | structured_search_lane |
| `AE2_bounded_factor_pack_repair` | `bounded_factor_pack_repair` | 256 | 64 | highest_priority_search_lane |
| `AE3_event_state_actor_motif` | `event_state_actor_motif` | 256 | 64 | event_module_lane |
| `AE4_regime_context_interaction` | `regime_context_interaction` | 256 | 64 | gate_interaction_lane |

## Forbidden

- Do not throw all 4775 fields into one formula generator.
- Do not allow future labels, timestamps, text, keys, or same-day unavailable fields into alpha search.
- Do not treat event, regime, or tradability fields as ordinary direct rank formulas.
- Do not claim alpha proof from searcher adaptation classification.
- Do not claim new alpha without new-vs-149 signal-vector recluster.
- Do not update official baseline from replay canary alone.

## Decision Logic

Phase3AE is ready for lane-specific selector-only dry runs and replay canaries. It is not permission for full-field, one-pot formula search. Lane B is the highest-value next lane because it converts high-value repair-queue fields into bounded factor packs while explicitly defending against PIT, unit, coverage-mask, and shuffled-field artifacts.

## Outputs

- lane manifest: `reports\phase3ae_structured_large_search_prelaunch_20260604\phase3ae_lane_manifest.csv`
- run plan: `runtime\run_plans\phase3ae_structured_large_search_prelaunch_v1.json`
- machine summary: `reports\phase3ae_structured_large_search_prelaunch_20260604\phase3ae_structured_large_search_prelaunch.json`
