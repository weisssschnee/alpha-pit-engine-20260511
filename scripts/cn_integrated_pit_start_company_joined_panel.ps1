$ErrorActionPreference = "Stop"

$RemoteTool = "G:\Chengbo\tools\company-remote\company-remote.ps1"
$RepoRoot = "G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531"
$SyncRoot = "G:\Project_V7_Rotation\runtime\cn_integrated_pit_join_sync"
$Archive = Join-Path $SyncRoot "cn_integrated_pit_source_20260602.zip"
$SidecarArchive = Join-Path $SyncRoot "cn_integrated_pit_selected_sidecars_20260602.zip"
$RemoteArchive = "D:/HermesWorker/runtime/cn_integrated_pit_source_20260602.zip"
$RemoteSidecarArchive = "D:/HermesWorker/runtime/cn_integrated_pit_selected_sidecars_20260602.zip"
$SidecarRoot = Join-Path $RepoRoot "runtime\cn_integrated_pit_selected_sidecars_20260602"
$RemoteScript = "D:/HermesWorker/runtime/cn_integrated_pit_remote_build_joined_panel.ps1"
$LocalRemoteScript = Join-Path $RepoRoot "scripts\cn_integrated_pit_remote_build_joined_panel.ps1"

if (-not (Test-Path $RemoteTool)) { throw "missing remote tool: $RemoteTool" }
if (-not (Test-Path $RepoRoot)) { throw "missing repo root: $RepoRoot" }
if (-not (Test-Path $SidecarRoot)) { throw "missing sidecar root: $SidecarRoot" }
if (-not (Test-Path (Join-Path $SidecarRoot "minute_selected_sidecar.parquet"))) { throw "missing minute sidecar" }
if (-not (Test-Path (Join-Path $SidecarRoot "nonminute_selected_sidecar.parquet"))) { throw "missing nonminute sidecar" }
if (-not (Test-Path $LocalRemoteScript)) { throw "missing remote script: $LocalRemoteScript" }

New-Item -ItemType Directory -Force -Path $SyncRoot | Out-Null
git -C $RepoRoot archive --format=zip --output=$Archive HEAD
if (Test-Path $SidecarArchive) {
  Remove-Item -Force $SidecarArchive
}
Compress-Archive -Path (Join-Path $SidecarRoot "*") -DestinationPath $SidecarArchive -Force

powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $Archive -RemotePath $RemoteArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $SidecarArchive -RemotePath $RemoteSidecarArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $LocalRemoteScript -RemotePath $RemoteScript
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action start-detached -DetachedCommand "powershell -ExecutionPolicy Bypass -File D:\HermesWorker\runtime\cn_integrated_pit_remote_build_joined_panel.ps1"
