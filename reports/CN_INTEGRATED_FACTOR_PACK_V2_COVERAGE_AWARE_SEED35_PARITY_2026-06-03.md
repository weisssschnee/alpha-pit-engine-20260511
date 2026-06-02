# CN Integrated Factor Pack V2 Coverage-Aware Seed35 Parity

Date: 2026-06-03

## Decision

`HOLD_FRESH_SEED_CLAIM_QUEUE_PARITY`

This run changed the selector seed from `integrated_v2_coverage_seed34` to
`integrated_v2_coverage_seed35`, but the selected integrated-feature queue was
identical.

## Queue Comparison

| metric | value |
| --- | ---: |
| seed34 selected integrated candidates | 19 |
| seed35 selected integrated candidates | 19 |
| overlap | 19 |
| jaccard | 1.0000 |

## Seed35 Replay Result

| metric | value |
| --- | ---: |
| audited | 19 |
| raw non-gap replay pass | 16 |
| cost survive | 12 |
| deployable clusters | 10 |
| top cluster share | 6.25% |
| median replay sortino | -0.126466 |
| median turnover | 0.573237 |

## Lane Attribution

| factor lane | audited |
| --- | ---: |
| rzrq_size_normalized | 15 |
| quality_x_rzrq_flow | 3 |
| minute_amount_share_daily | 1 |

## Interpretation

The coverage-aware selector result is stable, but this seed change is not a
valid fresh-seed validation because it did not change the selected queue. The
correct next validation must rebuild or perturb the candidate pool, not only
change the selector seed.

## Next Gate

Run a true fresh-pool validation:

- rebuild shared candidate pool with fresh generation seed or expanded source pool;
- keep `cn_integrated_feature_factor_candidate_pack_v2_coverage_aware_20260603`
  fixed;
- require queue overlap with the seed34 queue below 85% before replay;
- then run replay/new-vs-149/marginal-vs-X0 audit.
