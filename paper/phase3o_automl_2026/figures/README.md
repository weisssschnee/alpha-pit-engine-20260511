# Figures

This directory is reserved for paper figures generated from public aggregate artifacts.

Allowed sources:

- `generated/daily_oos_r3_curve.csv`
- `generated/placebo_robustness_table.csv`
- `generated/r3_sensitivity_audit.csv`

Do not generate figures from private formula ledgers, full target-weight files, broker data, or unreleased commercial quality-model artifacts.

Build command from the repository root:

```powershell
py paper\phase3o_automl_2026\scripts\build_paper_figures.py
```

Current scripted figures:

- `fig2_equity_curve_scripted.svg`
- `fig3_robustness_audit_scripted.svg`
- `fig4_threshold_sensitivity_scripted.svg`
