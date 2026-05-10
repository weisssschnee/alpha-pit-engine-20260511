# Phase2 Stock-PIT Proof Gates - 2026-05-10

## Goal

Build a repeatable proof suite for three research gates before the next large search:

1. Searcher A/B test: equal-budget `baseline_forward_first` vs `rx_typed_beam_no_policy` vs `rx_typed_beam_ucb`.
2. Fast-to-strict calibration: take top fast-screen candidates into strict audit, including cost shadow and turnover.
3. Coverage / cluster health: detect family, skeleton, field, and operator collapse.

This is research-grade evidence only. It is not a commercial promotion gate.

## Implemented

- Service: `src/our_system_phase2/services/stock_pit_proof_suite.py`
- CLI: `src/our_system_phase2/runtime/stock_pit_proof_suite.py`
- Tests: `tests/test_phase2_v21_runtime.py`

The suite writes:

- `ab_test_report.json`
- per-variant `candidate_ledger.json`
- per-variant `stage1_validation_report.json`
- optional `fast_to_strict_calibration_report.json`
- top-level `proof_suite_report.json`

## Real-data smoke run

Command:

```powershell
$env:PYTHONPATH='src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.stock_pit_proof_suite `
  --mode proof-suite `
  --dataset-path G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet `
  --output-root runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-smoke-20260510 `
  --previous-search-root runtime\next_stage_artifacts\phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4 `
  --candidate-budget 16 `
  --target-window-count 8 `
  --max-window 40 `
  --beam-width 16 `
  --max-beam-records 128 `
  --strict-top-n 1
```

Output root:

`runtime/next_stage_artifacts/phase2-stock-pit-proof-suite-smoke-20260510`

## Smoke result

Top-level decision:

`PASS_RESEARCH_PROOF_GATES_NOT_COMMERCIAL_PROOF`

Important nuance:

- `rx_typed_beam_no_policy` beat baseline on mean terminal reward in this tiny equal-budget smoke.
- `rx_typed_beam_ucb` did **not** beat baseline in this tiny smoke. UCB remains unproven and needs a larger A/B budget before we claim it helps.
- All three variants passed cluster health in this budget slice.
- Fast-to-strict top1 passed the proxy smoke, but top1 is too small for correlation proof.

| variant | count | mean reward | top reward | cluster health |
|---|---:|---:|---:|---|
| baseline_forward_first | 16 | 0.272441 | 1.306414 | PASS |
| rx_typed_beam_no_policy | 16 | 0.448400 | 1.308982 | PASS |
| rx_typed_beam_ucb | 16 | 0.158639 | 0.620847 | PASS |

Top strict-calibrated expression:

```text
CSRank(CSResidual(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))),CSRank(Log($final_float_market_cap))))
```

Strict audit top1:

- fast IC: `0.028931`
- strict IC: `0.028931`
- strict cost-adjusted spread: `0.005492`
- strict cost-adjusted sortino: `6.219060`
- strict one-way turnover: `0.867862`
- strict gatekeeper: `HOLD_RESEARCH`
- blockers: sector neutralization not run, capacity model not run, promotion-grade universe/survivorship not complete

## Next proof budget

Before claiming system superiority:

1. Run A/B with at least `candidate_budget >= 128` per variant.
2. Run strict calibration on `top_n >= 8`, enough for Spearman fast-vs-strict correlation.
3. Require per-challenger gates:
   - `rx_typed_beam_no_policy` must beat baseline.
   - `rx_typed_beam_ucb` must beat both baseline and no-policy RX, or be kept as optional exploration only.
4. Keep coverage gate hard: no family/skeleton dominance in the promoted shortlist.
