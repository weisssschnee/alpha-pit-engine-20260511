# CN Integrated PIT Join Preflight

- decision: `PASS_JOIN_PREFLIGHT_WITH_DATE_COVERAGE_WARNING`
- selected_count: `64`
- selected_join_executable_count: `64`
- selected_blocked_count: `0`
- integrated_selected_count: `35`
- integrated_join_executable_count: `35`
- integrated_blocked_count: `0`

## Panel Coverage

- base date range: `2025-08-06` to `2026-05-08`
- minute date range: `2023-01-04` to `2026-04-10`
- nonminute date range: `2023-01-04` to `2026-04-10`
- date_coverage_warning: `True`

## By Lane
- cn_integrated_feature_layer / join_executable: `35`
- legacy_unknown / join_executable: `29`

## Field Sources
- base_replay: `43`
- nonminute_panel: `23`
- minute_panel: `12`
- derivable: `5`

## Missing Fields
- none

## Required Join Policy

- normalize base code from `sh/sz/bj` prefix format to `.SH/.SZ/.BJ` suffix format before joining.
- join minute panel on `normalized_code` and `date = exec_date`.
- join nonminute context panel on `normalized_code` and `date`.
- derive `vwap = amount / volume` in the joined replay panel with a zero-volume guard.

## Blocking Items
- Minute/nonminute panel date coverage ends before the base replay panel; replay after panel max date will have missing integrated features.
- Build step must normalize code format before joining: sh/sz/bj prefix to .SH/.SZ/.BJ suffix.
- Build step must derive vwap from base amount/volume with a zero-volume guard.
