# CN ZZShare Limit/Sentiment Factor Pack v1

status: `zzshare_limit_sentiment_factor_pack_ready_for_panelization_then_selector_no_replay_yet`
candidate_count: `49`
replay_executable: `False`
requires_panelization: `True`

## Factor Lanes

- `zls_auction_money_to_offer`: `1`
- `zls_auction_turnover_to_amount`: `1`
- `zls_event_direct`: `6`
- `zls_event_direct_zrank`: `6`
- `zls_high_board_x_open_board`: `1`
- `zls_hot_rank_direct`: `4`
- `zls_hot_rank_inverse`: `1`
- `zls_hot_rank_x_capacity`: `1`
- `zls_ladder_to_limit_ratio`: `1`
- `zls_lb_height_x_open_board`: `1`
- `zls_limit_up_down_ratio`: `1`
- `zls_market_up_down_ratio`: `1`
- `zls_max_seal_to_amount`: `1`
- `zls_open_board_rate`: `1`
- `zls_seal_to_amount`: `1`
- `zls_sentiment_direct`: `10`
- `zls_sentiment_direct_zrank`: `10`
- `zls_streak_x_seal`: `1`

## Policy

- X0/R3 remains read-only.
- This pack is not replay proof and cannot run official replay until panelized.
- `next_*` fields are blocked as future labels.
- `uplimit_stocks` event fields require event-time cutoff or T+1 lag.
- market sentiment and hot-rank fields are T+1 context only.
