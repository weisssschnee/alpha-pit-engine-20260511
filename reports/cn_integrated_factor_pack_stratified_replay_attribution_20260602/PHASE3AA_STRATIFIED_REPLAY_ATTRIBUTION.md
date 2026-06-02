# Phase3AA Stratified Replay Attribution

decision: `REVIEW_STRATIFIED_REPLAY_HAS_DEPLOYABLE_BUT_NEEDS_CONCENTRATION_AUDIT`
audited: `35`
raw_non_gap_replay_pass: `3`
cost_survive: `26`
row_deployable: `0`
deployable_clusters: `1`
median_replay_sortino: `-1.92524`
median_turnover: `0.097008`

## Interpretation

- This is a frozen-selection replay attribution; it does not regenerate candidates or rescore the selector.
- A zero-deployable result means this stratum should not be promoted from daily replay evidence alone.
- If the stratum is event-time sensitive, the next route is event-time/minute validation rather than same daily replay promotion.
