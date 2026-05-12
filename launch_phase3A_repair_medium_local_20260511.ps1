param(
    [string]$RepoRoot = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo",
    [string]$Python = "G:\PythonProject\.venv\Scripts\python.exe",
    [string]$DatasetPath = "G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet",
    [string]$FailureDetailPath = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\reports\PHASE3_REPAIR_AUDIT_2026-05-11_failure_detail.csv",
    [string]$ModelDir = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\data\models",
    [string]$OutputBase = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\runtime\next_stage_artifacts\phase3A-repair-medium-local-20260511",
    [int[]]$Seeds = @(1, 2, 3),
    [int]$CandidateBudget = 64,
    [int]$StrictAuditBudget = 64,
    [int]$TargetWindowCount = 6,
    [int]$MaxWindow = 34,
    [int]$BeamWidth = 16,
    [int]$MaxBeamRecords = 256
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputBase | Out-Null
$env:PYTHONPATH = Join-Path $RepoRoot "src"
Set-Location $RepoRoot

$statusPath = Join-Path $OutputBase "medium_status.jsonl"
"{""created_at"":""$(Get-Date -Format o)"",""status"":""started"",""seeds"":[$($Seeds -join ',')],""candidate_budget"":$CandidateBudget,""strict_audit_budget"":$StrictAuditBudget,""kpi"":""deployable_unique_clusters_per_audited""}" | Add-Content -Path $statusPath -Encoding UTF8

foreach ($seed in $Seeds) {
    $seedName = "phase3A_repair_seed${seed}_20260511"
    $seedRoot = Join-Path $OutputBase $seedName
    New-Item -ItemType Directory -Force -Path $seedRoot | Out-Null
    "{""created_at"":""$(Get-Date -Format o)"",""status"":""seed_started"",""seed"":$seed,""output_root"":""$seedRoot""}" | Add-Content -Path $statusPath -Encoding UTF8

    $arguments = @(
        "-m", "our_system_phase2.runtime.stock_pit_phase3_repair",
        "--dataset-path", $DatasetPath,
        "--output-root", $seedRoot,
        "--failure-detail-path", $FailureDetailPath,
        "--replay-ranker-model-dir", $ModelDir,
        "--candidate-budget", "$CandidateBudget",
        "--strict-audit-budget", "$StrictAuditBudget",
        "--target-window-count", "$TargetWindowCount",
        "--max-window", "$MaxWindow",
        "--beam-width", "$BeamWidth",
        "--max-beam-records", "$MaxBeamRecords",
        "--top-bottom-quantile", "0.02",
        "--recent-quarter-window-count", "2",
        "--recent-warmup-days", "60",
        "--strict-cost-bps", "10",
        "--low-corr-threshold", "0.80",
        "--turnover-survival-max-one-way", "0.75",
        "--max-audited-per-return-corr-cluster-per-seed", "4",
        "--max-audited-per-ast-cluster-per-seed", "3",
        "--seed", $seedName
    )

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
