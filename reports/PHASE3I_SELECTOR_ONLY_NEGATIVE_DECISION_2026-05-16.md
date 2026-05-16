# Phase3I Selector-Only Negative Decision

- decision: `HOLD_PHASE3I_SMOKE`
- scope: selector-only, no replay
- seed: `41`
- shared pool: `D:\p3i_selector_only_20260516\s41\shared_candidate_pool.json`
- discovery baseline: `149`
- selector vector baseline: `137`

## Result

Feature preflight passed, but selector-only dry run failed the smoke gate.

| arm | selected | median turnover proxy | p90 turnover proxy | mean selected-queue signal corr |
| --- | ---: | ---: | ---: | ---: |
| I0 G2 primary | 64 | 0.066093 | 0.117566 | 0.440209 |
| I1 cost/turnover constrained | 64 | 0.068233 | 0.127073 | 0.487729 |
| I2 capacity/liquidity | 64 | 0.066728 | 0.120072 | 0.477701 |
| I3 book-proxy hardened | 64 | 0.067250 | 0.125580 | 0.457424 |

## Blocking Findings

- I1 failed its purpose: p90 turnover proxy increased instead of decreasing.
- I3 failed its purpose: selected-queue signal correlation increased instead of decreasing.
- I2 has sufficient liquidity/capacity feature coverage, but the queue is too close to I0 and does not improve turnover or signal-corr metrics.
- No replay-label leakage was reported by selector audit.

## Decision

Do not run Phase3I smoke from this selector-only output.

Required next actions:

1. Run selector delta audit for I1/I3/I2 versus I0.
2. Calibrate pre-replay turnover proxy against historical final strict/replay turnover.
3. Implement I1 tail-turnover guard only if the proxy is useful.
4. Implement I3 selected-queue diversity-first only if delta audit confirms score-scale or priority failure.

