# Phase3 Ranker Reproducibility Policy

Date: 2026-05-15

## Decision

Decision: `RANKER_V1_DIAGNOSTIC_ONLY_FOR_PHASE3H_PROMOTION`.

The current replay ranker artifacts are allowed for:

- Backward-compatible diagnostics.
- Historical report reproduction.
- Non-promotional comparison.

They are not allowed for:

- Phase3H promotion-grade selector decisions.
- Claims that a selector has passed a reproducible production gate.

## Reason

The company-machine manifest found sklearn version drift:

- runtime sklearn: `1.8.0`
- ranker artifacts include older sklearn metadata warnings from `1.6.1`
- model manifest decision: `HOLD_REPRODUCIBILITY`

Loading old sklearn artifacts under a newer runtime can be acceptable for diagnostics, but it is not a clean basis for a new selector promotion.

## Required Standard for Promotion-Grade Ranker Use

A Phase3H promotion-grade ranker must include:

- sklearn version
- numpy version
- pandas version
- feature schema hash
- training data hash
- label definition
- training row count
- label distribution
- AUC / AP or equivalent ranking lift
- top-decile lift
- model SHA256

## Refit Policy

If historical training rows and labels are available, create `ranker_v2` under the current runtime environment.

If the training data is incomplete, do not fake a refit by loading and re-dumping old joblib files. In that case, keep old rankers as `diagnostic_only` and exclude them from Phase3H promotion-grade selection.

## Phase3H Impact

G2 promotion is not blocked by this policy because G2's core improvement is signal-vector diversity, not ranker promotion.

True book or replay-aware selector promotion remains blocked until reproducible model artifacts exist or the selector is proven without those rankers.
