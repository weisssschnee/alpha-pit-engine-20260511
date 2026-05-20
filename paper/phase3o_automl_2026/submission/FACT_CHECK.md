# FACT_CHECK.md

Date: 2026-05-20

Scope: Phase3O AutoML paper pack under `paper/phase3o_automl_2026`.

Decision: **PASS_WITH_REPO_HYGIENE_FIXES**

The main evidence chain is traceable to committed paper-pack artifacts. The remaining issues are presentation/reproducibility hygiene: no committed draft/figure assets, moving `main` after the paper pack, and stale paper-facing forward status relative to the live cloud shadow.

## Repository State

| Item | Value | Source | Status |
|---|---:|---|---|
| Audit base local HEAD | `a39cfc28694d84bec14391603db1d43cd59e68a4` | `git rev-parse HEAD` before submission hygiene files | PASS |
| Audit base `origin/main` | `a39cfc28694d84bec14391603db1d43cd59e68a4` | `git rev-parse origin/main` before submission hygiene files | PASS |
| Paper pack first commit | `92440a6` | `generated/freeze_status.csv` | PASS |
| Research state commit used to generate pack | `23f5039` | `generated/freeze_status.csv` | PASS |
| Frozen evidence-pack tag | `phase3o-automl-paper-pack-v0.1 -> 10f379d` | `git ls-remote --tags origin phase3o-automl-paper-pack-v0.1` | PASS |
| Submission hygiene commit | `0459a5d` | `git log --oneline` | PASS |
| X0 freeze tag | `phase3o-x0-shadow-v1` | local + remote `git ls-remote --tags` | PASS |
| Freeze tag target commit | `a60bfbe` | `generated/freeze_status.csv`, remote tag deref | PASS |
| Latest `main` moved after paper pack | yes, includes `a39cfc2` after `10f379d` | `git log --oneline` | FIX |

Recommended citation for reproducibility: cite `phase3o-x0-shadow-v1` for the frozen object and `phase3o-automl-paper-pack-v0.1` for the frozen paper evidence pack, rather than moving `main`.

Suggested reproducibility wording:

> The frozen evidence pack is tagged as `phase3o-automl-paper-pack-v0.1` and points to commit `10f379d`. Submission statements and hygiene files were added later in commit `0459a5d` without changing the frozen X0/R3 evidence object.

## Confidentiality / Redaction Policy

| Item | Policy | Status |
|---|---|---|
| Full alpha formulas | Do not add to the paper submission pack. Keep in private runtime/proof artifacts only. | PASS |
| Formula family descriptions | Allowed when reduced to non-reconstructive short names, e.g. `open_volatility_x_vwap_abs_delta`. | PASS |
| Exact cluster target-weight files | Do not publish as paper assets unless explicitly anonymized or downsampled. | PASS |
| Shadow/live cloud paths | Allowed only as process evidence; avoid credentials, API keys, and broker/account identifiers. | PASS |
| Commercial quality model / ranker internals | Do not disclose trained model files, feature importances sufficient to reconstruct, or private labels. | PASS |
| Public reproducibility | Use synthetic/demo data and aggregate tables, not full commercial formula inventory. | PASS |

This fact-check intentionally verifies public paper claims without copying the full commercial formula set from `runtime/baselines`.

## Frozen Object Claims

| Claim | Verified Value | Source | Status |
|---|---:|---|---|
| Frozen object exists | `X0_official_6_R3_liquidity_low_v1` | `generated/freeze_status.csv` | PASS |
| Object status | `official_daily_shadow` | `generated/freeze_status.csv` | PASS |
| Official clusters | `001|005|006|009|002|004` | `generated/freeze_status.csv` | PASS |
| Official gate | `R3_liquidity_low` | `generated/freeze_status.csv` | PASS |
| Official shadow profile | `x0_official6_r3_liquidity_low` | `generated/freeze_status.csv` | PASS |
| Locked object hash unchanged after code/deployment extensions | `yes_code_and_deployment_extended; locked object hash unchanged` | `generated/freeze_status.csv` | PASS |
| Stable object hash | `454b5b5e225c5acbefb7a49629eb5aec97a07871625bf38e2aeb3ee2b68af896` | `generated/freeze_status.csv` | PASS |

