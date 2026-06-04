# Phase3AE Bounded Repair Release 2026-06-04

This folder is the git-tracked release index for the current Phase3AE Lane B work.

## Decision

`PASS_AE2_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_HOLD_REPLAY_CANARY`

AE2 bounded repair fields are now:

- converted into bounded candidate formulas
- panel-visible
- value-coverage filtered, so schema-only / all-null fields cannot reach selection
- routed through the mature G2 selector-only path
- selected into a frozen 64-row queue
- paired coverage-mask and shuffled-value placebo packs are generated
- blocked from promotion until paired replay canary is run

This is not an alpha proof and not a full large-search authorization.

## Commits

- `6294e49 add phase3ae bounded repair factor pack`
- `a5cce1d add phase3ae bounded repair selector gate`
- current worktree update adds value-coverage filtering and placebo pack generation

## Core Results

### Factor Pack

- source fields: `94`
- bounded candidates: `686`
- coverage placebo required: `686`
- shuffled-field placebo required: `686`
- event cutoff candidates: `268`
- flow/liquidity candidates: `348`
- capacity candidates: `94`

### Selector-Only Gate

- source factor pack candidates: `686`
- available candidates after panel availability filter: `686`
- value-filtered candidates after non-null coverage gate: `294`
- missing field candidates: `0`
- low value-coverage candidates blocked: `392`
- AE2 rows injected into mature shared pool: `192`
- selector selected count: `64`
- AE2 selected count: `31`
- selector audit rows: `379`
- forbidden selected hits: `0`
- low coverage selected hits: `0`
- missing audit metadata rows: `0`
- blockers: none

### AE2 Selected Lane Split

- `event_state_machine_formula_lane`: `15`
- `announcement_pit_formula_lane`: `9`
- `lagged_daily_formula_lane`: `7`

### AE2 Selected Role Split

- `event_state_bounded_formula_candidate`: `15`
- `flow_liquidity_bounded_formula_candidate`: `8`
- `leverage_flow_bounded_formula_candidate`: `7`
- `capacity_normalized_bounded_formula_candidate`: `1`

### Selected Field Coverage

The first placebo-pack run exposed a real blocker: selected schema-visible HFQ aliases included all-null fields. The selector gate now rejects zero/non-material value coverage before queue construction.

Selected AE2 fields in the current queue have nonzero coverage:

- billboard / flow fields: about `66.13%`
- holder change field: about `84.21%`
- RZRQ fields: about `58.38%` to `59.59%`
- sparse fengdan event fields: about `0.088%` to `0.788%`, retained because event non-null counts are above the sparse-event minimum

This means the current queue is value-gated. It still needs true-vs-placebo replay comparison before any alpha claim.

## Git-Tracked Artifacts

### Factor Pack

- `src/our_system_phase2/runtime/phase3ae_bounded_repair_factor_pack_v1.py`
- `runtime/factor_packs/phase3ae_bounded_repair_factor_pack_v1_20260604.json`
- `reports/phase3ae_bounded_repair_factor_pack_v1_20260604/PHASE3AE_BOUNDED_REPAIR_FACTOR_PACK_V1_2026-06-04.md`
- `reports/phase3ae_bounded_repair_factor_pack_v1_20260604/phase3ae_bounded_repair_factor_pack_report.json`
- `reports/phase3ae_bounded_repair_factor_pack_v1_20260604/phase3ae_bounded_repair_candidates.csv`
- `reports/phase3ae_bounded_repair_factor_pack_v1_20260604/phase3ae_bounded_repair_source_fields.csv`

### Selector-Only Gate

- `src/our_system_phase2/runtime/phase3ae_bounded_repair_selector_only_gate_v1.py`
- `src/our_system_phase2/runtime/phase3ae_bounded_repair_placebo_pack_v1.py`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/PHASE3AE_BOUNDED_REPAIR_SELECTOR_ONLY_GATE_V1_2026-06-04.md`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_selector_only_gate_v1.json`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_selected_candidates.csv`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_field_locations.csv`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_value_coverage_fields.csv`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_low_coverage_candidates.csv`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_low_coverage_selected_hits.csv`
- `reports/phase3ae_bounded_repair_selector_only_gate_v1_20260604/phase3ae_bounded_repair_joined_panel_report.json`
- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/phase3ae_bounded_repair_factor_pack_value_filtered_v1_20260604.json`
- `reports/phase3ae_bounded_repair_placebo_v1_20260604/PHASE3AE_BOUNDED_REPAIR_PLACEBO_PACK_V1_2026-06-04.md`
- `reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_bounded_repair_placebo_pack_report.json`
- `reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_placebo_candidate_pairs.csv`
- `reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_placebo_field_stats.csv`
- `reports/phase3ae_bounded_repair_placebo_v1_20260604/phase3ae_placebo_candidates.csv`
- `runtime/factor_packs/phase3ae_bounded_repair_placebo_factor_pack_v1_20260604.json`
- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3_strict_selection_inputs.json`
- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3_selection_only_report.json`
- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/selector_only/aa/phase3e_selector_audit.csv`
- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/shared_candidate_pool_phase3ae_bounded_repair_enriched.json`

### Replay Canary Plan

- `runtime/run_plans/phase3ae_bounded_repair_replay_canary_run_plan_v1_20260604.json`

## Local Runtime Artifact

The joined panel is intentionally not committed because it is large and regenerable:

- `runtime/phase3ae_bounded_repair_selector_only_v1_20260604/phase3ae_bounded_repair_joined_panel_v1.parquet`
- rows: `988005`
- columns: `759`
- size: about `384 MB`

## Go / No-Go

### Allowed Now

Run the AE2 64-audited replay canary from the frozen selector output, after the required placebo checks:

1. paired true-field vs coverage-mask placebo on selected AE2 rows
2. paired true-field vs shuffled-field placebo on selected AE2 rows
3. PIT lag / event cutoff contract check
4. frozen queue hash record
5. strict/replay/cluster canary on the frozen 64-row queue

### Not Allowed Yet

Do not start full Phase3AE large search from AE2 yet.

Reason:

- selector-only gate proves routing and queue selection, not alpha quality
- no replay pass yet
- no new-vs-149 replay cluster proof yet
- no coverage/shuffle placebo proof yet
- no cost/turnover/deployability evidence yet

## Large-Search Readiness

The system is at:

`READY_FOR_AE2_REPLAY_CANARY`

It is not yet at:

`READY_FOR_AE2_FULL_LARGE_SEARCH`

Large-search authorization should require the 64-audited canary to show:

- no PIT/cutoff violation
- true-field beats coverage-mask placebo
- true-field beats shuffled-field placebo
- new-vs-149 signal clusters are nontrivial
- top cluster share stays controlled
- turnover/cost does not collapse
