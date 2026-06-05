$ErrorActionPreference = "SilentlyContinue"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$RunRoot = "D:\p3ai\overnight_company_20260605_r4"

Write-Output "TIME=$(Get-Date -Format s)"
Write-Output "COMPUTER=$env:COMPUTERNAME"

Write-Output "OS_MEMORY_BEGIN"
$os = Get-CimInstance Win32_OperatingSystem
if ($os) {
  Write-Output ("TotalVisibleGB={0}" -f ([math]::Round($os.TotalVisibleMemorySize/1MB,2)))
  Write-Output ("FreePhysicalGB={0}" -f ([math]::Round($os.FreePhysicalMemory/1MB,2)))
  Write-Output ("TotalVirtualGB={0}" -f ([math]::Round($os.TotalVirtualMemorySize/1MB,2)))
  Write-Output ("FreeVirtualGB={0}" -f ([math]::Round($os.FreeVirtualMemory/1MB,2)))
  Write-Output ("PageFilesGB={0}" -f ([math]::Round($os.SizeStoredInPagingFiles/1MB,2)))
}
Write-Output "OS_MEMORY_END"

Write-Output "PAGEFILE_BEGIN"
Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage | Format-Table -AutoSize
Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize | Format-Table -AutoSize
Write-Output "PAGEFILE_END"

Write-Output "DISK_BEGIN"
Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free,@{n='FreeGB';e={[math]::Round($_.Free/1GB,2)}},@{n='UsedGB';e={[math]::Round($_.Used/1GB,2)}} | Format-Table -AutoSize
Write-Output "DISK_END"

Write-Output "PYTHON_VERSION_BEGIN"
if (Test-Path $Python) {
  @'
import importlib, platform, sys
print("python_exe", sys.executable)
print("python", sys.version.replace("\n"," "))
for name in ["numpy","pandas","pyarrow","numba","bottleneck","numexpr","polars","joblib","sklearn"]:
    try:
        m=importlib.import_module(name)
        print(name, getattr(m, "__version__", "unknown"))
    except Exception as e:
        print(name, "MISSING", type(e).__name__, str(e)[:120])
'@ | & $Python -
} else {
  Write-Output "PYTHON_MISSING=$Python"
}
Write-Output "PYTHON_VERSION_END"

Write-Output "CURRENT_R4_BEGIN"
$statusPath = Join-Path $RunRoot "overnight_status.jsonl"
if (Test-Path $statusPath) { Get-Content $statusPath -Tail 80 } else { Write-Output "NO_R4_STATUS" }
Write-Output "CURRENT_R4_END"

Write-Output "PROCESS_BEGIN"
tasklist /FI "IMAGENAME eq python.exe"
tasklist /FI "IMAGENAME eq powershell.exe"
Write-Output "PROCESS_END"
