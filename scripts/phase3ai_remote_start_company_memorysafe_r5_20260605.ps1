$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3ai_overnight_source_20260605.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3ai_overnight_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$RunRoot = "D:\p3ai\overnight_company_20260605_r5_memorysafe"
$StatusPath = Join-Path $RunRoot "overnight_status.jsonl"
$RunTag = "r5_memorysafe"

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

function Invoke-SearchLeg($leg, [bool]$canary) {
  $suffix = if ($canary) { "canary" } else { "main" }
  $launchRoot = Join-Path $RunRoot "$($leg.name)_$suffix"
  $shards = if ($canary) { [int]$leg.canary_shards } else { [int]$leg.shards }
  $maxActive = if ($canary) { 1 } else { [int]$leg.max_active }
  $argsList = @(
    "-m", "our_system_phase2.runtime.phase3ab_launch_large_search",
    "--repo-root", $RepoRoot,
    "--launch-root", $launchRoot,
    "--job-id", "phase3ai_company_$($RunTag)_$($leg.name)_$suffix",
    "--machine", "company",
    "--dataset-path", $DatasetPath,
    "--memory-base", (Join-Path $RepoRoot "reports"),
    "--memory-base", "D:\HermesWorker\workspace\our_system_phase1_repo\reports",
    "--memory-base", "D:\p3aa",
    "--memory-base", "D:\p3ab",
    "--memory-base", "D:\p3ai\overnight_company_20260605_r4",
    "--memory-base", $RunRoot,
    "--shard-count", "$shards",
    "--max-active", "$maxActive",
    "--candidates-per-shard", "$($leg.candidates)",
    "--target-window-count", "$($leg.windows)",
    "--max-window", "126",
    "--top-bottom-quantile", "0.02",
    "--recent-quarter-window-count", "2",
    "--recent-warmup-days", "60",
    "--parallel-workers", "1",
    "--previous-root-limit", "$($leg.previous_limit)",
    "--reward-root-limit", "$($leg.reward_limit)",
    "--max-family-share", "$($leg.family_share)",
    "--reward-exploration-share", "$($leg.exploration)",
    "--generator-mode", "$($leg.mode)",
    "--beam-width", "$($leg.beam_width)",
    "--max-beam-records", "$($leg.max_beam)",
    "--use-successive-halving",
    "--halving-survivor-fraction", "$($leg.halving_fraction)",
    "--halving-min-survivors", "$($leg.halving_min)",
    "--poll-seconds", "20"
  )
  Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="start"; leg=$leg.name; stage=$suffix; launch_root=$launchRoot; shards=$shards; max_active=$maxActive; mode=$leg.mode})
  & $Python @argsList
  $code = $LASTEXITCODE
  $summary = Summarize-Launch $launchRoot
  $effectiveCode = $code
  if ([int]$summary.shard_count -gt 0 -and [int]$summary.total_eval -gt 0 -and [int]$summary.failed -eq 0) {
    $effectiveCode = 0
  }
  Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="finish"; leg=$leg.name; stage=$suffix; exit_code=$code; effective_exit_code=$effectiveCode; summary=$summary})
  return @{code=$effectiveCode; raw_code=$code; summary=$summary; launch_root=$launchRoot}
}

$deadline = (Get-Date).AddHours(8.25)
$legs = @(
  [ordered]@{name="c4_forward_fresh_ms"; mode="forward_first"; canary_shards=4; shards=128; max_active=2; candidates=64; windows=72; beam_width=64; max_beam=8192; family_share=0.12; exploration=0.80; previous_limit=24; reward_limit=12; halving_fraction=0.35; halving_min=48; canary_min_eval=48},
  [ordered]@{name="c5_rx_orthogonal_ms"; mode="rx_typed_beam"; canary_shards=4; shards=96; max_active=2; candidates=32; windows=96; beam_width=768; max_beam=131072; family_share=0.04; exploration=0.82; previous_limit=28; reward_limit=14; halving_fraction=0.42; halving_min=32; canary_min_eval=32},
  [ordered]@{name="c6_forward_lowcap_ms"; mode="forward_first"; canary_shards=4; shards=96; max_active=2; candidates=64; windows=96; beam_width=64; max_beam=8192; family_share=0.10; exploration=0.82; previous_limit=28; reward_limit=14; halving_fraction=0.35; halving_min=48; canary_min_eval=48},
  [ordered]@{name="c7_rx_extended_ms"; mode="rx_typed_beam"; canary_shards=4; shards=96; max_active=2; candidates=32; windows=120; beam_width=1024; max_beam=196608; family_share=0.06; exploration=0.84; previous_limit=32; reward_limit=16; halving_fraction=0.44; halving_min=32; canary_min_eval=32}
)

Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="memorysafe_begin"; run_root=$RunRoot; deadline=$deadline.ToString("s"); python=$Python; dataset=$DatasetPath; max_active_main=2; note="r5 lowers per-leg peak memory after r4 ArrayMemoryError"})
foreach ($leg in $legs) {
  if ((Get-Date) -gt $deadline) {
    Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="deadline_stop_before_leg"; leg=$leg.name})
    break
  }
  $canaryResult = Invoke-SearchLeg $leg $true
  $eval = [int]$canaryResult.summary.total_eval
  if ($canaryResult.code -ne 0 -or $eval -lt [int]$leg.canary_min_eval) {
    Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="skip_main_failed_canary"; leg=$leg.name; eval=$eval; min_eval=$leg.canary_min_eval; exit_code=$canaryResult.code})
    continue
  }
  if ((Get-Date) -gt $deadline) {
    Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="deadline_stop_after_canary"; leg=$leg.name})
    break
  }
  Invoke-SearchLeg $leg $false | Out-Null
}
Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="memorysafe_end"; run_root=$RunRoot})

