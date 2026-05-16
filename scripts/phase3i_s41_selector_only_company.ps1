$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "C:\Users\EDY\src"
$python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$src = "C:\Users\EDY\src"
$dataset = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$root = "D:\p3i_selector_only_20260516"
$seedRoot = Join-Path $root "s41"
$sourceRoot = Join-Path $seedRoot "shared_pool_source\i0_source"
$pool = Join-Path $seedRoot "shared_candidate_pool.json"
$selectorRoot = Join-Path $seedRoot "selector"
$featureRoot = Join-Path $seedRoot "feature_preflight"
$auditRoot = Join-Path $seedRoot "selector_audit"
$logs = Join-Path $seedRoot "logs"

New-Item -ItemType Directory -Force -Path $sourceRoot, $selectorRoot, $featureRoot, $auditRoot, $logs | Out-Null

& $python -m our_system_phase2.runtime.stock_pit_phase3_repair `
  --output-root $sourceRoot `
  --dataset-path $dataset `
  --ablation-arm Phase3I_I0_G2_primary `
  --seed 41 `
  --candidate-budget 64 `
  --strict-audit-budget 64 `
  --selection-only `
  --shared-candidate-pool-output $pool `
  --quiet *> (Join-Path $logs "01_generate_shared_pool.log")

& $python -m our_system_phase2.runtime.phase3i_feature_preflight `
  --pool $pool `
  --output-root $featureRoot *> (Join-Path $logs "02_feature_preflight.log")

& $python -m our_system_phase2.runtime.phase3i_apply_shared_selector_pool `
  --pool $pool `
  --output-root $selectorRoot `
  --arms i0 i1 i2 i3 *> (Join-Path $logs "03_apply_selectors.log")

& $python -m our_system_phase2.runtime.phase3i_selector_only_dryrun_audit `
  --run-root $selectorRoot `
  --feature-preflight (Join-Path $featureRoot "phase3i_feature_preflight.json") `
  --output-root $auditRoot *> (Join-Path $logs "04_selector_audit.log")

$manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  phase = "Phase3I"
  mode = "selector_only_no_replay"
  seed = 41
  root = $seedRoot
  pool = $pool
  feature_preflight = (Join-Path $featureRoot "phase3i_feature_preflight.json")
  selector_audit = (Join-Path $auditRoot "phase3i_selector_only_dryrun_audit.json")
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $seedRoot "phase3i_selector_only_seed_manifest.json")
