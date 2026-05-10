# Phase2 Maxopt Next-Wave Search Flow - 2026-05-10

## Experiment Record

- date: 2026-05-10
- experiment_id: `20260510_maxopt_rxbeam_nextwave_001`
- objective: launch the next large discovery wave on the fixed stock-level `maxopt` panel, using capacity-aware RX typed-beam generation, reward-memory routing, duplicate memory, A-share tradability filters, and successive halving.
- status: prepared, not launched
- mode: heavy discovery
- decision: `HOLD_RESEARCH` until candidates pass strict audit and portfolio replay

## Inputs

- main panel:
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
  - size: `116.56MB`
  - rows: `1,090,783`
  - symbols: `6,333`
  - dates: `2025-08-06` to `2026-05-08`
  - role: `stock_pit_panel`
- quality report:
  `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt_report.json`
- previous reward/search-memory root:
  `runtime\next_stage_artifacts\phase2-ashare-v2-fast-context-local-continue-20260508-from108-max4`
- chain audit smoke:
  `runtime\next_stage_artifacts\phase2-nextwave-maxopt-chain-audit-20260510-smoke.json`
- maxopt upgrade note:
  `reports\PHASE2_MAXOPT_REWARD_GENERATOR_UPGRADE_2026-05-10.md`

## Current Searcher Flow

1. Preflight chain audit
   - verifies stock-PIT dataset role
   - verifies required OHLCV and tradability columns
   - verifies `after_open` signal clock, T+1 execution, horizon 1
   - verifies fast-context eligibility
   - verifies previous-root search memory can be indexed
2. Policy state build
   - reads previous stock-PIT validation reports
   - quarantines wrong dataset roles
   - builds UCB reward memory over family, role, motif, field, operator, window, skeleton, and regime gate
3. Generator
   - primary: `rx_typed_beam`
   - opens price/open/limit/trend/liquidity/capacity interactions
   - uses only canonical capacity fields per semantic family:
     - `float_cap -> final_float_market_cap`
     - `total_cap -> final_total_market_cap`
   - redundant same-source cap fields are diagnostics only, not formula fuel
4. Scheduling and memory
   - exact expression duplicate filter against previous root
   - family cap: `0.12`
   - reward routing: UCB with exploration
   - not a commercial edge claim and not full online RL
5. Validation
   - `after_open`
   - full-day fields, including cap/share fields, lagged by evaluator
   - T+1 entry, T+2 close-to-close horizon 1
   - entry limit-up blocks long buys
   - entry limit-down blocks short sells
   - suspension filters active
   - top/bottom quantile: `0.02`
6. Successive halving
   - stage0 cheap validation
   - survivor fraction: `0.35`
   - minimum survivors: `96`
   - stage1 validates survivors with the same trading contract
7. Output use
   - stage1 reports can feed the factor-library optimizer and strict audit queue
   - no result is promotion-grade until strict audit, replay, cost/capacity checks, and forward shadow

## Primary Launch Command

Dry run:

```powershell
.\launch_phase2_maxopt_next_wave_pending_approval_20260510.ps1
```

Approved primary RX typed-beam launch:

```powershell
.\launch_phase2_maxopt_next_wave_pending_approval_20260510.ps1 -Approved -RunMode forward_first
```

Approved broader sequential launch:

```powershell
.\launch_phase2_maxopt_next_wave_pending_approval_20260510.ps1 -Approved -RunMode both_sequential
```

## Primary RX Typed-Beam Parameters

- root:
  `runtime\next_stage_artifacts\phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3`
- shard count: `64`
- active workers: `3`
- candidates per shard: `512`
- generator mode: `rx_typed_beam`
- beam width: `96`
- max beam records: `8192`
- target window count: `24`
- max window: `126`
- recent quarter windows: `2`
- recent warmup days: `60`
- parallel workers per shard: `1`
- use fast context: `true`
- previous-search root: current clean stock-PIT root
- reward-control root: current clean stock-PIT root
- reward exploration share: `0.30`
- family cap: `0.12`
- successive halving: enabled

## Secondary Unreached Parameters

- root:
  `runtime\next_stage_artifacts\phase2-nextwave-unreached-maxopt-fast-context-20260510-max4`
- shard count: `128`
- active workers: `4`
- target window count: `24`
- max window: `126`
- same dataset, memory, reward, validation, and family cap contract

## Expected Results

This wave is successful if it produces at least one of:

- a non-limit-pressure family with `IC >= 0.045` and long Sortino or spread Sortino competitive with current leaders
- a cap-normalized/liquidity-normalized family that survives tradability and capacity diagnostics
- evidence that the current winner family remains dominant even after opening size/capacity space
- a clean reject signal showing that the next improvement should be data enrichment or portfolio construction rather than more formula enumeration

## Cost and Time

- estimated runtime: hours to overnight on local machine depending on memory pressure
- expected bottleneck: rolling/groupby expression evaluation, not preflight or replay
- GPU: not used by current expression evaluator
- memory: do not maximize workers blindly; paging hurts throughput and can corrupt timing assumptions

## Reproducibility

- reproducible: partial
- reproducible because:
  - inputs are fixed local files
  - command-line parameters are fixed
  - roots and logs are fixed
  - policy state is persisted under each root
- partial because:
  - previous-root reward memory can change if that root is modified
  - process scheduling can alter wall-clock timing
  - future appended data would change the panel

## Continuation

After launch, inspect:

- `runtime\next_stage_artifacts\phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3\supervisor_status.json`
- `runtime\next_stage_artifacts\phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3\stock_pit_policy_state.json`
- worker `stage1_validation_report.json` files
- `runtime\next_stage_artifacts\phase2-nextwave-rxbeam-maxopt-fast-context-20260510-max3.supervisor.log`

Do not mix old validation-slice outputs with maxopt outputs without labeling the dataset lineage.
