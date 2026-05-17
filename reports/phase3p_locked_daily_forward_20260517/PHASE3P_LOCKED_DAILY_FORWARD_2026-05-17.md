# Phase3P Locked Daily Forward

- decision: `PASS_PHASE3P_LOCKED_DAILY_FORWARD_EXPORTED`
- data_date: `2026-05-08`
- gate_version: `phase3o_r3_liquidity_low_2025h2_q33_v1`
- gate_active: `False`
- git_commit: `aacc60c`

## Profiles

| profile | status | active/cash | signals | positions | pnl status | realized proxy | no-gate proxy | missed return |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |
| x0_official6_r3_liquidity_low | formal_candidate_shadow | cash | 0 | 0 | pending_next_trade_date | None | None | None |
| x4_plus003_minus002_r3_liquidity_low | research_candidate_shadow_diagnostic | cash | 0 | 0 | pending_next_trade_date | None | None | None |

## Boundaries

- X0 is the formal locked daily shadow.
- X4 is diagnostic-only.
- PnL is a daily proxy and is pending when no next trade date exists in the input dataset.
- This is not production execution, slippage, capacity, or live survival evidence.
