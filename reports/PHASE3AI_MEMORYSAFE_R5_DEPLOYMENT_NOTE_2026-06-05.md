# Phase3AI Memory-Safe R5 Deployment Note - 2026-06-05

## Decision

`DEPLOY_PHASE3AI_R5_MEMORYSAFE_DUAL_MACHINE`

R4 is retained as partial research output only. R4 is not a clean large-search conclusion because the company-machine main leg hit Windows commit/pagefile pressure.

## Root Cause

The company machine has more physical RAM than the local machine, but a much smaller virtual-memory/commit cushion.

| machine | physical visible | total virtual | pagefile | observed issue |
| --- | ---: | ---: | ---: | --- |
| local | 23.42 GB | 142.01 GB | 118.59 GB | tolerated larger pandas spikes |
| company | 31.59 GB | 62.84 GB | 31.25 GB | pagefile peak hit 31.25 GB; pandas ArrayMemoryError |

R4 company `c4_forward_fresh_main` failed 65 / 96 shards. Sample stderr showed `numpy._core._exceptions._ArrayMemoryError` in pandas/numpy allocations, including 63 MB to 349 MB arrays. This is commit-limit/fragmentation pressure, not evidence that the formula/search logic is invalid.

## R4 Recoverable Output

Company R4:

- `c4_forward_fresh_canary`: 88 eval, 0 failed.
- `c4_forward_fresh_main`: 1,984 eval from 31 completed shards, 65 failed shards.
- `c5_rx_orthogonal_canary`: entered canary before R4 was stopped.

Local R4:

- `l1_forward_broad_canary`: 4 / 4 shards completed.
- total validation eval: 192.
- best shard Sortino range: 3.60 to 4.60.
- launcher interrupted before main; local R4 is canary-only.

## R5 Launch Contract

R5 reduces peak memory while keeping the mature search path:

- `phase3ab_launch_large_search`
- `stock_pit_large_search_supervisor`
- `--use-fast-context`
- `--use-successive-halving`
- search-memory roots including reports and R4 partial output
- no replay/deployable/final-cluster labels in selection

Company R5:

- run root: `D:\p3ai\overnight_company_20260605_r5_memorysafe`
- deadline: about 8.25 hours from launch
- main max active workers: 2
- canary max active workers: 1
- legs:
  - `c4_forward_fresh_ms`
  - `c5_rx_orthogonal_ms`
  - `c6_forward_lowcap_ms`
  - `c7_rx_extended_ms`

Local R5:

- run root: `G:\Project_V7_Rotation\runtime\phase3ai_overnight_local_20260605_r5_memorysafe`
- deadline: about 8.25 hours from launch
- main max active workers: 2
- canary max active workers: 1
- legs:
  - `l1_forward_fresh_ms`
  - `l2_rx_orthogonal_ms`
  - `l3_forward_extended_ms`

## Current Status At Deployment

- company R5 started at `2026-06-05T09:40:17`, first canary running.
- local R5 started at `2026-06-05T09:42:49`, first canary running.
- source commit: `0874e73`
- bundle backup: `G:\Project_V7_Rotation\backups\phase3ai_memorysafe_r5_0874e73.bundle`

## Next Check

Check after 60-90 minutes:

- company `overnight_status.jsonl`
- local `overnight_status.jsonl`
- failed shard count
- pagefile peak and free virtual memory
- canary pass-to-main behavior

