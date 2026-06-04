# Phase3AE Bounded Repair Factor Pack v1

decision: `PASS_AE2_BOUNDED_REPAIR_FACTOR_PACK_READY_FOR_SELECTOR_ONLY_CANARY`

## Scope

Lane B bounded factor-pack repair. This pack converts panel-ready repair-queue fields into bounded formula candidates for selector-only dry run and 64-audited canary. It does not start full search and cannot update the 149 baseline.

## Counts

- source fields: 94
- candidates: 686
- coverage placebo required: 686
- shuffled-field placebo required: 686
- event cutoff candidates: 268
- flow/liquidity candidates: 348
- capacity candidates: 94

## Factor Lanes

- event_state_machine_formula_lane: 268
- announcement_pit_formula_lane: 206
- lagged_daily_formula_lane: 192
- pit_context_formula_lane: 20

## Source Families

- price_state: 33
- limit_event: 20
- flow_liquidity: 13
- disclosure_event_flow: 12
- capacity_size: 5
- limit_event_sentiment: 4
- other: 4
- leverage_flow: 3

## Required Next Step

Run AE2 selector-only dry run first. If it passes forbidden-field, PIT/cutoff, coverage placebo, shuffled-field placebo, and source attribution checks, run a 64-audited replay canary. Do not run full search from this pack directly.

## Outputs

- factor pack: `runtime\factor_packs\phase3ae_bounded_repair_factor_pack_v1_20260604.json`
- candidates: `reports\phase3ae_bounded_repair_factor_pack_v1_20260604\phase3ae_bounded_repair_candidates.csv`
- source fields: `reports\phase3ae_bounded_repair_factor_pack_v1_20260604\phase3ae_bounded_repair_source_fields.csv`
- report json: `reports\phase3ae_bounded_repair_factor_pack_v1_20260604\phase3ae_bounded_repair_factor_pack_report.json`
