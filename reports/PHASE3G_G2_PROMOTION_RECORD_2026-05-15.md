# Phase3G G2 Promotion Record

Date: 2026-05-15

## Decision

Decision: `PROMOTE_G2_TO_PHASE3H_CONTROL`.

Promoted component:

- `G2_E3_signal_vector_diversified`

Promotion scope:

- Phase3H control.
- Primary signal-vector selector candidate.
- Pre-replay signal-cluster cap and selected-queue signal diversity.

Not promoted as:

- True book-marginal selector.
- Return-residual selector.
- Commercial deployment proof.

## Basis

Phase3G algorithmic decision: `PASS_CONFIRM_PHASE3G_ALGORITHMIC`.

Aggregate type: `fixed_mixed`.

G2 outcome:

- audited: `256`
- deployable clusters: `67`
- top cluster share: `4.9587%`
- median turnover: `0.211370`

Control comparison:

| Arm | Deployable | Top Cluster Share | Median Turnover |
| --- | ---: | ---: | ---: |
| G0 E0 stable | 54 | 18.2186% | 0.178381 |
| G1 E3 current proxy | 51 | 36.3281% | 0.126914 |
| G2 signal-vector diversified | 67 | 4.9587% | 0.211370 |
| G3 strong signal-vector proxy | 54 | 3.8627% | 0.222916 |

## Baseline Policy

Metadata policy: `DUAL_BASELINE_ACCEPTED`.

- discovery baseline: `134`
- selector vector baseline: `122`

Rationale:

- The declared cumulative accounting remains `134`.
- Only `122` clusters are independently vector-matchable after Phase3G signal-vector reclustering.
- Five declared clusters lack representative rows.
- Seven representative rows naturally merge under signal-vector reclustering.

G2 is allowed to proceed as a Phase3H signal-vector control under the selector vector baseline. True book residual remains blocked because cheap return vectors are not available.

## Confirmed

- Signal-vector proxy is materially better than symbolic/semantic proxy for pre-replay concentration control.
- G2 avoids the Phase3F failure mode where concentration migrated from `cluster_001` to `cluster_003`.
- G2 improves deployable yield while keeping top cluster concentration low.

## Not Confirmed

- True return-residual marginal value.
- Book construction.
- Capacity.
- Live execution.
- Commercial-grade robustness.

## Required Next Use

Phase3H should use G2 as the control arm for robustness and turnover calibration.

Phase3H must not run a true book-residual arm until cheap return-vector coverage exists for both registry representatives and candidates.
