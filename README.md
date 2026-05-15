# Alpha PIT Engine Export

This repository is a compact export of the Phase2 A-share alpha discovery work that is under our direct control.

It contains:

- Phase2 alpha search, validation, proof-suite, ledger-policy, and A-share state modules under `src/our_system_phase2`.
- The focused Phase2 runtime/test coverage in `tests/test_phase2_v21_runtime.py`.
- Recent proof and bias-audit reports under `reports/`.
- Company-PC proof launch/check artifacts under `runtime/next_stage_artifacts/`.
- Local TDX/TDXGP data-build scripts under `scripts/`.

It intentionally excludes:

- Raw market data files: `*.parquet`, `*.csv`, `*.db`, `*.sqlite`.
- Long-running shard outputs and search ledgers not needed for code review.
- Local credentials, caches, virtualenvs, and machine-specific IDE state.

## Current Research State

The latest true-limit validation uses `TDXGP GPJYVALUE(15)` as the preferred close-locked limit-up/down source:

- `value1 == 2`: close locked limit-up.
- `value1 == -2`: close locked limit-down.
- `rt_change_pct>=9.8` / `<=-9.8` remains only a fallback.

The current algorithm-level conclusion is `HOLD_RESEARCH`: UCB/reward memory has not yet proven superior to baseline under strict/replay validation. See:

- `reports/PHASE2_TDXGP_LIMIT_STATUS_AUDIT_2026-05-11.md`
- `reports/PHASE2_TDXGP_LIMIT_P0_P3_RESULTS_2026-05-11.md`

The latest exported research stack also includes:

- Replay-aware candidate logging and selector diagnostics.
- True-limit search bakeoff v2.
- Phase3 failure-aware AST repair and global cluster aggregation.
- Phase3B repair-aware quota experiment wiring.
- Formula Generator V2, a motif-first role-based generator prototype.

The current Phase3A aggregate result is `PASS_CONFIRM_PHASE3A` for search-structure confirmation, not a commercial alpha proof. Phase3B is designed to test whether direct R0 quota and child-side repair-aware soft quota can preserve AST repair yield while reducing cluster concentration.

The latest exported Phase3G result confirms the signal-vector diversified selector as the current best search-mechanics candidate:

- `G2_E3_signal_vector_diversified`: 67 deployable clusters / 256 audited, top cluster share 4.9587%.
- Global fixed aggregate: 144 deployable clusters / 1024 audited, global top cluster share 16.2577%.
- Status: `PASS_CONFIRM_PHASE3G_ALGORITHMIC` with `HOLD_METADATA_ONLY`, not commercial alpha deployment proof.
- Current metadata blocker: declared baseline `134` vs vector/recluster matchable `122`.
- Current true book-marginal blocker: no cheap return vectors for candidates or registry representatives.
- Current ranker reproducibility blocker: company runtime loads old replay rankers with sklearn version warnings.

Key current reports:

- `reports/PHASE3_REPAIR_AUDIT_2026-05-11.md`
- `reports/PHASE3_ABLATION_GLOBAL_AGGREGATE_2026-05-12.md`
- `reports/PHASE3B_REPAIR_QUOTA_FLOW_2026-05-12.md`
- `reports/FORMULA_GEN_V2_DESIGN_2026-05-12.md`
- `reports/PHASE3G_DECISION_RECORD_2026-05-15.md`
- `reports/phase3g_registry_qa_20260515/PHASE3G_REGISTRY_QA_2026-05-15.md`
- `reports/phase3g_run_completion_audit_20260515/PHASE3G_RUN_COMPLETION_AUDIT_2026-05-15.md`
- `reports/phase3_model_env_manifest_company_20260515/PHASE3_MODEL_ENV_MANIFEST_2026-05-15.md`
- `reports/phase3h_book_vector_preflight_20260515/PHASE3H_BOOK_VECTOR_PREFLIGHT_2026-05-15.md`
- `reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/PHASE3G_S29_S32_COMPANY_FIXED_MIXED_GLOBAL_AGGREGATE_2026-05-15.md`

## Quick Checks

```powershell
$env:PYTHONPATH = "src"
python -m pytest tests/test_phase2_v21_runtime.py -k "tdxgp_limit_status or limit_state_masks or prepare_market_panel" -q
```
