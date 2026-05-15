# Phase3H Registry Canonicalization

- created_at: `2026-05-15T16:15:49+08:00`
- decision: `PASS_DUAL_BASELINE_POLICY`
- metadata_policy: `DUAL_BASELINE_ACCEPTED`
- discovery_baseline: `134`
- selector_vector_baseline: `122`
- representative_count: `129`
- missing_representatives: `5`
- merged_representatives: `7`

## Policy

Use discovery_baseline=134 for historical cumulative cluster accounting and selector_vector_baseline=122 for Phase3H signal-vector nearest-cluster/cap logic.

This clears the Phase3G metadata blocker for using G2 as a Phase3H signal-vector control. It does not clear the true book-residual selector gate.

## Interpretation

The 134->122 gap is accepted as registry canonicalization: five declared clusters lack representatives and seven representative rows naturally merge under signal-vector reclustering. This no longer blocks G2 as a Phase3H signal-vector control, but it still blocks any true book-residual selector claim.

## Missing Representatives

| declared_cluster_id | reason |
| --- | --- |
| declared_missing_001 | declared_count_exceeds_representative_rows |
| declared_missing_002 | declared_count_exceeds_representative_rows |
| declared_missing_003 | declared_count_exceeds_representative_rows |
| declared_missing_004 | declared_count_exceeds_representative_rows |
| declared_missing_005 | declared_count_exceeds_representative_rows |

## Natural Signal-Vector Merges

| declared_cluster_id | vector_cluster_id | canonical_declared_cluster | peers |
| --- | --- | --- | --- |
| cluster_021 | cluster_017 | cluster_001 | cluster_001,cluster_021,cluster_062 |
| cluster_030 | cluster_007 | cluster_011 | cluster_011,cluster_030 |
| cluster_062 | cluster_017 | cluster_001 | cluster_001,cluster_021,cluster_062 |
| cluster_090 | cluster_072 | cluster_043 | cluster_043,cluster_090 |
| cluster_097 | cluster_137 | cluster_027 | cluster_027,cluster_097 |
| cluster_117 | cluster_068 | cluster_057 | cluster_057,cluster_117 |
| cluster_142 | cluster_304 | cluster_038 | cluster_038,cluster_142 |

## Outputs

- `phase3h_registry_canonicalization.json`
- `declared_to_vector_cluster_map.csv`
- `missing_representatives.csv`
- `merged_representatives.csv`
