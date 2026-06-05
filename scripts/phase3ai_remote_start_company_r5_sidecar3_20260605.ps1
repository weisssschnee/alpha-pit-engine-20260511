$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3ai_overnight_source_20260605.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3ai_overnight_sidecar3_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$RunRoot = "D:\p3ai\overnight_company_20260605_r5_sidecar3"
$StatusPath = Join-Path $RunRoot "sidecar3_status.jsonl"

if (-not (Test-Path $Archive)) { throw "missing archive: $Archive" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $DatasetPath)) { throw "missing dataset: $DatasetPath" }

if (Test-Path $RepoRoot) {
  Remove-Item -Recurse -Force $RepoRoot
}
New-Item -ItemType Directory -Force -Path $RepoRoot | Out-Null
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"
$env:NUMEXPR_MAX_THREADS = "4"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

function Write-Status($item) {
  $item | ConvertTo-Json -Depth 8 -Compress | Add-Content -Path $StatusPath -Encoding UTF8
}

function Get-JsonInt($obj, $name) {
  $prop = $obj.PSObject.Properties[$name]
  if ($null -eq $prop -or $null -eq $prop.Value) { return 0 }
  return [int]$prop.Value
}

function Summarize-Launch($launchRoot) {
  $summary = [ordered]@{
    launch_root = $launchRoot
    shard_count = 0
    total_ledger = 0
    total_eval = 0
    failed = 0
    top_sortino = $null
    top_candidate = $null
    completed = 0
    running = 0
  }
  if (-not (Test-Path $launchRoot)) { return $summary }
  Get-ChildItem $launchRoot -Directory -Filter "supervisor-shard_*" | ForEach-Object {
    $summary.shard_count += 1
    $stagePath = Join-Path $_.FullName "stage1_summary.json"
    if (-not (Test-Path $stagePath)) { return }
    $stage = Get-Content $stagePath -Raw | ConvertFrom-Json
    $summary.total_ledger += Get-JsonInt $stage "ledger_record_count"
    $summary.total_eval += Get-JsonInt $stage "validation_evaluated_count"
    $top = $stage.top_long_sortino
    if ($null -ne $top -and ($null -eq $summary.top_sortino -or [double]$top -gt [double]$summary.top_sortino)) {
      $summary.top_sortino = [double]$top
      $summary.top_candidate = $stage.top_candidate_id
    }
  }
  $supervisor = Join-Path $launchRoot "supervisor\supervisor_status.json"
  if (Test-Path $supervisor) {
    $s = Get-Content $supervisor -Raw | ConvertFrom-Json
    $summary.failed = Get-JsonInt $s "failed_count"
    $summary.completed = Get-JsonInt $s "completed_count"
    $summary.running = Get-JsonInt $s "running_count"
  }
  return $summary
}

function Invoke-Leg($name, $mode, $canaryShards, $mainShards, $candidates, $windows, $beamWidth, $maxBeam, $familyShare, $exploration, $previousLimit, $rewardLimit, $halvingFraction, $halvingMin, $minEval) {
  foreach ($stage in @("canary","main")) {
    $isCanary = $stage -eq "canary"
    $shards = if ($isCanary) { $canaryShards } else { $mainShards }
    $maxActive = 1
    $launchRoot = Join-Path $RunRoot "$($name)_$stage"
    Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="start"; leg=$name; stage=$stage; launch_root=$launchRoot; shards=$shards; max_active=$maxActive; mode=$mode})
    $argsList = @(
      "-m", "our_system_phase2.runtime.phase3ab_launch_large_search",
      "--repo-root", $RepoRoot,
      "--launch-root", $launchRoot,
      "--job-id", "phase3ai_company_r5_sidecar3_$($name)_$stage",
      "--machine", "company",
      "--dataset-path", $DatasetPath,
      "--memory-base", (Join-Path $RepoRoot "reports"),
      "--memory-base", "D:\HermesWorker\workspace\our_system_phase1_repo\reports",
      "--memory-base", "D:\p3ai\overnight_company_20260605_r4",
      "--memory-base", "D:\p3ai\overnight_company_20260605_r5_memorysafe",
      "--memory-base", "D:\p3ai\overnight_company_20260605_r5_sidecar",
      "--memory-base", "D:\p3ai\overnight_company_20260605_r5_sidecar2",
      "--memory-base", $RunRoot,
      "--shard-count", "$shards",
      "--max-active", "$maxActive",
      "--candidates-per-shard", "$candidates",
      "--target-window-count", "$windows",
      "--max-window", "126",
      "--top-bottom-quantile", "0.02",
      "--recent-quarter-window-count", "2",
      "--recent-warmup-days", "60",
      "--parallel-workers", "1",
      "--previous-root-limit", "$previousLimit",
      "--reward-root-limit", "$rewardLimit",
      "--max-family-share", "$familyShare",
      "--reward-exploration-share", "$exploration",
      "--generator-mode", "$mode",
      "--beam-width", "$beamWidth",
      "--max-beam-records", "$maxBeam",
      "--use-successive-halving",
      "--halving-survivor-fraction", "$halvingFraction",
      "--halving-min-survivors", "$halvingMin",
      "--poll-seconds", "20"
    )
    & $Python @argsList
    $code = $LASTEXITCODE
    $summary = Summarize-Launch $launchRoot
    $effectiveCode = $code
    if ([int]$summary.shard_count -gt 0 -and [int]$summary.total_eval -gt 0 -and [int]$summary.failed -eq 0) { $effectiveCode = 0 }
    Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="finish"; leg=$name; stage=$stage; exit_code=$code; effective_exit_code=$effectiveCode; summary=$summary})
    if ($isCanary -and ($effectiveCode -ne 0 -or [int]$summary.total_eval -lt $minEval)) {
      Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="skip_main_failed_canary"; leg=$name; eval=$summary.total_eval; min_eval=$minEval; exit_code=$effectiveCode})
      break
    }
  }
}

Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="sidecar3_begin"; run_root=$RunRoot; note="adds fifth memory-safe company lane after sidecar1 dropped active load"})
Invoke-Leg "sc5_forward_underused_field_ms" "forward_first" 4 128 52 96 64 8192 0.07 0.90 36 18 0.35 40 40
Invoke-Leg "sc6_rx_repair_orthogonal_ms" "rx_typed_beam" 4 96 28 120 1024 196608 0.03 0.90 40 20 0.45 28 28
Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="sidecar3_end"; run_root=$RunRoot})
