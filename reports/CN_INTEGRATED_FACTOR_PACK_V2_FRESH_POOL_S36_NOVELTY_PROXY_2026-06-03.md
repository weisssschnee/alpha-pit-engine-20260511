# CN Integrated Factor Pack V2 Fresh Pool S36 Novelty Proxy

Date: 2026-06-03

## Decision

`PASS_EXACT_EXPRESSION_NOVELTY_PROXY_HOLD_SIGNAL_CORR_NOVELTY`

This is a no-search, no-replay accounting check against the complete 149
representative registry.

## Scope

This audit only checks exact canonical expression overlap against:

`reports/phase3k_c_complete_149_registry_20260517/phase3k_c_149_representatives.csv`

It does **not** assert signal-corr `new_vs_149`. Signal-corr novelty still
requires vector/recluster comparison.

## Result

| metric | value |
| --- | ---: |
| audited rows | 19 |
| raw replay pass | 14 |
| cost survive | 10 |
| deployable row proxy | 7 |
| exact duplicate vs 149 | 0 |
| exact new vs 149 | 7 |

The Phase3 replay report counted `8` deployable clusters. This lightweight
expression audit uses a row-level deployable proxy and therefore reports `7`
deployable rows. The difference should not be interpreted as a cluster-count
disagreement.

## Interpretation

The fresh-pool integrated candidates are not exact repeats of the 149
representative formulas. This supports continuing the RZRQ-normalized /
quality-x-RZRQ research lane.

Promotion remains blocked because exact expression novelty is weaker than
signal-corr novelty. The next novelty gate should use signal-vector nearest
registry comparison or replay-cluster reclustering.

## Outputs

- `reports/cn_integrated_factor_pack_v2_fresh_pool_s36_novelty_proxy_20260603/fresh_pool_s36_exact_novelty_proxy.json`
- `reports/cn_integrated_factor_pack_v2_fresh_pool_s36_novelty_proxy_20260603/fresh_pool_s36_exact_novelty_proxy.csv`
