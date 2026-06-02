# CN Underutilized Field Book Readiness Decision - 2026-06-01

decision: `PASS_BOOK_READINESS_AUDIT_READY`

## Scope

No-replay book-readiness screen for the `13` newly promoted discovery clusters in `cn_discovery_baseline_162_20260601`.

This audit does not rerun strict replay, does not change the baseline, and does not prove production readiness. It screens the new clusters for turnover, strict cost-adjusted strength, long-side liquidity/capacity proxy, and limit/suspension exposure.

## Result

- new clusters audited: `13`
- errors: `0`
- book-readiness candidates: `6`
- watch candidates: `7`
- research-only high risk: `0`
- missing replay metrics: `0`

## Aggregate Metrics

- median strict turnover: `0.136363`
- p90 strict turnover: `0.288182`
- median strict cost-adjusted sortino: `1.389663`
- median long-selected amount: `3,061,652,736`
- median long-selected float mcap: `83,793,072,586`
- median long-selected limit/susp rate: `0.0`

## Core Book-Readiness Candidates

- `cluster_090`: `fundamental_x_activity`, turnover `0.125682`, sortino `5.429641`
- `cluster_011`: `fundamental_risk_inverse`, turnover `0.064204`, sortino `3.895127`
- `cluster_024`: `fundamental_quality`, turnover `0.117614`, sortino `2.672103`
- `cluster_031`: `fundamental_risk_inverse`, turnover `0.167749`, sortino `2.439269`
- `cluster_029`: `fundamental_risk_inverse`, turnover `0.136363`, sortino `1.994263`
- `cluster_028`: `fundamental_quality`, turnover `0.152841`, sortino `1.389663`

## Watch Candidates

- `cluster_089`: high sortino but higher turnover, watch
- `cluster_038`: useful but higher turnover, watch
- `cluster_088`: low turnover but weaker sortino, watch
- `cluster_086`: low turnover but weaker sortino, watch
- `cluster_084`: moderate turnover and weak sortino, watch
- `cluster_039`: low turnover but weak sortino, watch
- `cluster_091`: moderate turnover and weak sortino, watch

## Interpretation

The `13` new discovery clusters are not merely novelty artifacts. Six have enough turnover/cost/liquidity profile to be treated as book-readiness candidates for the next validation layer. The remaining seven should stay in a watch bucket until book marginality, stability, and source-family concentration are checked.

The strongest axis is fundamental risk/quality plus activity interaction:

- `fundamental_risk_inverse`
- `fundamental_quality`
- `fundamental_x_activity`

Direct limit/event remains absent from the core candidates in this slice.

## Not Confirmed

- production readiness;
- minute execution;
- true slippage;
- true capacity;
- live/paper survival;
- book-level marginal value.

## Next Gate

Run a small no-search book construction audit:

1. `B0`: existing X0/R3 / current official book reference;
2. `B1`: six core new clusters only;
3. `B2`: X0/R3 plus six core new clusters;
4. `B3`: thirteen new clusters with source/factor caps.

The next decision should use book-level marginal value, not standalone cluster sortino.

## Artifacts

- `reports/cn_underutilized_field_book_readiness_20260601/CN_UNDERUTILIZED_FIELD_BOOK_READINESS_2026-06-01.md`
- `reports/cn_underutilized_field_book_readiness_20260601/cn_underutilized_field_book_readiness.json`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_rows.csv`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_shortlist.json`
- `reports/cn_underutilized_field_book_readiness_20260601/book_readiness_errors.csv`
