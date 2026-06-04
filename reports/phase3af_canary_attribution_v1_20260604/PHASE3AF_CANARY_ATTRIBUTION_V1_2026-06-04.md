# Phase3AF Canary Attribution V1

decision: `PASS_PHASE3AF_CANARY_ATTRIBUTION_READY`

## Counts

- `pair_rows`: `31`
- `cluster_rows`: `69`
- `replay_positive_cluster_rows`: `36`

## Replay Positive By Arm

- `coverage_mask_placebo`: `14`
- `paired_true_ae2`: `5`
- `shuffled_value_placebo`: `17`

## Replay Positive By Input Field Family

- `billboard_flow`: `15`
- `event_limit_membership`: `6`
- `holder_announcement`: `2`
- `rzrq_leverage_flow`: `13`

## Interpretation

- `coverage_mask_cluster_strength`: Coverage-mask replay-positive clusters need event/membership validation, not numeric-field promotion.
- `numeric_value_strength`: True AE2 only has numeric-value evidence where it beats both coverage and shuffled controls; aggregate canary did not prove that.
