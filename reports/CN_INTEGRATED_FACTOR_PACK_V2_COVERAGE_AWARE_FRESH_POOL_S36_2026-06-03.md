# CN Integrated Factor Pack V2 Coverage-Aware Fresh Pool S36

Date: 2026-06-03

## Decision

`PASS_TRUE_FRESH_POOL_CANARY_HOLD_PROMOTION`

This run rebuilt a mature Phase3I/G2 shared candidate pool from scratch, then
injected the fixed coverage-aware v2 integrated factor pack. Unlike the seed35
parity run, this produced a genuinely different integrated-feature queue.

## Fresh Pool Construction

| item | value |
| --- | ---: |
| source arm | `Phase3I_I0_G2_primary` |
| seed | `36` |
| candidate budget | 96 |
| strict audit budget | 64 |
| raw shared pool candidates | 484 |
| fixed coverage-aware v2 rows injected | 294 |
| enriched pool candidates | 778 |
| raw pool generation elapsed | about 2h 11m |

The mature raw-pool generation path is expensive because it runs the native
multi-lane Phase3 generation and signal-vector selector preparation before the
integrated factor pack is injected.

## Queue Delta Versus Base Coverage-Aware Run

| metric | value |
| --- | ---: |
| base integrated selected | 19 |
| fresh-pool integrated selected | 19 |
| overlap | 12 |
| union | 26 |
| jaccard | 0.4615 |
| fresh-only candidates | 7 |
| base-only candidates | 7 |

This passes the fresh queue-difference gate. Replay was therefore justified.

## Replay Result

| metric | base coverage-aware | fresh-pool s36 |
| --- | ---: | ---: |
| audited | 19 | 19 |
| raw non-gap replay pass | 16 | 14 |
| cost survive | 12 | 10 |
| deployable clusters | 10 | 8 |
| deployable / audited | 52.63% | 42.11% |
| top cluster share | 6.25% | 7.14% |
| unique return-corr clusters | 14 | 14 |
| median replay sortino | -0.126466 | -0.391947 |
| median turnover | 0.573237 | 0.579617 |

## Lane Attribution

| factor lane | audited | raw pass | cost survive | median replay sortino |
| --- | ---: | ---: | ---: | ---: |
| rzrq_size_normalized | 15 | 11 | 9 | -0.391947 |
| quality_x_rzrq_flow | 2 | 1 | 1 | 5.243003 |
| minute_amount_share_daily | 2 | 2 | 0 | -4.488697 |

## Strong Candidate Examples

| expression | lane | replay sortino | strict cost sortino | turnover |
| --- | --- | ---: | ---: | ---: |
| `CSRank(Div($ctx_rzrq_rzche,Add(Abs($amount),0.000001)))` | rzrq_size_normalized | 20.333583 | 2.091783 | 0.694942 |
| `CSRank(Div($ctx_rzrq_rzjme5d,Add(Abs($amount),0.000001)))` | rzrq_size_normalized | 13.295636 | 14.959325 | 0.563370 |
| `CSRank(Mul(ZScore($ctx_fund_bs_cash_to_assets),ZScore($ctx_rzrq_rzjme)))` | quality_x_rzrq_flow | 11.236184 | 8.729872 | 0.775000 |

## Interpretation

The true fresh-pool canary weakens the headline count versus the first
coverage-aware smoke, but it still supports the main technical conclusion:

- the RZRQ normalized-by-liquidity/size axis is real enough to survive a fresh
  mature-chain raw pool;
- quality x RZRQ flow remains a secondary high-upside interaction lane;
- direct minute amount share is still not cost robust;
- direct fundamental quality is not selected under the disciplined pool cap.

The result does not justify promotion. It does justify keeping the
coverage-aware integrated factor pack as an active research lane.

## Blockers Before Promotion

- `new_vs_149` is not yet audited for these fresh-pool deployable clusters.
- marginal value versus locked `X0/R3` is not yet audited.
- current validation uses the same date panel, not a fresh date range.
- mature raw-pool generation took about two hours for one seed; progress logging
  after `stage1_variant_reports_written` is too coarse.

## Next Gate

Run a no-search novelty and marginal audit on the fresh-pool candidates:

1. map fresh deployable clusters to the 149 discovery registry;
2. test marginal daily-proxy value versus locked `X0/R3`;
3. only then decide whether to run a second true fresh-pool seed.
