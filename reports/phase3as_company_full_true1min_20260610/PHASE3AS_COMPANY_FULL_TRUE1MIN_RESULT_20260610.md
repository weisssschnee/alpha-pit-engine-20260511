# Phase3AS Company Full True 1min Result

decision: `PHASE3AS_TRUE_1MIN_SIDECAR_CANARY_EXECUTABLE_NOT_ALPHA_PROOF`

## Run

- machine: `DESKTOP-7877972`
- worker job: `phase3as_company_full_true1min_retry_20260610`
- started: `2026-06-10 22:18:39`
- ended: `2026-06-10 22:39:37`
- exit: `0`
- command: `phase3as-true-1min-sidecar-canary-eval --sample-trade-times 0 --horizons 1,5,15,30`

## Counts

- input candidates: `1087`
- evaluated candidates: `1087`
- errors: `0`
- trade_time groups: `58563`
- panel rows: `351137`
- panel codes: `6`
- memory hits: `1007`
- fresh eligible candidates: `80`

## Interpretation

- This confirms the Phase3AR sidecar/event candidate packs are executable on the true `trade_time` 1min canary.
- Fresh robust rows are concentrated in `cn_integrated_v2_quality_x_rzrq_flow_*`.
- Fresh robust mean IC is close to zero despite high `ic_abs_mean`; with only 6 stocks, absolute per-minute cross-section correlation is noisy and should not be treated as alpha proof.
- `event_state_cutoff_canary` has `0` nonzero-IC rows in this 6-stock full canary, so the current event-cutoff line is coverage-limited, not validated.
- X0/R3 remains read-only; no promotion decision is implied.

## Local Pull

- pulled output root: `runtime/phase3as_company_full_true1min_20260610_pull`
- rows CSV: `runtime/phase3as_company_full_true1min_20260610_pull/phase3as_true_1min_sidecar_canary_eval_rows.csv`
- summary JSON: `runtime/phase3as_company_full_true1min_20260610_pull/phase3as_true_1min_sidecar_canary_eval_summary.json`

## Next

Before any large search claim, expand beyond the 6-stock true 1min canary. The next useful step is a wider true 1min panel canary with the same Phase3AS evaluator and search-memory tagging.
