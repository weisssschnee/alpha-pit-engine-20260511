# CN ZZShare Limit/Sentiment Factor Pack v1 Decision

decision: `PASS_ZZSHARE_FACTOR_PACK_V1_READY_FOR_PANELIZATION`

candidate_count: `157`
replay_executable: `False`
requires_panelization: `True`

confirmed:
- ZZShare limit/sentiment fields are converted into candidate expressions with search-memory keys
- future-label fields remain blocked
- event, sentiment, and hot-rank lanes are separated

not_confirmed:
- panelized feature coverage
- selector queue value
- replay pass
- deployable alpha

next: `build ZZShare sidecar/panelization, then run selector-only before replay`
