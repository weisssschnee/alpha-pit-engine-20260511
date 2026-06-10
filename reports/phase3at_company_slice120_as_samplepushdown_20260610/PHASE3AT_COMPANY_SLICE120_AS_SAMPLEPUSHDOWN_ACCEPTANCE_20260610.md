# Phase3AT Company Slice120 AS Sample-Pushdown Acceptance

decision: `ACCEPT_ENGINEERING_GATE_NOT_ALPHA_PROOF`

## Scope

This run validates the Phase3AS true 1min sidecar evaluator on the company machine after the sample-pushdown fix.

- input panel: `runtime/phase3at_wide_true1min_prelaunch_slice120_dailyjoin_20260610/phase3ar_wide_sidecar/phase3ar_true_1min_sidecar_canary.parquet`
- company task: `job_20260611_040150_f21f83`
- company start/end: `2026-06-11T04:01:54` .. `2026-06-11T04:04:08`
- X0/R3: read-only, no promotion decision

## Fix Accepted

The old AS path read the full 1min augmented panel with all expression columns before applying `sample_trade_times`, which made slice120 memory-fragile.

The accepted path now:

- reads all `trade_time` values only to choose sampled signal timestamps;
- reads expression fields only on sampled signal timestamps;
- reads only `code/date/trade_time/close` on the label window needed for future 1min returns;
- reports signal and label read windows separately.

## Counts

- input candidates: `1087`
- evaluated candidates: `1087`
- errors: `0`
- memory hits: `1007`
- fresh candidates: `80`
- panel codes: `120`
- original trade_time groups: `58563`
- signal trade_time groups evaluated: `2400`
- signal panel rows: `271896`
- label read trade_time groups: `58563`
- panel schema columns: `417`
- read expression/core columns: `382`
- expression fields: `372`

## Result Read

This is an engineering pass, not an alpha pass.

The robust fresh subset is weak. The best fresh robust candidates are repeated lagged sentiment-count fields with about `0.0122` absolute IC on horizon 1 and near-zero IC on longer horizons. Event-state candidates can show high absolute IC only at tiny event counts, so they remain diagnostic.

## Hard Rules Preserved

- true 1min cross-section key is `trade_time`;
- `date` remains compatibility metadata, not the cross-section key;
- future labels are computed from true 1min rows by `code`;
- daily/event sidecars are used only after Phase3AR PIT/cutoff materialization;
- search-memory hits are tagged and are not counted as fresh structures;
- no old 1D kline path is used for this AS validation.

## Outputs

- summary: `runtime/phase3at_company_slice120_as_samplepushdown_20260610_pull/phase3as_true_1min_sidecar_canary_eval_summary.json`
- rows: `runtime/phase3at_company_slice120_as_samplepushdown_20260610_pull/phase3as_true_1min_sidecar_canary_eval_rows.csv`
- errors: `runtime/phase3at_company_slice120_as_samplepushdown_20260610_pull/phase3as_true_1min_sidecar_canary_eval_errors.csv`
