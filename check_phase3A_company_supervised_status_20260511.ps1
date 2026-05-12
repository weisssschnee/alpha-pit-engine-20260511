param(
    [string]$OutputBase = "D:\HermesWorker\runtime\phase3A-supervised-medium-20260511-seed4",
    [string]$TaskName = "Phase3ACompanySeed4Supervised20260511",
    [int]$HeartbeatStaleSeconds = 180,
    [int]$FileStaleSeconds = 900
)

$ErrorActionPreference = "Stop"

$statusPath = Join-Path $OutputBase "supervisor_status.jsonl"
$now = Get-Date
$records = @()
if (Test-Path $statusPath) {
    $records = Get-Content $statusPath -ErrorAction Stop |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json }
}

$last = $records | Select-Object -Last 1
$lastHeartbeat = $records | Where-Object { $_.status -eq "heartbeat" } | Select-Object -Last 1
$finished = $records | Where-Object { $_.status -eq "python_finished" } | Select-Object -Last 1

$heartbeatAge = $null
if ($lastHeartbeat) {
    $heartbeatAge = [int]($now - [datetime]$lastHeartbeat.created_at).TotalSeconds
}

$latestFileAge = $null
if ($lastHeartbeat -and $lastHeartbeat.latest_file_time) {
    $latestFileAge = [int]($now - [datetime]$lastHeartbeat.latest_file_time).TotalSeconds
}

$reportExists = $false
if ($lastHeartbeat -and $lastHeartbeat.PSObject.Properties.Name -contains "report_exists") {
    $reportExists = [bool]$lastHeartbeat.report_exists
}
if ($finished -and $finished.PSObject.Properties.Name -contains "report_exists") {
    $reportExists = [bool]$finished.report_exists
}

$pythonProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "python*" -and
        ($_.CommandLine -like "*phase3A*" -or $_.CommandLine -like "*stock_pit_phase3_repair*")
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine

$taskText = cmd /c "schtasks /Query /TN $TaskName /V /FO LIST 2>nul"

$verdict = "UNKNOWN"
$reason = "no status records"
if ($finished) {
    if ($finished.report_exists -and ($finished.exit_code -eq 0 -or $null -eq $finished.exit_code)) {
        $verdict = "COMPLETE"
        $reason = "finished with report"
    } else {
        $verdict = "FAILED"
        $reason = "finished without successful report"
    }
} elseif (-not $lastHeartbeat) {
    $verdict = "FAILED"
    $reason = "no heartbeat"
} elseif ($heartbeatAge -gt $HeartbeatStaleSeconds) {
    $verdict = "STALLED"
    $reason = "heartbeat stale: ${heartbeatAge}s"
} elseif ($latestFileAge -gt $FileStaleSeconds -and -not $reportExists) {
    $verdict = "STALLED"
    $reason = "latest output stale: ${latestFileAge}s"
} else {
    $verdict = "HEALTHY"
    $reason = "heartbeat and output are fresh"
}

[pscustomobject]@{
    checked_at = $now.ToString("o")
    verdict = $verdict
    reason = $reason
    output_base = $OutputBase
    last_status = if ($last) { $last.status } else { $null }
    heartbeat_age_seconds = $heartbeatAge
    latest_file_age_seconds = $latestFileAge
    strict_files = if ($lastHeartbeat) { $lastHeartbeat.strict_files } else { $null }
    report_exists = $reportExists
    latest_file = if ($lastHeartbeat) { $lastHeartbeat.latest_file } else { $null }
    compute_pid = if ($lastHeartbeat -and ($lastHeartbeat.PSObject.Properties.Name -contains "compute_pid")) { $lastHeartbeat.compute_pid } else { $null }
    compute_working_set = if ($lastHeartbeat -and ($lastHeartbeat.PSObject.Properties.Name -contains "compute_working_set")) { $lastHeartbeat.compute_working_set } else { $null }
    active_python_count = ($pythonProcs | Measure-Object).Count
    task_summary = ($taskText -join "`n")
} | ConvertTo-Json -Depth 6
