# CN Integrated Factor Pack V2 Signal Novelty Audit

Date: 2026-06-03

## Decision

`PASS_SIGNAL_VECTOR_NOVELTY_PROXY_HOLD_FINAL_RECLUSTER`

This audit compares the fresh-pool integrated v2 candidates against the frozen
149 representative registry using sampled pre-replay signal vectors.

It does not run new search, does not rerun replay, and does not assert final
global replay-cluster novelty.

## Inputs

| item | path |
| --- | --- |
| candidate rows | `runtime/cn_integrated_factor_pack_v2_coverage_aware_fresh_pool_replay_s36_20260603/attribution/stratified_replay_rows.csv` |
| registry | `reports/phase3k_c_complete_149_registry_20260517/phase3k_c_149_representatives.csv` |
| dataset | `G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_all_fields_local.parquet` |

## Result

| metric | value |
| --- | ---: |
| registry rows | 149 |
| registry vector ready | 149 |
| registry vector errors | 0 |
| candidate rows | 19 |
| candidate vector ready | 19 |
| row-level deployable proxy | 7 |
| exact duplicate vs 149 among deployable proxy | 0 |
| signal duplicate vs 149 proxy among deployable proxy | 0 |
| signal-new vs 149 proxy among deployable proxy | 7 |
| duplicate threshold | 0.80 |
| highest deployable nearest-corr to 149 | 0.382300 |

## Interpretation

This is materially stronger than exact-expression novelty. The fresh-pool
deployable proxy rows are not just different strings; under the sampled
pre-replay signal representation, they are also far from the 149 representative
registry. The highest nearest-registry correlation among deployable proxy rows
is only `0.3823`, well below the `0.80` collision threshold.

The result supports treating the RZRQ-normalized lane as a genuinely new
research direction relative to the current 149 registry.

## Limits

Promotion is still blocked because this is not:

- a full global replay recluster;
- a marginal-value audit versus locked `X0/R3`;
- a fresh-date validation;
- production or execution evidence.

## Next Gate

Run a no-search marginal audit versus locked `X0/R3` using only the
signal-new deployable proxy rows. If marginal value is weak, keep the lane as
discovery-only despite novelty.
