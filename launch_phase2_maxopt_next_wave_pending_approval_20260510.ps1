param(
    [switch]$Approved,
    [ValidateSet("unreached_first", "forward_first", "both_sequential")]
    [string]$RunMode = "forward_first"
)

$ErrorActionPreference = "Stop"

$RepoRoot = "G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo"
$PythonExe = "G:\PythonProject\.venv\Scripts\python.exe"
$DatasetPath = "G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$ArtifactRoot = "runtime\next_stage_artifacts"

$UnreachedRoot = Join-Path $ArtifactRoot "phase2-nextwave-unreached-maxopt-fast-context-20260510-max4"
$ForwardRoot = Join-Path $ArtifactRoot "phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3"
$PreviousRoot = Join-Path $ArtifactRoot "phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4"
$PreflightReport = Join-Path $ArtifactRoot "phase2-nextwave-maxopt-chain-audit-20260510.json"
$UnreachedLog = Join-Path $ArtifactRoot "phase2-nextwave-unreached-maxopt-fast-context-20260510-max4.supervisor.log"
$ForwardLog = Join-Path $ArtifactRoot "phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3.supervisor.log"
$UnreachedPolicyState = Join-Path $UnreachedRoot "stock_pit_policy_state.json"
$ForwardPolicyState = Join-Path $ForwardRoot "stock_pit_policy_state.json"

function Quote-CommandArg {
    param([string]$Value)
    if ($Value -match "[\s'`"&|<>]") {
        return "'" + $Value.Replace("'", "''") + "'"
    }
    return $Value
}

function Join-CommandLine {
    param(
        [string]$Exe,
        [string[]]$ArgList
    )
    $parts = @((Quote-CommandArg $Exe))
    $parts += @($ArgList | ForEach-Object { Quote-CommandArg $_ })
    return ($parts -join " ")
}

$UnreachedArgs = @(
    "-m", "our_system_phase2.runtime.stock_pit_unreached_search_supervisor",
    "--launch-root", $UnreachedRoot,
    "--shard-count", "128",
    "--start-shard", "0",
    "--end-shard", "127",
    "--max-active", "4",
    "--dataset-path", $DatasetPath,
    "--target-window-count", "24",
    "--max-window", "126",
    "--top-bottom-quantile", "0.02",
    "--recent-quarter-window-count", "2",
    "--recent-warmup-days", "60",
    "--parallel-workers", "1",
    "--previous-search-root", $PreviousRoot,
    "--max-family-share", "0.12",
    "--reward-control-root", $PreviousRoot,
    "--reward-exploration-share", "0.30",
    "--policy-state-path", $UnreachedPolicyState,
    "--poll-seconds", "30",
    "--use-fast-context"
)

$ForwardArgs = @(
    "-m", "our_system_phase2.runtime.stock_pit_large_search_supervisor",
    "--launch-root", $ForwardRoot,
    "--shard-count", "64",
    "--start-shard", "0",
    "--end-shard", "64",
    "--max-active", "3",
    "--dataset-path", $DatasetPath,
    "--candidates-per-shard", "512",
    "--target-window-count", "24",
    "--max-window", "126",
    "--top-bottom-quantile", "0.02",
    "--recent-quarter-window-count", "2",
    "--recent-warmup-days", "60",
    "--parallel-workers", "1",
    "--previous-search-root", $PreviousRoot,
    "--max-family-share", "0.12",
    "--reward-control-root", $PreviousRoot,
    "--reward-exploration-share", "0.30",
    "--policy-state-path", $ForwardPolicyState,
    "--generator-mode", "rx_typed_beam",
    "--beam-width", "96",
    "--max-beam-records", "8192",
    "--use-successive-halving",
    "--halving-survivor-fraction", "0.35",
    "--halving-min-survivors", "96",
    "--poll-seconds", "30",
    "--use-fast-context"
)

$UnreachedCommand = Join-CommandLine -Exe $PythonExe -ArgList $UnreachedArgs
$ForwardCommand = Join-CommandLine -Exe $PythonExe -ArgList $ForwardArgs

Write-Host "Phase2 maxopt next wave is prepared but not launched by default."
Write-Host "Run mode: $RunMode"
Write-Host ""
Write-Host "Primary RX typed-beam maxopt command:"
Write-Host $ForwardCommand
Write-Host "Log: $ForwardLog"
Write-Host ""
Write-Host "Secondary unreached-space command:"
Write-Host $UnreachedCommand
Write-Host "Log: $UnreachedLog"
Write-Host ""
Write-Host "Status files after launch:"
Write-Host "  $UnreachedRoot\supervisor_status.json"
Write-Host "  $ForwardRoot\supervisor_status.json"
Write-Host "Policy-state files after launch:"
Write-Host "  $UnreachedPolicyState"
Write-Host "  $ForwardPolicyState"
Write-Host "Preflight audit after approved launch:"
Write-Host "  $PreflightReport"
Write-Host ""

if (-not $Approved) {
    Write-Host "Dry run only. Re-run with -Approved after explicit user approval."
    exit 0
}

Set-Location $RepoRoot
$env:PYTHONPATH = "src"
New-Item -ItemType Directory -Force -Path $ArtifactRoot | Out-Null

$GeneratorKind = if ($RunMode -eq "unreached_first") { "stock_pit_unreached" } else { "stock_pit_forward_first" }
& $PythonExe -m our_system_phase2.runtime.stock_pit_chain_audit `
    --dataset-path $DatasetPath `
    --previous-search-root $PreviousRoot `
    --signal-clock "after_open" `
    --execution-lag-days 1 `
    --horizon-days 1 `
    --feature-lag-days 0 `
    --top-bottom-quantile 0.02 `
    --recent-quarter-window-count 2 `
    --recent-warmup-days 60 `
    --use-fast-context `
    --parallel-workers 1 `
    --max-active-workers 4 `
    --max-family-share 0.12 `
    --generator-kind $GeneratorKind `
    --output $PreflightReport `
    --fail-on-hard-blockers

if ($RunMode -eq "unreached_first") {
    $BackgroundCommand = "Set-Location '$RepoRoot'; `$env:PYTHONPATH='src'; $UnreachedCommand *> '$UnreachedLog'"
} elseif ($RunMode -eq "forward_first") {
    $BackgroundCommand = "Set-Location '$RepoRoot'; `$env:PYTHONPATH='src'; $ForwardCommand *> '$ForwardLog'"
} else {
    $BackgroundCommand = "Set-Location '$RepoRoot'; `$env:PYTHONPATH='src'; $ForwardCommand *> '$ForwardLog'; if (`$LASTEXITCODE -eq 0) { $UnreachedCommand *> '$UnreachedLog' } else { exit `$LASTEXITCODE }"
}

$Process = Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -PassThru -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $BackgroundCommand
)

Write-Host "Launched background supervisor PID: $($Process.Id)"
