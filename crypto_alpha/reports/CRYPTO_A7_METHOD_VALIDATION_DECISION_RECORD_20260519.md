# Crypto A7 Method Validation Decision Record

- decision: `HOLD_CORE4_ALPHA_PROMOTION`
- date: `2026-05-19`
- scope: fixed Core4 method validation, not search

## Summary

Core4 remains a strong crypto 1h research object, but it does not pass A7 promotion into alpha shadow proof.

The blockers are structural:

1. A7.1 baseline/placebo gate held because only 1/4 Core clusters beat their own component baselines.
2. A7.2 fixed-split revalidation held because the R3 risk-scaled book still has recent OOS compounded drawdown worse than -30%.
3. Fresh May 2026 forward slice is currently negative across R0/R1/R2/R3.

Dry shadow may continue only as engineering telemetry. It is excluded from alpha proof until A7 blockers are cleared.

## A7.0 Protocol

- decision: `PASS_A7_0_PROTOCOL_DEFINED`
- report: `G:\AlphaFactory_CryptoData\alphafactory_crypto\reports\CRYPTO_A7_METHOD_VALIDATION_DESIGN.md`
- split ledger: `G:\AlphaFactory_CryptoData\alphafactory_crypto\runtime\a7_method_validation\crypto_a7_0_split_ledger_20260519.csv`

Rules fixed:

- feature available time: 1h bar close
- execution time: next 1h bar open
- label start: next 1h bar open
- label end: next 1h bar open plus candidate horizon bars
- required alignment: `feature_available_time < execution_time <= label_start`
- split type: contiguous time blocks, no random row split
- purge/embargo: 24 one-hour bars at both ends of each split
- costs: 5 / 10 / 20 bps
- funding: latest-known funding may enter signal; forward funding event cost is included in replay

## A7.1 Baseline / Placebo

- decision: `HOLD_A7_1_BASELINE_PLACEBO_SUITE`
- report: `G:\AlphaFactory_CryptoData\alphafactory_crypto\reports\CRYPTO_A7_1_BASELINE_PLACEBO_SUITE_20260519.md`
- pass count: `1/4`

| cluster | full recent 10bps ann | best component recent 10bps ann | component margin | sign flip recent 10bps ann | decision |
|---|---:|---:|---:|---:|---|
| `crypto_a4_1h_001` | 1.7110 | 3.7077 | -1.9967 | -7.5903 | `HOLD` |
| `crypto_a4_1h_002` | 3.7870 | 6.7792 | -2.9921 | -13.3976 | `HOLD` |
| `crypto_a4_1h_003` | 1.5515 | 0.5141 | 1.0374 | -5.7018 | `PASS` |
| `crypto_a4_1h_004` | 1.8763 | 6.7792 | -4.9029 | -10.3497 | `HOLD` |

Interpretation:

- Placebos did not explain Core4; sign flip is negative.
- But the composite formula is not consistently stronger than simple component baselines.
- The dominant issue is that funding-related single components are very strong and explain much of Core4.

## A7.2 Fixed-Split Revalidation

- decision: `HOLD_A7_2_CORE4_FIXED_SPLIT_REVALIDATION`
- report: `G:\AlphaFactory_CryptoData\alphafactory_crypto\reports\CRYPTO_A7_2_CORE4_FIXED_SPLIT_REVALIDATION_20260519.md`
- blockers:
  - `A7_1_component_placebo_not_all_passed`
  - `R3_recent_compounded_dd_worse_than_30pct`

Key R3 10bps metrics:

| split | ann mean | compounded max DD | month pass | mean gross | mean turnover |
|---|---:|---:|---:|---:|---:|
| validation 2025H1 | 1.0632 | -0.4878 | 0.500 | 0.500 | 0.097 |
| recent OOS 2025H2-2026Apr | 0.5808 | -0.5209 | 0.700 | 0.500 | 0.100 |
| fresh forward 2026May | -2.7641 | -0.1763 | 0.000 | 0.500 | 0.096 |

LOO diagnostics:

- symbol LOO recent positive rate: `1.0`
- cluster LOO recent min annualized: `1.7129`

Interpretation:

- Core4 is not single-symbol fragile.
- Core4 is not single-cluster fragile in recent OOS.
- Risk scaling R3 remains too drawdown-heavy for alpha shadow proof.
- Fresh May 2026 does not currently support promotion.

## Current Status

Core4 status:

- `research proof object`: retained
- `engineering dry shadow`: allowed
- `alpha shadow proof`: not promoted
- `paper/live trading`: not allowed

A7.3 generator/reward bakeoff:

- status: `blocked`
- reason: A7.2 did not pass

## Required Next Action

Do not expand search or promote Core4.

Recommended next diagnostic:

1. Reframe Core4 as a funding-state family rather than a four-formula book.
2. Run a narrow `A7B funding-baseline audit`:
   - funding-only book
   - funding-only plus basis confirmation
   - Core4
   - same fixed split, same cost, same purge/embargo
3. Only if the simpler funding baseline also survives risk and fresh-forward checks should a new locked candidate be considered.

Until then, keep Core4 dry-shadow output labeled:

`engineering_dry_run_excluded_from_alpha_proof`.
