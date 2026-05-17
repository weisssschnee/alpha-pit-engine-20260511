# Phase3P Cloud Shadow

Purpose: run the locked `X0_official_6_R3_liquidity_low_v1` object on the cloud as an append-only shadow pipeline.

Boundaries:

- No broker trade context.
- No orders.
- No account unlock.
- No mutation of existing Hermes or V7 runtime directories.
- If the alpha panel is missing or evaluation fails, the runner records a blocked/cash state and writes no positions.

Default cloud root:

```text
/home/admin/alpha_shadow/x0_official_shadow_v1
```

Expected layout:

```text
config/phase3o_x0_official_shadow_v1.json
bin/phase3p_cloud_shadow_runner.py
bin/phase3p_futu_snapshot_panel_sync.py
bin/run_phase3p_cloud_shadow.sh
input/latest_panel.parquet   # optional future alpha panel
input/latest_panel.csv.gz    # preferred cloud-safe panel without pyarrow
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

Current smoke coverage:

- gate-off path: `2026-05-08`, `0` signals, `0` positions, cash snapshot.
- gate-on path: `2026-04-10`, `1408` signal rows, `943` shadow positions.
- Futu snapshot sync path: `2026-05-15`, `5200 / 5200` valid SH/SZ symbols mapped, BJ unsupported and excluded from the appended snapshot date.
- latest cloud shadow date: `2026-05-15`, R3 gate off, cash snapshot.
- Futu quote probe: OK.
- Trade context / orders: not used.

The cron runs Futu snapshot sync before the shadow runner. Snapshot sync is quote-context only. It updates SH/SZ rows; BJ rows are not available through Futu snapshot in this environment.
