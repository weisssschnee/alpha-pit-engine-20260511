# Phase3AQ Sanitized Formula Packs Acceptance

decision: `TRUE_1MIN_CANARY_PACK_READY`

## Inputs

- source packs: `runtime/factor_packs/phase3an_sanitized_v1_20260609`
- adapter contract: `runtime/phase3aq_true_1min_formula_adapter_20260610`
- input candidates: `1370`

## Sanitized Outputs

- direct true 1min: `84`
- opening-window true 1min: `13`
- blocked / sidecar required: `1273`

## Expression Smoke

Smoke panel:

`runtime/phase3aq_true_1min_formula_adapter_20260610/canary/phase3aq_true_1min_formula_canary.parquet`

Results:

- direct pack: `84 / 84` evaluated with non-null output
- opening-window pack: `13 / 13` evaluated with non-null output
- eval failures: `0`

## Interpretation

The `97` passing formulas are ready for a true `trade_time` 1min canary search.

The `1273` blocked formulas are not declared invalid. Most require one of:

- lagged context sidecar for `ctx_*`
- market-cap / float-share sidecar for `final_*` and `float_share`
- event-state availability adapter for `evt_*`
- explicit daily context replacement for blocked `daily_ret`

## Hard Rules Preserved

- Search memory keys and candidate provenance are preserved.
- `daily_ret` is blocked, not silently mapped to minute returns.
- `first5/15/30` are opening-window fields, not frequency segmentation.
- X0/R3 remains read-only.