## R3 Gate Definition Claims

| Claim | Verified Value | Source | Status |
|---|---:|---|---|
| Gate plain-language definition | market-wide low-liquidity regime from lagged short/long liquidity ratio | `generated/r3_gate_definition.csv` | PASS |
| Gate feature | `liquidity_ratio_lag1` | `generated/r3_gate_definition.csv` | PASS |
| Lag rule | `lagged_only` | `generated/r3_gate_definition.csv` | PASS |
| Threshold source | 2025H2 train window; q33 in runner implementation | `generated/r3_gate_definition.csv` | PASS |
| 2026 does not set numeric threshold | `no_for_numeric_threshold; yes_research_touched_for_gate_choice` | `generated/r3_gate_definition.csv` | PASS_WITH_BOUNDARY |
| 2026 active days | `38 / 78` | `generated/r3_gate_definition.csv` | PASS |
| 2026 active ratio | `0.487179` | `generated/r3_gate_definition.csv` | PASS |

Boundary: R3 is recent-OOS / research-touched historical OOS, not untouched locked-forward proof.

## Main Performance Claims

| Claim | Verified Value | Source | Status |
|---|---:|---|---|
| No-gate annualized proxy | `0.729231` | `generated/regime_gate_oos_table.csv` | PASS |
| No-gate Sharpe proxy | `2.219926` | `generated/regime_gate_oos_table.csv` | PASS |
| No-gate max drawdown | `-0.10425684` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 full-calendar annualized proxy | `1.175657` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 Sharpe proxy | `4.547115` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 Sortino proxy | `6.085253` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 max drawdown | `-0.03442312` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 total return proxy | `0.266314` | `generated/regime_gate_oos_table.csv` | PASS |
| R3 active-day annualized proxy | `3.918442` | `generated/regime_gate_oos_table.csv` | PASS_WITH_INTERPRETATION |
| R3 inactive annualized proxy | `-0.361992` | `generated/regime_gate_oos_table.csv` | PASS |

Interpretation guard: `3.918442` is active-day conditional annualization, not full-calendar strategy annualization. The paper must not describe this as a 391.8% complete strategy return.

## Placebo / Robustness Claims

| Claim | Verified Value | Source | Status |
|---|---:|---|---|
| R3 true annualized proxy | `1.175657` | `generated/placebo_robustness_table.csv` | PASS |
| Random active-day p95 | `0.933008` | `generated/placebo_robustness_table.csv` | PASS |
| Block placebo p95 | `0.9983` | `generated/placebo_robustness_table.csv` | PASS |
| Circular shift p95 | `1.098173` | `generated/placebo_robustness_table.csv` | PASS |
| Inverted gate annualized proxy | `-0.205755` | `generated/placebo_robustness_table.csv` | PASS |
| R3 robustness decision | `PASS_STRICT_GATE_ROBUSTNESS` | `generated/placebo_robustness_table.csv` | PASS |
| Failed control gates exist | F1/F2/F3 all `HOLD_STRICT_GATE_ROBUSTNESS` | `generated/placebo_robustness_table.csv` | PASS |

## R3 Sensitivity Claims

| Threshold | Active Ratio | Annualized Proxy | Sharpe | Max DD | Random p95 | Decision | Source | Status |
|---|---:|---:|---:|---:|---:|---|---|---|
| q25 | `0.128205` | `0.435259` | `4.170470` | `-0.00259208` | `0.355670` | PASS | `generated/r3_sensitivity_audit.csv` | PASS |
| q30 | `0.230769` | `0.599803` | `3.972418` | `-0.01576915` | `0.552589` | PASS | `generated/r3_sensitivity_audit.csv` | PASS |
| q33 | `0.487179` | `1.175657` | `4.547115` | `-0.03442312` | `0.837281` | PASS | `generated/r3_sensitivity_audit.csv` | PASS |
| q35 | `0.512821` | `1.124614` | `4.370534` | `-0.04156776` | `0.906951` | PASS | `generated/r3_sensitivity_audit.csv` | PASS |
| q40 | `0.576923` | `0.969264` | `3.644568` | `-0.04918273` | `0.957589` | PASS | `generated/r3_sensitivity_audit.csv` | PASS |

