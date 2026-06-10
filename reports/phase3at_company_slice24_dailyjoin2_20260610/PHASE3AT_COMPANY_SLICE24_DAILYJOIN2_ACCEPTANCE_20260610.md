# Phase3AT Company Slice24 DailyJoin2 Acceptance

decision: `COMPANY_TRUE_1MIN_SIDECAR_CHAIN_VALIDATED_NOT_ALPHA_PROOF`

## What Passed

- AQ true 1min panel: `1306461` rows, `24` codes, `58563` trade_time groups.
- `date_equals_trade_time`: `True`; `exec_date` remains trading-day join key.
- AR sidecar panel: `1306461` rows, `417` columns.
- AR status counts: `{'diagnostic_context_only': 149, 'event_state_cutoff_canary': 85, 'sidecar_context_formula': 1002, 'still_blocked': 37}`.
- AS evaluated: `1087/1087`, errors `0`.
- Search memory hits: `1007`; fresh candidates `80`.
- AS sample: `2400` trade_time groups, `53538` rows, `24` codes.

## Engineering Fix

- Non-minute sidecars now join on unique `code + exec_date` keys before expanding back to 1min rows.
- This removed the fullA minute-row blowup path and made the company run finish cleanly.

## Boundary

- This is chain validation, not alpha proof.
- Fresh robust rows should be reviewed on wider cross-section before any reward/search-axis change.

## Files

- Runtime pull: `runtime/phase3at_company_slice24_dailyjoin2_20260610_pull`
- Fresh robust top CSV: `reports/phase3at_company_slice24_dailyjoin2_20260610/phase3at_company_slice24_dailyjoin2_fresh_robust_top.csv`
- Acceptance JSON: `reports/phase3at_company_slice24_dailyjoin2_20260610/phase3at_company_slice24_dailyjoin2_acceptance_summary.json`
