# CN Research Field/Factor V2 Path

status: `PASS_EVENT_PLUS_FUNDAMENTAL_FEATURE_LAYER_READY_FOR_G2_SELECTOR_NO_REPLAY`

## Scope

This record defines the controlled path from newly aggregated CN public enrichment data into the mature shared-pool / G2 signal-vector selector.

It does not promote any alpha, change X0/R3, or claim replay/deployability.

## Input Assets

- event feature layer: `runtime/derived_features/cn_event_daily_features_v1_20260531.parquet`
- event-augmented mature panel: `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_augmented_v1_20260531.parquet`
- fundamental aggregate package: `G:/Project_V7_Rotation/data/cn_public_enrichment/cn_fundamental_akshare_batch_v1_20260531/aggregated_v1`
- fundamental PIT panel: `runtime/fundamental_features/cn_fundamental_daily_pit_features_v1_20260531.parquet`
- research factor pack: `runtime/factor_packs/cn_research_factor_candidate_pack_v2_20260531.json`
- event+fundamental mature panel: `runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet`

## Fundamental PIT Policy

Promotion-grade candidate inputs are limited to datasets with usable announcement or notice dates:

- `balance_sheet_report_em`: `NOTICE_DATE` then next trading day as-of.
- `profit_sheet_report_em`: `NOTICE_DATE` then next trading day as-of.
- `cash_flow_sheet_report_em`: `NOTICE_DATE` then next trading day as-of.
- `share_change_cninfo`: `公告日期` then next trading day as-of.
- `main_stock_holder_sina`: `公告日期` then next trading day as-of.
- `circulate_stock_holder_sina`: `公告日期` then next trading day as-of.

Held out from promotion-grade feature construction:

- `financial_analysis_indicator_sina`: diagnostic until announcement-date join is proven.
- `zygc_em`: diagnostic until announcement-date join is proven.
- `dividend_cninfo`: held because sampled implementation-announcement dates include 1970 anomalies.

## Factor Conversion Lanes

- `direct_event`: direct event morphology fields.
- `event_curve`: rolling or age-aware event transformations.
- `event_x_flow`: event fields crossed with flow/amount/turnover proxies.
- `event_residual_size`: event residualization against size/capacity proxies.
- `event_x_theme`: event fields crossed with theme/plate proxies.
- `fundamental_quality`: PIT quality/cashflow/margin/holder fields.
- `fundamental_risk_inverse`: inverse leverage, goodwill, and inventory risk fields.
- `fundamental_size_residual`: fundamental scale residualized against total assets.
- `fundamental_x_event`: PIT quality fields interacted with event morphology.

## Chain Contract

- Candidate generation is research-only and `official_book_eligible = false`.
- Event fields remain subject to evaluator signal-clock lags.
- Fundamental fields are already lagged through the notice-date next-trading-day as-of panel and must not be same-day joined from raw reports.
- Shared-pool injection must pass `--include-fundamental-candidates`; otherwise pure `fund_` rows are correctly filtered out by the older event-only injection contract.
- `FieldEncoder` has explicit `fund_` handling; fundamental fields must not fall back to `close`.
- Signal-vector smoke must verify at least one `fund_` expression evaluates through the mature evaluator before any selector run.

## Current Verification

- controlled fundamental smoke: `PASS_CN_FUNDAMENTAL_CONTROLLED_SMOKE_WITH_PIT_HOLDS`
- fundamental PIT panel: `PASS_CN_FUNDAMENTAL_PIT_FEATURE_PANEL_BUILT`
- research signal panel v2: `PASS_CN_RESEARCH_SIGNAL_PANEL_V2_BUILT`
- v2 shared-pool preflight: `PASS_FACTOR_PACK_READY_FOR_G2_SELECTOR`
- v2 fundamental signal-vector smoke: `PASS_EVENT_FIELD_SIGNAL_VECTOR_SMOKE`

## Next Allowed Step

Run selector-only G2 micro dry-run on the v2 enriched pool and v2 event+fundamental panel.

Do not run replay or search before selector-only output proves:

- frozen queue exists,
- selected `fund_` exposure is nonzero or explicitly zero by score,
- no forbidden replay/deployable/final-cluster fields are used,
- source attribution separates event, fundamental, and event-fundamental interaction candidates.
