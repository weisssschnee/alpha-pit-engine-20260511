# CN Integrated PIT Joined Replay Smoke

- decision: `PASS_ENGINEERING_JOIN_AND_LOADER_HOLD_ALPHA_SMOKE`
- joined_panel: `D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet`
- joined_rows: `988005`
- joined_columns: `81`
- replay_smoke_output: `D:\p3cn_integrated\replay_smoke_joined_fixed16_20260602\aa`
- local_report_snapshot: `runtime/cn_integrated_pit_joined_replay_smoke_20260602`

## Engineering Result

- field availability on joined panel: `PASS_REPLAY_FIELD_AVAILABILITY`
- selected_executable_count: `64 / 64`
- integrated_selected_executable_count: `35 / 35`
- loader fix: `ctx_*`, `m1_*`, and `vwap` are now included by `_available_market_panel_usecols`
- replay smoke chain: completed for `16` selected rows

## Alpha Smoke Result

- audited rows: `16`
- source mix:
  - legacy: `10`
  - cn_integrated_feature_layer: `6`
- strict proxy / replay:
  - legacy strict_proxy pass, replay fail: `7`
  - legacy strict_proxy fail, replay fail: `3`
  - integrated strict_proxy fail, replay fail: `6`
- deployable_clusters: `0`

## Integrated Candidate Finding

The first integrated candidates selected by the G2 queue are direct RZRQ rank variants:

- `CSRank(ZScore($ctx_rzrq_rzche3d))`
- `CSRank($ctx_rzrq_rzche3d)`
- `CSRank($ctx_rzrq_rzjme5d)`
- `CSRank($ctx_rzrq_rzmre10d)`
- `CSRank($ctx_rzrq_rzjme3d)`
- `CSRank($ctx_rzrq_rzjme10d)`

All six failed strict/replay. This is not a field-join failure; it is a candidate-quality / selector-ranking result for this small smoke.

## Known Coverage Caveat

The joined panel intentionally uses the overlap window `2025-08-06` to `2026-04-10`. The base replay panel extends to `2026-05-08`, but the current minute/nonminute context panels end at `2026-04-10`.

## Next Action

Do not run a large replay on this queue as-is. The executable path is now open, but the integrated candidates at the top of the queue are low-quality direct RZRQ ranks. The next gate should rerank or rebalance integrated candidates toward interaction / transformed features before spending replay budget.
