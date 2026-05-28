# Phase3Z45b Regime / Timing Audit

Decision: `HOLD_RESEARCH_REGIME_TIMING_AUDIT_COMPLETE`.

This is a diagnostic-only audit. It does not change X0/R3 or promote any Z45b candidate.

## Best 2026 OOS Regime Slice By Cluster

| cluster | best regime | days | ann daily-equiv | sortino | turnover |
|---|---|---:|---:|---:|---:|
| cluster_002 | breadth_bucket:breadth_low | 10 | 4.454866 | 43.485857 | 0.013762 |
| cluster_007 | limit_density_bucket:limit_density_low | 8 | 3.262919 | 13.601995 | 0.678704 |
| cluster_017 | limit_density_bucket:limit_density_low | 9 | 2.43732 | 10.7393 | 0.013805 |
| cluster_001 | limit_density_bucket:limit_density_low | 8 | 1.339791 | 7.389884 | 0.013741 |
| cluster_030 | breadth_bucket:breadth_mid | 17 | 0.734481 | 16.270176 | 0.040993 |

## Timing Profile

| cluster | best horizon | h1 ann | best ann | h3/h1 mean ratio | h5/h1 mean ratio | profile |
|---|---:|---:|---:|---:|---:|---|
| cluster_001 | 3 | 0.136626 | 0.14873 | 1.082743 | 0.751357 | delayed_or_persistent |
| cluster_002 | 1 | 0.687009 | 0.687009 | 0.477939 | 0.425372 | front_loaded |
| cluster_007 | 3 | 0.203679 | 0.413526 | 1.867458 | 1.492486 | delayed_or_persistent |
| cluster_017 | 1 | 0.252193 | 0.252193 | 0.863156 | 0.60433 | short_horizon |
| cluster_030 | 1 | 0.098834 | 0.098834 | -1.307367 | -1.533014 | front_loaded |

## Bias Boundary

- No new search and no parameter tuning were performed.
- Regime buckets use 2025H2 train thresholds, then report 2026 OOS behavior.
- Timing metrics use T+1 execution and 10bps one-way-turnover deduction.
- Multi-day horizon metrics are daily-equivalent diagnostics from overlapping horizon labels, not production PnL.
- Evidence remains `HOLD_RESEARCH` because OOS sample is recent and weak.
