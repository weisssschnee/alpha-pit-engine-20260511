# Phase3G Decision Record

Date: 2026-05-15

## Decision

Algorithmic decision: `PASS_CONFIRM_PHASE3G_ALGORITHMIC`.

Metadata gate: `HOLD_METADATA_ONLY`.

Primary selector candidate:

- `G2_E3_signal_vector_diversified`

Not promoted:

- `G1_E3_current_proxy`: productive, but still concentrated.
- `G3_E3_strong_signal_vector_proxy`: diversity is too aggressive relative to yield.

Current production research baseline remains non-commercial. This result confirms a better pre-replay clustering proxy for search selection; it does not prove fund-level deployability or true book-marginal value.

## Evidence

Stage 1 vector proxy audit passed:

- Signal-vector AUC: `0.6766`
- Symbolic proxy AUC: `0.5533`
- Signal-vector precision at 0.8: `0.8531`
- Cluster 003 recall at 0.8: `0.9306`
- Cross-cluster false positive rate: `0.0165`

Final fixed-mixed company aggregate:

- Audited: `1024`
- Global unique clusters: `291`
- Global deployable clusters: `144`
- Raw non-gap pass: `978`
- Global top cluster share: `16.2577%`

Per-arm outcome:

| Arm | Audited | Deployable | Top Cluster Share | Median Turnover |
| --- | ---: | ---: | ---: | ---: |
| G0 E0 stable | 256 | 54 | 18.2186% | 0.178381 |
| G1 E3 current proxy | 256 | 51 | 36.3281% | 0.126914 |
| G2 signal-vector diversified | 256 | 67 | 4.9587% | 0.211370 |
| G3 strong signal-vector proxy | 256 | 54 | 3.8627% | 0.222916 |

## Interpretation

The Phase3F failure mode was real: symbolic, AST, field, operator, and semantic proxies can move concentration from one cluster to another instead of preventing it.

Phase3G fixes the proxy layer. Signal-vector similarity is not a full book-marginal value model, but it is a high-precision collision detector. That is enough to control pre-replay queue concentration.

G2 is the current best tradeoff:

- Higher deployable count than G0/G1/G3.
- Much lower concentration than G1.
- Less over-diversified than G3.

This is not a true book-marginal selector. It uses a signal-vector cluster proxy, not a return-residual or book-residual objective.

## Caveats

- `metadata_gate_decision = HOLD_METADATA_ONLY` because the final fixed aggregate was company-machine only.
- `aggregate_type = fixed_mixed`: G0/G1 came from the old official valid run; G2/G3 came from the fixed rerun.
- The report still includes legacy `return_corr_cluster` wording. The more accurate term for this phase is `signal-corr deployable cluster`.
- `phase3_cumulative_baseline_declared_clusters = 134`, while the fixed aggregate resolved `phase3_cumulative_baseline_deployable_clusters = 122`. This baseline QA mismatch should be resolved before a commercial-grade Phase4 claim.
- Some launch status files marked runs failed because `exit_code` was null even though reports and `report_written/completed` progress markers existed. Artifact completion must override nullable exit-code status.
- Sector/capacity/survivorship/final book construction remain blockers.

## Next Required Work

1. Resolve `134` declared vs `122` vector-matchable/reclustered baseline accounting.
2. Treat nullable launcher exit codes as warnings when artifact completion passes.
3. Record sklearn/model environment manifests before Phase3H.
4. Do not run H2 true book-residual selector until cheap return vectors exist for both candidates and registry representatives.
5. Use G2 as the Phase3H control only after metadata QA is explicit.

## Files

- `reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/PHASE3G_S29_S32_COMPANY_FIXED_MIXED_GLOBAL_AGGREGATE_2026-05-15.md`
- `reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/phase3g_s29_s32_company_fixed_mixed_global_aggregate_report.json`
- `reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/phase3g_s29_s32_company_fixed_mixed_per_arm_metrics.csv`
