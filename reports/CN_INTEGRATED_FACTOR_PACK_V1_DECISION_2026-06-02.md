# CN Integrated Factor Pack v1 Decision

decision: `PASS_INTEGRATED_FACTOR_PACK_V1_READY_FOR_SELECTOR_PREFLIGHT`

candidate_count: `211`

confirmed:
- integrated materialized fields now have candidate expressions with search-memory keys
- source-priority metadata is attached
- official X0/R3 remains read-only

not_confirmed:
- replay pass
- deployable alpha
- production readiness

next: `run selector-only shared-pool preflight for this pack`
