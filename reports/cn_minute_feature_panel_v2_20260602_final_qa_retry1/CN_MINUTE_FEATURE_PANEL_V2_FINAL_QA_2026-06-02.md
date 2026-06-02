# CN Minute Feature Panel V2 Final QA - 2026-06-02

decision: `PASS_MINUTE_FEATURE_PANEL_V2_FINAL_QA`
parquet_files: `5`
total_rows: `3997944`
duplicate_key_rows: `0`
key_null_rows: `0`
context_sample_any_match_rate: `0.8749049855677657`
unknown_field_count: `0`

## Boundary

- `ctx_*` fields are prior-trading-day context only.
- `m1_first5/15/30_*` fields are intraday observable after the stated cutoff.
- `label_*` and full-day summaries are evaluation-only, not selector input.
