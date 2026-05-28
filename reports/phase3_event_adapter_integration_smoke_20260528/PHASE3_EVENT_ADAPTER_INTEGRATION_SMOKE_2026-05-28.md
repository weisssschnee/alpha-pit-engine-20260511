# Phase3 Event Adapter Integration Smoke

- decision: `PASS_EVENT_ADAPTER_INTEGRATION_SMOKE`
- candidate_count: `47`
- evaluated_count: `45`
- skipped_count: `2`
- eval_error_count: `0`
- new_event_adapter_candidate_count: `30`
- metadata_missing_count: `0`
- forbidden_field_hit_count: `0`
- lag_audit_pass: `True`

## Interpretation

- Event-derived fields now enter diagnostic candidate templates with provenance, lag, leakage, tradability, and search-memory metadata.
- The after-open clock keeps open-print fields unlagged and full-day close/touch/break/high-board fields lagged.
- This is not a replay result and cannot change X0/R3/G2/J2/J4.
