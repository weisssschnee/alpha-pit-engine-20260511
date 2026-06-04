$ErrorActionPreference = "Stop"

$TaskIds = @(
  "job_20260605_004614_3da597",
  "job_20260605_005923_9287bc",
  "job_20260605_011913_ed2700"
)
$Patterns = @(
  "phase3ai_remote_start_company_overnight_20260605",
  "overnight_company_20260605",
  "phase3ai_overnight_company"
)

foreach ($taskId in $TaskIds) {
  $taskName = "HermesRemote_$taskId"
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
}

$stopped = @()
Get-CimInstance Win32_Process | ForEach-Object {
  $cmd = [string]$_.CommandLine
  foreach ($pattern in $Patterns) {
    if ($cmd -like "*$pattern*") {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      $stopped += [ordered]@{
        pid = $_.ProcessId
        name = $_.Name
        pattern = $pattern
      }
      break
    }
  }
}

[ordered]@{
  stopped_tasks = @($TaskIds | ForEach-Object { "HermesRemote_$_" })
  stopped_processes = $stopped
  time = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 5
