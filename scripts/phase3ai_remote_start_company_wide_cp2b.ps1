$ErrorActionPreference = "Stop"

$Archive = "D:\HermesWorker\runtime\phase3ai_wide_cp2b_source_20260604.zip"
$RepoRoot = "D:\HermesWorker\workspace\phase3ai_wide_cp2b_current"
$Python = "D:\HermesWorker\workspace\.venv\Scripts\python.exe"
$DatasetPath = "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"
$LaunchRoot = "D:\p3ai\wide_cp2b_20260604"
$JobId = "phase3ai_wide_cp2b_20260604_company"

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

# CP2b is the orthogonal checkpoint after CP2a reconfirmed one dominant
# open-gap x volatility family. It tightens per-family budget and adds CP1c/CP2a
# as memory so the next search budget is spent on adjacent/non-dominant space.
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
  "--memory-base", "D:\p3ai\wide_cp1c_20260604",
  "--memory-base", "D:\p3ai\wide_cp2a_20260604",
  "--shard-count", "24",
  "--max-active", "4",
  "--candidates-per-shard", "128",
  "--target-window-count", "48",
  "--max-window", "126",
  "--top-bottom-quantile", "0.02",
  "--recent-quarter-window-count", "2",
  "--recent-warmup-days", "60",
  "--parallel-workers", "1",
  "--previous-root-limit", "160",
  "--reward-root-limit", "80",
  "--max-family-share", "0.02",
  "--reward-exploration-share", "0.80",
  "--generator-mode", "rx_typed_beam",
  "--beam-width", "512",
  "--max-beam-records", "98304",
  "--use-successive-halving",
  "--halving-survivor-fraction", "0.40",
  "--halving-min-survivors", "48",
  "--poll-seconds", "20"
)

& $Python @argsList
