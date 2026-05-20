# DATA_AVAILABILITY.md

Date: 2026-05-20

## Summary

This repository contains paper-facing aggregate evidence, synthetic reproduction scripts, and frozen-object metadata for the Phase3O/X0 daily regime-gated shadow result.

It does **not** provide a full commercial alpha release. Full formula inventory, raw market data, private runtime ledgers, broker/cloud credentials, and trained quality/ranker model internals are intentionally excluded.

## Publicly Available in This Repository

- Aggregate paper tables under `paper/phase3o_automl_2026/generated/`
- Synthetic reproduction scripts under `paper/phase3o_automl_2026/repro/`
- Paper table-building scripts under `paper/phase3o_automl_2026/scripts/`
- Fact-check and evidence-boundary statements under `paper/phase3o_automl_2026/submission/`

The synthetic demo is intended to verify the audit mechanics, not to reproduce the private alpha economics.

## Not Publicly Released

- Complete representative alpha formulas
- Full target-weight files for commercial shadow profiles
- Raw licensed or vendor-derived market data
- Futu credentials, cloud credentials, SSH keys, and operational secrets
- Minute-level execution data, if acquired later
- Commercial quality/ranker model files and private training labels

## Reproduction Modes

### Synthetic Reproduction

From the repository root:

```powershell
py paper\phase3o_automl_2026\repro\make_synthetic_panel.py
py paper\phase3o_automl_2026\repro\run_toy_regime_gate.py
py paper\phase3o_automl_2026\scripts\build_paper_phase3o_tables.py
py paper\phase3o_automl_2026\scripts\build_r3_sensitivity_audit.py
```

### Aggregate Evidence Reproduction

The paper tables can be rebuilt from committed aggregate reports and generated CSV/JSON files. These artifacts support the paper-level claims listed in `FACT_CHECK.md`.

### Full Commercial Reproduction

Full commercial reproduction requires private data and formula/runtime artifacts that are not released in this public paper pack.

## Evidence Boundary

The released evidence supports a daily-proxy, regime-gated, shadow-research claim. It does not support claims of production readiness, true execution, live trading, real slippage, or real capacity.

