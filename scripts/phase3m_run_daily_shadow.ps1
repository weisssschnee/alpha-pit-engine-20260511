param(
  [string]$SignalDate = "",
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$env:PYTHONPATH = "src"
$Python = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = "py"
}

if ($SignalDate -eq "") {
  $exportArgs = @("-m", "our_system_phase2.runtime.phase3l_p_locked_forward_export")
} else {
  $exportArgs = @("-m", "our_system_phase2.runtime.phase3l_p_locked_forward_export", "--signal-date", $SignalDate)
}

if ($Force) {
  $exportArgs += "--force"
}

& $Python @exportArgs
& $Python -m our_system_phase2.runtime.phase3m_shadow_reconciliation
& $Python -m our_system_phase2.runtime.phase3m_paper_order_intent
& $Python -m our_system_phase2.runtime.phase3m_production_readiness_gate
