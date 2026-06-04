# CN Field Searcher Readiness Summary

Date: 2026-06-04

Decision:

```text
PASS_STRUCTURED_LARGE_SEARCH_PRELAUNCH_READY
```

This summary consolidates the field-ingestion, panelization, HFQ valuation, and searcher-adaptation reports that define the current boundary for the next large-scale search. The important conclusion is not "all fields should enter search"; it is that the fields now have explicit routing into formula search, event-state search, regime/gate interaction, tradability gates, or blocked metadata/cutoff/label lanes.

## Executive Summary

The system is at the door of large-scale search, but only for structured lane-based search.

Allowed next step:

```text
Phase3AE structured large-search prelaunch
```

Not allowed:

```text
Throw all 4775 fields into one formula generator.
Use timestamps, future labels, text, keys, or same-day unavailable fields as alpha inputs.
Treat event/regime/tradability fields as ordinary direct rank formulas.
```

## Current Evidence

| Area | Decision | Main Evidence |
|---|---:|---|
| Field integration completeness | `HOLD_FIELD_INTEGRATION_NOT_FULLY_CLOSED` | 4775 asset fields tracked; 1045 panel fields; 761 factor aliases; 143 selector aliases; 1319 high-value gaps |
| Searcher adaptation classification | `PASS_SEARCHER_ADAPTATION_CLASSIFICATION_WITH_REPAIR_QUEUE` | 1774 direct formula-ready fields; 1416 formula repair queue fields; 256 event-state fields; 395 gate/regime fields; 491 blocked/key/cutoff fields |
| HFQ valuation sidecar | `PASS_HFQ_VALUATION_SIDECAR_BUILT` | 988005 rows; 10 lagged valuation/liquidity features; mean non-null rate 0.907 |
| HFQ augmented panel | `PASS_PHASE3AD_AUGMENTED_PANEL_BUILT` | 988005 rows; columns 674 -> 684; no collisions; SHA256 `cb8b71480b38dd198f570504f8d2181460cce6945f42dfeeea1130dbc2732069` |
| HFQ factor pack | `PASS_HFQ_VALUATION_FACTOR_PACK_READY` | 12 focused HFQ valuation/liquidity candidates |
| HFQ selector-only canary | `PASS_HFQ_VALUATION_SELECTOR_ONLY_CANARY` | 496 pool candidates -> 180 capped pool -> 32 selected; 12 HFQ candidates in pool; 9 selected |

## Searcher Routing Result

From 4775 tracked fields:

| Route | Count | Meaning |
|---|---:|---|
| Direct formula search ready | 1774 | Already has enough integration proof for bounded formula candidate generation or selector canary |
| Direct formula repair queue | 1416 | Suitable in principle, but needs factor pack, PIT sidecar, or ingestion repair |
| Event-state machine fields | 256 | Should enter event-state / actor-motif validation, not plain rank formulas |
| Event-state repair queue | 47 | Event fields with incomplete sidecar/factor-pack/PIT materialization |
| Regime / gate / context fields | 395 | Should be used as gates, context, or interactions |
| Blocked / key / cutoff fields | 491 | Metadata, keys, timestamps, cutoffs, text, or future labels; not alpha formula inputs |
| Non-formula-search fields | 886 | Valid data assets, but unsuitable for direct formula replay |

## Concrete Field Decisions

Confirmed direct lagged formula candidates:

```text
pe_ttm
pb
ps_ttm
volume_ratio
turnover_ratio
```

These are now integrated through lagged daily/HFQ valuation paths and have selector-admission evidence.

Confirmed event-state / actor-motif candidates:

```text
auction_money
fengdan_rate
lb_2_num
max_lb_num
up_limit_keep_times
open_board / limit board state fields
```

These should be validated through event count, observable cutoff, matched-control, same-count random placebo, and tradability audits.

Confirmed blocked or non-direct fields:

```text
up_limit_time
next_open_pct
next_close_pct
code/date/time keys
text descriptions
future labels
```

`up_limit_time` is an observability/cutoff contract, not a rankable alpha field. `next_open_pct` and `next_close_pct` are future labels and remain blocked.

High-value repair queue examples:

```text
BILLBOARD_NET_AMT
ACCUM_AMOUNT
DEAL_AMOUNT_RATIO
RZYEZB
amount_yuan
volume_shares
float_shares
fengdan_rate
```

