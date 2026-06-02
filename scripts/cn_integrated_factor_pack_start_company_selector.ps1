$ErrorActionPreference = "Stop"

$RemoteTool = "G:\Chengbo\tools\company-remote\company-remote.ps1"
$RepoRoot = "G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531"
$Archive = "G:\Project_V7_Rotation\runtime\cn_integrated_factor_pack_sync\cn_integrated_factor_pack_source_20260602.zip"
$RemoteArchive = "D:/HermesWorker/runtime/cn_integrated_factor_pack_source_20260602.zip"
$SignalVectorRoot = Join-Path $RepoRoot "runtime\phase3g_signal_vectors"
$SignalVectorArchive = "G:\Project_V7_Rotation\runtime\cn_integrated_factor_pack_sync\cn_integrated_factor_pack_signal_vectors_20260602.zip"
$RemoteSignalVectorArchive = "D:/HermesWorker/runtime/cn_integrated_factor_pack_signal_vectors_20260602.zip"
$SourcePool = Join-Path $RepoRoot "runtime\cn_factor_pack_phase3aa_preflight_20260531\shared_candidate_pool_raw.json"
$RemoteSourcePool = "D:/HermesWorker/runtime/cn_integrated_factor_pack_source_pool_raw_20260602.json"
$RemoteScript = "D:/HermesWorker/runtime/cn_integrated_factor_pack_remote_company_selector.ps1"
$LocalRemoteScript = Join-Path $RepoRoot "scripts\cn_integrated_factor_pack_remote_company_selector.ps1"

if (-not (Test-Path $RemoteTool)) { throw "missing remote tool: $RemoteTool" }
if (-not (Test-Path $RepoRoot)) { throw "missing repo root: $RepoRoot" }
if (-not (Test-Path $SourcePool)) { throw "missing source pool: $SourcePool" }
if (-not (Test-Path $SignalVectorRoot)) { throw "missing signal vector root: $SignalVectorRoot" }
if (-not (Test-Path $LocalRemoteScript)) { throw "missing remote script: $LocalRemoteScript" }

New-Item -ItemType Directory -Force -Path (Split-Path $Archive -Parent) | Out-Null
git -C $RepoRoot archive --format=zip --output=$Archive HEAD
if (Test-Path $SignalVectorArchive) {
  Remove-Item -Force $SignalVectorArchive
}
Compress-Archive -Path (Join-Path $SignalVectorRoot "*") -DestinationPath $SignalVectorArchive -Force

powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $Archive -RemotePath $RemoteArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $SignalVectorArchive -RemotePath $RemoteSignalVectorArchive
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $SourcePool -RemotePath $RemoteSourcePool
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action upload -LocalPath $LocalRemoteScript -RemotePath $RemoteScript
powershell -ExecutionPolicy Bypass -File $RemoteTool -Action start-detached -DetachedCommand "powershell -ExecutionPolicy Bypass -File D:\HermesWorker\runtime\cn_integrated_factor_pack_remote_company_selector.ps1"
