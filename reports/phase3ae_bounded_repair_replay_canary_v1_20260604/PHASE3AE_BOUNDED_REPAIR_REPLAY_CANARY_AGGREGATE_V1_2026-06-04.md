# Phase3AE Bounded Repair Replay Canary Aggregate V1

decision: `HOLD_AE2_REPLAY_CANARY_COVERAGE_MEMBERSHIP_CONFOUND`

## Arm Summary

| arm | audited | deployable | raw non-gap | top share |
|---|---:|---:|---:|---:|
| `full64_true` | 64 | 14 | 22 | 0.0909 |
| `paired_true_ae2` | 31 | 3 | 5 | 0.2000 |
| `coverage_mask_placebo` | 31 | 6 | 24 | 0.1250 |
| `shuffled_value_placebo` | 31 | 1 | 17 | 0.0588 |

## Blockers

- `true_field_not_better_than_coverage_mask_placebo`

## Interpretation

- `full64_true_field`: The full selected queue runs and has deployable output, but this mixes AE2 with non-AE2 selections.
- `paired_true_vs_shuffled`: True AE2 beats shuffled-value placebo, so stock-field numeric alignment is not completely random.
- `paired_true_vs_coverage`: Coverage-mask placebo beats true AE2, so current edge is more consistent with coverage/event membership than numeric bounded field values.
- `large_search_policy`: Do not launch AE2 full large search from this result. Split coverage/event-membership lane from numeric-value lane first.
