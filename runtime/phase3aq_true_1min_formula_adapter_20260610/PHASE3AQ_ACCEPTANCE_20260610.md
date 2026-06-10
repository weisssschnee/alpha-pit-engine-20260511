# Phase3AQ Acceptance

decision: `TRUE_1MIN_FORMULA_ADAPTER_ACCEPTED_FOR_CANARY_SEARCH_PREP`

## Verified

- Canary panel has `trade_time`.
- Mature-compatible `date` equals `trade_time`, not trading day.
- `exec_date` is preserved as the trading-day join key.
- `daily_ret` is not materialized; use `ret_1m` or explicit lagged daily context.
- `first5` / `first15` / `first30` are opening-window fields only.
- Before each opening window completes, its fields are null.
- Field contract covers all formula-facing canary fields.
- Mature expression engine smoke passed on true `trade_time` rows.

## Canary

- rows: `351137`
- codes: `6`
- trade_time_count: `58563`
- vwap scale: `amount / (vol * 100)`
- vwap median abs ratio error to close: `0.00042183239896803615`

## Outputs

- `phase3aq_true_1min_field_contract.csv`
- `phase3aq_formula_rewrite_rules.json`
- `phase3aq_true_1min_formula_adapter_report.json`
- `phase3aq_true_1min_formula_adapter_qa.json`
- `phase3aq_expression_engine_smoke.json`
- `canary/phase3aq_true_1min_formula_canary.parquet`

## Remaining Before Large Search

- Build formula-pack sanitizer against the Phase3AQ contract.
- Add explicit context sidecar joins for lagged daily/fundamental/RZRQ fields.
- Add event-state availability joins for `evt_*`.
- Build labels on `trade_time` horizons instead of old daily forward returns.
