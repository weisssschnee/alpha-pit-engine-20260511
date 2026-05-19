# Phase3O Paper Info Pack

Generated: `2026-05-19T11:57:15+08:00`

## Freeze Status

- object_id: `X0_official_6_R3_liquidity_low_v1`
- status: `official_daily_shadow`
- stable_object_hash: `454b5b5e225c5acbefb7a49629eb5aec97a07871625bf38e2aeb3ee2b68af896`
- official_clusters: `001 | 005 | 006 | 009 | 002 | 004`
- gate: `R3_liquidity_low`
- current_head: `23f5039`
- origin_main: `23f5039`
- post_freeze_note: code/deployment extended after freeze; locked object hash unchanged.

## Key 2026 X0+R3 Metrics

- full_calendar_annualized: `1.175657`
- active_annualized: `3.918442`
- sharpe: `4.547115`
- sortino: `6.085253`
- max_drawdown: `-0.03442312`
- active_ratio: `0.487179`

## Active-Day Sanity

- decision: `PASS_ACTIVE_RETURN_SANITY_AUDIT`
- gate_lag_check: `PASS`
- top_1_active_day_share: `0.154022`
- top_3_active_day_share: `0.38279`
- top_5_active_day_share: `0.596353`

## Limit Audit

- decision: `HOLD_LIMIT_GENERATOR_COVERAGE_GAP`
- interpretation: limit is currently a generator coverage gap / diagnostic line, not part of locked X0.

## Forward Shadow Status

- cloud_decision: `PASS_CLOUD_SHADOW_FUTU_SNAPSHOT_SYNC_DEPLOYED`
- latest_cloud_snapshot_date: `2026-05-15`
- latest_cloud_gate_active: `False`
- latest_cloud_positions: `0`
- forward performance claim: not made; active-day sample is insufficient.

## Generated Tables

- `core_report_manifest`: `paper\phase3o_automl_2026\generated\core_report_manifest.csv`
- `freeze_status`: `paper\phase3o_automl_2026\generated\freeze_status.csv`
- `cluster_composition`: `paper\phase3o_automl_2026\generated\cluster_composition.csv`
- `r3_gate_definition`: `paper\phase3o_automl_2026\generated\r3_gate_definition.csv`
- `regime_gate_oos_table`: `paper\phase3o_automl_2026\generated\regime_gate_oos_table.csv`
- `placebo_robustness_table`: `paper\phase3o_automl_2026\generated\placebo_robustness_table.csv`
- `daily_oos_r3_curve`: `paper\phase3o_automl_2026\generated\daily_oos_r3_curve.csv`
- `forward_status`: `paper\phase3o_automl_2026\generated\forward_status.csv`
- `evidence_boundary`: `paper\phase3o_automl_2026\generated\evidence_boundary.csv`
- `author_affiliation_template`: `paper\phase3o_automl_2026\generated\author_affiliation_template.csv`
- `experiment_record`: `paper\phase3o_automl_2026\generated\experiment_record.json`

## Paper Wording Boundary

Use: `locked daily shadow candidate with strong research-touched recent-OOS evidence`.

Do not use: `production-ready`, `live-proven`, `true execution validated`, or `untouched OOS proven`.
