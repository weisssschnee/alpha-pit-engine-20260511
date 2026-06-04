$ErrorActionPreference = "Stop"

$RunRoot = "D:\p3ai\overnight_company_20260605_r3"
$StatusPath = Join-Path $RunRoot "overnight_status.jsonl"
$JobId = "job_20260605_011913_ed2700"
$JobStatusPath = "D:\HermesWorker\runtime\jobs\$JobId.status.json"
$JobLogPath = "D:\HermesWorker\runtime\jobs\$JobId.log"

$processes = @()
Get-CimInstance Win32_Process -Filter "name='python.exe'" | ForEach-Object {
  $cmd = [string]$_.CommandLine
  if ($cmd -like "*phase3ai_overnight_company_r3*" -or $cmd -like "*overnight_company_20260605_r3*" -or $cmd -like "*stock_pit_large_search*") {
    $processes += [ordered]@{
      pid = $_.ProcessId
      ppid = $_.ParentProcessId
      working_set_mb = [math]::Round(([double]$_.WorkingSetSize / 1MB), 1)
      command = $cmd
    }
  }
}

[ordered]@{
  time = (Get-Date).ToString("s")
  run_root_exists = Test-Path $RunRoot
  status_tail = if (Test-Path $StatusPath) { @(Get-Content $StatusPath -Tail 20) } else { @() }
  job_status = if (Test-Path $JobStatusPath) { Get-Content $JobStatusPath -Raw } else { $null }
  job_log_tail = if (Test-Path $JobLogPath) { @(Get-Content $JobLogPath -Tail 40) } else { @() }
  processes = $processes
} | ConvertTo-Json -Depth 8
