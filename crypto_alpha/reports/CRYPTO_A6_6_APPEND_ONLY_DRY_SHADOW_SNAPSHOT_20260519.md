# Crypto A6.6 Append-Only Dry Shadow Snapshot

- decision: `PASS_A6_6_APPEND_ONLY_DRY_SHADOW_SNAPSHOT_WRITTEN`
- object_id: `crypto_core4_conservative_dry_shadow_v0`
- input_max_timestamp: `2026-05-19T07:00:00Z`
- signal_time: `2026-05-19T07:59:59.999000Z`
- execution_time: `2026-05-19T08:00:00Z`
- gross_cap: `0.2`
- final_gross_exposure: `0.20000000000000004`
- final_net_exposure: `-1.3877787807814457e-17`
- position_count: `11`

## Outputs

- signals: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\hourly_signals\20260519T070000Z.csv`
- positions: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\hourly_positions\20260519T070000Z.csv`
- book_snapshot: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\hourly_book_snapshot\20260519T070000Z.json`
- regime_state: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\hourly_regime_state\20260519T070000Z.json`
- shadow_pnl: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\hourly_shadow_pnl\20260519T070000Z.json`
- fee_slippage_proxy: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\fee_slippage_proxy_log\20260519T070000Z.json`
- funding_payment_log: `G:\AlphaFactory_CryptoData\alphafactory_crypto\shadow_forward\core4_conservative_v0\funding_payment_log\20260519T070000Z.json`
- cluster_decisions: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a6_6_core4_append_only_shadow_snapshot\20260519T070000Z_cluster_decisions.csv`

## Boundary

- This is a dry-shadow snapshot only.
- It writes target positions for the next 1h bar under the conservative gross cap.
- It does not connect to an exchange and does not place orders.
- Existing snapshot files are never overwritten.
