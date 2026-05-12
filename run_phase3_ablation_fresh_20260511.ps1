param(
    [string]$RepoRoot = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo",
    [string]$Python = "G:\PythonProject\.venv\Scripts\python.exe",
    [string]$DatasetPath = "G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet",
    [string]$FailureDetailPath = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\reports\PHASE3_REPAIR_AUDIT_2026-05-11_failure_detail.csv",
    [string]$ModelDir = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\data\models",
    [string]$OutputBase = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\runtime\next_stage_artifacts\phase3-ablation-fresh-20260511-local",
    [int[]]$Seeds = @(7, 8),
    [string[]]$Arms = @(
        "original_R0",
        "R0_cluster_quota_only",
        "R0_AST_repair_only",
        "R0_cluster_quota_AST_repair_only",
        "Phase3A_full"
    ),
    [int]$CandidateBudget = 64,
    [int]$StrictAuditBudget = 64,
    [int]$TargetWindowCount = 6,
    [int]$MaxWindow = 34,
    [int]$BeamWidth = 16,
    [int]$MaxBeamRecords = 256,
    [int]$HeartbeatSeconds = 30,
    [string]$RunTag = "20260511",
    [string]$ExperimentId = "20260511_phase3_ablation_fresh",
    [string]$Objective = "A/B/C/D/E ablation for cluster quota and AST repair contribution"
)

$ErrorActionPreference = "Stop"

function Write-JsonLine {
    param(
        [string]$Path,
        [hashtable]$Record
    )
    $Record["created_at"] = (Get-Date -Format o)
    ($Record | ConvertTo-Json -Compress -Depth 12) | Add-Content -Path $Path -Encoding UTF8
}

function Write-JsonFile {
    param(
        [string]$Path,
        [hashtable]$Record
    )
    ($Record | ConvertTo-Json -Depth 14) | Set-Content -Path $Path -Encoding UTF8
}

function Get-StringHash {
    param([string]$Text)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $sha.Dispose()
    }
}

function Get-LatestFileInfo {
    param([string]$RunRoot)
    $latest = Get-ChildItem $RunRoot -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) {
        return @{
            latest_file = $latest.FullName
            latest_file_time = $latest.LastWriteTime.ToString("o")
        }
    }
    return @{
        latest_file = ""
        latest_file_time = ""
    }
}

