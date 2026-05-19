$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$LogDir = Join-Path $Root "runtime\a6_6_core4_append_only_shadow_snapshot\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "core4_shadow_snapshot_$Stamp.log"

"BEGIN $(Get-Date -Format o)" | Tee-Object -FilePath $LogPath
"SCRIPT $ScriptDir\crypto_a6_6_core4_append_only_shadow_snapshot.py" | Tee-Object -FilePath $LogPath -Append

py -3 "$ScriptDir\crypto_a6_6_core4_append_only_shadow_snapshot.py" 2>&1 | Tee-Object -FilePath $LogPath -Append
$ExitCode = $LASTEXITCODE

"END $(Get-Date -Format o) exit_code=$ExitCode" | Tee-Object -FilePath $LogPath -Append
exit $ExitCode
