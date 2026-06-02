param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot

$assetPlanPath = Join-Path $repoRoot "runtime\manifests\cn_data_feature_workspace_git_asset_plan_20260601.json"
if (-not (Test-Path -LiteralPath $assetPlanPath)) {
    throw "Missing asset plan: $assetPlanPath"
}

$assetPlan = Get-Content -LiteralPath $assetPlanPath -Raw | ConvertFrom-Json
$paths = @()
$paths += @($assetPlan.stage_code)
$paths += @($assetPlan.stage_decision_reports)
$paths += @($assetPlan.stage_metadata)
$paths = $paths | Where-Object { $_ } | Select-Object -Unique

$missing = @()
foreach ($path in $paths) {
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot $path))) {
        $missing += $path
    }
}

Write-Host "CN data feature workspace staging plan"
Write-Host "repo: $repoRoot"
Write-Host "paths: $($paths.Count)"
Write-Host "missing: $($missing.Count)"
Write-Host "execute: $Execute"

if ($missing.Count -gt 0) {
    Write-Host "Missing paths:"
    $missing | ForEach-Object { Write-Host "  $_" }
    throw "Refusing to stage because whitelist contains missing paths."
}

Write-Host ""
Write-Host "Whitelist:"
$paths | ForEach-Object { Write-Host "  $_" }

if (-not $Execute) {
    Write-Host ""
    Write-Host "Dry run only. Re-run with -Execute to call git add for these exact paths."
    exit 0
}

$chunkSize = 40
for ($i = 0; $i -lt $paths.Count; $i += $chunkSize) {
    $chunk = $paths[$i..([Math]::Min($i + $chunkSize - 1, $paths.Count - 1))]
    git add -- @chunk
}

Write-Host ""
Write-Host "Staged exact whitelist paths. Review with: git diff --cached --stat"