Claim supported: q33 is not an isolated single-threshold artifact.  
Claim not supported: retuning R3 after seeing q25/q30/q35/q40.

## Cluster Composition Claims

| Cluster | Short Name | Role | Source Lane | Turnover Proxy | Source | Status |
|---|---|---|---|---:|---|---|
| cluster_001 | `vwap_abs_delta_volatility_state` | core | `agnostic_freeform_ast` | `0.073418` | `generated/cluster_composition.csv` | PASS |
| cluster_005 | `open_volatility_x_vwap_abs_delta` | core | `agnostic_freeform_ast` | `0.199872` | `generated/cluster_composition.csv` | PASS |
| cluster_006 | `close_magnitude_x_amount_magnitude` | core | `r0_cem_led` | `0.051814` | `generated/cluster_composition.csv` | PASS |
| cluster_009 | `close_size_residual_x_abs_close_delta` | support | `formula_gen_v2_repair_expansion` | `0.103397` | `generated/cluster_composition.csv` | PASS |
| cluster_002 | `open_rank_x_amount_mean` | support | `agnostic_freeform_ast` | `0.076805` | `generated/cluster_composition.csv` | PASS |
| cluster_004 | `close_mean_x_float_mcap_state` | support | `formula_gen_v2_repair_expansion` | `0.027425` | `generated/cluster_composition.csv` | PASS |

Cluster formulas are intentionally not fully disclosed in the paper pack table. The paper should call these cluster families or representatives, not open formula release.

## Forward / Shadow Claims

| Claim | Verified Value | Source | Status |
|---|---:|---|---|
| Formal X0 forward profile exists | `x0_official6_r3_liquidity_low` | `generated/forward_status.csv` | PASS |
| Formal X0 forward status | `TRACKING` | `generated/forward_status.csv` | PASS |
| Observed return days in paper pack | `0` | `generated/forward_status.csv` | PASS |
| Active observed days in paper pack | `0` | `generated/forward_status.csv` | PASS |
| Cloud shadow status in paper pack | `PASS_CLOUD_SHADOW_SIGNALS_EXPORTED` | `generated/cloud_shadow_latest_status.json` | PASS |
| Cloud paper-pack latest date | `2026-05-18` | `generated/cloud_shadow_latest_status.json` | PASS_BUT_STALE |

Important update: cloud runtime has later shadow outputs after the paper pack. The paper pack can only claim protocol deployment, not forward performance.

## Figure / Draft Asset Claims

| Asset Type | Verified State | Source | Status |
|---|---|---|---|
| Figure files (`png/jpg/svg/pdf`) | no committed files found under `paper/phase3o_automl_2026` | `git ls-files`, local file scan | FIX |
| Draft files (`docx/md` under drafts/submission) | no committed draft found before this fact-check file | `git ls-files`, local file scan | FIX |
| Submission statements | absent before this fact-check file | `git ls-files`, local file scan | FIX |

Any paper figure must be generated from `generated/daily_oos_r3_curve.csv`, `generated/placebo_robustness_table.csv`, or `generated/r3_sensitivity_audit.csv`, and the figure generation script should be committed.

## Reproducibility Files

| File | Local Status | Source | Status |
|---|---|---|---|
| `repro/make_synthetic_panel.py` | tracked | `git ls-files` | PASS |
| `repro/run_toy_regime_gate.py` | tracked | `git ls-files` | PASS |
| `generated/synthetic/synthetic_panel.csv` | tracked | `git ls-files` | PASS |
| `generated/synthetic/toy_daily_gate.csv` | tracked | `git ls-files` | PASS |
| `generated/synthetic/toy_regime_gate_summary.json` | tracked | `git ls-files` | PASS |
| README exact commands | present | `paper/phase3o_automl_2026/README.md` | PASS |
| README line count | `44` | local line-count check | PASS |
| `build_paper_phase3o_tables.py` line count | `447` | local line-count check | PASS |
| `build_r3_sensitivity_audit.py` line count | `201` | local line-count check | PASS |

