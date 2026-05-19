# Crypto AlphaFactory Artifacts

This folder is the crypto-line counterpart to the CN AlphaFactory research artifacts. It contains source scripts, configuration, reports, and lightweight runtime manifests/tables copied from:

`G:\AlphaFactory_CryptoData\alphafactory_crypto`

Large raw/silver/gold data, parquet panels, append-only shadow outputs, and heavy time-series diagnostics remain outside Git under `G:\AlphaFactory_CryptoData`.

## Current Status

Crypto is not at the same proof level as the CN line.

Confirmed:

- Data line produced normalized silver/gold inputs for core12 futures and related features.
- A0-A6 found and froze a promising 1h funding/basis/price Core4 research object.
- A6 dry-shadow infrastructure can generate append-only engineering telemetry.
- A7 method validation ledger, baseline/placebo suite, fixed-split revalidation, and A7B funding-baseline audit were run.

Not confirmed:

- Core4 is not promoted to alpha shadow proof.
- Dry-shadow PnL is engineering telemetry only and excluded from alpha evidence.
- No paper/live trading approval.
- No production readiness, true execution proof, or real capacity proof.
- No generator/reward bakeoff promotion after A7 because Core4 failed the alpha proof gate.

Blocking result:

- A7.1: only 1 of 4 Core clusters beat its component baseline.
- A7.2: recent OOS remained positive, but drawdown/fresh-May behavior was not acceptable.
- A7B: funding-only dominance risk remains; Core4 residual edge is not enough to promote.

## Evidence Level

`crypto Core4 = research proof object`

`A6 dry-shadow = engineering telemetry only`

`A7/A7B decision = HOLD_ALPHA_SHADOW_PROOF`

## Directory Layout

- `config/`: crypto method and motif configuration.
- `scripts/`: reproducible scripts for A0-A7B and dry-shadow telemetry.
- `reports/`: human-readable reports and decision records.
- `runtime/`: small manifests, summary tables, baselines, and audit outputs.
- `cn_reference/`: selected CN-line reference utilities used to adapt the AlphaFactory method.

## Next Correct Step

Do not expand crypto search until the method gate is repaired.

Recommended next task:

`A7B/FundingCore narrow audit`

Purpose:

- Decide whether a simpler funding-related object should replace Core4.
- Re-run the same split, cost, funding-fee, placebo, ablation, drawdown, symbol/month stability checks.
- Only after a simple object passes should generator/reward bakeoff resume.

