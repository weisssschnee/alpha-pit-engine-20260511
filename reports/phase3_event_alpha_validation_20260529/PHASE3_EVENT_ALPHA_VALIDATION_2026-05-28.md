# Phase3 Event Alpha Validation

- decision: `HOLD_EVENT_ALPHA_VALIDATION_DIAGNOSTIC_ONLY`
- candidate_count: `5`
- scope: diagnostic only; no search; no official promotion.
- matched/tradability controls are not available in this daily diagnostic input.

## Grade Counts

- research_candidate_hold_tradability: `3`
- research_candidate: `1`
- diagnostic_research_fragile: `1`

## Event Rows

| cluster | events | mean | median | hit | top3 share | random p95 pass | grade | decision |
|---|---:|---:|---:|---:|---:|---|---|---|
| cluster_001 | 51 | 0.00050832 | -0.000419 | 0.49019608 | 0.30770365 | `False` | `research_candidate_hold_tradability` | `EVENT_COUNT_GE_50_TRADABILITY_MISSING` |
| cluster_002 | 37 | 0.00207738 | 0.00054455 | 0.54054054 | 0.34095477 | `True` | `research_candidate` | `EVENT_COUNT_20_49_PLACEBO_OK` |
| cluster_007 | 47 | 0.00073592 | -0.00114936 | 0.44680851 | 0.26868994 | `False` | `diagnostic_research_fragile` | `EVENT_COUNT_20_49_OR_FRAGILE` |
| cluster_017 | 53 | 0.00089284 | 0.00054426 | 0.50943396 | 0.27347718 | `False` | `research_candidate_hold_tradability` | `EVENT_COUNT_GE_50_TRADABILITY_MISSING` |
| cluster_030 | 70 | 0.00037408 | -0.00088471 | 0.48571429 | 0.22282912 | `False` | `research_candidate_hold_tradability` | `EVENT_COUNT_GE_50_TRADABILITY_MISSING` |

## Boundary

- Event-count evidence is preserved instead of forcing dense daily-alpha promotion.
- Missing matched-control and tradability controls block event-proof promotion.
- These rows can inform Z46 canary design but cannot alter X0/R3.
