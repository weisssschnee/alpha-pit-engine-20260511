$ErrorActionPreference = "Continue"

$RunRoot = "D:\p3ai\overnight_company_20260605_r4"
$StatusPath = Join-Path $RunRoot "overnight_status.jsonl"
$JobId = "job_20260605_011913_ed2700"
$JobLogPath = "D:\HermesWorker\runtime\jobs\$JobId.log"

Write-Output "TIME=$((Get-Date).ToString('s'))"
Write-Output "RUN_ROOT_EXISTS=$(Test-Path $RunRoot)"
if (Test-Path $StatusPath) {
  Write-Output "STATUS_TAIL_BEGIN"
  Get-Content $StatusPath -Tail 20
  Write-Output "STATUS_TAIL_END"
} else {
  Write-Output "NO_OVERNIGHT_STATUS"
}
if (Test-Path $JobLogPath) {
  Write-Output "JOB_LOG_TAIL_BEGIN"
  Get-Content $JobLogPath -Tail 40
  Write-Output "JOB_LOG_TAIL_END"
}
Write-Output "PYTHON_TASKLIST_BEGIN"
cmd /c tasklist /FI "IMAGENAME eq python.exe"
Write-Output "PYTHON_TASKLIST_END"
Write-Output "POWERSHELL_TASKLIST_BEGIN"
cmd /c tasklist /FI "IMAGENAME eq powershell.exe"
Write-Output "POWERSHELL_TASKLIST_END"
