# Crypto AlphaFactory Bootstrap Preflight

- generated_at: `2026-05-19T03:34:20Z`
- decision: `PASS_BOOTSTRAP_PREFLIGHT_WITH_WARNINGS`
- root: `G:\AlphaFactory_CryptoData`
- workspace: `G:\AlphaFactory_CryptoData\alphafactory_crypto`

## Manifest Summary

| dataset | manifest rows | files present | files missing | symbols | data types | intervals | source rows |
|---|---:|---:|---:|---:|---|---|---:|
| `futures_vision` | 3360 | 3360 | 0 | 12 | `{"indexPriceKlines": 672, "klines": 1344, "markPriceKlines": 672, "premiumIndexKlines": 672}` | `{"1d": 336, "1h": 1344, "1m": 1344, "5m": 336}` | 62756028 |
| `spot_vision` | 672 | 672 | 0 | 6 | `{"spot_klines": 672}` | `{"1d": 168, "1h": 168, "1m": 168, "5m": 168}` | 8950818 |
| `funding_rate` | 12 | 12 | 0 | 12 | `{"fundingRate": 12}` | `{"8h": 12}` | 31296 |
| `positioning_recent` | 60 | 60 | 0 | 12 | `{"globalLongShortAccountRatio": 12, "openInterestHist": 12, "takerlongshortRatio": 12, "topLongShortAccountRatio": 12, "topLongShortPositionRatio": 12}` | `{"5m": 60}` | 500928 |

## Timestamp / Schema Checks

- vision samples scanned: `84`
- timestamp units: `{'milliseconds': 83, 'unknown': 1}`
- bad 12-column samples: `0`
- API CSV issue samples: `0`

## Universe Gaps

- futures_missing_core12: `[]`
- funding_missing_core12: `[]`
- positioning_missing_core12: `[]`

## Warnings

- positioning appears recent-only; keep diagnostic-only for historical backtest
- some sampled zip files could not be scanned

## Blockers

- none

## Execution Boundary

- FundingRate can enter long-history backtests only with lagged/asof semantics.
- Positioning recent29d is diagnostic-only for now.
- Binance Vision spot timestamp unit must be normalized during bronze parsing.
- Coarser intervals are overlapping evidence, not independent samples.

## Next Step

Build bronze normalization for `futures_um` and `spot` bars plus fundingRate. Start alpha smoke on 1h/5m core12 after bronze row-count and timestamp checks pass.
