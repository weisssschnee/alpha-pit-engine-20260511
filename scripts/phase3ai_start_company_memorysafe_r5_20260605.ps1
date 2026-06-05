$ErrorActionPreference = "Stop"

$RemoteTool = "G:\Chengbo\tools\company-remote\company-remote.ps1"
$RepoRoot = "G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531"
$Archive = "G:\Project_V7_Rotation\runtime\phase3ai_sync\phase3ai_overnight_source_20260605.zip"
$RemoteArchive = "D:/HermesWorker/runtime/phase3ai_overnight_source_20260605.zip"
$RemoteScript = "D:/HermesWorker/runtime/phase3ai_remote_start_company_memorysafe_r5_20260605.ps1"
$LocalRemoteScript = Join-Path $RepoRoot "scripts\phase3ai_remote_start_company_memorysafe_r5_20260605.ps1"

New-Item -ItemType Directory -Force -Path (Split-Path $Archive -Parent) | Out-Null
git -C $RepoRoot archive --format=zip --output=$Archive HEAD

powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $Archive -RemotePath $RemoteArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $LocalRemoteScript -RemotePath $RemoteScript
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action start-detached -DetachedCommand "powershell -ExecutionPolicy Bypass -File D:\HermesWorker\runtime\phase3ai_remote_start_company_memorysafe_r5_20260605.ps1"

