# CN Field Utilization Audit

decision: `FIELD_UTILIZATION_AUDIT_FINDS_MATERIAL_FLOW_AND_DERIVED_FIELD_GAPS`

## Counts

- panel_column_count: 152
- factor_pack_candidate_count: 834
- shared_pool_candidate_count: 1631
- selected_count: 64
- strict_audited_count: 64
- replay_pass_row_count: 62

## Family Utilization

| family | panel fields | factor-pack fields | pool fields | selected fields | strict fields | replay-pass fields | selected expr |
|---|---:|---:|---:|---:|---:|---:|---:|
| capacity_size | 21 | 1 | 3 | 2 | 2 | 2 | 16 |
| flow_liquidity | 4 | 3 | 4 | 2 | 2 | 2 | 12 |
| fundamental_holder_share | 5 | 5 | 5 | 3 | 3 | 3 | 5 |
| fundamental_quality | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| fundamental_risk | 3 | 3 | 3 | 3 | 3 | 3 | 5 |
| fundamental_scale_income_cash | 9 | 9 | 9 | 9 | 9 | 9 | 18 |
| limit_event_morphology | 81 | 81 | 81 | 6 | 6 | 4 | 12 |
| limit_seal_flow | 3 | 3 | 3 | 0 | 0 | 0 | 0 |
| metadata_id | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| other_unclassified | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| price_return | 7 | 0 | 4 | 3 | 3 | 3 | 27 |
| theme_sector | 5 | 1 | 1 | 1 | 1 | 0 | 2 |
| tradability_raw | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

## Critical Findings

- flow/liquidity fields exist in panel and mature generators, but v2 factor pack does not provide a dedicated standalone flow-liquidity lane
- turnover_ratio/seal flow fields appear in event_x_flow but were not selected in the current 64 queue
- raw volume appears through mature generators, not the v2 research factor pack
- volume/amount ratio and price-volume divergence fields are not materialized as named derived fields
- several raw panel columns are metadata or tradability controls and should not be promoted as alpha fields without role separation

## Missing Expected Derived Fields

- volume_ratio_5_20
- amount_ratio_5_20
- turnover_ratio_z20
- amount_to_float_mcap
- volume_to_float_share
- amihud_absret_over_amount
- seal_money_to_amount
- seal_rate_z20
- price_volume_divergence_5
- sector_relative_amount_ratio
- fundamental_quality_x_amount_ratio

## Next Action

`build_cn_flow_liquidity_factor_pack_v1_before_claiming_field_coverage_complete`
