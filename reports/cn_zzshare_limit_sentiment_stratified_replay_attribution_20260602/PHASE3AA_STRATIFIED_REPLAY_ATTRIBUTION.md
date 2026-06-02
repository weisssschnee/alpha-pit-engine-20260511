# Phase3AA Stratified Replay Attribution

decision: `HOLD_STRATIFIED_REPLAY_NO_DEPLOYABLE_SIGNAL`
audited: `27`
raw_non_gap_replay_pass: `0`
cost_survive: `3`
deployable: `0`
deployable_clusters: `0`
median_replay_sortino: `-2.434472`
median_turnover: `1.0`

## Interpretation

- This is a frozen-selection replay attribution; it does not regenerate candidates or rescore the selector.
- A zero-deployable result means this stratum should not be promoted from daily replay evidence alone.
- If the stratum is event-time sensitive, the next route is event-time/minute validation rather than same daily replay promotion.
