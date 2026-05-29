$ErrorActionPreference = "Stop"

$RepoRoot = "G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528"
$Python = "G:\PythonProject\.venv\Scripts\python.exe"
$LaunchRoot = "G:\Project_V7_Rotation\runtime\phase3aa_smoke_20260529"
$JobId = "phase3aa_local_smoke_20260529"

$env:PYTHONPATH = "src"

$ArgsList = @(
  "-m", "our_system_phase2.runtime.phase3aa_launch_mature_search",
  "--repo-root", $RepoRoot,
  "--launch-root", $LaunchRoot,
  "--job-id", $JobId,
  "--machine", "local",
  "--shard-count", "4",
  "--max-active", "2",
  "--target-window-count", "12",
  "--parallel-workers", "2",
  "--previous-root-limit", "80",
  "--reward-root-limit", "40",
  "--max-family-share", "0.18",
  "--reward-exploration-share", "0.35"
)

$LogDir = Join-Path $LaunchRoot "launcher_logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Start-Process `
  -FilePath $Python `
  -ArgumentList $ArgsList `
  -WorkingDirectory $RepoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput (Join-Path $LogDir "stdout.log") `
  -RedirectStandardError (Join-Path $LogDir "stderr.log")

Write-Output "started $JobId"
Write-Output "launch_root=$LaunchRoot"