New-Item -ItemType Directory -Force -Path $OutputBase | Out-Null
$Arms = @($Arms | ForEach-Object { "$_".Split(",") } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$env:PYTHONPATH = Join-Path $RepoRoot "src"
Set-Location $RepoRoot

$statusPath = Join-Path $OutputBase "ablation_status.jsonl"
$batchManifestPath = Join-Path $OutputBase "run_manifest.json"

$gitCommit = "unknown"
try {
    $gitCommit = (git rev-parse HEAD 2>$null).Trim()
}
catch {
    $gitCommit = "unknown"
}

$pipFreeze = ""
try {
    $pipFreeze = (& $Python -m pip freeze 2>$null) -join "`n"
}
catch {
    $pipFreeze = ""
}

$config = @{
    seeds = $Seeds
    arms = $Arms
    candidate_budget = $CandidateBudget
    strict_audit_budget = $StrictAuditBudget
    target_window_count = $TargetWindowCount
    max_window = $MaxWindow
    beam_width = $BeamWidth
    max_beam_records = $MaxBeamRecords
    dataset_path = $DatasetPath
}

Write-JsonFile $batchManifestPath @{
    schema_version = "phase3_ablation_batch_manifest_v1"
    experiment_id = $ExperimentId
    objective = $Objective
    git_commit = $gitCommit
    config_hash = Get-StringHash ($config | ConvertTo-Json -Compress)
    python_exe = $Python
    pip_freeze_hash = Get-StringHash $pipFreeze
    start_time = (Get-Date -Format o)
    machine_id = $env:COMPUTERNAME
    user = $env:USERNAME
    config = $config
    status_path = $statusPath
}

Write-JsonLine $statusPath @{
    status = "batch_started"
    seeds = $Seeds
    arms = $Arms
    candidate_budget = $CandidateBudget
    strict_audit_budget = $StrictAuditBudget
}

foreach ($seed in $Seeds) {
    foreach ($arm in $Arms) {
        $runId = "phase3_ablation_${arm}_seed${seed}_${RunTag}"
        $runRoot = Join-Path $OutputBase $runId
        $stdoutPath = Join-Path $runRoot "stdout.json"
        $stderrPath = Join-Path $runRoot "stderr.log"
        $statePath = Join-Path $runRoot "state.json"
        $manifestPath = Join-Path $runRoot "run_manifest.json"
        $heartbeatPath = Join-Path $runRoot "heartbeat.json"
        New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

        if (Test-Path (Join-Path $runRoot "phase3_repair_report.json")) {
            Write-JsonLine $statusPath @{
                status = "run_skipped_existing_report"
                run_id = $runId
                seed = $seed
                ablation_arm = $arm
                run_root = $runRoot
            }
            continue
        }

        $arguments = @(
            "-m", "our_system_phase2.runtime.stock_pit_phase3_repair",
            "--dataset-path", $DatasetPath,
            "--output-root", $runRoot,
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
            "--ablation-arm", $arm,
            "--seed", $runId
        )

        $runConfig = @{
            seeds = $Seeds
            arms = $Arms
            candidate_budget = $CandidateBudget
            strict_audit_budget = $StrictAuditBudget
            target_window_count = $TargetWindowCount
            max_window = $MaxWindow
            beam_width = $BeamWidth
            max_beam_records = $MaxBeamRecords
            dataset_path = $DatasetPath
            run_id = $runId
            arm = $arm
            seed = $seed
        }
        Write-JsonFile $manifestPath @{
            schema_version = "phase3_ablation_run_manifest_v1"
            experiment_id = $runId
            ablation_arm = $arm
            seed = $seed
            git_commit = $gitCommit
            config_hash = Get-StringHash ($runConfig | ConvertTo-Json -Compress)
            python_exe = $Python
            pip_freeze_hash = Get-StringHash $pipFreeze
            start_time = (Get-Date -Format o)
            machine_id = $env:COMPUTERNAME
            command_line = @($Python) + $arguments
        }

        Write-JsonFile $statePath @{
            run_started = $true
            seed_finished = $false
            report_written = $false
            exit_code = $null
            current_stage = "starting"
        }

        Write-JsonLine $statusPath @{
            status = "run_started"
            run_id = $runId
            seed = $seed
            ablation_arm = $arm
            run_root = $runRoot
        }

        $process = Start-Process `
            -FilePath $Python `
            -ArgumentList $arguments `
            -WorkingDirectory $RepoRoot `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -PassThru

        while (-not $process.HasExited) {
            Start-Sleep -Seconds $HeartbeatSeconds
            $process.Refresh()
            $strictDir = Join-Path $runRoot "strict_phase3"
            $strictCount = 0
            if (Test-Path $strictDir) {
                $strictCount = (Get-ChildItem $strictDir -Filter "*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
            }
            $reportExists = Test-Path (Join-Path $runRoot "phase3_repair_report.json")
            $latestInfo = Get-LatestFileInfo -RunRoot $runRoot
            $stage = "stage1_or_selection"
            if ($strictCount -gt 0) { $stage = "strict_running" }
            if ($strictCount -ge $StrictAuditBudget) { $stage = "post_strict_reporting" }
            if ($reportExists) { $stage = "report_written" }
            Write-JsonFile $heartbeatPath @{
                last_update_time = (Get-Date -Format o)
                run_id = $runId
                seed = $seed
                ablation_arm = $arm
                current_stage = $stage
                strict_file_count = $strictCount
                audited_count = $strictCount
                report_exists = $reportExists
                launcher_pid = $process.Id
                launcher_cpu = $process.CPU
                launcher_working_set = $process.WorkingSet64
                latest_file = $latestInfo.latest_file
                latest_file_time = $latestInfo.latest_file_time
            }
            Write-JsonLine $statusPath @{
                status = "heartbeat"
                run_id = $runId
                seed = $seed
                ablation_arm = $arm
                current_stage = $stage
                strict_files = $strictCount
                report_exists = $reportExists
            }
        }

        $process.WaitForExit()
        $process.Refresh()
        $finalReportExists = Test-Path (Join-Path $runRoot "phase3_repair_report.json")
        $exitCode = $process.ExitCode
        if ($null -eq $exitCode -and $finalReportExists) {
            $exitCode = 0
        }
        Write-JsonFile $statePath @{
            run_started = $true
            seed_finished = $true
            report_written = $finalReportExists
            exit_code = $exitCode
            current_stage = if ($finalReportExists) { "seed_finished" } else { "failed_without_report" }
        }
        Write-JsonLine $statusPath @{
            status = "run_finished"
            run_id = $runId
            seed = $seed
            ablation_arm = $arm
            exit_code = $exitCode
            report_exists = $finalReportExists
            stdout_bytes = if (Test-Path $stdoutPath) { (Get-Item $stdoutPath).Length } else { 0 }
            stderr_bytes = if (Test-Path $stderrPath) { (Get-Item $stderrPath).Length } else { 0 }
        }
        if ($exitCode -ne 0 -or -not $finalReportExists) {
            throw "ablation run $runId failed with exit code $exitCode, report_exists=$finalReportExists"
        }
    }
}

Write-JsonLine $statusPath @{
    status = "batch_completed"
    seeds = $Seeds
    arms = $Arms
}
