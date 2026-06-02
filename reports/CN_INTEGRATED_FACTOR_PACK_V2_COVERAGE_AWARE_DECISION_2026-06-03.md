# CN Integrated Factor Pack v2 Coverage-Aware Gate

decision: `PASS_COVERAGE_AWARE_PACK_READY_FOR_SELECTOR_PREFLIGHT`
input_candidates: `355`
output_candidates: `294`
min_joint_coverage: `0.02`

## Interpretation

This gate measures whether candidate fields are observable on the PIT replay panel before replay.
It does not use replay pass, deployable labels, final clusters, or PnL labels.

## Lane Summary

- `minute_amount_share_daily`: kept `6` / `6`, median_joint_coverage `0.86852901`
- `minute_vs_daily_vwap_residual`: kept `8` / `8`, median_joint_coverage `0.86852901`
- `quality_direct_control`: kept `4` / `5`, median_joint_coverage `0.03143405`
- `quality_holder_residual`: kept `24` / `30`, median_joint_coverage `0.02989661`
- `quality_minus_balance_risk`: kept `12` / `15`, median_joint_coverage `0.03076705`
- `quality_size_residual`: kept `12` / `15`, median_joint_coverage `0.03143405`
- `quality_x_market_breadth`: kept `48` / `60`, median_joint_coverage `0.03143405`
- `quality_x_minute_pressure`: kept `72` / `90`, median_joint_coverage `0.03143405`
- `quality_x_rzrq_flow`: kept `72` / `90`, median_joint_coverage `0.03078122`
- `rzrq_size_normalized`: kept `36` / `36`, median_joint_coverage `0.59568727`
