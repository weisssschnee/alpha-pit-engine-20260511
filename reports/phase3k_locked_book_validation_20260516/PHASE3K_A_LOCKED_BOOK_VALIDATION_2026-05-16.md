# Phase3K-A Locked Book Validation - 2026-05-16

Decision: `PASS_KA_J4_RELAXED_HYGIENE_OVERLAY`

This is a no-search validation over locked Phase3J books. It does not generate formulas, reselect clusters, or tune thresholds.

## Compared Books

| metric | K0 J0 all | K1 J2 locked | K2 J4 relaxed locked |
| --- | ---: | ---: | ---: |
| cluster_count | 34 | 23 | 22 |
| median_turnover | 0.203328 | 0.17779 | 0.174296 |
| p90_turnover | 0.382188 | 0.276502 | 0.278967 |
| max_raw_share | 0.210526 | 0.129032 | 0.133333 |
| source_lane_top_share | 0.441176 | 0.521739 | 0.545455 |
| limit_suspension_loss_proxy | 0.023369 | 0.024846 | 0.025427 |
| median_capacity_proxy | 23524393.039062 | 23895134.562695 | 24333428.564258 |
| equal_cost_adjusted_proxy | 1.758429 | 1.75884 | 1.840207 |
| liquidity_adjusted_cost_adjusted_proxy | 2.15671 | 2.083104 | 2.100618 |
| liquidity_adjusted_top_cluster_contribution | 0.17298 | 0.213203 | 0.21323 |
| stress_1p0_survival_rate | 0.882353 | 0.913043 | 0.954545 |
| median_selected_date_count | 102.0 | 102.0 | 102.0 |
| p10_tradable_breadth | 110.0 | 110.0 | 110.0 |

## Cluster 087

- found: `True`
- source lane: `r0_cem_led`
- capacity proxy: `3707378.642187`
- capacity percentile within J2: `0.043478`
- cost-adjusted score: `-0.031224`
- cost score percentile within J2: `0.043478`
- expression: `Neg(CSRank(CSResidual(CSRank(Mean(Abs($amount),8)),CSRank(Mean(Abs($amount),21)))))`

## Interpretation

- J2 remains the baseline book-readiness book.
- J4_relaxed is evaluated as a hygiene overlay, not a mature capacity model.
- J4_relaxed removes only cluster_087; any improvement should be interpreted narrowly.
- cluster_087 remains a plausible removal target: low capacity percentile and negative cost-adjusted score.
- J4_relaxed does not degrade equal or liquidity-adjusted cost proxy versus J2 in this locked audit.

## Bias Scope

- K-A validates locked cluster-level proxies only.
- Subperiod stability is proxy-only here because no new subperiod replay is run.
- Capacity and execution remain research proxies, not production proof.
- K-B fresh G2 validation is still required for rule generalization.
