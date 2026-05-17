# Phase3P Cloud Shadow Deployment

- decision: `PASS_CLOUD_SHADOW_SCAFFOLD_DEPLOYED`
- cloud_host: `admin@120.78.231.37`
- cloud_root: `/home/admin/alpha_shadow/x0_official_shadow_v1`
- object_id: `X0_official_6_R3_liquidity_low_v1`
- book_version: `phase3p_x0_official6_r3_v1_cloud_shadow`
- gate_version: `phase3o_r3_liquidity_low_2025h2_q33_v1`
- execution_scope: `append_only_cloud_shadow_no_execution`

## Installed Files

```text
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/phase3p_cloud_shadow_runner.py
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh
/home/admin/alpha_shadow/x0_official_shadow_v1/config/phase3o_x0_official_shadow_v1.json
/home/admin/alpha_shadow/x0_official_shadow_v1/README.md
```

## Smoke Result

- locked_object_ok: `true`
- stable_object_hash: `454b5b5e225c5acbefb7a49629eb5aec97a07871625bf38e2aeb3ee2b68af896`
- futu_quote_probe_ok: `true`
- output_date: `2026-05-17`
- current_decision: `BLOCKED_INPUT_PANEL_MISSING`
- active_or_cash: `blocked_cash`
- position_count: `0`
- signal_row_count: `0`

The cloud machine has FutuOpenD running and quote connectivity works through the existing project venv. The cloud runner did not generate positions because the X0 alpha panel is not yet synced to the cloud.

## Cron

Installed isolated cron entry:

```cron
20 16 * * 1-5 /usr/bin/flock -n /tmp/phase3p_cloud_shadow_x0_cron.lock /home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh >> /home/admin/alpha_shadow/x0_official_shadow_v1/logs/cron.log 2>&1
```

This writes append-only daily artifacts. It does not place orders or open a trade context.

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
- Missing alpha panel is represented explicitly as `BLOCKED_INPUT_PANEL_MISSING`; positions stay empty.

## Next Required Step

Sync or build the official X0 alpha panel on the cloud:

```text
/home/admin/alpha_shadow/x0_official_shadow_v1/input/latest_panel.parquet
```

Until that exists and is wired into the evaluator, the cloud shadow process is an operational heartbeat and lock verification, not a live signal generator.
