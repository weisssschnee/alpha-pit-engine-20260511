# Mature Chain Feature Workspace

Date: 2026-05-28

This workspace exists to adapt new research features without bypassing the mature Phase3 chain.

## Workspace

Path:

```text
G:\Project_V7_Rotation\alpha_pit_engine_mature_feature_workspace_20260528
```

Branch:

```text
feature/mature-chain-adapter-20260528
```

Base:

```text
origin/main @ 2b9096f
```

## Rule

New feature work must reuse the locked chain:

```text
generator / feature adapter
-> search memory / duplicate control
-> shared candidate pool
-> frozen selection
-> strict replay / validation
-> global clustering
-> OOS / regime / marginal audit
-> promotion triage
-> chain-lock update
```

Diagnostic probes can be fast and narrow, but they cannot become official candidates unless they pass the promotion gates.

## Official Entry

Use:

```powershell
G:\PythonProject\.venv\Scripts\python.exe app.py status
G:\PythonProject\.venv\Scripts\python.exe app.py list
```

Diagnostic commands require:

```powershell
--allow-diagnostic
```

## Feature Adapter Policy

Allowed feature adapters:

```text
limit/event morphology
regime-conditional clustering
candidate-pool source weighting
runtime state registry
search-memory / ledger policy updates
```

Adapter constraints:

```text
1. Do not replace G2, X0/R3, J2/J4, or Phase3P without an explicit decision record.
2. Do not use replay/deployable/final-cluster labels in pre-replay selection.
3. Do not run seed-local clustering as promotion evidence.
4. Do not treat diagnostic output as an alpha candidate.
5. Do not add a feature lane without source metadata, search-memory metadata, and promotion-gate metadata.
```

## Current Official Objects

```text
Discovery primary:
    G2_signal_vector_diversified_selector

Official shadow:
    X0_official_6_R3_liquidity_low_v1

Book-readiness filters:
    J2_balanced
    J4_relaxed

Forward object:
    Phase3P_locked_daily_forward
```

## Current Diagnostic Lessons

Phase3Z45b limit/open/touch search is diagnostic only:

```text
status: diagnostic_only_failed_promotion
reason: no marginal value vs X0/R3 after timing, regime, and fragility audits
use: inform future reward redesign, not direct promotion
```

The next event/limit feature work must be represented as feature adapters inside the mature chain, not as standalone promotion evidence.

## Event Derived Feature Layer

The first executable adapter is:

```text
service: our_system_phase2.services.event_derived_features
audit:   our_system_phase2.runtime.phase3_event_derived_feature_audit
route:   app.py --allow-diagnostic event-derived-feature-audit
smoke:   app.py --allow-diagnostic event-adapter-integration-smoke
```

It standardizes:

```text
close-lock limit up/down
open-limit up/down
intraday touch up/down
touch/open then not close
close-lock streak ge n
touch streak ge n
break board after streak ge n
limit-down rebound after streak ge n
market high-board rank
post high-board t+d
break after high-board t+d
```

It records:

```text
source fields
lag rule
availability clock
tradability rule
leakage flag
coverage
```

This is still a feature adapter. It does not promote limit/event alpha by itself.

## Event Adapter Integration Smoke

The diagnostic smoke proves the adapter reaches the mature candidate path:

```text
event-derived field contract
-> limit/event motif ledger
-> source/search-memory metadata
-> after-open lag policy
-> real panel expression evaluation
```

Required metadata for each diagnostic candidate:

```text
feature_adapter
event_fields
event_family
lag_rule
tradability_rule
leakage_flag
search_memory_key
```

The smoke is not replay, not global clustering, and not alpha promotion.
