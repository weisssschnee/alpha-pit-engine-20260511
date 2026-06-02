# CN Integrated Feature Transform Plan v1 Decision

decision: `PASS_INTEGRATED_FEATURE_TRANSFORM_PLAN_V1`

confirmed:
- 1min, limit-event-aligned, and non-minute PIT context fields now have one selector-facing transform map.
- labels/meta/key fields are explicitly blocked from selector input.
- RZRQ, holder, and fundamental context are ready for factor-pack templates under conservative lag rules.
- billboard remains diagnostic only.

not_confirmed:
- that every high-value raw field is panelized
- that these transforms produce deployable alpha
- production or execution readiness

next: `build_integrated_factor_pack_v1_from_high_priority_backlog_then_run_selector_only_smoke`
