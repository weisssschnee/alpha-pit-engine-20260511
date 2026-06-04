$ErrorActionPreference = "Stop"

$Script = "G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\scripts\phase3ai_local_overnight_worker_20260605.ps1"
$LogDir = "G:\Project_V7_Rotation\runtime\phase3ai_overnight_local_20260605_r3"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "local_overnight_launcher.log"
$StatusPath = Join-Path $LogDir "local_overnight_launcher_status.json"

$launcher = @"
`$ErrorActionPreference = 'Stop'
`$start = Get-Date
"BEGIN `$(`$start.ToString('s'))" | Out-File -FilePath '$LogPath' -Append -Encoding utf8
`$exitCode = 0
try {
  powershell -NoProfile -ExecutionPolicy Bypass -File '$Script' *>> '$LogPath'
  `$exitCode = `$LASTEXITCODE
} catch {
  `$exitCode = 1
  "EXCEPTION: `$(`$_.Exception.Message)" | Out-File -FilePath '$LogPath' -Append -Encoding utf8
}
`$end = Get-Date
@{
  started_at = `$start.ToString('s')
  ended_at = `$end.ToString('s')
  exit_code = `$exitCode
  log = '$LogPath'
} | ConvertTo-Json -Depth 3 | Set-Content -Path '$StatusPath' -Encoding UTF8
"END code=`$exitCode `$(`$end.ToString('s'))" | Out-File -FilePath '$LogPath' -Append -Encoding utf8
"@

$LaunchScript = Join-Path $LogDir "launch_local_overnight.ps1"
Set-Content -LiteralPath $LaunchScript -Value $launcher -Encoding UTF8
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",$LaunchScript) -WindowStyle Hidden
Write-Output "LOCAL_OVERNIGHT_STARTED"
Write-Output "LOG=$LogPath"
Write-Output "STATUS=$StatusPath"
