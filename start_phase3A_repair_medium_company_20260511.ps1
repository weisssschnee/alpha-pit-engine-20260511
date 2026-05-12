param(
    [string]$RepoRoot = "D:\HermesWorker\workspace\our_system_phase1_repo",
    [string]$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe",
    [string]$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet",
    [string]$OutputBase = "D:\HermesWorker\runtime\phase3A-repair-medium-company-20260511-seeds2-3"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputBase | Out-Null

$runScript = Join-Path $RepoRoot "run_phase3A_repair_medium_company_20260511.ps1"
$launcherStdout = Join-Path $OutputBase "launcher_stdout.log"
$launcherStderr = Join-Path $OutputBase "launcher_stderr.log"

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $runScript
)

$process = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList $arguments `
    -WindowStyle Hidden `
    -RedirectStandardOutput $launcherStdout `
    -RedirectStandardError $launcherStderr `
    -PassThru

[pscustomobject]@{
    status = "started"
    pid = $process.Id
    output_base = $OutputBase
    launcher_stdout = $launcherStdout
    launcher_stderr = $launcherStderr
} | ConvertTo-Json -Compress
