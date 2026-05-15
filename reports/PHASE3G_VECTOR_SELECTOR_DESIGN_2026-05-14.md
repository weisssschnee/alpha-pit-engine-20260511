# Phase3G Vector Selector Design

## Decision

Implement `E3VectorDiversifiedSelector` as a signal-vector proxy selector, not a true book-marginal selector.

## Basis

Phase3G signal vector audit passed the vector proxy gate:

- sampled signal vector AUC: `0.676645`
- symbolic proxy AUC: `0.553337`
- sampled signal vector precision@0.8: `0.853125`
- symbolic precision@0.8: `0.597256`
- Phase3F `cluster_003` recall@0.8: `0.930620`
- Phase3F `cluster_003` false positive rate@0.8: `0.016469`

Interpretation:

Signal vector is not a perfect global ranking metric. It is a high-precision collision detector. Use it for caps and selected-queue collision penalties.

## Arms

- `G0_E0_stable`: unchanged E0/D3 primary control
- `G1_E3_current_proxy`: existing E3 symbolic proxy control
- `G2_E3_signal_vector_diversified`: E3 proxy plus signal-vector caps and queue penalties
- `G3_E3_strong_signal_vector_proxy`: stronger signal-vector diversity pressure

## Leakage Boundary

Allowed:

- candidate expression
- pre-replay sampled signal vector
- frozen 134 registry signal vectors
- source lane metadata
- turnover / complexity / pathology proxy

Forbidden:

- candidate replay pass/fail
- candidate final deployable label
- candidate final signal cluster label

## Gate

Run selector-only dry run first:

- G2 overlap with G1 `< 85%`
- G3 overlap with G1 `< 80%`
- G2 selected-queue signal corr at least `20%` below G1
- G2 does not starve `agnostic_freeform_ast` or `formula_gen_v2_repair_expansion`

Only if this passes should Phase3G smoke be run.
