# CN ZZShare Limit Sentiment Selector Pool Preflight Decision

decision: `PASS_ZZSHARE_SELECTOR_POOL_PREFLIGHT_HOLD_FULL_G2_SELECTOR`

confirmed:
- ZZShare factor candidates are injected into the mature shared candidate pool
- required joined-panel fields pass the availability gate
- forbidden replay/future label fields are absent
- source-priority and source-credit metadata are present

not_confirmed:
- mature G2 selected queue
- replay/deployable alpha
- production readiness

next: `run mature G2 selector-only on the ZZShare joined panel and frozen enriched pool`
