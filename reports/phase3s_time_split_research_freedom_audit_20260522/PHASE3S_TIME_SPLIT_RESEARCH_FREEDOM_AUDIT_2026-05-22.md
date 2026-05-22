# Phase3S Time-Split / Research-Freedom Audit

- decision: `PASS_TIME_SPLIT_AUDIT_WITH_LOCKED_FORWARD_REQUIRED`
- object_id: `X0_official_6_R3_liquidity_low_v1`
- scope: no search, no retraining, no formula/gate/weight changes.

## Evidence Labels

| slice | label |
| --- | --- |
| `train_2025h2` | development/gate-training window |
| `oos_2026` | recent-OOS relative to 2025H2 gate training; research-touched relative to full project |
| `locked_forward_after_2026_05_17` | highest-grade future OOS if append-only and no rule changes |

## Current Official Object

- official_clusters: `001 / 005 / 006 / 009 / 002 / 004`
- 2026 full-calendar annualized: `117.57%`
- 2026 active-day annualized diagnostic: `391.84%`
- 2026 active ratio: `48.72%`
- 2026 max drawdown: `-3.44%`

## Gate Train vs Recent-OOS

| gate/window | full ann compound | active ann compound | active ratio |
| --- | ---: | ---: | ---: |
| R0 train_2025h2 | `30.96%` |  |  |
| R0 oos_2026 | `72.92%` |  |  |
| R3 train_2025h2 | `14.95%` |  |  |
| R3 oos_2026 | `117.57%` | `391.84%` | `48.72%` |

Interpretation: `oos_2026` is valid recent-OOS relative to the 2025H2 gate-training window, but it is research-touched relative to the whole project. It must not be treated as an untouched final test.

## Stage Accounting

| stage | sample use | dates | boundary |
| --- | --- | --- | --- |
| formula_search_and_cluster_discovery | `research_touched_development` | 2025-08-06..2026-05-08 | Not an untouched test because multiple iterations inspected recent 2026 outcomes. |
| gate_selection | `train_validation_split_with_research_touch` | train=2025H2; validation=2026 historical slice | 2026 is OOS relative to the 2025H2 gate training window, but not untouched relative to the full research process. |
| daily_proof_book_freeze | `research_touched_recent_oos_proof` | 2025H2+2026 through 2026-05-08 | Valid L2.5 daily proof; not production or untouched holdout proof. |
| cloud_shadow_deployment | `locked_forward_infrastructure` | starts after 2026-05-17 freeze | This becomes the highest-quality OOS only after accumulating active days without rule changes. |

## Limit Diagnostic Status

- decision: `HOLD_DIRECT_LIMIT_DIAGNOSTIC_NO_SMOKE_PASS`

| role | evaluated | pass smoke | promoted | best rank IC | best long sortino |
| --- | ---: | ---: | ---: | ---: | ---: |
| event_factor | 24 | 0 | 0 | 0.010892 | 0.425403 |
| interaction_factor | 24 | 0 | 0 | -0.001329 | 1.922721 |

## Allowed Next Research

- R3-on regime-specific search using existing historical data only as research-touched development.
- Limit interaction diagnostic lane remains allowed, but only as diagnostic and with lag/tradability checks.
- Book-marginal selector work may proceed only if it does not use locked-forward outcomes for tuning.

## Blocked Actions

- Do not call 2026 historical results untouched OOS.
- Do not use locked-forward observations to tune X0/R3, J2/J4, or diagnostic profiles.
- Do not promote X4/oracle based on historical performance alone.
- Do not retrain mainline solely because limit diagnostics exist; current limit smoke has zero promoted candidates.

## Practical Conclusion

Continue alpha research, but treat 2026 historical performance as research-touched recent-OOS. The next clean evidence layer is locked-forward shadow after the X0/R3 freeze. New searches may use historical data for research, but they must not consume locked-forward observations for tuning.
