# Phase3P Cloud Shadow

Purpose: run the locked `X0_official_6_R3_liquidity_low_v1` object on the cloud as an append-only shadow pipeline.

Boundaries:

- No broker trade context.
- No orders.
- No account unlock.
- No mutation of existing Hermes or V7 runtime directories.
- Until the full alpha panel is synced, the runner records `BLOCKED_INPUT_PANEL_MISSING` and writes cash/blocked snapshots.

Default cloud root:

```text
/home/admin/alpha_shadow/x0_official_shadow_v1
```

Expected layout:

```text
config/phase3o_x0_official_shadow_v1.json
bin/phase3p_cloud_shadow_runner.py
bin/run_phase3p_cloud_shadow.sh
input/latest_panel.parquet   # optional future alpha panel
runtime/phase3p_cloud_shadow/...
reports/phase3p_cloud_shadow_status.json
logs/
```

Smoke:

```bash
/home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh --force
```

Suggested cron after smoke:

```cron
20 16 * * 1-5 /home/admin/alpha_shadow/x0_official_shadow_v1/bin/run_phase3p_cloud_shadow.sh
```
