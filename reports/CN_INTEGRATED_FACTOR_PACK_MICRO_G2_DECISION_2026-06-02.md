# CN Integrated Factor Pack Micro-G2 Decision

decision: `PASS_INTEGRATED_FACTOR_PACK_MICRO_G2_SELECTOR_PREFLIGHT_NO_REPLAY`

confirmed:
- factor-pack-only injection works: `211 / 211` integrated candidates entered the enriched shared pool.
- micro-G2 selector completed on cached mature pool.
- selected queue count: `24`.
- selected integrated candidates: `12 / 24`.
- selected integrated buckets:
  - research/RZRQ: `7`
  - fundamental: `3`
  - minute/event-style: `2`
- replay-label leakage guard passed: `selector_uses_forbidden_fields = false`.
- signal-vector proxy requirement passed: `true`.

not_confirmed:
- replay pass
- deployable alpha
- cluster novelty
- production readiness
- full-size G2 selector runtime stability

runtime note:
- Full mixed-pool G2 selector was too slow in the interactive run and was stopped.
- The successful micro-G2 run used `factor_pack_only=true`, `pool_cap=60`, `signal_sample_size=200`, and `strict_audit_budget=24`.

next:
- Run a background/company-machine selector-only job with factor-pack-only injection and larger pool/sample.
- Only after selector-only queue quality is acceptable, run replay smoke.
