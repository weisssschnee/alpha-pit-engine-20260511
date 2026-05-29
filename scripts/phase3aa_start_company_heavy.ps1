$ErrorActionPreference = "Stop"

$RemoteTool = "G:\Chengbo\tools\company-remote\company-remote.ps1"
$RepoRoot = "D:\HermesWorker\alpha-pit-engine-20260511"
$Python = "D:\HermesWorker\.venv\Scripts\python.exe"
$LaunchRoot = "D:\p3aa\company_heavy_20260529"
$JobId = "phase3aa_company_heavy_20260529"

$RemoteCommand = @"
cd /d $RepoRoot && git fetch origin && git checkout feature/mature-chain-adapter-20260528 && git pull --ff-only origin feature/mature-chain-adapter-20260528 && set PYTHONPATH=src && "$Python" -m our_system_phase2.runtime.phase3aa_launch_mature_search --repo-root "$RepoRoot" --launch-root "$LaunchRoot" --job-id "$JobId" --machine company --shard-count 32 --max-active 6 --target-window-count 24 --parallel-workers 2 --previous-root-limit 120 --reward-root-limit 60 --max-family-share 0.18 --reward-exploration-share 0.35
"@

powershell -ExecutionPolicy Bypass -File $RemoteTool -Action start-detached -DetachedCommand $RemoteCommand
