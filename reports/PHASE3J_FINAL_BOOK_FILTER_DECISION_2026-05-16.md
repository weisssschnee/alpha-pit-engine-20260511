# Phase3J Final Book Filter Decision - 2026-05-16

## Decision

`PASS_PHASE3J_BOOK_FILTER_DISCOVERY`

Phase3J is closed as a cluster-level book-readiness audit. The result is not a production deployment proof. It freezes two filters for forward validation:

- `J2_filter_v1`: baseline book-readiness candidate.
- `J4_relaxed_filter_v1`: liquidity-aware overlay candidate.

No further `amount / capacity / limit` threshold tuning is allowed before Phase3K.

## Locked Filters

### J2 Filter V1

- role: baseline book-readiness candidate
- cluster count: 23
- p90 turnover: 0.276502
- max raw share: 12.90%
- median capacity proxy: 23.90M
- equal-weight cost-adjusted proxy: 1.758840
- status: locked for Phase3K forward validation

### J4 Relaxed Filter V1

- role: liquidity-aware overlay candidate
- cluster count: 22
- relation to J2: `J2_minus_cluster_087`
- p90 turnover: 0.278967
- max raw share: 13.33%
- median capacity proxy: 24.33M
- equal-weight cost-adjusted proxy: 1.840207
- status: locked for Phase3K forward validation

Locked J4 relaxed thresholds:

- amount bottom quantile: 0.05
- capacity bottom quantile: 0.05
- gate mode: reject only when both amount and capacity are below threshold
- max limit hit rate: 0.20
- max suspension rate: 0.01

## Removed Cluster

J4 relaxed removes exactly one J2 cluster:

- cluster: `cluster_087`
- source lane: `r0_cem_led`
- capacity proxy: 3.71M
- cost-adjusted score: -0.031224
- representative expression: `Neg(CSRank(CSResidual(CSRank(Mean(Abs($amount),8)),CSRank(Mean(Abs($amount),21)))))`

This supports J4 relaxed as a hygiene overlay, not a separate mature book model.

## Stability Evidence

- J2/J4 relaxed overlap: 22/23
- J4 relaxed additions: 0
- sensitivity variants passing gate: 129/216
- local plateau pass: 18/18
- near-best variants: 24

The relaxed filter is not a single-parameter accident, but its improvement is narrow. It should be validated forward, not tuned further.

## Demoted

### Original J4

Original J4 is demoted.

Reason: over-filtered. It reduced the book to 15 clusters and retained only 44.12% of G2 deployable clusters, which is too aggressive for the current evidence level.

## Confirmed

- G2 should remain discovery primary.
- Candidate-level turnover pre-filtering damaged discovery efficiency.
- Cluster-level filtering is the right place to handle turnover and book-readiness.
- J2 is the baseline book-readiness candidate.
- J4 relaxed is a retained liquidity-aware overlay candidate.

## Not Confirmed

- mature capacity model
- production book
- execution fill model
- live slippage / liquidity survival
- commercial deployment readiness

## Frozen Artifact

- locked filter JSON: `runtime/baselines/phase3j_locked_book_filters.json`
- filter version: `phase3j_locked_book_filters_v1_20260516`
- filter version hash: `111fdfdd54c168fff76b`

## Next Phase

`Phase3K_locked_book_validation`

Use fresh G2 discovery outputs and apply fixed filters without tuning:

- K0: G2 discovered clusters -> no book filter / J0 reference
- K1: G2 discovered clusters -> `J2_filter_v1`
- K2: G2 discovered clusters -> `J4_relaxed_filter_v1`

Primary Phase3K question:

Can J4 relaxed repeatedly remove low-quality clusters without sacrificing useful clusters, compared with J2, on fresh G2 outputs?
