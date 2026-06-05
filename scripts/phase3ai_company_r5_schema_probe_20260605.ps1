$ErrorActionPreference = "SilentlyContinue"
$Files = @(
  "D:\p3ai\overnight_company_20260605_r5_memorysafe\c4_forward_fresh_ms_main\supervisor-shard_64_of_128\stage1_summary.json",
  "D:\p3ai\overnight_company_20260605_r5_memorysafe\c4_forward_fresh_ms_main\supervisor-shard_64_of_128\stage1_validation_report.json",
  "D:\p3ai\overnight_company_20260605_r5_memorysafe\c4_forward_fresh_ms_main\supervisor-shard_64_of_128\successive_halving\successive_halving_stage1_ledger.json"
)
foreach ($f in $Files) {
  Write-Output "FILE_BEGIN=$f"
  if (Test-Path $f) {
    Get-Content $f -TotalCount 80
  } else {
    Write-Output "MISSING"
  }
  Write-Output "FILE_END=$f"
}
