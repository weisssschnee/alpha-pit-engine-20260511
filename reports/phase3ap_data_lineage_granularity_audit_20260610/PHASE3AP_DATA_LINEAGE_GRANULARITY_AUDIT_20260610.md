# Phase3AP Data Lineage Granularity Audit

decision: `PHASE3AP_LINEAGE_AUDIT_FAILS_EXISTING_1MIN_FIRST_CLAIM`

## Core Finding

AE/AN/AO current-wide used code-date daily backbones with minute-derived/context columns. They are not true 1min-row searches. firstN opening-window fields are features, not 5/15/30min data segmentation.

Clarification: `first5`/`first15`/`first30` are valid opening-window feature summaries. They do not mean the data was resampled to 5/15/30min, and they must not be used as separate data backbones.

## Impact

- `raw_minute_2023_2025_sample` and `raw_minute_2026_sample` are true 1min rows because they have `trade_time`.
- `Phase3AE` and `Phase3AN` outputs are code-date panels. They contain `m1_*`/event/context columns, but no `trade_time`.
- `Phase3AO current-panel` inherits the Phase3AN code-date panel and is diagnostic only for 1min claims.
- `Phase3AO long-history` remains invalidated.

## Required Correction

Future minute-first search must use a real minute-row backbone with `trade_time`, not a daily code-date panel with minute-derived columns. Event cutoff fields may control availability, but must not define the search frequency.

