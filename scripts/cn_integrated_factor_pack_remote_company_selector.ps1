$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\cn_integrated_factor_pack_source_20260602.zip"
$SourcePool = "D:\HermesWorker\runtime\cn_integrated_factor_pack_source_pool_raw_20260602.json"
$SignalVectorArchive = "D:\HermesWorker\runtime\cn_integrated_factor_pack_signal_vectors_20260602.zip"
$RepoRoot = "D:\HermesWorker\workspace\cn_integrated_factor_pack_20260602"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$OutputRoot = "D:\p3cn_integrated\selector_only_20260602"
$LogRoot = Join-Path $OutputRoot "logs"

if (-not (Test-Path $Archive)) { throw "missing archive: $Archive" }
if (-not (Test-Path $SourcePool)) { throw "missing source pool: $SourcePool" }
if (-not (Test-Path $SignalVectorArchive)) { throw "missing signal vector archive: $SignalVectorArchive" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $DatasetPath)) { throw "missing dataset: $DatasetPath" }

if (Test-Path $RepoRoot) {
  Remove-Item -Recurse -Force $RepoRoot
}
New-Item -ItemType Directory -Force -Path $RepoRoot, $OutputRoot, $LogRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force
New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "runtime\phase3g_signal_vectors") | Out-Null
Expand-Archive -Path $SignalVectorArchive -DestinationPath (Join-Path $RepoRoot "runtime\phase3g_signal_vectors") -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"

$FactorPack = "runtime\factor_packs\cn_integrated_feature_factor_candidate_pack_v1_20260602.json"
if (-not (Test-Path $FactorPack)) { throw "missing factor pack in repo archive: $FactorPack" }

& $Python app.py phase3aa-cached-mature-pool -- `
  --source-pool $SourcePool `
  --output-root $OutputRoot `
  --dataset-path $DatasetPath `
  --factor-pack $FactorPack `
  --factor-pack-only `
  --include-research-factor-candidates `
  --include-fundamental-candidates `
  --strict-audit-budget 64 `
  --event-share 0.20 `
  --selector-pool-cap 160 `
  --signal-sample-size 1500 `
  --signal-warmup-days 60 `
  --max-event-rows 211 `
  --max-event-per-role 211 `
  --force *> (Join-Path $LogRoot "01_selector_only.log")

$Manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  phase = "CNIntegratedFactorPack"
  mode = "company_selector_only_no_replay"
  output_root = $OutputRoot
  source_pool = $SourcePool
  signal_vector_archive = $SignalVectorArchive
  factor_pack = $FactorPack
  dataset_path = $DatasetPath
  strict_audit_budget = 64
  event_share = 0.20
  selector_pool_cap = 160
  signal_sample_size = 1500
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $OutputRoot "company_selector_only_manifest.json")
