# Crypto A6 Core4 Risk Gate Decision Record

- generated_at: `2026-05-19T08:24:00Z`
- decision: `HOLD_SHADOW_A6_CORE4_RISK_NOT_READY`
- locked_object: `crypto_core4_locked_research_book_v1`
- locked_object_hash: `f07b8a9387c1c80be70c29c06a22d3782710d5d46a074ece7d4a6e7c6175f33b`

## Confirmed

- Core4 is frozen as a crypto 1h research proof object.
- A6.1 found no return-unit bug: no hourly return bar is `<= -100%`.
- The original `-93%` compounded drawdown is caused by unscaled full-notional compounding and clustered loss hours, not an immediate data unit error.
- Core4 remains economically interesting after cost: unscaled recent OOS 10bp annualized proxy is positive.

## Not Confirmed

- Shadow readiness.
- Production readiness.
- Live trading readiness.
- Acceptable risk scale.
- Real exchange slippage/capacity.
- Time-varying tradable universe.

## A6.2 Official Risk Scaling Result

Fixed variants tested:

- `R0_unscaled`
- `R1_gross_1x_cap`
- `R2_rolling_vol_target_50bp`
- `R3_vol_target_gross_0p5x_cap`

Official A6.2 gate:

- recent OOS 10bp annualized > 30%
- compounded max drawdown better than `-30%`
- monthly pass rate >= 70%

Result:

- `decision: HOLD_A6_2_NO_RISK_SCALED_SHADOW_CANDIDATE`
- no fixed official variant passed the drawdown gate.

Key recent OOS 10bp figures:

| variant | ann mean | compounded max DD | month pass | mean gross |
|---|---:|---:|---:|---:|
| `R0_unscaled` | 2.2867 | -0.9441 | 0.700 | 1.990 |
| `R1_gross_1x_cap` | 1.1795 | -0.7642 | 0.700 | 0.999 |
| `R2_rolling_vol_target_50bp` | 1.3229 | -0.8016 | 0.700 | 1.287 |
| `R3_vol_target_gross_0p5x_cap` | 0.5897 | -0.5130 | 0.700 | 0.500 |

## A6.2B Diagnostic Risk Budget

A diagnostic gross-cap ladder was run only to estimate the risk budget required to control drawdown. This is not an official promotion rule and must not be treated as OOS-optimized sizing.

Recent OOS 10bp ladder:

| gross cap | ann mean | compounded max DD | month pass |
|---:|---:|---:|---:|
| 0.50 | 0.5897 | -0.5130 | 0.700 |
| 0.40 | 0.4718 | -0.4374 | 0.700 |
| 0.35 | 0.4128 | -0.3953 | 0.700 |
| 0.30 | 0.3538 | -0.3502 | 0.700 |
| 0.25 | 0.2949 | -0.3017 | 0.700 |
| 0.20 | 0.2359 | -0.2496 | 0.700 |
| 0.15 | 0.1769 | -0.1937 | 0.700 |

Largest diagnostic cap meeting positive 10bp and DD < 30%:

```text
gross_cap = 0.20
```

## Decision

Core4 remains:

```text
locked research proof object
```

Core4 is not allowed to proceed to normal shadow deployment yet.

The only acceptable next step is a conservative dry-shadow design using an externally specified risk budget, likely at or below `0.20` gross cap, followed by forward-only observation. This must be documented as risk-budget selection, not as alpha optimization.

## Required Next Action

Do not run A6.3 official tradable book replay as if A6.2 passed.

Allowed next work:

1. Define `A6.3-conservative-dry-shadow` with gross cap selected from risk tolerance, not recent OOS.
2. Run 10bp/20bp cost replay at that fixed external risk budget.
3. If stable, start append-only hourly shadow without exchange orders.

