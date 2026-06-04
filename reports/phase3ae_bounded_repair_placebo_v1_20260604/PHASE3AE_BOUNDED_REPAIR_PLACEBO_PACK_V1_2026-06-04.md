# Phase3AE Bounded Repair Placebo Pack V1

decision: `PASS_AE2_PLACEBO_PACK_READY_FOR_REPLAY_CANARY_COMPARISON`

## Counts

- selected AE2 true candidates: `31`
- input fields: `11`
- placebo candidates: `62`

## Interpretation

Coverage-mask candidates test event/coverage membership. A strong coverage placebo is not automatically bad; it means the edge may come from field availability or event membership rather than numeric magnitude.

Shuffled-value candidates preserve coverage and date-level distribution while breaking stock-field alignment. If shuffled candidates match true candidates, numeric field values are not adding much beyond coverage/distribution.

This pack is for paired replay canary comparison only. It is not an alpha proof.

## Outputs

- placebo_factor_pack: `runtime\factor_packs\phase3ae_bounded_repair_placebo_factor_pack_v1_20260604.json`
- placebo_sidecar: `runtime\phase3ae_bounded_repair_placebo_v1_20260604\phase3ae_bounded_repair_placebo_sidecar_v1.parquet`
- candidate_pairs: `reports\phase3ae_bounded_repair_placebo_v1_20260604\phase3ae_placebo_candidate_pairs.csv`
- field_stats: `reports\phase3ae_bounded_repair_placebo_v1_20260604\phase3ae_placebo_field_stats.csv`
- candidates_csv: `reports\phase3ae_bounded_repair_placebo_v1_20260604\phase3ae_placebo_candidates.csv`
- report_json: `reports\phase3ae_bounded_repair_placebo_v1_20260604\phase3ae_bounded_repair_placebo_pack_report.json`
- markdown: `reports\phase3ae_bounded_repair_placebo_v1_20260604\PHASE3AE_BOUNDED_REPAIR_PLACEBO_PACK_V1_2026-06-04.md`
