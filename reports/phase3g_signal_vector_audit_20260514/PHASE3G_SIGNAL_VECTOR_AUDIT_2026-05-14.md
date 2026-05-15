# Phase3G Signal Vector Audit

## Decision

- decision: `PASS_VECTOR_PROXY_GATE`
- experiment_id: `20260514_phase3g_signal_vector_audit`
- candidate_rows: `1444`
- registry_rows: `129`
- vector_errors: `0`

## Calibration

| score | AUC | precision@threshold | recall@threshold | FPR@threshold | pairs |
|---|---:|---:|---:|---:|---:|
| sampled_signal_vector_corr | 0.676645 | 0.853125 | 0.42015 | 0.015266 | 738651 |
| daily_rank_ic_vector_corr | 0.671123 | 0.435748 | 0.459863 | 0.125674 | 738651 |
| daily_long_short_return_vector_corr | 0.647186 | 0.505815 | 0.359493 | 0.074125 | 738651 |
| symbolic_ast_field_operator_proxy | 0.553337 | 0.597256 | 0.055126 | 0.007845 | 738651 |

## Cluster Focus

| score | cluster | scope | members | recall | false positive rate |
|---|---|---|---:|---:|---:|
| sampled_signal_vector_corr | cluster_001 | phase3f | 1 | None | 0.0 |
| sampled_signal_vector_corr | cluster_003 | phase3f | 47 | 0.93062 | 0.016469 |
| daily_long_short_return_vector_corr | cluster_001 | phase3f | 1 | None | 0.129921 |
| daily_long_short_return_vector_corr | cluster_003 | phase3f | 47 | 0.786309 | 0.130524 |

## Findings

- Phase3G is a no-run audit: it does not generate new formulas or run replay.
- Best vector AUC=0.676645; best precision@0.8=0.853125.
- Symbolic proxy AUC=0.553337; vector proxy should replace symbolic proxy only if materially stronger.
- Current post-replay cluster labels are signal-correlation clusters, so pre-replay sampled signal vectors are the closest available observable proxy.
- E3V2 vector-diversified selector is eligible for selector-only dry run.

## Outputs

- summary_json: `reports\phase3g_signal_vector_audit_20260514\phase3g_signal_vector_audit_summary.json`
- summary_md: `reports\phase3g_signal_vector_audit_20260514\PHASE3G_SIGNAL_VECTOR_AUDIT_2026-05-14.md`
- vectors_npz: `runtime\phase3g_signal_vectors\phase3g_signal_vectors_20260514.npz`
- metadata_parquet: `runtime\phase3g_signal_vectors\vector_metadata.parquet`
- unique_metadata_parquet: `runtime\phase3g_signal_vectors\unique_vector_metadata.parquet`
- pair_metrics_csv: `reports\phase3g_signal_vector_audit_20260514\phase3g_pair_metrics.csv`
- vector_cluster_purity_csv: `reports\phase3g_signal_vector_audit_20260514\phase3g_vector_cluster_purity.csv`
- queue_vector_corr_csv: `reports\phase3g_signal_vector_audit_20260514\phase3g_queue_vector_corr.csv`
- errors_csv: `reports\phase3g_signal_vector_audit_20260514\phase3g_vector_errors.csv`
