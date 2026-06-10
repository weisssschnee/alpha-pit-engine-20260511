# Phase3AO Wrong-Source Cleanup And Acceptance

decision: `PHASE3AN_DAILY_BACKBONE_DIAGNOSTIC__PHASE3AO_LONG_HISTORY_OLD_1D_INVALIDATED`

## Finding

The Phase3AO long-history line used an old TDX daily backbone:

`G:/Project_V7_Rotation/scripts/data/phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet`

That panel was then joined with selected minute/nonminute sidecars. It was not a true 1min-first large search backbone. Therefore its long-history alpha results cannot be accepted as evidence about the new 1min/enriched field system.

This does **not** invalidate the Phase3AN current-wide line as a **daily-backbone diagnostic**. Phase3AN built and used:

`runtime/phase3an_daily_sentiment_joined_panel_20260609/phase3an_daily_sentiment_joined_panel.parquet`

That panel has 988,005 rows and 811 columns. It is a `date/code` panel with minute-derived and lagged sentiment/context columns, not a raw 1min-row or true minute-first backbone. The Phase3AN join report recorded `PASS_PHASE3AN_DAILY_SENTIMENT_PANEL_JOIN`, and the Phase3AN replay slim panel for audit128 recorded 0 missing expression fields. The 30/30 current-panel replay that used this panel is therefore valid only as recent daily-backbone diagnostic evidence.

## Cleanup

- Removed old `phase2/phase3n *_maxopt.parquet` daily search backbones.
- Removed old `tdx_official_vipdoc` raw daily package.
- Removed Phase3AO long-history joined panels, sidecars, replay outputs, logs, and launch scripts.
- Removed the less-complete 152-column augmented daily panel.
- Kept the 811-column `phase3an_daily_sentiment_joined_panel` as the validated Phase3AN daily-backbone diagnostic panel.

## Guardrail

`cn_integrated_pit_selected_panel_builder build-joined-panel` now refuses legacy 1D TDX backbones unless `--allow-legacy-daily-backbone` is explicitly passed for diagnostic reproduction.

## Current Data Routes

- 1min-derived code-date feature input, not primary minute-first backbone:
  `runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1`
- Raw/silver minute sources:
  `stock_1min_2023_2025_symbol_parquet_v2`
  `stock_1min_2026_parquet_by_date`
- Lagged context:
  `runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602`
- Valid recent current-wide diagnostic panel:
  `runtime/phase3an_daily_sentiment_joined_panel_20260609/phase3an_daily_sentiment_joined_panel.parquet`

## Alpha Evidence Status

- Phase3AO long-history outputs: invalidated, not accepted.
- Phase3AN current-wide panel and slim replay panel: valid daily-backbone diagnostic infrastructure.
- Phase3AO current-panel top30/expanded72 outputs: valid recent diagnostic evidence on Phase3AN panel, not true 1min-first evidence, not long-history proof, and not promotion evidence.
- X0/R3 official object: unaffected and remains read-only.

## Acceptance Checks

- Legacy old-source path scan: zero hits after cleanup.
- Builder compile: passed.
- Legacy backbone guard self-test: passed.
- Company machine active Python jobs checked: running crypto probe only, not this A-share wrong-source line.

## Next

Prepare the next search as two separated lanes:

- Phase3AN-current-wide continuation: recent-panel diagnostic only, using the 811-column Phase3AN panel.
- Phase3AP true minute/cutoff large search: blocked until a real `trade_time` or explicit cutoff cross-section primary backbone is built. The existing minute feature panel can be a feature input, not the primary backbone.

Both lanes must use search memory, field validation, PIT lag contracts, and explicit dataset provenance in every output.
