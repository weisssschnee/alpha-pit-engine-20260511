# Crypto A7 Method Validation Design

- generated_at: `2026-05-19T10:29:14Z`
- experiment_id: `20260519_crypto_a7_method_validation`
- stable_design_hash: `bb938d242d8d9d952b9104fe57fb10640dc39025a29646bc2813080510e866e2`
- decision_scope: `method validation before any crypto alpha shadow proof promotion`

## Time Alignment

| field | rule |
|---|---|
| feature_available_time | 1h bar close timestamp; formula uses current and past normalized features only |
| execution_time | next 1h bar open |
| label_start | next 1h bar open |
| label_end | next 1h bar open plus candidate horizon bars |
| required inequality | feature_available_time < execution_time <= label_start |

## Splits

| split | start | end | raw hours | purged hours | OOS grade |
|---|---:|---:|---:|---:|---|
| `train_2024` | `2024-01-01T00:00:00Z` | `2024-12-31T23:59:59Z` | 8784 | 8736 | `SOLID` |
| `validation_2025H1` | `2025-01-01T00:00:00Z` | `2025-06-30T23:59:59Z` | 4344 | 4296 | `SOLID` |
| `recent_oos_2025H2_2026Apr` | `2025-07-01T00:00:00Z` | `2026-04-30T23:59:59Z` | 7296 | 7248 | `SOLID` |
| `fresh_forward_2026May` | `2026-05-01T00:00:00Z` | `2026-05-19 07:00:00+00:00` | 440 | 392 | `BASIC` |

## Fixed Protocol

- purge/embargo: `24` 1h bars at both ends of each split.
- split type: contiguous month/time blocks; no random row split.
- universe: static core12 futures for research validation; production time-varying universe is not confirmed.
- cost stress: 5 / 10 / 20 bps.
- funding: signal may use latest-known funding only; forward funding payment must be included in replay.
- A6 dry-shadow remains engineering telemetry until A7 passes.

## Required Gates

1. A7.1 Core4 must beat simple component baselines and fail placebo alternatives.
2. A7.2 Core4 fixed-split revalidation must survive cost, month, symbol, and cluster LOO checks.
3. A7.3 generator/reward bakeoff is blocked until A7.2 passes.
