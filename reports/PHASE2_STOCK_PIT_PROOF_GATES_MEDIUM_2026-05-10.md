# Phase2 Stock-PIT Medium Proof Run - 2026-05-10

## Experiment Record

- date: 2026-05-10
- experiment_id: `20260510_stock_pit_medium_proof_001`
- objective: prove whether `rx_typed_beam_no_policy` and `rx_typed_beam_ucb` beat the baseline searcher under equal candidate budget, and whether fast-screen reward survives strict audit.
- status: running
- mode: research

### Inputs

- dataset: `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- dataset manifest: stock-level maxopt panel, 1,090,783 rows, 6,333 symbols, 2025-08-06 to 2026-05-08, size about 122 MB.
- prior reward root: `runtime\next_stage_artifacts\phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4`

### Parameters

- variants: `baseline_forward_first`, `rx_typed_beam_no_policy`, `rx_typed_beam_ucb`
- candidate budget: 128 per variant
- target window count: 8
- max operator window: 40
- beam width: 24
- max beam records: 512
- signal clock: `after_open`
- execution lag: T+1
- feature lag: field-aware, default 0 plus after-open full-day field lagging inside validator
- top/bottom quantile: 0.02
- recent quarter windows: 2
- warmup days: 60
- strict top N: 8
- strict cost: 10 bps

### Commands

```powershell
.\launch_phase2_stock_pit_proof_suite_medium_20260510.ps1
```

Equivalent module command:

```powershell
$env:PYTHONPATH='src'
G:\PythonProject\.venv\Scripts\python.exe -m our_system_phase2.runtime.stock_pit_proof_suite `
  --mode proof-suite `
  --dataset-path G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet `
  --output-root runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510 `
  --previous-search-root runtime\next_stage_artifacts\phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4 `
  --candidate-budget 128 `
  --target-window-count 8 `
  --max-window 40 `
  --beam-width 24 `
  --max-beam-records 512 `
  --strict-top-n 8 `
  --top-bottom-quantile 0.02 `
  --recent-quarter-window-count 2 `
  --recent-warmup-days 60 `
  --strict-cost-bps 10.0
```

### Outputs

- output root: `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510`
- expected report: `proof_suite_report.json`
- expected A/B report: `ab_test_report.json`
- expected calibration report: `fast_to_strict_calibration_report.json`
- logs: `proof_suite_stdout.log`, `proof_suite_stderr.log`

### Bias Audit Boundary

- This is discovery/research evidence, not promotion.
- Strict audit includes cost shadow and turnover, but still reports `HOLD_RESEARCH` unless missing promotion-grade blockers are resolved.
- UCB must pass its own per-variant gate. A win by RX no-policy does not prove UCB.

### Cost and Time

- estimated: roughly 2 to 4 hours on local CPU, depending on memory pressure.
- actual: pending.

### Decision

HOLD_RESEARCH until the run completes and the reports are reviewed.

### Next Action

- Inspect the output root after completion.
- If UCB loses again, keep it as exploration-only or reduce its routing weight before the next large search.

## Company-PC Takeover

The original local run was stopped after the company PC run was confirmed active.

- local partial root: `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510`
- local stopped PIDs: `2416`, `48184`, `25520`
- company task: `Phase2ProofMediumCompany20260510`
- company output root: `D:\HermesWorker\runtime\phase2-stock-pit-proof-suite-medium-company-20260510`
- company command wrapper: `D:\HermesWorker\runtime\phase2-stock-pit-proof-suite-medium-company-20260510\run_proof_suite_company.cmd`
- active company process chain at launch: `cmd.exe` PID `25368`, `.venv` Python PID `17964`, real Python PID `21464`
- first company artifact observed: `ab_test\baseline_forward_first\candidate_ledger.json`

Company old-search harvest:

- local harvest root: `runtime\next_stage_artifacts\company_harvest_20260510`
- remote harvest zip: `D:\HermesWorker\runtime\20260510_ashare_company_harvest.zip`
- harvested file count: `661`

Decision state remains `HOLD_RESEARCH` until the company proof run writes `proof_suite_report.json`.

## Company-PC Final Verification

Status:

- company task completed with exit code `0`.
- remote final root:
  `D:\HermesWorker\runtime\phase2-stock-pit-proof-suite-medium-company-20260510`
- local final archive:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-company-20260510\phase2-stock-pit-proof-suite-medium-company-20260510-final.zip`
- local expanded root:
  `runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-company-20260510\expanded`

Top-level decision:

- `PASS_RESEARCH_PROOF_GATES_NOT_COMMERCIAL_PROOF`

Proof gates:

- search A/B: `PASS_AB_ADVANTAGE_RESEARCH_EVIDENCE`
- fast-to-strict calibration: `PASS_FAST_TO_STRICT_CALIBRATION_SMOKE`
- coverage / cluster health: `PASS_COVERAGE_CLUSTER_HEALTH`

Variant comparison:

| variant | mean reward | mean IC | mean long sortino | strong long sortino | coverage | top coverage |
|---|---:|---:|---:|---:|---|---|
| baseline_forward_first | 0.223750 | -0.000839 | 0.737332 | 7 | PASS | PASS |
| rx_typed_beam_no_policy | 0.339562 | 0.005766 | 1.270762 | 10 | PASS | PASS |
| rx_typed_beam_ucb | 0.236572 | 0.003491 | 0.678738 | 0 | PASS | PASS |

Interpretation:

- `rx_typed_beam_no_policy` is the clear winner in this medium proof run.
- `rx_typed_beam_ucb` is slightly above baseline by mean reward, but clearly loses to
  `rx_typed_beam_no_policy`; it should not be promoted as the primary scheduler.
- No variant produced `strong_ic_count >= 1` under the current strict IC threshold
  `0.045`; the proof is based on reward/Sortino/coverage, not high IC breakout.

Fast-to-strict calibration:

- strict top N: `8`
- strict pass proxy count: `8`
- strict pass proxy rate: `1.0`
- Spearman fast reward to strict IC: `0.383240`
- Spearman fast IC to strict IC: `1.0`
- all strict rows stayed `HOLD_RESEARCH`, not promotion, because commercial blockers
  such as sector neutralization/capacity/promotion-grade universe remain unresolved.

Best fast candidate:

```text
CSRank(CSResidual(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))),CSRank(Log($final_float_market_cap))))
```

Best candidate strict audit:

- strict IC: `0.028931`
- strict cost-adjusted spread: `0.005492`
- strict cost-adjusted sortino: `6.219060`
- mean one-way turnover: `0.867862`
- gatekeeper decision: `HOLD_RESEARCH`
