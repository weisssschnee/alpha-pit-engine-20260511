$ErrorActionPreference = "SilentlyContinue"

Write-Output "TIME=$(Get-Date -Format s)"
Write-Output "COMPUTER=$env:COMPUTERNAME"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Output "IS_ADMIN=$isAdmin"
Write-Output "USER=$($identity.Name)"

Write-Output "COMPUTER_SYSTEM_BEGIN"
Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile,TotalPhysicalMemory | Format-List
Write-Output "COMPUTER_SYSTEM_END"

Write-Output "PAGEFILE_USAGE_BEGIN"
Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | Format-Table -AutoSize
Write-Output "PAGEFILE_USAGE_END"

Write-Output "PAGEFILE_SETTING_BEGIN"
Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize | Format-Table -AutoSize
Write-Output "PAGEFILE_SETTING_END"

Write-Output "DISK_BEGIN"
Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}},@{n='UsedGB';e={[math]::Round($_.Used/1GB,2)}} | Format-Table -AutoSize
Write-Output "DISK_END"

Write-Output "PROCESS_SUMMARY_BEGIN"
tasklist /FI "IMAGENAME eq python.exe"
tasklist /FI "IMAGENAME eq powershell.exe"
Write-Output "PROCESS_SUMMARY_END"