The earlier raw-fetch concern appears to be a web/cache/path issue, not a local tracking issue.

## Bias / Boundary Audit

| Topic | Finding | Status |
|---|---|---|
| Look-ahead / gate lag | R3 definition states `lagged_only`; this supports the claim but should remain explicit in the paper. | PASS |
| 2026 threshold selection | Numeric threshold not selected on 2026, but gate choice is research-touched. | PASS_WITH_BOUNDARY |
| OOS strength | 2026 is recent-OOS / research-touched, not untouched locked-forward OOS. | HOLD_RESEARCH_FOR_PRODUCTION |
| Costs / slippage | Daily proxy only; no minute slippage or real fill model. | HOLD_RESEARCH_FOR_PRODUCTION |
| Capacity | Daily capacity/liquidity proxies only. | HOLD_RESEARCH_FOR_PRODUCTION |
| Forward/live | Forward shadow protocol has started; paper pack has insufficient observed days. | HOLD_RESEARCH_FOR_PRODUCTION |
| Negative weights / short leg | Negative `target_weight` means long-short shadow underweight/short-leg target; not literal A-share short execution. | PASS_WITH_IMPLEMENTATION_BOUNDARY |

## Forbidden Claims

The paper must not claim:

- production-ready strategy
- live-proven alpha
- real execution validation
- minute slippage validation
- real capacity validation
- untouched forward OOS proof
- full-calendar annualized return of 391.8%
- literal A-share short execution from negative weights
- X4 or oracle variants as official selection rules

## Supported Claims

The current GitHub paper pack supports:

- X0/R3 is a frozen daily shadow research object.
- R3 improves recent-OOS daily proxy performance over no-gate in 2026.
- R3 passes random/block/circular/inverted-gate placebo checks.
- q33 R3 threshold is not an isolated sensitivity point.
- Failed control gates exist and do not pass the same robustness standard.
- Forward shadow protocol is deployed, but forward performance evidence is not yet mature.
- The result is daily-proxy L2.5 evidence, not production or execution proof.

## Resolved Hygiene Items

| Item | Resolution | Commit / Artifact | Status |
|---|---|---|---|
| Paper evidence state needs immutable reference | Added `phase3o-automl-paper-pack-v0.1` tag pointing to `10f379d` | Git tag | RESOLVED |
| Fact-check file missing | Added `submission/FACT_CHECK.md` | `0459a5d` | RESOLVED |
| Data availability statement missing | Added `submission/DATA_AVAILABILITY.md` | `0459a5d` | RESOLVED |
| AI use statement missing | Added `submission/AI_USE_STATEMENT.md` | `0459a5d` | RESOLVED |
| Conflict / confidentiality statement missing | Added `submission/CONFLICT_OF_INTEREST.md` | `0459a5d` | RESOLVED |
| Draft/figure directories absent | Added guarded README files | `0459a5d` | PARTIAL_RESOLVED |
| Figure-generation script missing | Added `scripts/build_paper_figures.py`; script uses aggregate CSVs only | post-`0459a5d` hygiene update | RESOLVED |
| Redacted scripted figures missing | Added SVG figures generated from public aggregate CSVs | post-`0459a5d` hygiene update | RESOLVED |

## Remaining Fixes Before Submission

1. Refresh or clearly version `cloud_shadow_latest_status.json`; the paper-pack version is stale relative to cloud runtime.
2. Decide whether the v0.5/v0.6 manuscript enters the public repo as redacted PDF/Markdown. Do not publish a DOCX containing private comments or unreleased formulas.
3. Keep formulas private or intentionally redacted; do not accidentally publish commercial formula details.
