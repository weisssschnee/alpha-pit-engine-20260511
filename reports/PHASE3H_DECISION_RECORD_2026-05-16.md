# Phase3H Decision Record

Date: 2026-05-16

## Decision

Decision: `PASS_CONFIRM_PHASE3H_G2_DISCOVERY_PRIMARY`

Scope:

- Promote `H1_G2_signal_vector_selector` as the primary selector for diversified discovery.
- Do not promote it as a true book-marginal selector.
- Do not promote it as a production/live alpha system.
- Reject `H2_G2_turnover_calibrated` as a separate production candidate.

## Evidence

Execution:

- run root: `D:\p3h_official_20260516`
- official arm-level aggregate: `D:\p3h_official_20260516\aggregate`
- global recluster output: `D:\p3h_official_20260516\global_recluster`
- dataset: `D:\HermesWorker\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- seeds: `33,34,35,36`
- official replay arms: `H0,H1,H2`
- H3: selector-only parity, no replay
- audited rows: `768`
- execution path: `shared_candidate_pool -> frozen selection -> strict/replay/cluster`
- discovery baseline: `134`
- selector vector baseline: `122`
- ranker policy: `diagnostic_only`
- proof suite: `scalar-turnover-fixed-2026-05-16`

Arm-level official aggregate:

| Arm | Audited | Deployable | Raw non-gap | Raw/deployable | Top cluster max | Median replay turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 stable | 256 | 43 | 114 | 2.6512 | 52.00% | 0.351537 |
| H1 G2 | 256 | 45 | 70 | 1.5556 | 12.50% | 0.380784 |
| H2 turnover-calibrated | 256 | 43 | 73 | 1.6977 | 21.05% | 0.365893 |

Global recluster aggregate:

| Arm | Audited | Deployable clusters | Raw non-gap | Unique signal clusters | Top cluster share | Median turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 stable | 256 | 29 | 114 | 39 | 42.1053% | 0.081663 |
| H1 G2 | 256 | 34 | 70 | 50 | 8.5714% | 0.137688 |
| H2 turnover-calibrated | 256 | 33 | 73 | 48 | 15.0685% | 0.140328 |

Global union:

- audited: `768`
- global unique signal clusters: `55`
- global deployable clusters: `37`
- new deployable clusters vs cumulative 134 baseline: `15`
- discovery cumulative baseline after Phase3H: `149`
- raw non-gap pass: `257`
- global top cluster id: `cluster_006`
- global top cluster share: `25.2918%`
- cluster label scope: `global_reclustered_across_replay_relevant_completed_phase3_rows_plus_phase2_r0_baseline`
- seed-local labels ignored: `true`

## Interpretation

`H1_G2_signal_vector_control` is not a pure yield lift on arm-level deployable count. It is a diversification and decongestion lift:

- deployable clusters improve from `29` to `34` in global recluster accounting.
- unique signal clusters improve from `39` to `50`.
- top cluster share falls from `42.1053%` to `8.5714%`.
- raw non-gap pass falls from `114` to `70`, while deployable rises, meaning raw repetition is reduced.

This matches the Phase3G diagnosis:

- symbolic/semantic proxy diversity was insufficient.
- signal-vector proxy diversity better observes pre-replay cluster collision.
- G2 should be used for diversified discovery, not as a true book-marginal selector.

`H2_G2_turnover_calibrated` is not independently useful:

- deployable clusters are below H1: `33` vs `34`.
- top cluster share is worse: `15.0685%` vs `8.5714%`.
- H1/H2 deployable Jaccard is `0.970588`.
- turnover improvement is not enough to justify a separate production candidate.

## Decision Fields

Promoted:

- primary_discovery_selector:
  - arm: `H1_G2_signal_vector_selector`
  - deployable_clusters: `34`
  - raw_non_gap: `70`
  - unique_clusters: `50`
  - top_cluster_share: `0.086`

Legacy control:

- arm: `H0_stable`
- deployable_clusters: `29`
- top_cluster_share: `0.421`

Not promoted:

- `H2_turnover_calibrated`
  - only small turnover improvement
  - deployable not better than H1
  - concentration worse than H1
  - high overlap with H1

Scope confirmed:

- signal_vector_diversified_discovery
- shared_pool_frozen_selection_execution
- low_concentration_cluster_discovery

Scope not confirmed:

- true_book_marginal
- return_residual_selector
- production_ready_trading
- capacity_validated_alpha_book

Baseline policy:

- discovery_baseline: `149`
- selector_vector_baseline: estimated `137` after adding 15 Phase3H vector-matchable clusters; do not assume `149`.
- representative_rows: `144`
- missing_representatives_carried_forward: `5`

## Bias And Evidence Limits

Bias decision: `HOLD_RESEARCH`

This Phase3H result is search-method evidence, not commercial alpha evidence.

Known limits:

- true book residual selector is not active.
- cheap return-vector coverage remains insufficient for true book-marginal selection.
- no live trading evidence.
- no capacity proof.
- no final cost/slippage/execution proof beyond current strict/replay assumptions.
- no promotion-grade survivorship/corporate-action audit in this record.

Clock/alignment carried from strict runs:

- true-limit evaluator
- after-open signal contract
- T+1 replay execution contract
- ranker policy is `diagnostic_only`

## Final Status

Promoted:

- `G2 signal-vector diversified selector`
  - status: `diversified_discovery_primary`
  - not status: `production_primary`
  - not status: `true_book_marginal`

Rejected:

- `H2 turnover-calibrated`
  - reason: too close to H1 and worse concentration.

Retained:

- `H0 stable`
  - status: historical control / fallback comparator.

Next phase:

- Do not continue broad formula search immediately.
- Do not revive H2 as production.
- Do not claim true book marginal.
- Start Phase3I as G2 deployment hardening / book-readiness:
  - run G2 cluster anatomy audit,
  - run turnover/cost/capacity audit,
  - run G2 vs H0 marginal audit,
  - keep shared-pool frozen-selection execution as the official path.
