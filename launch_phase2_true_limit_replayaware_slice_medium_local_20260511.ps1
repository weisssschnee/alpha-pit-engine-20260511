param(
    [string]$RepoRoot = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo",
    [string]$Python = "G:\PythonProject\.venv\Scripts\python.exe",
    [string]$DatasetPath = "G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet",
    [string]$ModelDir = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\data\models",
    [string]$OutputBase = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\runtime\next_stage_artifacts\phase2-true-limit-replayaware-slice-medium-local-20260511",
    [int[]]$Seeds = @(1, 2, 3),
    [int]$CandidateBudget = 64,
    [int]$TargetWindowCount = 6,
    [int]$MaxWindow = 34,
    [int]$BeamWidth = 16,
    [int]$MaxBeamRecords = 256,
    [int]$StrictTopNPerVariant = 4,
    [int]$StratifiedRandomNPerVariant = 2,
    [int]$ReplayAwareSliceNPerVariant = 2,
    [switch]$IncludeQd
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputBase | Out-Null
$env:PYTHONPATH = Join-Path $RepoRoot "src"
Set-Location $RepoRoot

$statusPath = Join-Path $OutputBase "medium_status.jsonl"
"{""created_at"":""$(Get-Date -Format o)"",""status"":""started"",""seeds"":[$($Seeds -join ',')],""candidate_budget"":$CandidateBudget,""replay_aware_slice_n_per_variant"":$ReplayAwareSliceNPerVariant}" | Add-Content -Path $statusPath -Encoding UTF8

foreach ($seed in $Seeds) {
    $seedName = "replayaware_medium_seed${seed}_20260511"
    $seedRoot = Join-Path $OutputBase $seedName
    New-Item -ItemType Directory -Force -Path $seedRoot | Out-Null
    "{""created_at"":""$(Get-Date -Format o)"",""status"":""seed_started"",""seed"":$seed,""output_root"":""$seedRoot""}" | Add-Content -Path $statusPath -Encoding UTF8

    $arguments = @(
        "-m", "our_system_phase2.runtime.stock_pit_true_limit_search_bakeoff_v2",
        "--dataset-path", $DatasetPath,
        "--output-root", $seedRoot,
        "--candidate-budget", "$CandidateBudget",
        "--target-window-count", "$TargetWindowCount",
        "--max-window", "$MaxWindow",
        "--beam-width", "$BeamWidth",
        "--max-beam-records", "$MaxBeamRecords",
        "--strict-top-n-per-variant", "$StrictTopNPerVariant",
        "--stratified-random-n-per-variant", "$StratifiedRandomNPerVariant",
        "--replay-ranker-model-dir", $ModelDir,
        "--replay-aware-slice-n-per-variant", "$ReplayAwareSliceNPerVariant",
        "--top-bottom-quantile", "0.02",
        "--recent-quarter-window-count", "2",
        "--recent-warmup-days", "60",
        "--strict-cost-bps", "10",
        "--low-corr-threshold", "0.80",
        "--turnover-survival-max-one-way", "0.75",
        "--seed", $seedName
    )
    if ($IncludeQd) {
        $arguments += "--include-qd"
    }

    $stdout = Join-Path $seedRoot "stdout.json"
    $stderr = Join-Path $seedRoot "stderr.log"
    & $Python @arguments 1> $stdout 2> $stderr
    $exitCode = $LASTEXITCODE
    "{""created_at"":""$(Get-Date -Format o)"",""status"":""seed_finished"",""seed"":$seed,""exit_code"":$exitCode,""output_root"":""$seedRoot""}" | Add-Content -Path $statusPath -Encoding UTF8
    if ($exitCode -ne 0) {
        throw "seed $seed failed with exit code $exitCode"
    }
}

"{""created_at"":""$(Get-Date -Format o)"",""status"":""completed"",""seeds"":[$($Seeds -join ',')]}" | Add-Content -Path $statusPath -Encoding UTF8
