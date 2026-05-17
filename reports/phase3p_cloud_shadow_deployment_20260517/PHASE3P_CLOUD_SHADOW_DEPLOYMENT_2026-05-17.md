# Phase3P Cloud Shadow Deployment

- decision: `PASS_CLOUD_SHADOW_FUTU_SNAPSHOT_SYNC_DEPLOYED`
- cloud_host: `admin@120.78.231.37`
- cloud_root: `/home/admin/alpha_shadow/x0_official_shadow_v1`
- object_id: `X0_official_6_R3_liquidity_low_v1`
- book_version: `phase3p_x0_official6_r3_v1_cloud_shadow`
- gate_version: `phase3o_r3_liquidity_low_2025h2_q33_v1`
- execution_scope: `append_only_cloud_shadow_no_execution`

## Installed Files

```text
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/phase3p_cloud_shadow_runner.py
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/phase3p_futu_snapshot_panel_sync.py
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh
/home/admin/alpha_shadow/x0_official_shadow_v1/config/phase3o_x0_official_shadow_v1.json
/home/admin/alpha_shadow/x0_official_shadow_v1/input/latest_panel.csv.gz
/home/admin/alpha_shadow/x0_official_shadow_v1/README.md
```

## Synced Panel

- cloud_path: `/home/admin/alpha_shadow/x0_official_shadow_v1/input/latest_panel.csv.gz`
- rows: `1,095,983`
- date_min: `2025-08-06`
- date_max: `2026-05-15`
- sha256: `08608324f437353b80b2d9927fd22cf8ef719a578ad6675b41e09f207cfdb70e`

The cloud panel is updated by Futu snapshot before the scheduled shadow run. Futu snapshot covers valid SH/SZ symbols; BJ symbols are unsupported in this environment and are excluded from the appended snapshot date.

Snapshot sync result:

- snapshot_date: `2026-05-15`
- valid SH/SZ requested: `5200`
- snapshot rows mapped: `5200`
- coverage vs valid Futu universe: `100%`
- coverage vs source universe including BJ: `82.11%`
- unsupported BJ/source symbols: `565`
- batch_error_count: `0`

## Smoke Results

Shared checks:

- locked_object_ok: `true`
- stable_object_hash: `454b5b5e225c5acbefb7a49629eb5aec97a07871625bf38e2aeb3ee2b68af896`
- futu_quote_probe_ok: `true`
- panel_status: `present`
- trade_context_used: `false`

Gate-off smoke:

- data_date: `2026-05-08`
- decision: `PASS_CLOUD_SHADOW_SIGNALS_EXPORTED`
- gate_active: `false`
- liquidity_ratio_lag1: `1.1521364560`
- threshold: `0.9378730200`
- active_or_cash: `cash`
- signal_row_count: `0`
- position_count: `0`

Gate-on smoke:

- data_date: `2026-04-10`
- decision: `PASS_CLOUD_SHADOW_SIGNALS_EXPORTED`
- gate_active: `true`
- liquidity_ratio_lag1: `0.9064989408`
- threshold: `0.9378730200`
- active_or_cash: `active`
- signal_row_count: `1408`
- position_count: `943`

Latest snapshot shadow:

- data_date: `2026-05-15`
- decision: `PASS_CLOUD_SHADOW_SIGNALS_EXPORTED`
- gate_active: `false`
- liquidity_ratio_lag1: `1.1526629008`
- threshold: `0.9378730200`
- active_or_cash: `cash`
- signal_row_count: `0`
- position_count: `0`

## Cron

Installed isolated cron entry:

```cron
20 16 * * 1-5 /usr/bin/flock -n /tmp/phase3p_cloud_shadow_x0_cron.lock /home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh >> /home/admin/alpha_shadow/x0_official_shadow_v1/logs/cron.log 2>&1
```

This first runs Futu snapshot sync, then writes append-only daily artifacts. It does not place orders or open a trade context.

## Daily Outputs

```text
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_regime_state/YYYYMMDD.json
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_gate_state/YYYYMMDD.json
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_signals/YYYYMMDD.csv
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_positions/YYYYMMDD.csv
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_book_snapshot/YYYYMMDD.json
runtime/phase3p_cloud_shadow/x0_official6_r3_liquidity_low/daily_shadow_pnl/YYYYMMDD.json
```

## Boundaries

- No order placement.
- No Futu trade context.
- No account unlock.
- No modification to `/home/admin/chengbo_ops/project_v7_cn`.
- No modification to Hermes services.
- No production-readiness claim.

## Next Required Step

Monitor the first scheduled post-close run and verify that the snapshot date advances as expected. If BJ coverage becomes required, it must be sourced from a separate data feed because Futu snapshot rejects `BJ.*` symbols in this environment.
