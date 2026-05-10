# Phase2 Limit Filter Fix Correction

## What Changed

The stock-PIT validator now treats all-null limit flag columns as unavailable and falls back to `rt_change_pct`:

- `rt_change_pct >= 9.8` -> entry limit-up / unbuyable for long side
- `rt_change_pct <= -9.8` -> entry limit-down / unsellable for short side

This fixes a real bug in `maxopt`: `is_limit_up/is_limit_down` columns exist but contain no valid values.

## Scope Of Impact

- Candidate formulas remain useful discovery artifacts.
- Search-space memory can remain.
- Reward memory, strict pass, replay pass, A/B comparison, and commercial-readiness conclusions from pre-fix runs must be tagged `pre_limit_filter_fix`.
- Affected recent proof roots:
  - `phase2-stock-pit-p0-p3-proof-company-medium5-decilefix-20260510`
  - `phase2-stock-pit-p0-p3-proof-company-stockonly-rerun-20260510`

## Current Fixed Audit Baseline

For `CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1)))` on stock-only maxopt:

| case | RankIC | long Sortino | IC excluded by entry limits |
|---|---:|---:|---:|
| pre_open, T+1 | -0.007030 | 1.190268 | 9541 |
| after_open, T+1 | 0.028443 | 2.905181 | 9541 |
| after_open, same-day close proxy | 0.008098 | 0.760249 | 9752 |

## Next Action

Run `limit-fallback-fixed` P0/P1/P2/P3 and treat that as the new baseline.

## Fixed P0/P1/P2/P3 Result

- experiment_id: `phase2-stock-pit-p0-p3-proof-company-limitfix-20260510`
- status: completed on company PC, task result `0`
- output mirror: `runtime/next_stage_artifacts/phase2-stock-pit-p0-p3-proof-company-limitfix-20260510`
- limit filter source: active fallback from `rt_change_pct>=9.8` / `rt_change_pct<=-9.8`

Decision gates:

- `ucb_wins_strict`: false
- `current_rx_no_policy_beats_simple_and_typed_random_strict`: false
- `commercial_claim_allowed`: false
- algorithm gate: `HOLD_REWARD_AND_VALIDATION_REPAIR_IF_UCB_ONLY_WINS_FAST_NOT_STRICT`

P0 fast-screen summary:

| variant | mean reward | top reward | mean RankIC | mean long Sortino | strong IC | joint strong |
|---|---:|---:|---:|---:|---:|---:|
| rx_typed_beam_ucb | 0.069393 | 0.647138 | 0.003196 | 0.151888 | 0 | 0 |
| rx_typed_beam_no_policy | 0.129141 | 1.104823 | 0.004314 | 0.459607 | 0 | 0 |
| typed_random | 0.091730 | 1.072001 | 0.001223 | 0.373112 | 0 | 0 |
| unreached_space_only | -0.019513 | 1.012724 | 0.000602 | 0.106575 | 0 | 0 |
| simple_template_baseline | 0.077292 | 1.175295 | 0.000000 | 0.087557 | 0 | 0 |

P3 strict/replay summary:

| variant | strict pass | low-corr strict | replay pass | cost survival | family entropy | cluster entropy |
|---|---:|---:|---:|---:|---:|---:|
| rx_typed_beam_ucb | 3/7 | 2 | 0/7 | 3/7 | 0.796312 | 1.153742 |
| rx_typed_beam_no_policy | 3/7 | 1 | 0/7 | 5/7 | 1.945910 | 1.277034 |
| typed_random | 4/7 | 1 | 0/7 | 5/7 | 1.475076 | 1.153742 |
| unreached_space_only | 5/7 | 2 | 1/7 | 5/7 | 1.945910 | 1.153742 |
| simple_template_baseline | 5/7 | 5 | 1/7 | 6/7 | 1.549826 | 1.945910 |

P1 calibration:

- Deciles 1-8: strict pass 0/16.
- Decile 9: strict pass 2/2, cost survival 2/2.
- Decile 10: strict pass 1/2, cost survival 1/2.
- This is directionally useful but still too sparse to justify a learned reward/surrogate upgrade.

P2 cluster health:

- strict-audited rows: 35
- cluster_count: 17
- signal_cluster_entropy: 2.356613
- dominant cluster: `cluster_002`, 12/35 rows, budget share 0.342857.
- dominant representative: open-gap residualized by cap/liquidity/volatility style transforms.
- dominant cluster strict pass: 12/12.
- dominant cluster replay pass: 0/12.

Notable fixed strict/replay candidates:

- `CSRank($close)` replay-passed under the validator's after-open field-lag semantics, but it is a simple price-level baseline and should not be treated as commercial edge.
- `open_location_x_prior_close_location` replay-passed from unreached space, with strict RankIC 0.025047 and replay long-only Sortino 0.733446, but turnover is high at 0.994303.
- Open-gap residual families still strict-pass after the fix, with RankIC around 0.026-0.028, but most fail portfolio replay and have high turnover around 0.87-0.92.

## Corrected Interpretation

- The `opengap` family was not only a sector-panel artifact and is not a future function under `after_open`.
- The previous limit-filter bug was real and materially affected proof credibility.
- Formula/search-space memory can stay.
- Pre-fix reward memory, strict pass, replay pass, A/B comparisons, and commercial-readiness claims must stay tagged `pre_limit_filter_fix`.
- Fixed evidence does not prove UCB superiority. It argues for reward/validation repair and stronger portfolio replay gating before the next large search.

## 2026-05-11 Superseding Note

We found and connected a more precise local source: `TDXGP GPJYVALUE(15): limit-up/down status`.

- `value1 == 2` is now treated as true close locked limit-up.
- `value1 == -2` is now treated as true close locked limit-down.
- `rt_change_pct>=9.8` / `<=-9.8` remains only a fallback when TDXGP status is unavailable.

This makes the 2026-05-10 `rt_change_pct` fallback proof an intermediate repair stage, not the final tradability baseline. See `reports/PHASE2_TDXGP_LIMIT_STATUS_AUDIT_2026-05-11.md`.
