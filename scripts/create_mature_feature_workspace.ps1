param(
    [string]$WorkspaceRoot = "G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528",
    [string]$BranchName = "feature/mature-chain-adapter-20260528",
    [string]$BaseRef = "origin/main",
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptPath "..")
$WorkspaceParent = Split-Path -Parent $WorkspaceRoot

if (-not (Test-Path $WorkspaceParent)) {
    New-Item -ItemType Directory -Path $WorkspaceParent | Out-Null
}

if (Test-Path $WorkspaceRoot) {
    throw "Workspace already exists: $WorkspaceRoot"
}

git -C $RepoRoot fetch origin
git -C $RepoRoot worktree add -b $BranchName $WorkspaceRoot $BaseRef

$State = [ordered]@{
    workspace_root = $WorkspaceRoot
    branch = $BranchName
    base_ref = $BaseRef
    created_at = (Get-Date).ToString("o")
    policy = "feature adapters must reuse app.py and phase3_algorithm_chain_lock_v1"
}

$StatePath = Join-Path $WorkspaceRoot "runtime\local_workspace_state.json"
$State | ConvertTo-Json -Depth 4 | Set-Content -Path $StatePath -Encoding UTF8

if (-not $SkipSmoke) {
    $Python = "G:\PythonProject\.venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        $Python = "python"
    }
    Push-Location $WorkspaceRoot
    try {
        & $Python app.py status
    }
    finally {
        Pop-Location
    }
}

Write-Host "Created mature feature workspace: $WorkspaceRoot"

