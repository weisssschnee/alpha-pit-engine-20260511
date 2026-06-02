param(
    [string]$Workspace = "D:\HermesWorker\workspace\cn_zzshare_limit_sentiment_join_20260602",
    [string]$RuntimeRoot = "D:\HermesWorker\runtime\cn_integrated_factor_pack_v2_selector_preflight_20260602",
    [string]$Python = "D:\Python311\python.exe"
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "src"
$pool = Join-Path $RuntimeRoot "shared_candidate_pool_integrated_v2_enriched.json"
$outputRoot = Join-Path $RuntimeRoot "selector_only"
$stdout = Join-Path $RuntimeRoot "selector_stdout.log"
$stderr = Join-Path $RuntimeRoot "selector_stderr.log"

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

$argsList = @(
    "-m", "our_system_phase2.runtime.phase3aa_apply_mature_g2_selector",
    "--pool", $pool,
    "--output-root", $outputRoot,
    "--dataset-path", "D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_selected_v1.parquet",
    "--signal-vector-npz", "D:\HermesWorker\data\phase3g_signal_vectors\phase3g_signal_vectors_20260514.npz",
    "--signal-vector-metadata", "D:\HermesWorker\data\phase3g_signal_vectors\vector_metadata.parquet",
    "--signal-runtime-cache-dir", "D:\HermesWorker\runtime\phase3g_signal_vectors\runtime_eval_cache_integrated_v2",
    "--total-budget", "64",
    "--event-share", "0.40",
    "--research-share", "0.30",
    "--pool-cap", "320",
    "--signal-sample-size", "3000",
    "--signal-warmup-days", "60",
    "--seed", "integrated_v2_seed33"
)

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList $argsList `
    -WorkingDirectory $Workspace `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -WindowStyle Hidden `
    -PassThru

$pidPath = Join-Path $RuntimeRoot "selector_pid.txt"
$process.Id | Out-File -Encoding ascii -FilePath $pidPath
Write-Output ("started_pid=" + $process.Id)
Write-Output ("runtime_root=" + $RuntimeRoot)
