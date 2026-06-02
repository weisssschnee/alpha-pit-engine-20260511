# CN ZZShare Limit Sentiment Selector-Only Gate V1

decision: `PASS_ZZSHARE_MATURE_G2_SELECTOR_ONLY_GATE_HOLD_REPLAY_SMOKE`

## Counts

- candidate_pool_count: `220`
- candidate_pool_count_before_prefilter: `437`
- selected_count: `64`
- zzshare_candidates_in_pool: `49`
- zzshare_candidates_selected: `27`
- selector_audit_rows: `216`
- selected_audit_rows: `64`

## Selected ZZShare Factor Lanes

- `zls_auction_money_to_offer`: `1`
- `zls_auction_turnover_to_amount`: `1`
- `zls_event_direct`: `6`
- `zls_event_direct_zrank`: `4`
- `zls_hot_rank_direct`: `1`
- `zls_hot_rank_inverse`: `1`
- `zls_ladder_to_limit_ratio`: `1`
- `zls_max_seal_to_amount`: `1`
- `zls_seal_to_amount`: `1`
- `zls_sentiment_direct_zrank`: `10`

## Queue Metrics

- selected_queue_signal_corr_mean: `0.209323`
- selected_queue_signal_corr_median: `0.09861`
- registry_signal_corr_mean: `0.085199`
- registry_signal_corr_median: `0.0`

## Interpretation

The mature G2 selector can see the ZZShare limit/sentiment pack and selects it materially in a no-replay gate.
This permits a frozen replay smoke, but it is not an alpha-quality or production claim.

## Next

`frozen replay smoke on selected rows only`
