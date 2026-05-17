# Phase3P Gate Failure Monitor

- decision: `PASS_PHASE3P_GATE_FAILURE_MONITOR_CREATED`
- scope: `fixed_r3_gate_failure_monitor_no_search_no_retuning`
- r3_threshold: `0.9888283511695009`

## Recent OOS 2026 Findings

Worst gate-on loss contributor:

- cluster: `cluster_009`
- negative book contribution on active loss days: `0.02828785`
- share of total loss abs: `0.217189`

cluster_002 watch:

- negative book contribution: `0.02640101`
- share of total loss abs: `0.202702`
- mean return on active loss days: `-0.01181847`

Largest gate-off missed positive regime:

- group: `limit_density_high`
- missed positive sum: `0.22413831`
- share of missed positives: `1.0`

## Output Tables

- `phase3p_gate_on_loss_cluster_attribution.csv`
- `phase3p_gate_on_loss_days.csv`
- `phase3p_gate_off_missed_return_by_regime.csv`
- `phase3p_gate_state_combo_monitor.csv`

## Boundary

This monitor explains locked gate behavior. It does not tune R3, change cluster membership, or promote any new rule.
