# Phase2 Stock-Only P0/P3 Rerun

## Experiment Record

- date: 2026-05-10
- experiment_id: phase2-stock-pit-p0-p3-proof-company-stockonly-rerun-20260510
- objective: rerun P0/P1/P2/P3 proof after excluding non-stock rows from the maxopt panel.
- status: completed
- mode: research

### Inputs

- data: `D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- local mirror: `G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- data identity after stock-only loader: 990549 rows, 5775 codes, 5490 codes on 2026-05-08, 0 bad prefixes among `880/sh000/sz399/bj899`.
- previous search roots:
  - `D:\HermesWorker\runtime\company-v2-fast-context-full-search-20260508-max3-gated`
  - `D:\HermesWorker\runtime\company-v2-tail-search-20260508-shards128-256`

### Parameters

- universe: A-share stock-only rows; `instrument_type == stock`; excludes `880*`, `sh000*`, `sz399*`, `bj899*`.
- signal clock: after_open
- execution: signal T, execute T+1, exit T+2 close-to-close
- candidate_budget: 128 per P0 variant
- target_window_count: 6
- max_window: 34
- beam_width: 24
- max_beam_records: 512
- strict_top_n_per_variant: 5
- random_pass_through_n_per_variant: 2
- strict_decile_sample_per_bucket: 2
- top_bottom_quantile: 0.02
- strict_cost_bps: 10

### Commands

```text
powershell -NoProfile -ExecutionPolicy Bypass -File D:\HermesWorker\workspace\our_system_phase1_repo\schedule_company_stockonly_proof_20260510.ps1
```

### Outputs

- root: `D:\HermesWorker\runtime\phase2-stock-pit-p0-p3-proof-company-stockonly-rerun-20260510`
- runner: `D:\HermesWorker\workspace\our_system_phase1_repo\company_run_stockonly_proof_20260510.py`
- status: `runner_status.json`
- expected final report: `p0_p3_proof_report.json`

### Current Notes

- Old `phase2-stock-pit-p0-p3-proof-company-medium5-decilefix-20260510` is now treated as pre-filter evidence, not promotion evidence.
- Tiny stock-only smoke completed successfully before this rerun.
- Company PC scheduled task `phase2_stockonly_proof_20260510` completed with result `0`.

### Result Status Correction

This run is now classified as `PRE_LIMIT_FILTER_FIX_EVIDENCE`.

After completion, a validation bug was found: `is_limit_up/is_limit_down` columns existed in the maxopt panel but were all null. The old validator treated the all-null columns as active sources and did not fall back to `rt_change_pct`, so entry limit-up/down filters did not actually exclude untradable rows.

The formulas and search directions remain useful as candidate discovery records, but the run's reward, strict-pass, replay-pass, and A/B conclusions are not promotion evidence.

### Pre-Fix Results Snapshot

- decision: `PASS_RESEARCH_PROOF_HARNESS_CREATED_NOT_COMMERCIAL_PROOF`
- commercial_claim_allowed: false
- UCB wins strict: false
- no-policy beats simple and typed-random strict: false
- stage1 joint-strong count: 0 for all variants.

P0/P3 strict summary:

| variant | strict pass | low-corr strict | replay pass | cost survival | family entropy | cluster entropy |
|---|---:|---:|---:|---:|---:|---:|
| rx_typed_beam_ucb | 4/7 | 2 | 0/7 | 0.714 | 0.796 | 0.796 |
| rx_typed_beam_no_policy | 5/7 | 1 | 2/7 | 0.857 | 1.748 | 0.796 |
| typed_random | 5/7 | 1 | 1/7 | 0.714 | 1.748 | 0.796 |
| unreached_space_only | 5/7 | 2 | 0/7 | 0.714 | 1.946 | 1.154 |
| simple_template_baseline | 3/7 | 3 | 1/7 | 0.857 | 1.277 | 1.475 |

P1 fast-to-strict calibration:

- Deciles 1-7: strict pass 0/14.
- Deciles 8-10: strict pass 3/6.
- Cost survival rises from 0 in low deciles to 1.0 in deciles 7-10.
- Portfolio replay pass remains weak in decile calibration.

P2 cluster health:

- cluster_count: 15
- signal_cluster_entropy: 2.070669
- dominant cluster: `cluster_001`, 15/35 strict-audited rows, budget share 0.429.
- `cluster_001` representative is open-gap residualized by cap; strict pass 15/15, replay contribution 3/15.

Notable strict/replay candidates:

- `CSRank($close)` has low turnover and strongest simple replay: long-only net mean 0.002186, long-only Sortino 1.575, one-way turnover 0.030.
- Open-gap residuals survive strict and sometimes replay, but turnover is high, roughly 0.83-0.90 one-way. Replay long-only Sortino is mostly 0.35-0.60, not commercial proof.

### Interpretation

- Stock-only filter did not kill the gap family, so opengap was not purely caused by sector-panel misuse.
- The current UCB memory is not proven useful under stock-only validation; it underperformed no-policy and did not produce replay pass.
- The current search still collapses into gap/trend clusters; strict pass alone is too permissive. Portfolio replay and cluster caps need to drive the next search.
- Old pre-filter medium5 is not valid promotion evidence; the stock-only rerun is the current baseline.

### Decision

HOLD_RESEARCH until the stock-only P0/P1/P2/P3 report completes and is compared with the pre-filter medium5 result.

Current decision: HOLD_RESEARCH. Next action is to rerun stock-only P0/P1/P2/P3 after the active `rt_change_pct` limit fallback fix. Search-space memory can be kept, but reward memory and proof conclusions from this run must be tagged `pre_limit_filter_fix`.
