# Phase3AR Sidecar Field Adapter

decision: `PHASE3AR_SIDECAR_FIELDS_ATTACHED_FOR_TRUE_1MIN_CANARY`

## Counts

- input blocked candidates: `1273`
- `diagnostic_context_only`: 149
- `event_state_cutoff_canary`: 85
- `sidecar_context_formula`: 966
- `still_blocked`: 73

## Hard Rules

- `ctx_*` fields join by `code + exec_date`; partitioned context `date` is explicitly treated as `exec_date`.
- cap fields use previous available daily row, not same-day daily values.
- `evt_*` and `mkt_*` fields are hidden before the cutoff encoded in the field name.
- `daily_ret` remains blocked.
- current-day aggregate fields such as `m1_amount_day` remain blocked because they require full-day future information.
- raw `evt_uplimit_*` fields without cutoff suffix or lag1 alias remain blocked; use `evt_limit_*_by_HHMM` or `ctx_zls_evt_*_lag1` instead.
- billboard fields remain diagnostic until a disclosure timestamp contract exists.

## Outputs

- augmented canary: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ar_sidecar_field_adapter_20260610\phase3ar_true_1min_sidecar_canary.parquet`
- context pack: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ar_sidecar_field_adapter_20260610\phase3ar_sidecar_context_formula_pack.json`
- event pack: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ar_sidecar_field_adapter_20260610\phase3ar_event_state_cutoff_canary_pack.json`
- diagnostic pack: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ar_sidecar_field_adapter_20260610\phase3ar_diagnostic_context_only_pack.json`
- still blocked: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ar_sidecar_field_adapter_20260610\phase3ar_still_blocked_formula_rows.json`
- field coverage: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\reports\phase3ar_sidecar_field_adapter_20260610\phase3ar_materialized_field_coverage.csv`

## Expression Smoke

- `sidecar_context_formula`: candidates=966 smoked=24 nonnull=24 errors=0
- `event_state_cutoff_canary`: candidates=85 smoked=24 nonnull=14 errors=0
- `diagnostic_context_only`: candidates=149 smoked=24 nonnull=24 errors=0
