# Phase3AF Membership Control Aggregate V1

decision: `HOLD_PHASE3AF_MEMBERSHIP_LANE_CONTROL_NOT_BEATEN`

## Arm Summary

| arm | audited | deployable | raw non-gap | top share | role |
|---|---:|---:|---:|---:|---|
| `coverage_mask_placebo` | 31 | 6 | 24 | 0.1250 | `coverage_reference` |
| `same_count_random` | 31 | 7 | 21 | 0.0952 | `same_count_control` |
| `matched_control` | 31 | 2 | 18 | 0.1667 | `matched_liquidity_size_control` |

## Blockers

- `coverage_mask_not_better_than_same_count_random`

## Interpretation

- `same_count_random`: Controls for date-level active-count/event-opportunity effects without preserving original symbols.
- `matched_control`: Controls for date plus amount/capitalization-bucket membership effects.
- `result`: Coverage membership cannot be expanded while same-count random is comparable or stronger, even if matched liquidity/size control is weaker.

## Next Policy

- `full_search_allowed`: `False`
- `recommended_next`: `If HOLD, analyze date/event-count effects and build stricter event-module validation before any large search.`
- `numeric_lane_status`: `AF-B remains blocked by true-field-vs-coverage-mask confound from Phase3AE.`
