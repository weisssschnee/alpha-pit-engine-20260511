$ErrorActionPreference = "Continue"

$LegRoot = "D:\p3ai\overnight_company_20260605_r3\c3_rx_deep_broad_canary"
$Files = @(
  "phase3ab_supervisor.log",
  "phase3ab_launch_manifest.json",
  "supervisor\supervisor_status.json",
  "supervisor\shard_00.stderr.log",
  "supervisor\shard_00.stdout.log",
  "supervisor-shard_00_of_06\stage1_summary.json",
  "supervisor-shard_00_of_06\worker_status.json"
)

Write-Output "TIME=$((Get-Date).ToString('s'))"
Write-Output "LEG_ROOT=$LegRoot"
foreach ($rel in $Files) {
  $path = Join-Path $LegRoot $rel
  Write-Output "FILE_BEGIN $rel"
  if (Test-Path $path) {
    Get-Content $path -Tail 80
  } else {
    Write-Output "MISSING $path"
  }
  Write-Output "FILE_END $rel"
}
