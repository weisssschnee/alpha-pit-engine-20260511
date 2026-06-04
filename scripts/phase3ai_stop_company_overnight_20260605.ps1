$ErrorActionPreference = "Stop"

$TaskId = "job_20260605_004614_3da597"
$TaskName = "HermesRemote_$TaskId"
$Patterns = @(
  "phase3ai_remote_start_company_overnight_20260605",
  "overnight_company_20260605",
  "phase3ai_overnight_company"
)

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

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
  stopped_task = $TaskName
  stopped_processes = $stopped
  time = (Get-Date).ToString("s")
} | ConvertTo-Json -Depth 5
