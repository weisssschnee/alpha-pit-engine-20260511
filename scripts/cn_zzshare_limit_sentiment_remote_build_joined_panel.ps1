$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_source_20260602.zip"
$SidecarArchive = "D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602.zip"
$RepoRoot = "D:\HermesWorker\workspace\cn_zzshare_limit_sentiment_join_20260602"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$InputPanel = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet"
$SidecarRoot = "D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602"
$SidecarPath = Join-Path $SidecarRoot "zzshare_selected_sidecar.parquet"
$OutputRoot = "D:\HermesWorker\runtime\cn_zzshare_limit_sentiment_joined_panel_v1_20260602"
$OutputPanel = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_zzshare_selected_v1.parquet"
$OutputReport = Join-Path $OutputRoot "joined_panel_report.json"
$LogRoot = Join-Path $OutputRoot "logs"

if (-not (Test-Path $Archive)) { throw "missing archive: $Archive" }
if (-not (Test-Path $SidecarArchive)) { throw "missing sidecar archive: $SidecarArchive" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $InputPanel)) { throw "missing input panel: $InputPanel" }

if (Test-Path $RepoRoot) { Remove-Item -Recurse -Force $RepoRoot }
if (Test-Path $SidecarRoot) { Remove-Item -Recurse -Force $SidecarRoot }
New-Item -ItemType Directory -Force -Path $RepoRoot, $SidecarRoot, $OutputRoot, $LogRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force
Expand-Archive -Path $SidecarArchive -DestinationPath $SidecarRoot -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"

& $Python app.py cn-zzshare-limit-sentiment-joined-panel-v1 `
  --input-panel $InputPanel `
  --zzshare-sidecar $SidecarPath `
  --output-panel $OutputPanel `
  --output-report $OutputReport *> (Join-Path $LogRoot "01_build_zzshare_joined_panel.log")

$Manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  phase = "CNZZShareLimitSentimentJoin"
  mode = "company_build_zzshare_joined_panel"
  input_panel = $InputPanel
  sidecar_path = $SidecarPath
  output_panel = $OutputPanel
  output_report = $OutputReport
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $OutputRoot "company_join_manifest.json")
