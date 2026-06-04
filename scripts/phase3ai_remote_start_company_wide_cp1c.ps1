$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3ai_wide_cp1c_source_20260604.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3ai_wide_cp1c_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$LaunchRoot = "D:\p3ai\wide_cp1c_20260604"
$JobId = "phase3ai_wide_cp1c_20260604_company"

if (-not (Test-Path $Archive)) { throw "missing archive: $Archive" }
if (-not (Test-Path $Python)) { throw "missing python: $Python" }
if (-not (Test-Path $DatasetPath)) { throw "missing dataset: $DatasetPath" }

if (Test-Path $RepoRoot) {
  Remove-Item -Recurse -Force $RepoRoot
}
New-Item -ItemType Directory -Force -Path $RepoRoot | Out-Null
Expand-Archive -Path $Archive -DestinationPath $RepoRoot -Force

Set-Location $RepoRoot
$env:PYTHONPATH = "src"
$env:NUMEXPR_MAX_THREADS = "8"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

# CP1/CP1b proved rx_typed_beam produced about 2k candidates in this slice.
# Sharding must use a smaller per-shard stride; otherwise every shard after
# shard0 is empty. CP1c covers the full slice as 8 x 256 checkpoint shards.
$argsList = @(
  "-m", "our_system_phase2.runtime.phase3ab_launch_large_search",
  "--repo-root", $RepoRoot,
  "--launch-root", $LaunchRoot,
  "--job-id", $JobId,
  "--machine", "company",
  "--dataset-path", $DatasetPath,
  "--memory-base", (Join-Path $RepoRoot "reports"),
  "--memory-base", "D:\HermesWorker\workspace\our_system_phase1_repo\reports",
  "--memory-base", "D:\p3aa",
  "--memory-base", "D:\p3ab",
  "--shard-count", "8",
  "--max-active", "4",
  "--candidates-per-shard", "256",
  "--target-window-count", "20",
  "--max-window", "126",
  "--top-bottom-quantile", "0.02",
  "--recent-quarter-window-count", "2",
  "--recent-warmup-days", "60",
  "--parallel-workers", "1",
  "--previous-root-limit", "80",
  "--reward-root-limit", "40",
  "--max-family-share", "0.25",
  "--reward-exploration-share", "0.80",
  "--generator-mode", "rx_typed_beam",
  "--beam-width", "192",
  "--max-beam-records", "32768",
  "--use-successive-halving",
  "--halving-survivor-fraction", "0.35",
  "--halving-min-survivors", "64",
  "--poll-seconds", "20"
)

& $Python @argsList
