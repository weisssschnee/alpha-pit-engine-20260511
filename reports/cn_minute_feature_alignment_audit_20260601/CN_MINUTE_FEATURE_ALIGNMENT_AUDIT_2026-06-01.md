# CN Minute Feature Alignment Audit - 2026-06-01

decision: `PASS_MINUTE_DAILY_ALIGNMENT_AUDIT`
audited_minute_days: `63`
minute_coverage_audited: `2026-01-05` to `2026-04-10`
minute_columns: `code, trade_time, close, open, high, low, vol, amount, date, pre_close, change, pct_chg`
median_prior_signal_overlap_rate: `0.997633`
min_prior_signal_overlap_rate: `0.996179`

## Interpretation

- 1min native fields are not the same object as daily/enrichment fields.
- Daily/fundamental/event fields are allowed only as lagged context for a minute trade date unless a timestamp contract proves intraday availability.
- Future intraday bars and close-derived returns are execution labels/diagnostics, not selector features.
- The next valid 1min feature step is to build minute-native early-session features and join lagged daily context by normalized code and prior trading day.

## Outputs

- overlap_csv: `reports\cn_minute_feature_alignment_audit_20260601\minute_daily_overlap_by_date.csv`
- field_route_contract_csv: `reports\cn_minute_feature_alignment_audit_20260601\field_route_contract.csv`
- coverage_csv: `reports\cn_minute_feature_alignment_audit_20260601\lagged_context_coverage_by_group.csv`
- minute_derived_contract_csv: `reports\cn_minute_feature_alignment_audit_20260601\minute_derived_feature_contract.csv`
- early_feature_sample_csv: `reports\cn_minute_feature_alignment_audit_20260601\minute_early_feature_sample.csv`
- json: `reports\cn_minute_feature_alignment_audit_20260601\cn_minute_feature_alignment_audit.json`
- markdown: `reports\cn_minute_feature_alignment_audit_20260601\CN_MINUTE_FEATURE_ALIGNMENT_AUDIT_2026-06-01.md`
