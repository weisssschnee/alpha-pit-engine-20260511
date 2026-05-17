# Phase3O Regime Gate Decision Record

- decision: `PASS_REGIME_GATED_DAILY_SHADOW_READY`
- evidence_level: `daily_regime_gated_shadow_no_execution`
- commit: `fa41c36`
- primary_gate: `R3_liquidity_low`
- formal_shadow_profile: `X0_official_6 + R3`
- research_shadow_profile: `X4_official_6_plus_003_minus_002 + R3`

## Decisions

1. `R3_liquidity_low` is the primary locked gate.
   - 2026 full-calendar annualized return for X0: `117.57%`
   - Sharpe: `4.55`
   - max drawdown: `-3.44%`
   - active ratio: `48.72%`
   - strict robustness: passed random, block-run, and circular-shift checks.

2. `X0_official_6 + R3` is the formal candidate shadow profile.
   - It keeps the official six-cluster book unchanged.
   - It is the only Phase3O profile suitable for formal locked forward tracking.

3. `X4_official_6_plus_003_minus_002 + R3` is retained as research/diagnostic shadow.
   - 2026 full-calendar annualized return: `123.34%`
   - Sharpe: `4.65`
   - max drawdown: `-3.20%`
   - It is not promoted into the formal proof book because cluster_003 substitution remains diagnostic.

4. Walk-forward weighting is not promoted.
   - Equal-weight R3 variants were already strong.
   - Walk-forward weighting did not provide enough incremental evidence to justify new degrees of freedom.

5. Phase3O5 locked forward export is active.
   - Latest signal date: `2026-05-08`
   - R3 gate active: `false`
   - Both profiles wrote explicit flat daily snapshots.
   - Gate-on smoke on `2026-04-30` generated non-empty signals and positions without errors.

## Confirmed

- Recent-regime gating materially improves the 2026 full-calendar profile versus no gate.
- `R3_liquidity_low` is cleaner than broader gates because it passes stricter placebo and timing checks.
- The project now has an append-only daily shadow export path for the formal profile and the diagnostic profile.

## Not Confirmed

- production readiness
- live or paper survival
- minute-level execution
- true slippage
- true capacity
- fill feasibility under limit/suspension conditions
- cluster_003 substitution as a formal book rule
- walk-forward weighting as a formal production rule

## Locked Objects

Formal candidate shadow:

```text
profile: x0_official6_r3_liquidity_low
clusters:
  cluster_001
  cluster_005
  cluster_006
  cluster_009
  cluster_002
  cluster_004
gate:
  R3_liquidity_low
```

Research diagnostic shadow:

```text
profile: x4_plus003_minus002_r3_liquidity_low
clusters:
  cluster_001
  cluster_005
  cluster_006
  cluster_009
  cluster_004
  cluster_003
gate:
  R3_liquidity_low
```

## Next Gate

Do not search or retune before forward accumulation. The next promotion gate is:

```text
daily locked forward observations
+ execution / slippage / capacity calibration
+ limit / suspension feasibility audit
```

