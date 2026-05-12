# Phase3 Ablation Fresh Run

- date: 2026-05-11
- experiment_id: `20260511_phase3_ablation_fresh`
- objective: isolate whether Phase3A lift comes from cluster quota, AST repair, their interaction, or residual/diagnostic slices.
- status: running
- decision: HOLD_RESEARCH until all run roots have `phase3_repair_report.json` and global aggregate is recomputed across all arms plus Phase2 R0 baseline.

## Arms

| arm | meaning |
| --- | --- |
| `original_R0` | R0/CEM-led baseline, no cluster quota, no AST repair |
| `R0_cluster_quota_only` | R0/CEM-led with cluster quota only |
| `R0_AST_repair_only` | R0 plus AST repair, no cluster quota |
| `R0_cluster_quota_AST_repair_only` | R0 plus cluster quota plus AST repair, no residual/diagnostic |
| `Phase3A_full` | cluster quota + AST repair + replay-aware residual + novelty diagnostic |

## Fixed Controls

- evaluator: TDXGP true-limit preferred
- clock: after_open + T+1
- dataset: `phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- cost: 10 bps
- top/bottom quantile: 0.02
- audited per run: 64
- candidate budget per run: 64
- seeds: 5, 6, 7, 8
- hard gate: no run enters formal stats without `phase3_repair_report.json`
- cluster rule: final report must globally recluster across all arms + Phase2 R0 baseline
- primary KPI: deployable global unique clusters / audited
- raw non-gap pass: diagnostic only

## Machine Allocation

| machine | seeds | output root |
| --- | --- | --- |
| company `DESKTOP-7877972` | 5, 6 | `D:\HermesWorker\runtime\phase3-ablation-fresh-20260511-company` |
| local `DESKTOP-SR4PA0E` | 7, 8 | `runtime\next_stage_artifacts\phase3-ablation-fresh-20260511-local` |

## Commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\schedule_phase3_ablation_local_20260511.ps1
ssh -F G:\Chengbo\company-pc-ssh-config.example company-pc-via-hermes-portable "powershell -NoProfile -ExecutionPolicy Bypass -File D:\HermesWorker\workspace\our_system_phase1_repo\schedule_phase3_ablation_company_20260511.ps1"
```

## Output Manifests

- local status: `runtime\next_stage_artifacts\phase3-ablation-fresh-20260511-local\ablation_status.jsonl`
- company status: `D:\HermesWorker\runtime\phase3-ablation-fresh-20260511-company\ablation_status.jsonl`
- preflight: `runtime\next_stage_artifacts\phase3-ablation-preflight-20260511-v2`

## Required Aggregate

After all 20 formal runs complete:

1. copy company run roots to local
2. run `stock_pit_phase3_aggregate.py` with all 20 seed roots and `reports\PHASE3_REPAIR_AUDIT_2026-05-11_pass_clusters.csv`
3. inspect `per_arm_metrics`, `arm_overlap_matrix`, `ast_repair_transition`, `denominator_audit`
4. decide whether B, C, D, or E explains the Phase3A lift

## Bias Audit

- discovery status: ablation/reproduction of search mechanism, not commercial alpha promotion
- OOS grade: weak recent PIT panel only
- blocking issue: not a commercial-grade proof until ablation aggregate, capacity/sector/style exposure, and longer independent OOS checks are complete
