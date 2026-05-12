# Phase3B Repair-Aware Quota Flow

Date: 2026-05-12

## Objective

Validate whether quota can reduce cluster collapse without suppressing AST repair.

Primary KPI:

- cost/turnover deployable global unique clusters per audited

Secondary KPI:

- top cluster share
- AST repair new deployable clusters vs original R0
- repair child escape quality
- raw non-gap replay pass as diagnostic only

## Fixed Contract

- evaluator: TDXGP true-limit preferred
- signal clock: after_open
- execution lag: T+1
- cost: 10 bps
- top/bottom quantile: 0.02
- reward: current R0 true-limit, unchanged for selection baseline
- commercial claim: not allowed from this experiment alone

## Arms

| arm | purpose |
|---|---|
| Phase3B_B0_incumbent_best | Current strongest control: R0 + AST repair only |
| Phase3B_B1_phase3A_full | Existing Phase3A full hard-quota interaction |
| Phase3B_B2_direct_R0_quota_only | Direct R0 quota, repair selected without parent quota |
| Phase3B_B3_repair_aware_soft_quota | Direct R0 quota plus child-side repair-aware soft quota |

## Budgets

For 64 audited rows per arm/seed:

| arm | R0 direct | AST repair | replay-aware residual | novelty diagnostic |
|---|---:|---:|---:|---:|
| B0 | 51 | 13 | 0 | 0 |
| B1 | 38 | 13 | 6 | 7 |
| B2 | 32 | 26 | 3 | 3 |
| B3 | 32 | 26 | 3 | 3 |

## Phase3B Quota Changes

- Direct R0 quota only affects direct replay candidates.
- Direct R0 quota rejects are logged and marked as eligible repair sources.
- Repair quota is applied after mutation, on child candidates.
- B3 uses parent soft cap plus provisional child cluster soft cap.
- Every quota event is written to `phase3_quota_events.json`.

Required quota fields:

- quota_applied
- quota_type
- quota_stage
- quota_basis
- rejected_by_quota
- quota_reject_reason
- parent_cluster
- provisional_child_cluster
- final_child_cluster
- corr_to_parent
- corr_to_existing_deployable
- escaped_parent_cluster
- repair_policy
- source_failure_reason
- operator_pathology_before
- operator_pathology_after

## Success Criteria

Minimum pass:

- deployable clusters >= 20 / 256
- top cluster share <= 40%
- AST repair new deployable clusters vs original_R0 >= 8

Strong pass:

- deployable clusters >= 22 / 256
- top cluster share <= 38%
- raw non-gap pass >= 95 / 256
- repair child escape rate >= 85%
- repair child deployable cluster contribution >= 10

Fail:

- deployable clusters < 18
- or top cluster share > 45%
- or repair candidates are mostly rejected before child-side evaluation

## Current Run

Local task:

- task: `Phase3BRepairQuotaLocal20260512`
- output: `runtime/next_stage_artifacts/phase3B-repair-quota-fresh-20260512-local`
- seeds: 9, 10, 11, 12
- arms: B0, B1, B2, B3
- status at launch check: running, first heartbeat written

Smoke:

- output: `runtime/next_stage_artifacts/phase3B-smoke-B3-20260512`
- result: completed
- purpose: chain validation only, not research evidence
