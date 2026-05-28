# Phase3 Mature Chain Parity Audit

Date: 2026-05-28

Decision:

```text
PASS_NO_REGRESSION_WITH_GOVERNANCE_IMPROVEMENT
HOLD_ALGORITHMIC_SUPERIORITY_CLAIM
```

This audit checks whether the current mature-chain workspace actually improves on the previous mature chain and whether it records the research outputs well enough to prevent diagnostic/probe results from being mistaken for official alpha.

## Compared Revisions

```text
old research-state baseline:
    f01ddd5 phase3s add time split research freedom audit

locked diagnostic-chain baseline:
    2b9096f phase3z45b finalize diagnostic audits

current workspace policy:
    ce61a05 phase3 add mature feature workspace policy
```

## Scope

This audit evaluates chain structure, routing, evidence tracking, and promotion safeguards.

It does not claim that `ce61a05` has higher alpha performance than `2b9096f`; no new search or replay was run for this audit.

## Findings

### 1. Old Mature Chain Coverage Is Preserved

The current chain still points to the same official objects:

```text
discovery primary:
    G2_signal_vector_diversified_selector

official shadow:
    X0_official_6_R3_liquidity_low_v1

book filters:
    J2_balanced + J4_relaxed

forward shadow:
    Phase3P_locked_daily_forward

bias / split audit:
    Phase3S_time_split_research_freedom_audit
```

Verified evidence paths exist:

```text
reports/PHASE3H_DECISION_RECORD_2026-05-16.md
reports/PHASE3O_REGIME_GATED_SHADOW_DECISION_RECORD_2026-05-17.md
runtime/baselines/phase3o_x0_official_shadow_v1.json
runtime/baselines/phase3j_locked_book_filters.json
reports/phase3p_locked_daily_forward_20260517/PHASE3P_LOCKED_DAILY_FORWARD_2026-05-17.md
reports/phase3s_time_split_research_freedom_audit_20260522/PHASE3S_TIME_SPLIT_RESEARCH_FREEDOM_AUDIT_2026-05-22.md
```

Verified official modules import:

```text
our_system_phase2.runtime.phase3p_locked_daily_forward
our_system_phase2.runtime.phase3s_time_split_research_freedom_audit
```

### 2. The New Workspace Adds Governance, Not Alpha Performance

Relative to `f01ddd5`, the current repo adds:

```text
app.py
runtime/baselines/phase3_algorithm_chain_lock_v1.json
runtime/baselines/phase3_mature_feature_workspace_v1.json
docs/MATURE_CHAIN_FEATURE_WORKSPACE_2026-05-28.md
scripts/create_mature_feature_workspace.ps1
```

Concrete improvements:

```text
1. Unified entrypoint:
   app.py status / app.py list

2. Diagnostic separation:
   diagnostic commands require --allow-diagnostic

3. Official object lock:
   G2 / X0-R3 / J2-J4 / Phase3P are named explicitly.

4. Promotion gate list:
   frozen queue, no replay-label selection, strict replay, global clustering, OOS/regime/marginal audit, decision record, chain-lock update.

5. Feature-adapter policy:
   limit/event morphology, regime-conditional clustering, candidate-pool priority, and search-memory changes must enter through mature-chain metadata.

6. Clean worktree isolation:
   new feature work happens in:
   G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528
```

These are engineering and governance advantages. They do not by themselves prove better alpha.

### 3. Diagnostic Results Are Now Better Recorded

The current chain records the latest failed diagnostic line explicitly:

```text
phase3z45b_parametric_limit_open_touch:
    status: diagnostic_only_failed_promotion
    evidence: reports/PHASE3Z45B_RESEARCH_DECISION_RECORD_2026-05-28.md
```

Verified Z45b audit modules import:

```text
phase3z45b_parametric_limit_result_audit
phase3z45b_deep_identity_audit
phase3z45b_oos_regime_candidate_audit
phase3z45b_vs_x0_marginal_audit
phase3z45b_regime_timing_audit
phase3z45b_regime_fragility_audit
```

Verified Z45b evidence exists:

```text
reports/PHASE3Z45B_RESEARCH_DECISION_RECORD_2026-05-28.md
reports/PHASE3Z45B_REGIME_TIMING_DECISION_ADDENDUM_2026-05-28.md
reports/PHASE3Z45B_REGIME_FRAGILITY_DECISION_ADDENDUM_2026-05-28.md
reports/phase3z45b_parametric_limit_open_touch_20260528/
```

This is materially better than leaving limit/event searches as scattered runtime outputs.

### 4. Diagnostic Gate Works

Verified behavior:

```text
python app.py phase3r-limit-diagnostic -- --help
    exits 2
    refuses diagnostic command without --allow-diagnostic

python app.py --allow-diagnostic z45b-result-audit -- --help
    exits 0
    displays audit command help
```

This prevents diagnostic probes from being casually treated as official chain runs.

## Limitations

### A. No New Algorithmic Superiority Was Proven

The new workspace policy is not a new search result. It should not be described as a stronger alpha engine by performance.

Correct claim:

```text
The new workspace preserves the mature chain and improves governance / reproducibility / feature-adapter discipline.
```

Incorrect claim:

```text
The new workspace proves higher alpha performance than the old mature chain.
```

### B. Historical Untracked Assets Are Not Fully Canonicalized

The old dirty worktree still contains many untracked reports, scripts, launchers, and runtime outputs. This audit does not promote them.

Correct status:

```text
Committed official/diagnostic records are tracked.
Large historical local outputs remain diagnostic until cataloged and promoted.
```

### C. Authority Commit Semantics Need Care

`phase3_algorithm_chain_lock_v1.json` uses:

```text
authority_commit = 2b9096f...
```

This is acceptable if interpreted as the last algorithm-chain authority commit before the workspace policy layer. It should not be interpreted as the latest repository commit.

If future tooling expects `authority_commit == HEAD`, the lock schema should be split into:

```text
algorithm_authority_commit
workspace_policy_commit
```

## Verdict

The current chain has a real advantage over the older mature chain in process control:

```text
PASS:
    official / diagnostic separation
    route-level diagnostic guard
    feature workspace profile
    bootstrap script
    promotion gate policy
    Z45b result recording
    evidence-path presence
    module import sanity

HOLD:
    algorithmic superiority claim
    full canonicalization of all old local assets
    production-readiness claim
```

Operational conclusion:

```text
Use ce61a05 as the working mature-feature-adapter baseline.
Use 2b9096f as the locked algorithm-chain authority baseline.
Do not promote any old or new diagnostic asset without the promotion gates.
```

