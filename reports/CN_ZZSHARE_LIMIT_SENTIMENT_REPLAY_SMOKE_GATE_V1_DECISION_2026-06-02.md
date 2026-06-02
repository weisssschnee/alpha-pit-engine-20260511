# CN ZZShare Limit Sentiment Replay Smoke Gate Decision

decision: `HOLD_ZZSHARE_DAILY_REPLAY_ALPHA_PROMOTION`

confirmed:
- ZZShare joined panel can run mature G2 selector-only.
- Selector-only gate selected `27 / 64` ZZShare candidates from `49` injected candidates.
- Frozen registry signal-vector store is available after uploading Phase3G vector artifacts to the company workspace.
- Global frozen replay smoke executed successfully, but only `1 / 16` audited rows was ZZShare, so it is not evidence for ZZShare alpha quality.
- Daily-safe `ctx_zls_*_lag1` replay smoke executed on `13` ZZShare context candidates.

daily_safe_ctx_replay_smoke:
  audit_count: 13
  strict_pass_proxy: 0
  portfolio_replay_pass: 1
  cost_survives: 0
  deployable_clusters: 0
  top_cluster_share: 1.0

held_out_from_daily_replay:
- `evt_zls_*` event/seal/auction fields.

reason:
- `evt_zls_*` fields are same-day event-time fields and cannot be safely used by the current `after_open` daily replay clock without explicit lagged materialization or a minute/event-time evaluator.
- The attempted ZZShare-only replay surfaced `missing_field:evt_zls_fd_max`; the correct fix is not to blindly add same-day `evt_` fields to the daily loader, because that would create a leakage route.

not_confirmed:
- ZZShare daily alpha.
- ZZShare deployable cluster.
- Event-time/minute alpha from `evt_zls_*`.
- Production readiness.

next:
- Build lagged daily `evt_zls_*_lag1` fields or route `evt_zls_*` into a minute/event-time evaluator.
- Do not promote ZZShare daily context candidates based on this smoke.
