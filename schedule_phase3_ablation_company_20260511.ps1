$ErrorActionPreference = "Stop"

$taskName = "Phase3AblationCompanyFresh20260511"
$scriptPath = "D:\HermesWorker\workspace\our_system_phase1_repo\start_phase3_ablation_company_20260511.ps1"
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

schtasks /Create /F /TN $taskName /SC ONCE /ST 23:59 /TR $taskCommand | Out-Host
schtasks /Run /TN $taskName | Out-Host
schtasks /Query /TN $taskName /V /FO LIST | Out-Host
