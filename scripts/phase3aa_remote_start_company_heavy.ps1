$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3aa_source_current.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3aa_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$LegacyReports = "D:\HermesWorker\workspace\our_system_phase1_repo\reports"
$LaunchRoot = "D:\p3aa\company_heavy_20260529_r3_memory"
$JobId = "phase3aa_company_heavy_20260529_r3_memory"

if (-not (Test-Path $Archive)) {
  throw "missing archive: $Archive"
}
if (-not (Test-Path $Python)) {
  throw "missing python: $Python"
}
if (-not (Test-Path $DatasetPath)) {
  throw "missing dataset: $DatasetPath"
}
if (Test-Path $RepoRoot) {
  Remove-Item -Recurse -Force $RepoRoot
}
New-Item -ItemType Directory -Force -Path $RepoRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"

& $Python -m our_system_phase2.runtime.phase3aa_launch_mature_search `
  --repo-root $RepoRoot `
  --launch-root $LaunchRoot `
  --job-id $JobId `
  --machine company `
  --dataset-path $DatasetPath `
  --memory-base $LegacyReports `
  --shard-count 32 `
  --max-active 6 `
  --target-window-count 24 `
  --parallel-workers 2 `
  --previous-root-limit 120 `
  --reward-root-limit 60 `
  --max-family-share 0.18 `
  --reward-exploration-share 0.35
