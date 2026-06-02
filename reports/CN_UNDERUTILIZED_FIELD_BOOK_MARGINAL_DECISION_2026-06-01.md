# CN Underutilized Field Book Marginal Audit - 2026-06-01

decision: `PASS_CORE6_MARGINAL_OVERLAY_READY_FOR_LOCKED_FORWARD_AUDIT`

## Scope

No-search audit. This reads the frozen 162 discovery/book-readiness artifacts and compares new clusters against locked X0/R3.
It does not promote a production book and does not run candidate generation.

## Book Results

| book | clusters | ann | sortino | maxDD | corr_to_x0 | delta_ann | delta_sortino |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0_x0_r3 | 6 | 1.175657 | 6.085253 | -0.03442312 | 1.0 | 0.0 | 0.0 |
| B1_core6_r3_equal | 6 | 1.807344 | 7.870828 | -0.07008099 | 0.657526 | 0.631687 | 1.785575 |
| B1_core6_ungated_equal | 6 | 2.980671 | 9.469339 | -0.07008099 | 0.556577 | 1.805014 | 3.384086 |
| B2_x0_plus_core6_r3_equal12 | 6 | 1.47148 | 7.727991 | -0.03015874 | 0.878539 | 0.295823 | 1.642738 |
| B2_x0_plus_core6_r3_10pct_overlay | 6 | 1.231855 | 6.240717 | -0.03268579 | 0.994586 | 0.056198 | 0.155464 |
| B3_new13_r3_equal | 13 | 1.242291 | 7.192009 | -0.07048653 | 0.632921 | 0.066634 | 1.106756 |
| B3_new13_r3_source_factor_capped | 13 | 1.062881 | 7.894424 | -0.0563541 | 0.59673 | -0.112776 | 1.809171 |
| B3_new13_ungated_equal | 13 | 2.3952 | 9.537721 | -0.06808444 | 0.518966 | 1.219543 | 3.452468 |

## Interpretation

- core_new_clusters: `6`
- all_new_clusters: `13`
- evaluation_start: `2026-01-05`
- evaluation_end: `2026-05-06`
- x0_daily_source: `G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528\reports\phase3n_long_history_locked_validation_20260517\phase3n_daily_returns.csv`

## Boundary

- Confirms or rejects marginal daily-proxy value only.
- Does not confirm minute execution, real slippage, real capacity, or live survival.
