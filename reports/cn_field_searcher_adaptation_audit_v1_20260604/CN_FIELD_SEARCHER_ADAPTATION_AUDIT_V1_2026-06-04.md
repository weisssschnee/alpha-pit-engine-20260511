# CN Field Searcher Adaptation Audit v1

decision: `PASS_SEARCHER_ADAPTATION_CLASSIFICATION_WITH_REPAIR_QUEUE`

## Summary

- field_count: `4775`
- direct_formula_search_ready_count: `1774`
- formula_search_repair_queue_count: `1416`
- event_state_machine_field_count: `256`
- event_state_search_repair_queue_count: `47`
- gate_or_regime_field_count: `395`
- blocked_or_key_field_count: `491`
- non_formula_search_field_count: `886`

## Suitability Counts

- `context_or_interaction`: `193`
- `diagnostic_review`: `587`
- `direct_formula_candidate`: `118`
- `direct_formula_candidate_after_notice_lag`: `2823`
- `direct_formula_candidate_lagged`: `249`
- `event_module_candidate`: `112`
- `event_module_or_gate`: `142`
- `gate_only`: `60`
- `not_direct_formula`: `2`
- `not_suitable`: `489`

## Lane Counts

- `announcement_pit_formula_lane`: fields `2823`, direct `2823`, event `0`, gate/context `0`, blocked `0`
- `blocked_not_search_input`: fields `489`, direct `0`, event `0`, gate/context `0`, blocked `489`
- `event_cutoff_contract`: fields `2`, direct `0`, event `2`, gate/context `0`, blocked `2`
- `event_state_machine_formula_lane`: fields `112`, direct `0`, event `112`, gate/context `0`, blocked `0`
- `event_state_machine_gate_lane`: fields `142`, direct `0`, event `142`, gate/context `0`, blocked `0`
- `lagged_daily_formula_lane`: fields `249`, direct `249`, event `0`, gate/context `0`, blocked `0`
- `lagged_price_context_lane`: fields `99`, direct `0`, event `0`, gate/context `99`, blocked `0`
- `lagged_state_context_lane`: fields `1`, direct `0`, event `0`, gate/context `1`, blocked `0`
- `manual_review_lane`: fields `587`, direct `0`, event `0`, gate/context `0`, blocked `0`
- `pit_context_formula_lane`: fields `118`, direct `118`, event `0`, gate/context `0`, blocked `0`
- `regime_context_interaction_lane`: fields `93`, direct `0`, event `0`, gate/context `93`, blocked `0`
- `tradability_risk_gate_lane`: fields `60`, direct `0`, event `0`, gate/context `60`, blocked `0`

## Searcher Contracts

- Direct formula lanes can enter bounded factor packs only after PIT or lag contracts, then selector canary and replay/style/cost audit.
- Event lanes must use event-state/actor-motif validation with cutoff proof, event count, matched controls, random same-count placebo, and tradability checks.
- Regime/context lanes must use gate or interaction validation, including gate lag and placebo checks. They are not standalone rank fields by default.
- Tradability, keys, timestamps, text, and future labels are not alpha search inputs.

## Interpretation

The searcher should not ingest all fields uniformly. Numeric PIT fields can become bounded formula candidates; timestamped event fields require event-state validation; regime and tradability fields belong in gate/interaction lanes; metadata, text, keys, cutoffs, and future labels stay blocked.

This audit proves adaptation by route, not by alpha performance. Direct formula lanes still need replay/style/cost audit; event lanes need event-count, matched-control, and tradability validation; regime/gate lanes need gate placebo and lag checks.

The immediate work queue is no longer vague: build factor-pack candidates for panel-ready numeric/event fields, build sidecars for high-value registered fields, and keep non-formula fields out of direct formula search.
