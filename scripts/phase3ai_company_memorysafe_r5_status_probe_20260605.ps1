$ErrorActionPreference = "SilentlyContinue"
$RunRoot = "D:\p3ai\overnight_company_20260605_r5_memorysafe"
$StatusPath = Join-Path $RunRoot "overnight_status.jsonl"

Write-Output "TIME=$(Get-Date -Format s)"
Write-Output "RUN_ROOT_EXISTS=$(Test-Path $RunRoot)"

Write-Output "STATUS_TAIL_BEGIN"
if (Test-Path $StatusPath) {
  Get-Content $StatusPath -Tail 120
} else {
  Write-Output "NO_STATUS"
}
Write-Output "STATUS_TAIL_END"

Write-Output "LEG_SUMMARY_BEGIN"
if (Test-Path $RunRoot) {
  Get-ChildItem $RunRoot -Directory | Sort-Object Name | ForEach-Object {
    $leg = $_.Name
    $supervisorStatus = Join-Path $_.FullName "supervisor\supervisor_status.json"
    $completed = 0
    $failed = 0
    $running = 0
    $eval = 0
    $best = $null
    if (Test-Path $supervisorStatus) {
      $s = Get-Content $supervisorStatus -Raw | ConvertFrom-Json
      $completed = ($s.completed.PSObject.Properties | Measure-Object).Count
      $failed = ($s.failed.PSObject.Properties | Measure-Object).Count
      $running = ($s.running.PSObject.Properties | Measure-Object).Count
      foreach ($p in $s.completed.PSObject.Properties) {
        $sum = $p.Value.summary
        if ($sum.validation_evaluated_count) { $eval += [int]$sum.validation_evaluated_count }
        if ($sum.top_long_sortino -ne $null) {
          $v = [double]$sum.top_long_sortino
          if ($best -eq $null -or $v -gt $best) { $best = $v }
        }
      }
    }
    Write-Output ("LEG={0} completed={1} failed={2} running={3} eval={4} best_sortino={5}" -f $leg,$completed,$failed,$running,$eval,$best)
  }
}
Write-Output "LEG_SUMMARY_END"

Write-Output "OS_MEMORY_BEGIN"
$os = Get-CimInstance Win32_OperatingSystem
if ($os) {
  Write-Output ("FreePhysicalGB={0}" -f ([math]::Round($os.FreePhysicalMemory/1MB,2)))
  Write-Output ("FreeVirtualGB={0}" -f ([math]::Round($os.FreeVirtualMemory/1MB,2)))
  Write-Output ("PageFilesGB={0}" -f ([math]::Round($os.SizeStoredInPagingFiles/1MB,2)))
}
Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | Format-Table -AutoSize
Write-Output "OS_MEMORY_END"

Write-Output "TASKLIST_BEGIN"
tasklist /FI "IMAGENAME eq python.exe"
tasklist /FI "IMAGENAME eq powershell.exe"
Write-Output "TASKLIST_END"

