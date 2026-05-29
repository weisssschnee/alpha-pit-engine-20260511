$ErrorActionPreference = "Stop"

$RemoteTool = "G:\Chengbo\tools\company-remote\company-remote.ps1"
$RepoRoot = "G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528"
$Archive = "G:\Project_V7_Rotation\runtime\phase3aa_sync\phase3aa_source_current.zip"
$RemoteArchive = "D:/HermesWorker/runtime/phase3aa_source_current.zip"
$RemoteScript = "D:/HermesWorker/runtime/phase3aa_remote_start_company_heavy.ps1"

New-Item -ItemType Directory -Force -Path (Split-Path $Archive -Parent) | Out-Null
git -C $RepoRoot archive --format=zip --output=$Archive HEAD

powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $Archive -RemotePath $RemoteArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath (Join-Path $RepoRoot "scripts\phase3aa_remote_start_company_heavy.ps1") -RemotePath $RemoteScript
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action start-detached -DetachedCommand "powershell -ExecutionPolicy Bypass -File D:\HermesWorker\runtime\phase3aa_remote_start_company_heavy.ps1"
