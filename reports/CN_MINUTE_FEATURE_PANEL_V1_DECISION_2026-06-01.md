# CN Minute Feature Panel V1 - 2026-06-01

decision: `PASS_MINUTE_FEATURE_PANEL_V1_BUILT`
rows: `345435`
columns: `114`
coverage: `2026-01-05` to `2026-04-10`
unique_symbols: `5500`
median_context_match_rate: `0.99763335`

## Boundary

- `m1_first5/*15/*30` fields are minute-native features with explicit earliest signal times.
- `ctx_*` fields are lagged daily/enrichment context from the previous trading day.
- `label_*` fields are future execution/evaluation labels and are forbidden as selector inputs.
