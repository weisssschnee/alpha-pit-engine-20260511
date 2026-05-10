# Phase2 TDXGP True-Limit P0/P3 Results

## Experiment

- experiment_id: `phase2-stock-pit-p0-p3-proof-company-tdxgp-limit-20260511`
- status: completed on company PC, task result `0`
- output mirror: `runtime/next_stage_artifacts/phase2-stock-pit-p0-p3-proof-company-tdxgp-limit-20260511`
- dataset: `phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet`
- limit source: `TDXGP GPJYVALUE(15)` sidecar, `value1==2/-2`
- fallback: `rt_change_pct>=9.8` / `<=-9.8` only when TDXGP status is absent

## Decision Gates

- `ucb_wins_strict`: false
- `current_rx_no_policy_beats_simple_and_typed_random_strict`: false
- `commercial_claim_allowed`: false
- algorithm gate: `HOLD_REWARD_AND_VALIDATION_REPAIR_IF_UCB_ONLY_WINS_FAST_NOT_STRICT`

## P0 Fast Screen

| variant | mean reward | top reward | mean RankIC | mean long Sortino | strong IC | joint strong |
|---|---:|---:|---:|---:|---:|---:|
| rx_typed_beam_ucb | 0.027663 | 0.632045 | 0.003095 | 0.051178 | 0 | 0 |
| rx_typed_beam_no_policy | 0.058658 | 0.975977 | 0.002966 | 0.358054 | 0 | 0 |
| typed_random | -0.011461 | 0.902742 | 0.000057 | 0.149398 | 0 | 0 |
| unreached_space_only | -0.085209 | 0.823536 | 0.000512 | -0.052564 | 0 | 0 |
| simple_template_baseline | 0.035294 | 1.113727 | 0.000000 | -0.005134 | 0 | 0 |

## P3 Strict And Replay

| variant | strict pass | low-corr strict | replay pass | cost survival | family entropy | cluster entropy |
|---|---:|---:|---:|---:|---:|---:|
| rx_typed_beam_ucb | 2/7 | 2 | 0/7 | 3/7 | 0.796312 | 0.955700 |
| rx_typed_beam_no_policy | 2/7 | 1 | 0/7 | 4/7 | 1.747868 | 1.549826 |
| typed_random | 3/7 | 1 | 0/7 | 3/7 | 1.277034 | 1.475076 |
| unreached_space_only | 4/7 | 2 | 1/7 | 4/7 | 1.945910 | 1.153742 |
| simple_template_baseline | 4/7 | 4 | 1/7 | 5/7 | 1.475076 | 1.945910 |

## P1 Calibration

- Deciles 1-9: strict pass 0/18 except cost survival appears once in decile 9.
- Decile 10: strict pass 2/2, cost survival 2/2.
- Portfolio replay pass remains 0 across the decile calibration sample.
- Interpretation: fast reward has some top-decile signal, but it is too sparse and not replay-calibrated enough for learned surrogate/RL reward escalation.

## P2 Cluster Health

- strict-audited rows: 35
- cluster_count: 18
- signal_cluster_entropy: 2.526041
- dominant cluster: `cluster_002`, 10/35 rows, budget share 0.285714
- dominant representative: open-gap residualized by cap/liquidity/volatility transforms
- dominant cluster strict pass: 9/10
- dominant cluster replay pass: 0/10

## Notable Survivors

- `CSRank($close)` replay-passed with strict RankIC 0.014278 and replay long-only Sortino 1.409699. This is a simple price-level baseline, not a new commercial alpha claim.
- `open_location_x_prior_close_location` from unreached space replay-passed with strict RankIC 0.023464 and replay long-only Sortino 0.547666, but one-way turnover is 0.993939.
- Open-gap residual families still strict-pass with RankIC around 0.023-0.026, but portfolio replay is mostly negative and turnover remains around 0.89-0.93.

## Interpretation

- The algorithm-layer conclusion is unchanged: current UCB/reward memory is not proven superior to baseline.
- The true-limit filter makes the evidence stricter: stage1 rewards, strict pass, and opengap headline metrics all weaken.
- The system's useful discovery signal currently appears more in unreached-space coverage and simple baselines than in UCB exploitation.
- Reward must be repaired around replay/cost/turnover/cluster contribution before another large search, otherwise the system will over-select strict-only gap variants that do not survive portfolio replay.

## Decision

HOLD_RESEARCH.

Next recommended action: make replay-adjusted reward the primary promotion objective for the next medium search, with cluster cap and random pass-through retained. Do not run a huge search on the old reward.
