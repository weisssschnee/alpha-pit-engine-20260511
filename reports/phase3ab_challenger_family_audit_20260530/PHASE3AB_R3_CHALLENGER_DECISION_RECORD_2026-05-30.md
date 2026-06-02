# Phase3AB R3 Challenger Decision Record

Decision: `HOLD_PHASE3AB_R3_CHALLENGER_DIAGNOSTIC_ONLY`.

## Confirmed

- 9 Phase3AB recent/R3 challenger candidates remain valid diagnostic candidates.
- All 9 fail X0/R3 marginal overlay promotion when evaluated against the locked X0/R3 daily object.
- The family is concentrated in `volume_ratio_x_momentum_curve`, `turnover_ratio_x_momentum_curve`, and `amount_ratio_x_momentum_curve`.

## Not Confirmed

- Official X0/R3 overlay promotion.
- All-history alpha validity.
- Production readiness, minute execution, true capacity, or live survival.

## Key Metrics

- x0_r3_ann: `1.175657`
- x0_r3_sortino: `6.085253`
- candidate_count: `9`
- overlay_reject_count: `9`
- r3_mean_abs_corr: `0.980032`
- r3_max_abs_corr: `0.999597`

## Standalone Book Check

| book | ann | sortino | max dd | delta ann vs X0 | blend7 delta ann |
|---|---:|---:|---:|---:|---:|
| x0_r3 | 1.175657 | 6.085253 | -0.03442312 | 0.0 |  |
| challenger_all9_r3_equal | 0.633729 | 2.612814 | -0.10170532 | -0.541928 | -0.087197 |
| challenger_all9_no_gate_equal | 0.59036 | 2.276754 | -0.17840631 | -0.585297 | -0.0952 |
| lane_amount_ratio_x_momentum_curve_r3_equal | 0.4604 | 1.944617 | -0.10293393 | -0.715257 | -0.120353 |
| lane_turnover_ratio_x_momentum_curve_r3_equal | 0.687607 | 2.872091 | -0.10004205 | -0.48805 | -0.077503 |
| lane_volume_ratio_x_momentum_curve_r3_equal | 0.686392 | 2.814522 | -0.1023408 | -0.489265 | -0.077718 |
| challenger_lane_balanced_r3_equal | 0.607822 | 2.604774 | -0.10177091 | -0.567835 | -0.091955 |
| challenger_top1_per_lane_r3_equal | 0.613364 | 2.963901 | -0.09768817 | -0.562293 | -0.090932 |

## Bias Audit

- OOS evidence grade: `WEAK`; 2026 window has 78 daily observations.
- Discovery status: post-discovery validation of Phase3AB search outputs.
- Cost model: 10 bps turnover-cost proxy inherited from candidate deep validation.
- Date alignment: candidate daily returns come from after-open signal and one-day execution lag; X0/R3 uses locked daily return object and official R3 gate.
- Blocking issue: weak recent-OOS-only evidence and no marginal improvement versus locked X0/R3.

## Required Next Action

- Do not add these candidates to X0/R3.
- Keep as diagnostic recent/R3 challenger pool.
- If searching further, use marginal-aware reward against X0/R3 and family duplicate penalties.

## Outputs

- family_summary_json: `reports\phase3ab_challenger_family_audit_20260530\phase3ab_challenger_family_audit.json`
- book_csv: `reports\phase3ab_challenger_family_audit_20260530\phase3ab_challenger_book_metrics.csv`
- pairwise_corr_csv: `reports\phase3ab_challenger_family_audit_20260530\phase3ab_challenger_pairwise_corr.csv`
- source_summary_csv: `reports\phase3ab_challenger_family_audit_20260530\phase3ab_challenger_source_summary.csv`
- daily_book_csv: `reports\phase3ab_challenger_family_audit_20260530\phase3ab_challenger_book_daily.csv`
