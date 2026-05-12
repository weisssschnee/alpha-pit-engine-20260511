param(
    [int]$Seed = 3,
    [string]$RepoRoot = "D:\HermesWorker\workspace\our_system_phase1_repo",
    [string]$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe",
    [string]$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet",
    [string]$OutputBase = "D:\HermesWorker\runtime\phase3A-supervised-company-20260511",
    [int]$CandidateBudget = 64,
    [int]$StrictAuditBudget = 64,
    [int]$TargetWindowCount = 6,
    [int]$MaxWindow = 34,
    [int]$BeamWidth = 16,
    [int]$MaxBeamRecords = 256,
    [int]$HeartbeatSeconds = 30
)

$ErrorActionPreference = "Stop"

function Write-JsonLine {
    param(
        [string]$Path,
        [hashtable]$Record
    )
    $Record["created_at"] = (Get-Date -Format o)
    ($Record | ConvertTo-Json -Compress -Depth 8) | Add-Content -Path $Path -Encoding UTF8
}

function Write-JsonFile {
    param(
        [string]$Path,
        [hashtable]$Record
    )
    ($Record | ConvertTo-Json -Depth 12) | Set-Content -Path $Path -Encoding UTF8
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

function Infer-Stage {
    param(
        [string]$LatestFile,
        [int]$StrictCount,
        [bool]$ReportExists
    )
    if ($ReportExists) { return "report_written" }
    if ($StrictCount -gt 0) { return "strict_running" }
    if ($LatestFile -like "*stage1_variant_reports.json") { return "stage1_finished" }
    if ($LatestFile -like "*variants*") { return "stage1_running" }
    if ($LatestFile -like "*cem_internal*") { return "cem_running" }
    return "starting"
}

$seedName = "phase3A_repair_seed${Seed}_20260511"
$seedRoot = Join-Path $OutputBase $seedName
$failureDetail = Join-Path $RepoRoot "reports\PHASE3_REPAIR_AUDIT_2026-05-11_failure_detail.csv"
$modelDir = Join-Path $RepoRoot "data\models"
$statusPath = Join-Path $OutputBase "supervisor_status.jsonl"
$manifestPath = Join-Path $OutputBase "run_manifest.json"
$statePath = Join-Path $OutputBase "state.json"
$heartbeatPath = Join-Path $OutputBase "heartbeat.json"
$stdoutPath = Join-Path $seedRoot "stdout.json"
$stderrPath = Join-Path $seedRoot "stderr.log"

New-Item -ItemType Directory -Force -Path $seedRoot | Out-Null
$env:PYTHONPATH = Join-Path $RepoRoot "src"
Set-Location $RepoRoot

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

Write-JsonFile $manifestPath @{
    schema_version = "phase3A_company_supervisor_manifest_v1"
    git_commit = $gitCommit
    config_hash = Get-StringHash (@{
        seed = $Seed
        candidate_budget = $CandidateBudget
        strict_audit_budget = $StrictAuditBudget
        target_window_count = $TargetWindowCount
        max_window = $MaxWindow
        beam_width = $BeamWidth
        max_beam_records = $MaxBeamRecords
        dataset_path = $DatasetPath
    } | ConvertTo-Json -Compress)
    python_exe = $Python
    pip_freeze_hash = Get-StringHash $pipFreeze
    start_time = (Get-Date -Format o)
    machine_id = $env:COMPUTERNAME
    user = $env:USERNAME
    seed = $Seed
    budget = @{
        candidate_budget = $CandidateBudget
        strict_audit_budget = $StrictAuditBudget
    }
    command_line = @($Python, "<arguments-not-yet-initialized>")
}

Write-JsonFile $statePath @{
    seed_started = $true
    stage1_started = $false
    stage1_finished = $false
    strict_started = $false
    strict_finished = $false
    repair_started = $false
    repair_finished = $false
    report_written = $false
    seed_finished = $false
    exit_code = $null
    current_stage = "starting"
}

Write-JsonLine $statusPath @{
    status = "started"
    seed = $Seed
    seed_root = $seedRoot
    candidate_budget = $CandidateBudget
    strict_audit_budget = $StrictAuditBudget
    python = $Python
}

$arguments = @(
    "-m", "our_system_phase2.runtime.stock_pit_phase3_repair",
    "--dataset-path", $DatasetPath,
    "--output-root", $seedRoot,
    "--failure-detail-path", $failureDetail,
    "--replay-ranker-model-dir", $modelDir,
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

Write-JsonFile $manifestPath @{
    schema_version = "phase3A_company_supervisor_manifest_v1"
    git_commit = $gitCommit
    config_hash = Get-StringHash (@{
        seed = $Seed
        candidate_budget = $CandidateBudget
        strict_audit_budget = $StrictAuditBudget
        target_window_count = $TargetWindowCount
        max_window = $MaxWindow
        beam_width = $BeamWidth
        max_beam_records = $MaxBeamRecords
        dataset_path = $DatasetPath
    } | ConvertTo-Json -Compress)
    python_exe = $Python
    pip_freeze_hash = Get-StringHash $pipFreeze
    start_time = (Get-Date -Format o)
    machine_id = $env:COMPUTERNAME
    user = $env:USERNAME
    seed = $Seed
    budget = @{
        candidate_budget = $CandidateBudget
        strict_audit_budget = $StrictAuditBudget
    }
    command_line = @($Python) + $arguments
}

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList $arguments `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

Write-JsonLine $statusPath @{
    status = "python_started"
    seed = $Seed
    pid = $process.Id
}

while (-not $process.HasExited) {
    Start-Sleep -Seconds $HeartbeatSeconds
    $process.Refresh()
    $compute = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "python*" -and
            $_.CommandLine -like "*$seedRoot*"
        } |
        Sort-Object WorkingSetSize -Descending |
        Select-Object -First 1
    $computeProcess = $null
    if ($compute) {
        $computeProcess = Get-Process -Id $compute.ProcessId -ErrorAction SilentlyContinue
    }
    $strictCount = 0
    $strictDir = Join-Path $seedRoot "strict_phase3"
    if (Test-Path $strictDir) {
        $strictCount = (Get-ChildItem $strictDir -Filter "*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    }
    $latest = Get-ChildItem $seedRoot -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    $latestFile = if ($latest) { $latest.FullName } else { "" }
    $latestTime = if ($latest) { $latest.LastWriteTime.ToString("o") } else { "" }
    $reportExists = Test-Path (Join-Path $seedRoot "phase3_repair_report.json")
    $currentStage = Infer-Stage -LatestFile $latestFile -StrictCount $strictCount -ReportExists $reportExists
    Write-JsonLine $statusPath @{
        status = "heartbeat"
        seed = $Seed
        launcher_pid = $process.Id
        launcher_cpu = $process.CPU
        launcher_working_set = $process.WorkingSet64
        compute_pid = if ($compute) { $compute.ProcessId } else { $null }
        compute_parent_pid = if ($compute) { $compute.ParentProcessId } else { $null }
        compute_cpu = if ($computeProcess) { $computeProcess.CPU } else { $null }
        compute_working_set = if ($computeProcess) { $computeProcess.WorkingSet64 } else { $null }
        strict_files = $strictCount
        latest_file = $latestFile
        latest_file_time = $latestTime
        current_stage = $currentStage
        report_exists = $reportExists
    }
    Write-JsonFile $heartbeatPath @{
        last_update_time = (Get-Date -Format o)
        current_stage = $currentStage
        latest_file = $latestFile
        latest_file_time = $latestTime
        valid_count = $null
        strict_file_count = $strictCount
        audited_count = $strictCount
        report_exists = $reportExists
        launcher_pid = $process.Id
        compute_pid = if ($compute) { $compute.ProcessId } else { $null }
        compute_working_set = if ($computeProcess) { $computeProcess.WorkingSet64 } else { $null }
    }
    Write-JsonFile $statePath @{
        seed_started = $true
        stage1_started = $true
        stage1_finished = Test-Path (Join-Path $seedRoot "stage1_variant_reports.json")
        strict_started = $strictCount -gt 0
        strict_finished = $strictCount -ge $StrictAuditBudget
        repair_started = Test-Path (Join-Path $seedRoot "variants\ast_failure_aware_repair")
        repair_finished = Test-Path (Join-Path $seedRoot "variants\ast_failure_aware_repair\stage1_validation_report.json")
        report_written = $reportExists
        seed_finished = $false
        exit_code = $null
        current_stage = $currentStage
    }
}

$process.Refresh()
$finalReportExists = Test-Path (Join-Path $seedRoot "phase3_repair_report.json")
Write-JsonLine $statusPath @{
    status = "python_finished"
    seed = $Seed
    pid = $process.Id
    exit_code = $process.ExitCode
    stdout_bytes = if (Test-Path $stdoutPath) { (Get-Item $stdoutPath).Length } else { 0 }
    stderr_bytes = if (Test-Path $stderrPath) { (Get-Item $stderrPath).Length } else { 0 }
    report_exists = $finalReportExists
}
Write-JsonFile $statePath @{
    seed_started = $true
    stage1_started = $true
    stage1_finished = Test-Path (Join-Path $seedRoot "stage1_variant_reports.json")
    strict_started = Test-Path (Join-Path $seedRoot "strict_phase3")
    strict_finished = ((Get-ChildItem (Join-Path $seedRoot "strict_phase3") -Filter "*.json" -ErrorAction SilentlyContinue | Measure-Object).Count -ge $StrictAuditBudget)
    repair_started = Test-Path (Join-Path $seedRoot "variants\ast_failure_aware_repair")
    repair_finished = Test-Path (Join-Path $seedRoot "variants\ast_failure_aware_repair\stage1_validation_report.json")
    report_written = $finalReportExists
    seed_finished = $true
    exit_code = $process.ExitCode
    current_stage = if ($finalReportExists) { "seed_finished" } else { "failed_without_report" }
}

if ($process.ExitCode -ne 0) {
    throw "phase3A company seed $Seed failed with exit code $($process.ExitCode)"
}
