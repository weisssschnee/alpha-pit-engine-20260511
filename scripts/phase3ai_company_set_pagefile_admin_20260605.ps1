param(
  [int]$InitialMB = 32768,
  [int]$MaximumMB = 65536,
  [switch]$Restart
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "This script must be run in an elevated Administrator PowerShell session."
}

Write-Output "TIME=$(Get-Date -Format s)"
Write-Output "USER=$($identity.Name)"
Write-Output "TARGET_PAGEFILE=C:\pagefile.sys"
Write-Output "INITIAL_MB=$InitialMB"
Write-Output "MAXIMUM_MB=$MaximumMB"

$cs = Get-CimInstance Win32_ComputerSystem
Set-CimInstance -InputObject $cs -Property @{AutomaticManagedPagefile = $false}

$existing = Get-CimInstance Win32_PageFileSetting | Where-Object { $_.Name -ieq "c:\pagefile.sys" }
if ($existing) {
  Set-CimInstance -InputObject $existing -Property @{InitialSize = $InitialMB; MaximumSize = $MaximumMB}
} else {
  $class = Get-CimClass Win32_PageFileSetting
  New-CimInstance -CimClass $class -Property @{Name = "C:\pagefile.sys"; InitialSize = $InitialMB; MaximumSize = $MaximumMB} | Out-Null
}

Write-Output "AFTER_SETTING_BEGIN"
Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile,TotalPhysicalMemory | Format-List
Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize | Format-Table -AutoSize
Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | Format-Table -AutoSize
Write-Output "AFTER_SETTING_END"

Write-Output "NOTE=Pagefile setting may require reboot to fully take effect."
if ($Restart) {
  Restart-Computer -Force
}

