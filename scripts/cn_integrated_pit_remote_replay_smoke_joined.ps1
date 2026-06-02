$ErrorActionPreference = "Stop"

$RepoRoot = "D:\HermesWorker\workspace\cn_integrated_pit_join_20260602"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$SelectionRoot = "D:\p3cn_integrated\selector_only_20260602\selector"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet"
$OutputRoot = "D:\p3cn_integrated\replay_smoke_joined_20260602"
$LogRoot = Join-Path $OutputRoot "logs"

if (-not (Test-Path $RepoRoot)) { throw "missing repo root: $RepoRoot" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $SelectionRoot)) { throw "missing selection root: $SelectionRoot" }
if (-not (Test-Path $DatasetPath)) { throw "missing dataset path: $DatasetPath" }

New-Item -ItemType Directory -Force -Path $OutputRoot, $LogRoot | Out-Null
Set-Location $RepoRoot
$env:PYTHONPATH = "src"

& $Python app.py phase3aa-smoke-from-selection `
  --selection-root $SelectionRoot `
  --output-root $OutputRoot `
  --dataset-path $DatasetPath `
  --audit-count 16 `
  --force *> (Join-Path $LogRoot "01_replay_smoke_joined.log")

$Manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  phase = "CNIntegratedPITJoin"
  mode = "joined_panel_replay_smoke"
  selection_root = $SelectionRoot
  dataset_path = $DatasetPath
  output_root = $OutputRoot
  audit_count = 16
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $OutputRoot "joined_replay_smoke_manifest.json")
