# Crypto A7C FundingCore Decision Record

- decision: `HOLD_FUNDINGCORE_ALPHA_SHADOW_PROOF`
- status: `fundingcore_research_baseline_only`
- generated_at: `2026-05-19T12:18:23Z`

## Summary

- validation 10bps annualized: `1.969657672528783`
- recent OOS 10bps annualized: `0.7862907354498385`
- fresh May 10bps annualized: `-2.856188962009161`
- validation 20bps annualized: `1.7112490999138206`
- recent OOS 20bps annualized: `0.5112879701508529`
- recent symbol LOO positive rate: `1.0`

## Decision

FundingCore is retained as the mandatory crypto benchmark and a simpler research baseline.

It is not promoted to alpha shadow proof if fresh May remains negative or drawdown risk remains unresolved.

## Confirmed

- Funding-only structure is the dominant simple explanation for Core4.
- FundingCore must be included in all future crypto reward/bakeoff comparisons.
- A6 dry-shadow remains engineering telemetry only.

## Not Confirmed

- paper/live readiness
- production execution
- independent Core4 alpha proof
- crypto generator/reward maturity

## Required Next Action

If FundingCore remains blocked, redesign crypto reward around funding-baseline residual edge before any generator bakeoff.
