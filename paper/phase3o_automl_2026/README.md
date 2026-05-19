# Phase3O AutoML Paper Pack

This directory stores paper-facing process files for the Phase3O/X0 regime-gated daily shadow result.

Scope:

- summarize frozen object state and evidence boundaries;
- build paper tables from existing reports;
- provide a synthetic reproducibility demo;
- avoid new alpha search or post-freeze tuning.

Primary scripts:

```text
scripts/build_paper_phase3o_tables.py
scripts/build_r3_sensitivity_audit.py
repro/make_synthetic_panel.py
repro/run_toy_regime_gate.py
```

Generated files are written to:

```text
generated/
```

Exact reproduction commands from the repository root:

```powershell
py paper\phase3o_automl_2026\scripts\build_paper_phase3o_tables.py
py paper\phase3o_automl_2026\scripts\build_r3_sensitivity_audit.py
py paper\phase3o_automl_2026\repro\make_synthetic_panel.py
py paper\phase3o_automl_2026\repro\run_toy_regime_gate.py
```

Expected key outputs:

```text
paper/phase3o_automl_2026/generated/PHASE3O_PAPER_INFO_PACK.md
paper/phase3o_automl_2026/generated/r3_sensitivity_audit.csv
paper/phase3o_automl_2026/generated/synthetic/synthetic_panel.csv
paper/phase3o_automl_2026/generated/synthetic/toy_regime_gate_summary.json
```
