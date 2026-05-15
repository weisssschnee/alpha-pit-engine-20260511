# Phase3H Design Record

Date: 2026-05-15

## Decision

Phase3H is scoped as `G2 robustness and turnover calibration`.

It is not scoped as true book-residual selection.

Reason:

- Phase3H book-vector preflight returned `HOLD_TRUE_BOOK_SELECTOR`.
- Candidate cheap return-vector coverage is `0.0`.
- Registry return-vector coverage is `0.0`.
- Daily IC vector coverage is `0.0`.
- The registry metadata issue is handled by dual baseline, but true book residual still lacks data.

## Baselines

- discovery baseline: `134`
- selector vector baseline: `122`

The discovery baseline is used for cumulative historical accounting.

The selector vector baseline is used for signal-vector nearest-cluster/cap logic.

## Arms

### H0: G0 Stable Historical Control

```yaml
H0_G0_stable:
  profile: E0_D3_primary
```

Purpose:

- Keep the old stable line as a fresh-seed control.

### H1: G2 Signal-Vector Control

```yaml
H1_G2_signal_vector_control:
  profile: G2_signal_vector_diversified
  selector_vector_baseline: 122
  discovery_baseline: 134
```

Purpose:

- Validate G2 on fresh seeds under the accepted dual-baseline policy.

### H2: G2 Turnover Calibrated

```yaml
H2_G2_turnover_calibrated:
  profile: G2_signal_vector_diversified
  selector_vector_baseline: 122
  discovery_baseline: 134
  turnover_structure_risk: stronger
  target_median_turnover: 0.18-0.20
```

Purpose:

- Test whether G2's median turnover can be reduced from roughly `0.211` toward `0.18-0.20` without losing most of its deployable edge.

### H3: G2 Registry Canonicalized

```yaml
H3_G2_registry_canonicalized:
  profile: G2_signal_vector_diversified
  selector_vector_baseline: canonical_122
  discovery_baseline: 134
  strict_vector_cluster_cap: true
```

Purpose:

- Validate that the canonical 122-vector registry policy is stable and does not create new concentration artifacts.

## Initial Matrix

```text
seeds: 33,34,35,36
audited: 64 per arm per seed
total: 1024 audited
```

Smoke before official:

```text
H0/H1/H2/H3 x seed33 x 16 audited
```

## Pass Criteria

Minimum pass for any H1/H2/H3 arm:

- deployable clusters at least `H0 + 5`
- top cluster share at most `10%`
- median turnover at most `0.21`
- new deployable clusters vs discovery baseline >= `3 / 256`

Strong pass:

- deployable clusters at least `G2 historical - 3`
- top cluster share at most `8%`
- median turnover at most `0.20`

## Explicit Non-Goals

- Do not run H2 true book residual.
- Do not call G2 a true book-marginal selector.
- Do not use old sklearn rankers as promotion-grade selectors.
- Do not restart broad formula search.

## Future Track

True book residual selection moves to a later phase after a return-vector builder produces adequate registry and candidate vector coverage.
