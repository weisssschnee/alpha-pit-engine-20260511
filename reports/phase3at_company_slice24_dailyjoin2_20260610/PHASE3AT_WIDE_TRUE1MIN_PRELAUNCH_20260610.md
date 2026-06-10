# Phase3AT Wide True 1min Prelaunch

decision: `PHASE3AT_WIDE_TRUE_1MIN_PRELAUNCH_COMPLETE`

## Counts

- source years: `2025`
- max source files: `24`
- source selection: `stride`
- AQ panel rows: `1306461`
- AQ codes: `24`
- AQ trade_time groups: `58563`
- AR candidates: `{'sidecar_context_formula': 1002, 'event_state_cutoff_canary': 85, 'diagnostic_context_only': 149, 'still_blocked': 37}`
- AS evaluated: `1087`
- AS errors: `0`
- AS memory hits: `1007`

## Hard Rules

- input grain is true `trade_time` 1min.
- `date` is minute timestamp for evaluator compatibility, not trading day.
- non-minute fields enter only through Phase3AR PIT/cutoff sidecars.
- this prelaunch does not modify X0/R3 and is not alpha proof.

## Outputs

- run plan: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3at_wide_true1min_prelaunch_slice24_dailyjoin2_20260610\phase3at_run_plan.json`
- summary: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3at_wide_true1min_prelaunch_slice24_dailyjoin2_20260610\phase3at_wide_true1min_prelaunch_summary.json`
- AS rows: `D:\HermesWorker\workspace\phase3aj_new_data_current\runtime\phase3at_wide_true1min_prelaunch_slice24_dailyjoin2_20260610\phase3as_wide_eval\phase3as_true_1min_sidecar_canary_eval_rows.csv`
