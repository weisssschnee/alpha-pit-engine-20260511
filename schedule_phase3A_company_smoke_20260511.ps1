$ErrorActionPreference = "Stop"

$task = "Phase3ACompanySmokeSupervised20260511"
$runner = "D:\HermesWorker\workspace\our_system_phase1_repo\run_phase3A_company_smoke_supervised_20260511.ps1"
$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$runner`""

cmd /c "schtasks /Delete /TN $task /F >nul 2>nul"
cmd /c "schtasks /Create /TN $task /SC ONCE /ST 23:59 /TR ""$tr"" /F"
cmd /c "schtasks /Run /TN $task"
