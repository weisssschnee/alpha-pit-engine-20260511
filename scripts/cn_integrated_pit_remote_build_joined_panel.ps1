$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\cn_integrated_pit_source_20260602.zip"
$SidecarArchive = "D:\HermesWorker\runtime\cn_integrated_pit_selected_sidecars_20260602.zip"
$RepoRoot = "D:\HermesWorker\workspace\cn_integrated_pit_join_20260602"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$BaseDataset = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$SidecarRoot = "D:\HermesWorker\runtime\cn_integrated_pit_selected_sidecars_20260602"
$OutputRoot = "D:\HermesWorker\runtime\cn_integrated_pit_joined_selected_panel_20260602"
$OutputPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet"
$OutputReport = Join-Path $OutputRoot "joined_panel_report.json"
$LogRoot = Join-Path $OutputRoot "logs"

if (-not (Test-Path $Archive)) { throw "missing archive: $Archive" }
if (-not (Test-Path $SidecarArchive)) { throw "missing sidecar archive: $SidecarArchive" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $BaseDataset)) { throw "missing base dataset: $BaseDataset" }

if (Test-Path $RepoRoot) {
  Remove-Item -Recurse -Force $RepoRoot
}
if (Test-Path $SidecarRoot) {
  Remove-Item -Recurse -Force $SidecarRoot
}
New-Item -ItemType Directory -Force -Path $RepoRoot, $SidecarRoot, $OutputRoot, $LogRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force
Expand-Archive -Path $SidecarArchive -DestinationPath $SidecarRoot -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"

& $Python app.py cn-integrated-pit-selected-panel-builder build-joined-panel `
  --base-dataset-path $BaseDataset `
  --sidecar-root $SidecarRoot `
  --output-path $OutputPath `
  --output-report $OutputReport `
  --start-date 2025-08-06 `
  --end-date 2026-04-10 *> (Join-Path $LogRoot "01_build_joined_panel.log")

$Manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  phase = "CNIntegratedPITJoin"
  mode = "company_build_joined_selected_panel"
  base_dataset = $BaseDataset
  sidecar_root = $SidecarRoot
  output_path = $OutputPath
  output_report = $OutputReport
  start_date = "2025-08-06"
  end_date = "2026-04-10"
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $OutputRoot "company_join_manifest.json")
