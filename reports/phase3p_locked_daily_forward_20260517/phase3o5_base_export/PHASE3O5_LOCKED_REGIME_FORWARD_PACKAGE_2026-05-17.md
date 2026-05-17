# Phase3O5 Locked Regime Forward Package

- decision: `PASS_LOCKED_REGIME_FORWARD_PACKAGE_CREATED`
- signal_date: `2026-05-08`
- gate: `R3_liquidity_low`
- gate_active: `False`
- liquidity_ratio_lag1: `1.073815504740658`
- threshold: `0.9888283511695009`

## Profiles

| profile | status | clusters | gate active | signal rows | positions | gross long | gross short | net |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| x0_official6_r3_liquidity_low | formal_candidate_shadow | 6 | False | 0 | 0 | 0.0 | 0.0 | 0.0 |
| x4_plus003_minus002_r3_liquidity_low | research_candidate_shadow_diagnostic | 6 | False | 0 | 0 | 0.0 | 0.0 | 0.0 |

## Boundaries

- X0 is the formal candidate shadow profile.
- X4 is a research/diagnostic profile and does not replace the formal proof book.
- Gate off writes explicit flat positions; gate on writes long/short shadow target weights.
- This package is append-only shadow infrastructure; it does not execute trades.
