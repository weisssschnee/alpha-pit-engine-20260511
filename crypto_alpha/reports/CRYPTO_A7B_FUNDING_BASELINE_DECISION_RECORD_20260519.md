# Crypto A7B Funding Baseline Decision Record

- decision: `HOLD_CORE4_INDEPENDENT_ALPHA_PROOF`
- date: `2026-05-19`
- scope: Core4 vs simpler funding/basis/price baselines under matched validation protocol

## Result

Core4 does not currently qualify as an independent crypto alpha proof object.

The main reason is not placebo leakage. The main reason is funding-baseline dominance:

- Funding-only beats Core4 in validation.
- Funding-only beats Core4 in recent OOS.
- Core4 residual vs funding remains positive, but not strong enough to justify Core4 as a standalone proof book.
- Fresh May 2026 is negative across Core4, funding-only, price-only, basis-only, and interaction variants.

## Matched Protocol

All objects used the same:

- universe: core12 futures
- frequency: 1h
- split ledger: A7.0
- purge/embargo: 24 bars
- execution: next 1h bar open proxy
- risk scaling: `R3_vol_target_gross_0p5x_cap`
- cost: 10bps for primary comparison
- funding treatment: latest-known funding in signal; forward funding event cost included

## 10bps Comparison

| object | validation ann | validation DD | recent ann | recent DD | fresh May ann | fresh May DD |
|---|---:|---:|---:|---:|---:|---:|
| `B0_Core4` | 1.0632 | -0.4878 | 0.5808 | -0.5209 | -2.7641 | -0.1763 |
| `B1_funding_only` | 1.9697 | -0.3767 | 0.7863 | -0.6195 | -2.8562 | -0.1808 |
| `B2_price_only` | -1.4115 | -0.5273 | -1.2631 | -0.6511 | -1.4050 | -0.1156 |
| `B3_basis_only` | -0.0083 | -0.3700 | -1.0524 | -0.6039 | -4.0260 | -0.1684 |
| `B4_price_x_funding` | 0.9659 | -0.5591 | 0.4484 | -0.5108 | -2.5130 | -0.1752 |
| `B5_basis_x_funding` | 1.1781 | -0.4021 | 0.7069 | -0.5424 | -3.0462 | -0.1816 |
| `B6_Core4_residual_vs_funding` | 0.1914 | -0.4068 | 0.4433 | -0.1492 | -0.6414 | -0.0673 |

## Interpretation

Funding-only is the dominant simple explanation.

Core4 still contains residual signal after train-period residualization against funding-only:

- validation residual ann: `0.1914`
- recent residual ann: `0.4433`

But residual evidence is not enough to promote Core4 because:

- full Core4 does not beat funding-only in validation or recent OOS;
- A7.1 already showed only 1/4 Core clusters beat their own component baselines;
- A7.2 still showed unacceptable drawdown;
- fresh May is negative.

## May 2026 Failure Attribution

May weakness is broad:

| object | May total return sum | May ann proxy | worst hour | top3 loss sum |
|---|---:|---:|---:|---:|
| `B0_Core4` | -0.1222 | -2.4324 | -0.0073 | -0.0197 |
| `B1_funding_only` | -0.1066 | -2.1215 | -0.0081 | -0.0222 |
| `B2_price_only` | -0.0824 | -1.6404 | -0.0071 | -0.0191 |
| `B3_basis_only` | -0.1453 | -2.8925 | -0.0121 | -0.0286 |
| `B4_price_x_funding` | -0.1138 | -2.2651 | -0.0074 | -0.0204 |
| `B5_basis_x_funding` | -0.1315 | -2.6178 | -0.0071 | -0.0202 |
| `B6_Core4_residual_vs_funding` | -0.0385 | -0.7656 | -0.0046 | -0.0112 |

This suggests the May drawdown is a funding/basis/price family regime issue, not only a Core4 construction issue.

## Current Crypto Line Status

Confirmed:

- A crypto 1h funding-related research signal exists.
- Core4 dry-shadow engineering pipeline works.
- Funding baseline is a necessary benchmark for future crypto reward design.

Not confirmed:

- Core4 as independent alpha proof.
- Crypto AlphaFactory reward/search loop.
- Production readiness.
- Paper trading readiness.
- Live trading readiness.

Blocked:

- A7.3 generator/reward bakeoff.
- Core4 alpha shadow proof promotion.

## Required Next Step

Do not expand formula search yet.

Recommended next work:

1. Define a simpler `FundingCore` research object from funding-only.
2. Run the same A6/A7 gates on FundingCore:
   - risk scaling;
   - fixed split;
   - placebo and wrong-lag funding;
   - May failure attribution;
   - symbol/month stability.
3. Redesign crypto reward to include `residual_edge_vs_funding_baseline`, otherwise future search will mostly rediscover funding wrappers.

Until then:

- `Core4` remains `research_proof_object`.
- A6 dry-shadow remains `engineering_telemetry_only`.
- No paper/live trading.
