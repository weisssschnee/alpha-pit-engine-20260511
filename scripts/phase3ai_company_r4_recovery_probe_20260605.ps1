$ErrorActionPreference = "SilentlyContinue"
$RunRoot = "D:\p3ai\overnight_company_20260605_r4"
$JobId = "job_20260605_014556_eeaa8c"

Write-Output "TIME=$(Get-Date -Format s)"
Write-Output "RUN_ROOT=$RunRoot"
Write-Output "RUN_ROOT_EXISTS=$(Test-Path $RunRoot)"

$statusPath = Join-Path $RunRoot "overnight_status.jsonl"
Write-Output "STATUS_TAIL_BEGIN"
if (Test-Path $statusPath) {
  Get-Content $statusPath -Tail 120
} else {
  Write-Output "NO_STATUS"
}
Write-Output "STATUS_TAIL_END"

Write-Output "LEG_SUMMARY_BEGIN"
if (Test-Path $RunRoot) {
  Get-ChildItem $RunRoot -Directory | Sort-Object Name | ForEach-Object {
    $leg = $_.Name
    $supervisorStatus = Join-Path $_.FullName "supervisor\supervisor_status.json"
    $summary = Join-Path $_.FullName "summary.json"
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
    $summaryExists = Test-Path $summary
    Write-Output ("LEG={0} completed={1} failed={2} running={3} eval={4} best_sortino={5} summary_exists={6}" -f $leg,$completed,$failed,$running,$eval,$best,$summaryExists)
    if ($failed -gt 0) {
      $failedSamples = @()
      foreach ($p in $s.failed.PSObject.Properties | Select-Object -First 8) {
        $failedSamples += ("{0}:pid={1}:code={2}" -f $p.Name,$p.Value.pid,$p.Value.return_code)
      }
      Write-Output ("LEG_FAILED_SAMPLE={0} {1}" -f $leg,($failedSamples -join ";"))
    }
  }
}
Write-Output "LEG_SUMMARY_END"

Write-Output "RECENT_FILES_BEGIN"
if (Test-Path $RunRoot) {
  Get-ChildItem $RunRoot -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 40 FullName,Length,LastWriteTime | Format-Table -AutoSize
}
Write-Output "RECENT_FILES_END"

Write-Output "FAILED_STDERR_SAMPLE_BEGIN"
$c4Status = Join-Path $RunRoot "c4_forward_fresh_main\supervisor\supervisor_status.json"
if (Test-Path $c4Status) {
  $s = Get-Content $c4Status -Raw | ConvertFrom-Json
  foreach ($p in $s.failed.PSObject.Properties | Select-Object -First 5) {
    Write-Output ("FAILED_SHARD={0} pid={1} code={2}" -f $p.Name,$p.Value.pid,$p.Value.return_code)
    $stderr = $p.Value.stderr
    if ($stderr -and (Test-Path $stderr)) {
      Get-Content $stderr -Tail 20
    } else {
      Write-Output "NO_STDERR_FILE"
    }
  }
}
Write-Output "FAILED_STDERR_SAMPLE_END"

Write-Output "PYTHON_TASKLIST_BEGIN"
tasklist /FI "IMAGENAME eq python.exe"
Write-Output "PYTHON_TASKLIST_END"
