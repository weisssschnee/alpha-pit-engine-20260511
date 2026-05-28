# Phase3Z47 Event Study

- decision: `HOLD_Z47_EVENT_STUDY_HAS_RESEARCH_CANDIDATES`
- trigger_count: `15`
- research_candidate_count: `4`
- date_range: `2025-08-06` to `2026-05-08`
- execution: signal T, entry T+1, horizon 1d
- boundary: diagnostic only; no official object changes.

## Decision Counts

- EVENT_STUDY_RESEARCH_CANDIDATE: `4`
- HOLD_PLACEBO_NOT_BEATEN: `1`
- HOLD_TRADABILITY_FAILURE: `7`
- REJECT_NO_MATCHED_EXCESS: `3`

## Trigger Results

| trigger | role | events | signed mean | signed excess | random p95 pass | top3 share | tradability fail | decision |
|---|---|---:|---:|---:|---|---:|---:|---|
| up_streak_ge5 | `event_module` | 343 | 0.01393321 | 0.01423769 | `True` | 0.022011 | 0.883382 | `HOLD_TRADABILITY_FAILURE` |
| break_after_streak_ge3 | `veto` | 627 | 0.01153412 | 0.01266344 | `True` | 0.02746 | 0.521531 | `EVENT_STUDY_RESEARCH_CANDIDATE` |
| post_high_board_t1 | `event_module` | 322 | 0.01357025 | 0.01018996 | `True` | 0.052051 | 0.618012 | `HOLD_TRADABILITY_FAILURE` |
| is_market_high_board | `event_module` | 324 | 0.01010227 | 0.00942716 | `True` | 0.033218 | 0.66358 | `HOLD_TRADABILITY_FAILURE` |
| up_streak_ge4 | `event_module` | 641 | 0.00785957 | 0.00810717 | `True` | 0.016528 | 0.823713 | `HOLD_TRADABILITY_FAILURE` |
| break_after_streak_ge2 | `veto` | 1841 | 0.00701982 | 0.00754048 | `True` | 0.012549 | 0.370994 | `EVENT_STUDY_RESEARCH_CANDIDATE` |
| up_streak_ge2 | `challenger` | 3157 | 0.00619315 | 0.0053931 | `True` | 0.007808 | 0.611973 | `HOLD_TRADABILITY_FAILURE` |
| post_high_board_t2 | `event_module` | 320 | 0.00462181 | 0.00507483 | `True` | 0.037956 | 0.55625 | `HOLD_TRADABILITY_FAILURE` |
| up_streak_ge3 | `challenger` | 1283 | 0.00524556 | 0.0049229 | `True` | 0.012731 | 0.764614 | `HOLD_TRADABILITY_FAILURE` |
| open_not_close_up | `veto` | 686 | 0.0042181 | 0.00396172 | `True` | 0.03371 | 0.198251 | `EVENT_STUDY_RESEARCH_CANDIDATE` |
| touch_not_close_up | `veto` | 17938 | 0.0011269 | 0.00131691 | `True` | 0.004835 | 0.092708 | `EVENT_STUDY_RESEARCH_CANDIDATE` |
| down_rebound_ge3 | `event_module` | 122 | 0.00232159 | 0.00065721 | `False` | 0.150976 | 0.606557 | `HOLD_PLACEBO_NOT_BEATEN` |
| down_rebound_ge2 | `event_module` | 436 | -0.00369067 | -0.00342948 | `False` | 0.058059 | 0.366972 | `REJECT_NO_MATCHED_EXCESS` |
| break_after_high_board_t1 | `veto` | 166 | -0.01392039 | -0.00790243 | `False` | 0.122988 | 0.421687 | `REJECT_NO_MATCHED_EXCESS` |
| down_streak_ge2 | `event_module` | 839 | -0.01875126 | -0.02041511 | `False` | 0.031778 | 0.636472 | `REJECT_NO_MATCHED_EXCESS` |

## Interpretation

- This line tests sparse event triggers directly, not dense formula candidates.
- Any research candidate still requires larger OOS, matched-control refinement, and strict tradability review.
- No result can modify X0/R3 or enter the official shadow book from this report.
