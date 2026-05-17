# Phase3O Regime-Gated Shadow Decision Record

- decision: `PASS_REGIME_GATED_DAILY_SHADOW_PROOF`
- evidence_level: `daily_regime_gated_shadow_no_execution`
- final_scope: `locked_daily_shadow_forward`
- primary_gate: `R3_liquidity_low`

## Official Shadow

```yaml
name: X0_official_6_R3_liquidity_low
clusters:
  - cluster_001
  - cluster_005
  - cluster_006
  - cluster_009
  - cluster_002
  - cluster_004
gate: R3_liquidity_low
```

Evidence:

```yaml
2026_full_calendar_annualized: 117.57%
sharpe: 4.55
max_drawdown: -3.44%
active_ratio: 48.7%
placebo:
  random: pass
  block: pass
  circular: pass
  inverted_gate: negative
```

## Diagnostic Shadow

```yaml
name: X4_6_plus_003_minus_002_R3
clusters:
  - cluster_001
  - cluster_005
  - cluster_006
  - cluster_009
  - cluster_004
  - cluster_003
gate: R3_liquidity_low
status: diagnostic_only
```

X4 remains useful for monitoring the cluster_003 substitution hypothesis, but it is not the formal proof book.

## Confirmed

- The project has a locked daily regime-gated shadow object.
- R3 liquidity-low gating materially improves the 2026 full-calendar profile of the official six-cluster book.
- R3 passes random active-day, block-run, circular-shift, and inverted-gate robustness checks at the current evidence level.
- The official daily shadow profile is append-only and does not require further alpha search or gate threshold tuning.

## Not Confirmed

- production_ready
- minute_execution
- real_slippage
- real_capacity
- live_survival
- true_book_marginal
- paper_trading_survival
- fill_feasibility_under_limit_or_suspension

## Locked Forward Rules

The Phase3P forward process must not retune or backfill:

```text
1. Keep the X0 official cluster list fixed.
2. Keep the X4 diagnostic cluster list fixed.
3. Keep the R3 liquidity-low threshold fixed from the 2025H2 training window.
4. Use lagged regime features only.
5. Export daily regime state, signals, positions, book snapshot, and shadow PnL proxy.
6. Append new dates only unless an explicit forced regeneration is requested for engineering recovery.
7. Treat X0 as the formal shadow and X4 as diagnostic-only.
```

## Promotion Gate

Phase3P can only upgrade evidence after locked forward observation:

```text
10 active days:
    process stability only

20 active days:
    preliminary gate direction check

40 active days:
    evidence upgrade candidate if returns, drawdown, gate correctness, and process integrity hold

60 active days:
    paper / tiny-live discussion may begin, still subject to execution and capacity calibration
```

## Current Action

Start `Phase3P_locked_daily_forward`.

No new alpha search, no gate retuning, no cluster substitution promotion, and no oracle combo usage.

