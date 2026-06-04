$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3ai_overnight_source_20260605.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3ai_overnight_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$RunRoot = "D:\p3ai\overnight_company_20260605_r2"
$StatusPath = Join-Path $RunRoot "overnight_status.jsonl"
$RunTag = "r2"

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
$env:NUMEXPR_MAX_THREADS = "8"
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
  }
  return $summary
}

function Invoke-SearchLeg($leg, [bool]$canary) {
  $suffix = if ($canary) { "canary" } else { "main" }
  $launchRoot = Join-Path $RunRoot "$($leg.name)_$suffix"
  $shards = if ($canary) { [int]$leg.canary_shards } else { [int]$leg.shards }
  $maxActive = if ($canary) { [Math]::Min([int]$leg.max_active, 2) } else { [int]$leg.max_active }
  $argsList = @(
    "-m", "our_system_phase2.runtime.phase3ab_launch_large_search",
    "--repo-root", $RepoRoot,
    "--launch-root", $launchRoot,
    "--job-id", "phase3ai_overnight_company_$($RunTag)_$($leg.name)_$suffix",
    "--machine", "company",
    "--dataset-path", $DatasetPath,
    "--memory-base", (Join-Path $RepoRoot "reports"),
    "--memory-base", "D:\HermesWorker\workspace\our_system_phase1_repo\reports",
    "--memory-base", "D:\p3aa",
    "--memory-base", "D:\p3ab",
    "--memory-base", "D:\p3ai",
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
  Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="start"; leg=$leg.name; stage=$suffix; launch_root=$launchRoot; shards=$shards; mode=$leg.mode})
  & $Python @argsList
  $code = $LASTEXITCODE
  $summary = Summarize-Launch $launchRoot
  Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="finish"; leg=$leg.name; stage=$suffix; exit_code=$code; summary=$summary})
  return @{code=$code; summary=$summary; launch_root=$launchRoot}
}

$deadline = (Get-Date).AddHours(8.25)
$legs = @(
  [ordered]@{name="c3_rx_deep_broad"; mode="rx_typed_beam"; canary_shards=6; shards=96; max_active=4; candidates=64; windows=72; beam_width=768; max_beam=131072; family_share=0.08; exploration=0.80; previous_limit=32; reward_limit=16; halving_fraction=0.38; halving_min=48; canary_min_eval=80},
  [ordered]@{name="c4_forward_fresh"; mode="forward_first"; canary_shards=6; shards=96; max_active=4; candidates=96; windows=72; beam_width=64; max_beam=8192; family_share=0.12; exploration=0.78; previous_limit=32; reward_limit=16; halving_fraction=0.35; halving_min=64; canary_min_eval=80},
  [ordered]@{name="c5_rx_orthogonal"; mode="rx_typed_beam"; canary_shards=8; shards=128; max_active=4; candidates=48; windows=96; beam_width=1024; max_beam=196608; family_share=0.04; exploration=0.80; previous_limit=40; reward_limit=20; halving_fraction=0.42; halving_min=40; canary_min_eval=48},
  [ordered]@{name="c6_forward_lowcap"; mode="forward_first"; canary_shards=6; shards=96; max_active=4; candidates=96; windows=96; beam_width=64; max_beam=8192; family_share=0.10; exploration=0.80; previous_limit=40; reward_limit=20; halving_fraction=0.35; halving_min=64; canary_min_eval=80},
  [ordered]@{name="c7_rx_gap_family_deep"; mode="rx_typed_beam"; canary_shards=8; shards=160; max_active=4; candidates=48; windows=120; beam_width=1536; max_beam=262144; family_share=0.12; exploration=0.74; previous_limit=48; reward_limit=24; halving_fraction=0.40; halving_min=48; canary_min_eval=48},
  [ordered]@{name="c8_forward_extended"; mode="forward_first"; canary_shards=8; shards=160; max_active=4; candidates=128; windows=120; beam_width=64; max_beam=8192; family_share=0.12; exploration=0.80; previous_limit=48; reward_limit=24; halving_fraction=0.35; halving_min=80; canary_min_eval=80},
  [ordered]@{name="c9_rx_ultra_orthogonal"; mode="rx_typed_beam"; canary_shards=8; shards=160; max_active=4; candidates=40; windows=144; beam_width=1536; max_beam=262144; family_share=0.03; exploration=0.80; previous_limit=48; reward_limit=24; halving_fraction=0.45; halving_min=40; canary_min_eval=48}
)

Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="overnight_begin"; run_root=$RunRoot; deadline=$deadline.ToString("s"); python=$Python; dataset=$DatasetPath})
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
Write-Status ([ordered]@{time=(Get-Date).ToString("s"); event="overnight_end"; run_root=$RunRoot})
