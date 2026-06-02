# CN Integrated Factor Pack Selector Preflight Decision

decision: `PASS_INTEGRATED_FACTOR_PACK_SHARED_POOL_LIGHT_PREFLIGHT_HOLD_FULL_G2_SELECTOR`

confirmed:
- integrated factor pack is injected into mature shared pool
- forbidden label/meta fields are absent
- source-priority/search-memory metadata is present

not_confirmed:
- full G2 selector queue
- replay/deployable alpha
- production readiness

next: `run micro-G2 selector with reduced pool/sample or company-machine full selector-only job`
