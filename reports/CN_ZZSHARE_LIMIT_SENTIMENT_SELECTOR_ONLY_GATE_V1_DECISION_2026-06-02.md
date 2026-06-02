# CN ZZShare Limit Sentiment Selector-Only Gate Decision

decision: `PASS_ZZSHARE_MATURE_G2_SELECTOR_ONLY_GATE_HOLD_REPLAY_SMOKE`

confirmed:
- ZZShare limit/sentiment candidates are visible to mature G2 selector
- selected queue includes a material ZZShare slice
- signal-vector proxy and frozen registry vector store are available
- forbidden replay labels are not used

not_confirmed:
- replay pass
- deployable alpha
- book marginal value
- production readiness

next: `frozen replay smoke on selected rows only`
