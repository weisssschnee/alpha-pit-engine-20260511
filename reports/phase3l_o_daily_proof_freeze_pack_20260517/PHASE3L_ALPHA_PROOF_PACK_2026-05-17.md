# Phase3L Alpha Proof Pack

- decision: `PASS_DAILY_STRONG_PROOF_BOOK_L2_5`
- evidence_level: `L2.5_daily_strong_proof_no_execution`
- candidate_book_clusters: 6
- candidate_sortino_proxy: 1.543331
- candidate_p90_turnover: 0.151635

## Candidate Book

| cluster | role | strength | daily_sortino | strict_sortino | turnover | source | weakness |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cluster_005 | core | 0.6975 | 2.203211 | 4.458059 | 0.199872 | agnostic_freeform_ast | high_turnover|weak_regime_proxy_axes=pit_regime_label:HOLD_INSUFFICIENT_AXIS_COVERAGE;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |
| cluster_001 | core | 0.5375 | 1.574226 | 3.82282 | 0.073418 | agnostic_freeform_ast | positive_sign_flip_score_but_placebo_not_passed|weak_regime_proxy_axes=liquidity_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK;pit_regime_label:HOLD_INSUFFICIENT_AXIS_COVERAGE;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |
| cluster_006 | core | 0.5075 | 1.799638 | 2.484331 | 0.051814 | r0_cem_led | weak_regime_proxy_axes=pit_regime_label:HOLD_INSUFFICIENT_AXIS_COVERAGE;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |
| cluster_009 | support | 0.4975 | 2.179256 | 3.286319 | 0.103397 | formula_gen_v2_repair_expansion | positive_sign_flip_score_but_placebo_not_passed|weak_regime_proxy_axes=pit_regime_label:HOLD_INSUFFICIENT_AXIS_COVERAGE;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |
| cluster_004 | support | 0.3875 | 1.330699 | 2.81205 | 0.027425 | formula_gen_v2_repair_expansion | weak_regime_proxy_axes=liquidity_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK;pit_regime_label:HOLD_INSUFFICIENT_AXIS_COVERAGE;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |
| cluster_002 | support | 0.383 | 1.273684 | 3.146535 | 0.076805 | agnostic_freeform_ast | weak_regime_proxy_axes=pit_regime_label:HOLD_AXIS_CONCENTRATED_OR_WEAK;volatility_lag_quantile:HOLD_AXIS_CONCENTRATED_OR_WEAK |

## Leave-One-Out Stress

| removed | clusters | sortino | delta | p90_turnover |
| --- | ---: | ---: | ---: | ---: |
| cluster_001 | 5 | 1.581717 | 0.038386 | 0.161282 |
| cluster_005 | 5 | 1.485564 | -0.057767 | 0.09276 |
| cluster_006 | 5 | 1.560813 | 0.017482 | 0.161282 |
| cluster_009 | 5 | 1.468648 | -0.074683 | 0.150645 |
| cluster_002 | 5 | 2.080365 | 0.537034 | 0.161282 |
| cluster_004 | 5 | 1.528002 | -0.015329 | 0.161282 |

## Boundaries

- This is daily proof, not production proof.
- Oracle combo is diagnostic only.
- Minute execution/capacity and live/paper survival remain blockers.
