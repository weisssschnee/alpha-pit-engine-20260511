# Phase3K Design Record - 2026-05-16

## Objective

Phase3K is locked book validation. It is not a formula search, selector bakeoff, or threshold tuning phase.

Phase3K splits two different questions:

- K-A: validate the existing locked books.
- K-B: validate whether the locked filter rules generalize to fresh G2 discovery output.

## Current State

- discovery primary: `G2_signal_vector_diversified`
- book-readiness baseline: `J2_filter_v1`
- book-readiness overlay: `J4_relaxed_filter_v1`
- locked artifact: `runtime/baselines/phase3j_locked_book_filters.json`
- locked hash: `111fdfdd54c168fff76b`

## K-A: Locked Existing Book Validation

K-A validates the current locked cluster lists without search and without reselecting clusters.

Compared books:

- K0: all G2 deployable clusters from Phase3J J0.
- K1: `J2_filter_v1`, 23 locked clusters.
- K2: `J4_relaxed_filter_v1`, 22 locked clusters.

The key question is not whether J4_relaxed massively beats J2. It cannot, because J4_relaxed is `J2_minus_cluster_087`.

The K-A question is:

Does removing `cluster_087` remain justified under book proxy, cost-stress proxy, turnover, concentration, liquidity/capacity, and available stability proxies?

If yes, J4_relaxed remains a hygiene overlay. If no, it is demoted to posthoc cleanup and J2 remains the main book-readiness baseline.

K-A outputs:

- `reports/phase3k_locked_book_validation_20260516/PHASE3K_A_LOCKED_BOOK_VALIDATION_2026-05-16.md`
- `reports/phase3k_locked_book_validation_20260516/phase3k_locked_book_validation.json`
- `reports/phase3k_locked_book_validation_20260516/phase3k_book_metrics.csv`
- `reports/phase3k_locked_book_validation_20260516/phase3k_cluster_members.csv`
- `reports/phase3k_locked_book_validation_20260516/phase3k_cluster_087_audit.csv`

## K-B: Locked Filter Generalization

K-B uses fresh G2 discovery output and applies locked rules without tuning.

Planned design:

- seeds: 47-50
- selector: G2 discovery primary
- audited: 64 per seed

For each seed:

- `J0_fresh`: all G2 deployable clusters.
- `J2_fresh`: apply locked J2 filter rule.
- `J4_fresh`: apply locked J4_relaxed rule.

K-B uses rules, not old cluster IDs. If it only reuses the old cluster list, it validates the old book but not filter generalization.

K-B is blocked until K-A is reviewed.

## Decision Boundaries

Do not do these in Phase3K:

- tune J4 thresholds
- start new formula search
- restart selector bakeoff
- call J4_relaxed a production book
- call cluster_087 removal a mature capacity model
- use K-A as live deployment evidence

## Bias Scope

Phase3K is still research validation.

Confirmed evidence can support book-readiness, not production deployment. Capacity, live fill, execution slippage, and live regime survival remain unconfirmed until explicitly tested.
