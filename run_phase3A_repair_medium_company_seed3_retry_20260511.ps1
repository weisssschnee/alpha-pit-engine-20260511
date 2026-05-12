$ErrorActionPreference = "Stop"

$repoRoot = "D:\HermesWorker\workspace\our_system_phase1_repo"
$outputBase = "D:\HermesWorker\runtime\phase3A-repair-medium-company-20260511-seed3-retry"

& (Join-Path $repoRoot "launch_phase3A_repair_medium_local_20260511.ps1") `
    -RepoRoot $repoRoot `
    -Python "D:\HermesWorker\workspace\.venv\Scripts\python.exe" `
    -DatasetPath "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet" `
    -FailureDetailPath (Join-Path $repoRoot "reports\PHASE3_REPAIR_AUDIT_2026-05-11_failure_detail.csv") `
    -ModelDir (Join-Path $repoRoot "data\models") `
    -OutputBase $outputBase `
    -Seeds @(3)
