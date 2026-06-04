# Phase3AF Split-Lane Prelaunch V1

decision: `PASS_PHASE3AF_SPLIT_LANE_PRELAUNCH_NO_SEARCH`

## Basis

- `phase3ae_canary_decision`: `HOLD_AE2_REPLAY_CANARY_COVERAGE_MEMBERSHIP_CONFOUND`
- `blockers`: `['true_field_not_better_than_coverage_mask_placebo']`
- `paired_true_deployable`: `3`
- `coverage_mask_deployable`: `6`
- `shuffled_value_deployable`: `1`

## Lanes

### AF_A_coverage_event_membership

Turn the coverage-mask result into a first-class event/coverage-membership lane.

Allowed inputs:
- coverage mask fields
- event membership fields
- coverage-conditioned actor motifs
- matched-control and same-count random controls

Not allowed:
- claim numeric field value edge
- promote to official book
- skip event count/tradability checks

First gate: `{'canary_scale': '64 audited', 'must_beat': 'same-count random and matched-control, not the original numeric expression', 'required_outputs': ['event_count', 'matched_control_excess', 'same_count_random_p95', 'tradability_failure_rate', 'new_vs_149_signal_cluster']}`

### AF_B_numeric_value_repair

Retain only bounded numeric formulas whose true values beat coverage-mask and shuffled-value controls.

Allowed inputs:
- nonzero value-coverage fields
- residualized numeric transforms
- field-value-minus-coverage controls

Not allowed:
- use schema visibility as success
- use coverage-only effect as numeric proof
- full large search before true-vs-coverage canary pass

First gate: `{'canary_scale': '64 audited', 'pass_condition': ['true_field_deployable > coverage_mask_deployable', 'true_field_deployable > shuffled_value_deployable', 'top_cluster_share <= 20%', 'no PIT/cutoff violation']}`

## Policy

- `phase3ae_full_large_search_allowed_now`: `False`
- `reason`: `AE2 true fields did not beat coverage-mask placebo.`
- `next_large_search_candidate`: `only after AF_A or AF_B passes its own canary`