These should be converted into bounded factor packs or PIT sidecars before replay.

## Searcher Lane Contract

Direct formula lanes:

```text
Use bounded formula packs only after PIT/lag contracts.
Then run selector canary, replay/style audit, and cost/turnover audit.
```

Event lanes:

```text
Use event-state / actor-motif generator.
Require cutoff proof, event count, matched control, same-count random placebo, and tradability checks.
```

Regime/context lanes:

```text
Use gate or interaction validation.
Require lag audit, random/block/circular placebo, and full-calendar gated replay.
```

Tradability/risk lanes:

```text
Use as execution/risk filters, not alpha formulas.
Require fillability, limit/suspension, turnover, and capacity impact audits.
```

Blocked lanes:

```text
No search. Only alignment, metadata, or forbidden-field audits.
```

## Report Links

- [Field Integration Completeness Audit](./cn_field_integration_completeness_audit_v1_20260603/CN_FIELD_INTEGRATION_COMPLETENESS_AUDIT_V1_2026-06-03.md)
- [Field Integration Completeness JSON](./cn_field_integration_completeness_audit_v1_20260603/field_integration_completeness_audit.json)
- [Field Searcher Adaptation Audit](./cn_field_searcher_adaptation_audit_v1_20260604/CN_FIELD_SEARCHER_ADAPTATION_AUDIT_V1_2026-06-04.md)
- [Searcher Lane Contract](./cn_field_searcher_adaptation_audit_v1_20260604/searcher_lane_contract_v1.json)
- [Searcher Adaptation Summary CSV](./cn_field_searcher_adaptation_audit_v1_20260604/searcher_adaptation_summary.csv)
- [Direct Formula Ready Fields Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/direct_formula_search_ready_fields_top.csv)
- [Formula Search Repair Queue Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/formula_search_repair_queue_top.csv)
- [Event-State Machine Fields Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/event_state_machine_fields_top.csv)
- [Event-State Repair Queue Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/event_state_search_repair_queue_top.csv)
- [Gate / Regime Fields Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/gate_or_regime_fields_top.csv)
- [Blocked / Key Fields Top CSV](./cn_field_searcher_adaptation_audit_v1_20260604/blocked_or_key_fields_top.csv)
- [HFQ Valuation Sidecar Report](./cn_phase3ad_hfq_valuation_sidecar_v1_20260603/CN_PHASE3AD_HFQ_VALUATION_SIDECAR_V1_2026-06-03.md)
- [HFQ Valuation Factor Pack Report](./cn_phase3ad_hfq_valuation_factor_pack_v1_20260603/CN_PHASE3AD_HFQ_VALUATION_FACTOR_PACK_V1_2026-06-03.md)
- [HFQ Augmented Panel Report](./cn_phase3ad_hfq_valuation_augmented_panel_v1_20260603/CN_PHASE3AD_AUGMENTED_PANEL_V1_2026-06-03.md)
- [HFQ Selector-Only Canary Report](./cn_phase3ad_hfq_valuation_selector_only_canary_v1_20260603/CN_PHASE3AD_HFQ_VALUATION_SELECTOR_ONLY_CANARY_V1_2026-06-03.md)

## Next Work Queue

1. Build bounded factor packs for panel-ready high-value fields:

```text
BILLBOARD_NET_AMT
ACCUM_AMOUNT
DEAL_AMOUNT_RATIO
amount_yuan
volume_shares
float_shares
RZYEZB
```

2. Build event-state packs for:

```text
fengdan_rate
auction_money
up_limit_keep_times
lb_2_num / lb_3_num / max_lb_num
open-board / high-board state transitions
```

3. Run selector-only dry runs by lane:

```text
Lane A: lagged daily / PIT formula
Lane B: bounded factor-pack repair
Lane C: event-state / actor-motif
Lane D: regime / context interaction
```

4. Only after lane dry runs pass:

```text
Launch structured large-scale search on local + company machines.
```

## Bottom Line

The new data layer is now sufficiently organized for structured large-scale search. The main blocker is no longer "unknown field integration"; it is the deliberate conversion of repair-queue fields into the correct searcher lane without violating PIT, event cutoff, or label-leakage boundaries.
