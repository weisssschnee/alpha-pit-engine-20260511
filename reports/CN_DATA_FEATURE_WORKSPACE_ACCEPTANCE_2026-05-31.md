# CN Data Feature Workspace Acceptance

Decision: `PASS_CN_DATA_FEATURE_WORKSPACE_BOOTSTRAP`

## Workspace

- path: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531`
- branch: `feature/data-feature-workspace-20260531`
- base_head: `c47d107`
- source_workspace: `G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528`

## Reused Mature Assets

- Phase3AA mature-chain shared-pool/event-G2 runtime modules copied.
- Phase3AB large-search, aggregate, deep-validation, R3 challenger, and family audit modules copied.
- Phase3AA/AB/Z46-Z49 reports and run plans copied as research provenance.
- X0/R3 official chain remains read-only. This workspace is for controlled CN data acceptance and feature construction.

## New Entrypoints

- `app.py cn-controlled-data-smoke`
- `app.py cn-event-derived-feature-smoke`
- `app.py cn-field-factor-pack`

## Data Smoke Result

- decision: `PASS_CN_CONTROLLED_DATA_SMOKE`
- report_root: `reports/cn_controlled_data_smoke_20260531`
- field_registry: `runtime/field_registry/cn_alpha_field_registry_v1_20260531.json`
- table_count: `13`
- field_count: `306`

Important policies:

- Daily/event fields are next-trading-day conservative unless timestamp observability is explicitly proven.
- 1min bars are observable only after bar close; daily use requires explicit aggregation and lag.
- `holder_num_detail` must be PIT by announcement date.
- `stock_calendar` is blocked as a daily tradable-state table until standardized.
- `review_uplimit_reason` and `review_uplimit_reason_open` are multi-record event tables at stock-date level and require aggregation before joining.

## Event-Derived Feature Smoke Result

- decision: `PASS_CN_EVENT_DERIVED_FEATURE_SMOKE`
- feature_path: `runtime/derived_features/cn_event_daily_features_v1_20260531.parquet`
- rows: `443570`
- columns: `154`
- date_range: `2026-01-05..2026-05-14`
- code_count: `5521`

The first feature panel distinguishes:

- open-at-limit but not close-at-limit: `limit_up_open_not_close`
- intraday touch but not close-at-limit: `limit_up_touch_not_close`
- close-at-limit without open-at-limit: `limit_up_close_not_open`
- parametric rolling event counts: `limit_up_*_count_tN` for `N=2..10`

## Field To Factor Pack Result

- decision: `PASS_CN_FIELD_FACTOR_CONVERSION_PACK`
- report_root: `reports/cn_field_factor_conversion_plan_20260531`
- field_pack: `runtime/field_registry/cn_field_factor_field_pack_v1_20260531.json`
- factor_pack: `runtime/factor_packs/cn_event_factor_candidate_pack_v1_20260531.json`
- field_count: `154`
- candidate_count: `760`

Generated factor lanes:

- `direct_event`: direct event state/count transforms.
- `event_curve`: short-minus-long event pressure curves.
- `event_x_flow`: event state interacted with amount/turnover/seal/plate proxies.
- `event_residual_size`: event state residualized against size/capacity proxies.
- `event_x_theme`: event state interacted with `plate_score`.

## Verification

- `py_compile`: passed for new CN data/feature modules and copied Phase3AA/AB modules.
- `pytest tests/test_event_derived_features.py -q`: `8 passed`.
- `app.py list`: includes new CN data/feature/factor-pack entrypoints and mature Phase3AA/AB routes.

## Next Gate

Before any new search:

1. Audit the generated event panel against a small hand-sampled set of known limit/open-board dates.
2. Add 1min-derived open/touch/close confirmation for selected partitions only.
3. Feed `cn_event_factor_candidate_pack_v1_20260531` into Phase3AA shared-pool preflight with search memory.
4. Keep X0/R3 official shadow object read-only.
