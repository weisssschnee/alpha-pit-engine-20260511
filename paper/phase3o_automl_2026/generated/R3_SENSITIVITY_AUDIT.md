# R3 Liquidity Threshold Sensitivity Audit

- scope: paper hygiene diagnostic; locked R3 is unchanged.
- train window: `2025-07-01` to `2025-12-31`
- OOS window: `2026-01-01` to `2026-05-08`
- random active-day placebo draws: `1000`

| threshold | active ratio | full ann | sharpe | max DD | random p95 | placebo decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| q25 | 0.128205 | 0.435259 | 4.17047 | -0.00259208 | 0.35567 | PASS_TRUE_GT_RANDOM_P95 |
| q30 | 0.230769 | 0.599803 | 3.972418 | -0.01576915 | 0.552589 | PASS_TRUE_GT_RANDOM_P95 |
| q33 | 0.487179 | 1.175657 | 4.547115 | -0.03442312 | 0.837281 | PASS_TRUE_GT_RANDOM_P95 |
| q35 | 0.512821 | 1.124614 | 4.370534 | -0.04156776 | 0.906951 | PASS_TRUE_GT_RANDOM_P95 |
| q40 | 0.576923 | 0.969264 | 3.644568 | -0.04918273 | 0.957589 | PASS_TRUE_GT_RANDOM_P95 |

## Boundary

This table checks nearby threshold robustness. It is not permission to retune R3; the official gate remains `R3_liquidity_low_v1`.
