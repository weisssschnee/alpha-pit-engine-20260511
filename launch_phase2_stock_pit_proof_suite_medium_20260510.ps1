param(
  [string]$OutputRoot = "runtime\next_stage_artifacts\phase2-stock-pit-proof-suite-medium-20260510",
  [int]$CandidateBudget = 128,
  [int]$StrictTopN = 8,
  [int]$BeamWidth = 24,
  [int]$MaxBeamRecords = 512
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$Python = "G:\PythonProject\.venv\Scripts\python.exe"
$DatasetPath = "G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$PreviousRoot = "runtime\next_stage_artifacts\phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4"
$env:PYTHONPATH = "src"

& $Python -m our_system_phase2.runtime.stock_pit_proof_suite `
  --mode proof-suite `
  --dataset-path $DatasetPath `
  --output-root $OutputRoot `
  --previous-search-root $PreviousRoot `
  --candidate-budget $CandidateBudget `
  --target-window-count 8 `
  --max-window 40 `
  --beam-width $BeamWidth `
  --max-beam-records $MaxBeamRecords `
  --strict-top-n $StrictTopN `
  --top-bottom-quantile 0.02 `
  --recent-quarter-window-count 2 `
  --recent-warmup-days 60 `
  --strict-cost-bps 10.0
