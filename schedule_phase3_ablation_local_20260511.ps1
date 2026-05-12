$ErrorActionPreference = "Stop"

$taskName = "Phase3AblationLocalFresh20260511"
$scriptPath = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\start_phase3_ablation_local_20260511.ps1"
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

schtasks /Create /F /TN $taskName /SC ONCE /ST 23:59 /TR $taskCommand | Out-Host
schtasks /Run /TN $taskName | Out-Host
schtasks /Query /TN $taskName /V /FO LIST | Out-Host
