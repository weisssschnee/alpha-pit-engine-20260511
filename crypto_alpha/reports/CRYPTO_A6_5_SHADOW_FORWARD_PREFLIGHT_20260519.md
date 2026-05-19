# Crypto A6.5 Shadow Forward Preflight

- generated_at: `2026-05-19T09:51:46Z`
- decision: `PASS_A6_5_FORWARD_PREFLIGHT_READY`
- shadow_root: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0`
- dry_shadow_object_exists: `True`
- panel_max_timestamp: `2026-05-19 07:00:00+00:00`
- staleness_hours: `2.86`

## Boundary

- Append-only forward cannot start from stale historical panels.
- Current 1h gold panel must be updated to latest market data before signal/position snapshots are generated.
- Direct exchange orders remain forbidden.
