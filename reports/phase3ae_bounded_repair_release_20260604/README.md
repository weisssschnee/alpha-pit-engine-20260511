# Phase3AE Bounded Repair Release 2026-06-04

This folder is the git-tracked release index for the current Phase3AE Lane B work.

## Decision

`HOLD_AE2_REPLAY_CANARY_COVERAGE_MEMBERSHIP_CONFOUND`

AE2 bounded repair fields are now:

- converted into bounded candidate formulas
- panel-visible
- value-coverage filtered, so schema-only / all-null fields cannot reach selection
- routed through the mature G2 selector-only path
- selected into a frozen 64-row queue
- paired coverage-mask and shuffled-value placebo packs are generated
- paired replay canary completed
- blocked from full large search because true-field AE2 did not beat coverage-mask placebo

This is not an alpha proof and not a full large-search authorization.

## Commits

- `6294e49 add phase3ae bounded repair factor pack`
- `a5cce1d add phase3ae bounded repair selector gate`
- current worktree update adds value-coverage filtering and placebo pack generation
- current worktree update also adds paired replay canary aggregate and mature loader sidecar-prefix support

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

### Replay Canary

The paired replay canary completed:

| arm | audited | deployable | raw non-gap | top share |
|---|---:|---:|---:|---:|
| `full64_true` | 64 | 14 | 22 | 0.0909 |
| `paired_true_ae2` | 31 | 3 | 5 | 0.2000 |
| `coverage_mask_placebo` | 31 | 6 | 24 | 0.1250 |
| `shuffled_value_placebo` | 31 | 1 | 17 | 0.0588 |

Interpretation:

- Full 64 true-field queue can replay and produce deployable output, but it mixes AE2 with non-AE2 selections.
- Paired true AE2 beats shuffled-value placebo, so stock-field numeric alignment is not pure noise.
- Coverage-mask placebo beats paired true AE2, so the current edge is more consistent with event/coverage membership than bounded numeric field values.

Policy:

- Do not launch AE2 full large search from this result.
- Split the next design into coverage/event-membership lane and numeric-value lane.
- Numeric bounded repair requires a stronger true-vs-coverage proof before large search.

### Phase3AF Follow-Up

Phase3AF split-lane prelaunch has been generated:

- coverage/event-membership lane: allowed as a separate event/membership hypothesis, with same-count random and matched-control gates
- numeric-value repair lane: blocked from large search until true-field beats both coverage-mask and shuffled-value placebo

Read-only attribution found replay-positive clusters by input family:

- `billboard_flow`: `15`
- `rzrq_leverage_flow`: `13`
- `event_limit_membership`: `6`
- `holder_announcement`: `2`

This supports a split-lane design. It does not support one-bucket AE2 full search.

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
- `src/our_system_phase2/runtime/phase3ae_bounded_repair_placebo_replay_prep_v1.py`
- `src/our_system_phase2/runtime/phase3ae_bounded_repair_replay_canary_aggregate_v1.py`
- `src/our_system_phase2/services/real_market_validation.py`
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
- `reports/phase3ae_bounded_repair_replay_canary_v1_20260604/PHASE3AE_BOUNDED_REPAIR_REPLAY_CANARY_AGGREGATE_V1_2026-06-04.md`
- `reports/phase3ae_bounded_repair_replay_canary_v1_20260604/phase3ae_bounded_repair_replay_canary_aggregate_v1.json`
- `reports/phase3ae_bounded_repair_replay_canary_v1_20260604/phase3ae_bounded_repair_replay_canary_arm_summary.csv`
- `reports/phase3ae_bounded_repair_replay_canary_v1_20260604/phase3ae_bounded_repair_placebo_replay_prep_v1.json`
- `reports/phase3af_split_lane_prelaunch_v1_20260604/PHASE3AF_SPLIT_LANE_PRELAUNCH_V1_2026-06-04.md`
- `reports/phase3af_split_lane_prelaunch_v1_20260604/phase3af_split_lane_prelaunch_v1.json`
- `reports/phase3af_canary_attribution_v1_20260604/PHASE3AF_CANARY_ATTRIBUTION_V1_2026-06-04.md`
- `reports/phase3af_canary_attribution_v1_20260604/phase3af_canary_attribution_v1.json`
- `reports/phase3af_canary_attribution_v1_20260604/phase3af_canary_cluster_attribution.csv`
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

No full AE2 large search is allowed from this release.

Allowed next work:

1. Audit coverage-mask placebo winners as a separate event/coverage-membership lane.
2. Redesign numeric-value bounded repair so true-field must beat coverage-mask placebo.
3. Keep replay canary outputs as diagnostic evidence, not promotion evidence.

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

Large-search authorization should require a future canary to show:

- no PIT/cutoff violation
- true-field beats coverage-mask placebo
- true-field beats shuffled-field placebo
- new-vs-149 signal clusters are nontrivial
- top cluster share stays controlled
- turnover/cost does not collapse
