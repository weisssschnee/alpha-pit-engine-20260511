# Phase3AG Event Opportunity Audit V1

decision: `HOLD_PHASE3AG_EVENT_OPPORTUNITY_CONFOUND_CONFIRMED`

## Basis

- `phase3af_membership_control_decision`: `HOLD_PHASE3AF_MEMBERSHIP_LANE_CONTROL_NOT_BEATEN`
- `phase3af_blockers`: `['coverage_mask_not_better_than_same_count_random']`
- `coverage_fields`: `11`
- `date_count`: `163`
- `row_count`: `988005`

## Control Integrity Flags

- `matched_control_count_loss_on_broad_field`: `7`
- `ok`: `4`

## Family Summary

| family | fields | coverage active | matched active | matched preservation | flags |
|---|---:|---:|---:|---:|---|
| `broad_billboard_coverage` | 4 | 2613492 | 1131523 | 0.4330 | `matched_control_count_loss_on_broad_field` |
| `broad_holder_coverage` | 1 | 831992 | 158026 | 0.1899 | `matched_control_count_loss_on_broad_field` |
| `broad_rzrq_coverage` | 2 | 1165580 | 629204 | 0.5398 | `matched_control_count_loss_on_broad_field` |
| `sparse_limit_event` | 4 | 16230 | 16230 | 1.0000 | `ok` |

## Blockers

- `same_count_random_beats_coverage_reference_in_replay`
- `matched_control_has_count_preservation_failure_on_broad_fields`

## Interpretation

- `same_count_random`: Because same-count random beat coverage reference, the observed AF-A effect cannot be treated as symbol-specific membership edge.
- `matched_control`: The prior matched-control replay is not decisive for broad fields because high-coverage masks lost active-count preservation.
- `field_family`: Sparse limit-event fields should be separated from broad coverage fields before any event-module canary.

## Next Policy

- `large_search_allowed`: `False`
- `allowed_next`: `Build sparse-event-only AF-A canary and corrected matched controls; keep broad coverage fields out of event-alpha promotion.`
- `blocked_next`: `Do not expand all coverage masks or numeric AE2 repair fields into a large search.`
