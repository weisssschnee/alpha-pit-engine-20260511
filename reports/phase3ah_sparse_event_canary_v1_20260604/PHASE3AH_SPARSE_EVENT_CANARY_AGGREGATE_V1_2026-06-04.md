# Phase3AH Sparse Event Canary Aggregate V1

decision: `HOLD_PHASE3AH_SPARSE_EVENT_CANARY_CONTROLS_NOT_BEATEN`

## Arm Summary

| arm | audited | deployable | raw non-gap | top share |
|---|---:|---:|---:|---:|
| `true_sparse_event` | 15 | 0 | 0 | 0.0000 |
| `coverage_sparse_event` | 15 | 2 | 9 | 0.3333 |
| `same_count_sparse_event` | 15 | 5 | 11 | 0.1818 |
| `matched_sparse_event` | 15 | 1 | 10 | 0.3000 |

## Blockers

- `true_sparse_value_not_better_than_sparse_coverage`
- `true_sparse_value_not_better_than_same_count_control`
- `sparse_coverage_not_better_than_same_count_control`

## Interpretation

- `numeric_sparse_event`: True sparse event values produced no deployable clusters in this canary.
- `membership_sparse_event`: Sparse coverage membership produced deployables but did not beat same-count random.
- `opportunity_count`: Same-count sparse control was strongest, so event opportunity/date-count effects remain the dominant explanation.

## Next Policy

- `large_search_allowed`: `False`
- `event_formula_expansion_allowed`: `False`
- `allowed_next`: `Treat limit/event fields as regime/opportunity diagnostics or veto/intensifier candidates, not rank-alpha search budget.`
