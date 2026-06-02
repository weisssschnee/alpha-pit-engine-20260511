# CN Fundamental Controlled Smoke

decision: `PASS_CN_FUNDAMENTAL_CONTROLLED_SMOKE_WITH_PIT_HOLDS`

## Dataset Status

- diagnostic_until_announcement_date_join: 2
- hold_due_announcement_date_anomaly_check: 1
- pit_ready_with_notice_date_lag: 6

## Key Policy

- financial_statement_use: NOTICE_DATE <= signal_date_previous_session; available next trading day
- report_date_warning: REPORT_DATE/日期/报告日期 is period date, not signal availability date
- dividend_warning: 1970 announcement dates block promotion until repaired
- holder_warning: holder tables are usable only by announcement date and aggregate-level features
- scope: top200 high-amount controlled smoke; not full-universe PIT proof

## Outputs

- cn_fundamental_controlled_smoke.json
- cn_fundamental_dataset_contract.csv
- cn_fundamental_field_contract.csv
- registry: runtime\field_registry\cn_fundamental_field_registry_v1_20260531.json
