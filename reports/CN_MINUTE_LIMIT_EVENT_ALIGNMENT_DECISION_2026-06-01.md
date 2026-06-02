# CN Minute Limit Event Alignment - 2026-06-01

decision: `PASS_LIMIT_EVENT_ALIGNMENT`
rows: `3997944`
days: `786`
symbols: `5762`

## Findings

- `up_limit_time` is aligned as stock-level timestamped intraday event features by cutoff.
- `uplimit_trend` is structurally supported, but current 2026 silver trend rows are null and blocked for 2026 use.
- Daily/fundamental/RZRQ/billboard fields remain retained as lagged/PIT context through the route audit; they are not discarded.
