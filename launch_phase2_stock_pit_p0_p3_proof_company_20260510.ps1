param(
  [string]$RunName = "phase2-stock-pit-p0-p3-proof-company-medium-20260510",
  [int]$CandidateBudget = 64,
  [int]$TargetWindowCount = 6,
  [int]$MaxWindow = 34,
  [int]$BeamWidth = 16,
  [int]$MaxBeamRecords = 256,
  [int]$StrictTopNPerVariant = 3,
  [int]$RandomPassThroughNPerVariant = 1,
  [int]$StrictDecileSamplePerBucket = 1
)

$ErrorActionPreference = "Stop"

$RepoRoot = "D:\HermesWorker\workspace\our_system_phase1_repo"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$Dataset = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$OutputRoot = "D:\HermesWorker\runtime\$RunName"
$PreviousA = "D:\HermesWorker\runtime\company-v2-fast-context-full-search-20260508-max3-gated"
$PreviousB = "D:\HermesWorker\runtime\company-v2-tail-search-20260508-shards128-256"

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$PythonPath = Join-Path $RepoRoot "src"

$args = @(
  "-m", "our_system_phase2.runtime.stock_pit_proof_suite",
  "--mode", "p0-p3-proof",
  "--dataset-path", $Dataset,
  "--output-root", $OutputRoot,
  "--previous-search-root", $PreviousA,
  "--previous-search-root", $PreviousB,
  "--candidate-budget", "$CandidateBudget",
  "--target-window-count", "$TargetWindowCount",
  "--max-window", "$MaxWindow",
  "--beam-width", "$BeamWidth",
  "--max-beam-records", "$MaxBeamRecords",
  "--strict-top-n-per-variant", "$StrictTopNPerVariant",
  "--random-pass-through-n-per-variant", "$RandomPassThroughNPerVariant",
  "--strict-decile-sample-per-bucket", "$StrictDecileSamplePerBucket",
  "--top-bottom-quantile", "0.02",
  "--recent-quarter-window-count", "2",
  "--recent-warmup-days", "60",
  "--strict-cost-bps", "10",
  "--low-corr-threshold", "0.80",
  "--seed", $RunName
)

$manifest = [ordered]@{
  created_at = (Get-Date).ToString("o")
  run_name = $RunName
  repo_root = $RepoRoot
  python = $Python
  dataset = $Dataset
  output_root = $OutputRoot
  candidate_budget = $CandidateBudget
  target_window_count = $TargetWindowCount
  max_window = $MaxWindow
  beam_width = $BeamWidth
  max_beam_records = $MaxBeamRecords
  strict_top_n_per_variant = $StrictTopNPerVariant
  random_pass_through_n_per_variant = $RandomPassThroughNPerVariant
  strict_decile_sample_per_bucket = $StrictDecileSamplePerBucket
  previous_search_roots = @($PreviousA, $PreviousB)
  command_args = $args
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $OutputRoot "launch_manifest.json") -Encoding UTF8

$stdout = Join-Path $OutputRoot "stdout.log"
$stderr = Join-Path $OutputRoot "stderr.log"
$quotedArgs = ($args | ForEach-Object {
  if ($_ -match '\s') {
    '"' + ($_ -replace '"', '\"') + '"'
  } else {
    $_
  }
}) -join " "
$cmdLine = "cd /d `"$RepoRoot`" && set PYTHONPATH=$PythonPath&& `"$Python`" $quotedArgs > `"$stdout`" 2> `"$stderr`""
$cmdLine | Set-Content -Path (Join-Path $OutputRoot "command_line.txt") -Encoding UTF8
$batPath = Join-Path $OutputRoot "run_p0_p3_proof.bat"
@(
  "@echo off",
  $cmdLine
) | Set-Content -Path $batPath -Encoding ASCII

$process = Start-Process `
  -FilePath "cmd.exe" `
  -ArgumentList "/c `"$batPath`"" `
  -WorkingDirectory $RepoRoot `
  -WindowStyle Hidden `
  -PassThru

[ordered]@{
  created_at = (Get-Date).ToString("o")
  status = "running"
  pid = $process.Id
  output_root = $OutputRoot
  stdout = $stdout
  stderr = $stderr
  command_line = $cmdLine
  batch_file = $batPath
} | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $OutputRoot "runner_status.json") -Encoding UTF8

Write-Output "started pid=$($process.Id) output=$OutputRoot"
