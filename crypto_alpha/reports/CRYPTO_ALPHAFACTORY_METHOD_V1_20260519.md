# Crypto AlphaFactory Method v1

## Decision

`GATE_BEFORE_SEARCH`

The crypto line must not directly run CN stock AlphaFactory generator, reward, replay,
or promotion logic. CN files copied into `alphafactory_crypto/cn_reference` are reference
patterns only.

## Why This Gate Exists

Crypto differs from the CN equity line in four material ways:

1. Trading calendar is continuous and intraday, not daily auction style.
2. Core signal fields are OHLCV, taker flow, mark/index/premium basis, funding, and later positioning.
3. Funding and positioning have event-time visibility rules; same-bar joins can create leakage.
4. Universe is only core12, so cross-sectional evidence is much smaller than A-share.

Therefore the reward and replay system must be modified before search.

## Current Inputs

- `G:\AlphaFactory_CryptoData\gold\panels\crypto_core12_5m_v1.parquet`
- `G:\AlphaFactory_CryptoData\gold\panels\crypto_core12_1h_v1.parquet`
- `G:\AlphaFactory_CryptoData\gold\feature_availability\crypto_feature_availability_20260519.parquet`

Recent-only positioning is excluded from historical research.

## Split Protocol

| Window | Role |
|---|---|
| 2024 | train / generator credit calibration |
| 2025H1 | validation |
| 2025H2-2026-04 | recent OOS |

Promotion requires validation and recent-OOS evidence. A single strong window is not enough.

## Generator Changes Required

The generator must be crypto-native:

- `price_momentum_continuation`
- `basis_premium_continuation`
- `funding_state_interaction`
- `volatility_state`
- `liquidity_state`
- `taker_flow_diagnostic`
- `spot_basis_core6_only`

It must not use stock-specific CN fields or assumptions.

## Reward Changes Required

Reward must score:

- oriented cross-sectional IC by split
- top/bottom long-short proxy by split
- stability across train / validation / recent OOS
- turnover proxy
- availability mask correctness
- signal cluster novelty

Hard rejects:

- using `fwd_ret_*` as feature input
- historical use of recent-only positioning
- same-bar funding or positioning leakage
- spot basis filled outside core6
- one-window-only success treated as promotion evidence

## Evaluation Stages

1. `A0_feature_smoke`: completed. This only creates priors.
2. `A1_generator_dry_run`: next. Generate crypto candidates with metadata and no promotion.
3. `A2_strict_replay`: fixed split evaluation with leakage gates.
4. `A3_cluster_registry`: count unique crypto clusters, not row-level winners.

## Current A0 Finding

Initial smoke suggests priority:

1. 5m short-horizon price momentum continuation
2. 5m basis / premium continuation
3. funding state and funding persistence
4. volatility state
5. flow/taker only as diagnostic until stronger interactions are shown

These are priors, not alpha proof.

## Next Step

Implement `A1_generator_dry_run` under `crypto_alphafactory_method_v1.json`.
No strict replay or search promotion should run before the gate checker passes.
