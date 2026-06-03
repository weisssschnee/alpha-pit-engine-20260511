# CN Integrated Field Utility Map v1

decision: `PASS_FIELD_UTILITY_MAP_FOUND_CANDIDATE_AXES`

## Counts

- row_count: `897223`
- field_count_scanned: `137`
- candidate_axis_count: `7`
- diagnostic_axis_count: `12`
- error_count: `0`

## Top Candidate Axes

| field | family | direction | oos net10 ann | oos IC | train net10 ann | R3 ann | non-R3 ann | decision |
|---|---|---|---:|---:|---:|---:|---:|---|
| m1_day_high | minute_range_price_state | negative | 0.282919 | -0.027694 | 0.313992 | 2.329644 | -0.233489 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| m1_first30_high | minute_range_price_state | negative | 0.293766 | -0.027314 | 0.293273 | 2.15802 | -0.200902 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| m1_first15_high | minute_range_price_state | negative | 0.283554 | -0.027153 | 0.273367 | 2.250103 | -0.222794 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| m1_first15_high_minute | minute_range_price_state | negative | 0.283554 | -0.027153 | 0.273367 | 2.250103 | -0.222794 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| m1_first5_high | minute_range_price_state | negative | 0.252293 | -0.026978 | 0.269209 | 2.112805 | -0.234085 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| m1_first30_vwap | minute_vwap_pressure | negative | 0.307788 | -0.026681 | 0.318796 | 2.119161 | -0.182049 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |
| open | price_state | negative | 0.412152 | -0.023244 | 0.248229 | 3.265056 | -0.244637 | CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH |

## Interpretation Boundary

This is a field-level utility map. It does not promote any field, formula, or book. Positive axes should feed repair/search lanes, then pass mature replay and X0 marginal audits.

Raw price-level axes such as `open` and raw minute high/VWAP fields are not standalone alpha claims. They are transformation seeds and must be normalized, size/residual controlled, or repaired into formulas before any replay or promotion decision.

R3-conditional axes are diagnostic until replayed through a locked gate and frozen selection path.
