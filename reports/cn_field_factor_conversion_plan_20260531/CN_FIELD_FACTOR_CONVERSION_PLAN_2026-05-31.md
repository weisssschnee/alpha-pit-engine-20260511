# CN Field To Factor Conversion Plan

Decision: `PASS_CN_FIELD_FACTOR_CONVERSION_PACK`

## Core Path

1. source table field
2. normalized field registry with lag/PIT policy
3. derived daily event feature panel
4. field pack with formula eligibility
5. factor candidate pack with expression metadata
6. Phase3AA shared-pool enrichment with search memory
7. G2/source-priority frozen selection
8. strict replay/global clustering/OOS-regime-marginal audit

## Counts

- field_count: `154`
- candidate_count: `760`
- field_pack: `runtime\field_registry\cn_field_factor_field_pack_v1_20260531.json`
- factor_pack: `runtime\factor_packs\cn_event_factor_candidate_pack_v1_20260531.json`

## Field Status

- diagnostic_only_not_promotion: `2`
- eligible_for_candidate_generation: `144`
- metadata_only_not_formula_numeric: `8`

## Factor Lanes

- direct_event: `240`
- event_curve: `120`
- event_residual_size: `80`
- event_x_flow: `288`
- event_x_theme: `32`

## Non-Negotiable Bias Controls

- Same-day close/touch/reason fields are not usable for same-day after-open selection without lag.
- `stock_calendar` and non-PIT holder fields remain blocked.
- Candidate rows are not alpha proof; they require shared-pool frozen selection and replay.
- `official_book_eligible=false` for every generated row.

## First Candidate Examples

| candidate_id | lane | expression |
| --- | --- | --- |
| `cn_factor_direct_event_0001` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t10,2))` |
| `cn_factor_direct_event_0002` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t10,3))` |
| `cn_factor_direct_event_0003` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t10,5))` |
| `cn_factor_direct_event_0004` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t2,2))` |
| `cn_factor_direct_event_0005` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t2,3))` |
| `cn_factor_direct_event_0006` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t2,5))` |
| `cn_factor_direct_event_0007` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t3,2))` |
| `cn_factor_direct_event_0008` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t3,3))` |
| `cn_factor_direct_event_0009` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t3,5))` |
| `cn_factor_direct_event_0010` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t4,2))` |
| `cn_factor_direct_event_0011` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t4,3))` |
| `cn_factor_direct_event_0012` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t4,5))` |
| `cn_factor_direct_event_0013` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t5,2))` |
| `cn_factor_direct_event_0014` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t5,3))` |
| `cn_factor_direct_event_0015` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t5,5))` |
| `cn_factor_direct_event_0016` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t6,2))` |
| `cn_factor_direct_event_0017` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t6,3))` |
| `cn_factor_direct_event_0018` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t6,5))` |
| `cn_factor_direct_event_0019` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t7,2))` |
| `cn_factor_direct_event_0020` | `direct_event` | `CSRank(Mean($limit_up_any_close_not_open_in_t7,3))` |