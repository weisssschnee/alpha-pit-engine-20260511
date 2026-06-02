# Phase3AA Stratified Replay Attribution

decision: `REVIEW_STRATIFIED_REPLAY_HAS_DEPLOYABLE_BUT_NEEDS_CONCENTRATION_AUDIT`
audited: `19`
raw_non_gap_replay_pass: `16`
cost_survive: `12`
row_deployable: `0`
deployable_clusters: `10`
median_replay_sortino: `-0.12646600000000002`
median_turnover: `0.573237`

## Interpretation

- This is a frozen-selection replay attribution; it does not regenerate candidates or rescore the selector.
- A zero-deployable result means this stratum should not be promoted from daily replay evidence alone.
- If the stratum is event-time sensitive, the next route is event-time/minute validation rather than same daily replay promotion.
