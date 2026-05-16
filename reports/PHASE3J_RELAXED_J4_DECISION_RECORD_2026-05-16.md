# Phase3J Relaxed J4 Decision Record - 2026-05-16

Decision: `PASS_RELAXED_J4_CANDIDATE`

## Result

The original J4 liquidity-aware book was too strict:

- Clusters: `15 / 34`
- Retention: `44.12%`
- p90 turnover: `0.213655`
- capacity proxy median: `46.94M`

The sensitivity audit found a better relaxed J4:

`J4_relaxed_a0.05_c0.05_and_l0.2`

- Clusters: `22 / 34`
- Retention: `64.71%`
- p90 turnover: `0.278967`
- capacity proxy median: `24.33M`
- max raw share: `13.33%`
- equal cost-adjusted score: `1.840207`

Filter:

- amount bottom quantile: `5%`
- capacity bottom quantile: `5%`
- gate mode: reject only if both amount and capacity are below threshold
- max limit-hit rate: `20%`
- max suspension rate: `1%`

## Interpretation

`J4_relaxed` is better than original J4 for the next book-readiness step because it keeps enough clusters while still improving turnover and concentration relative to J0.

Compared with J2:

- cluster count: `22` vs `23`
- p90 turnover: `0.278967` vs `0.276502`
- max raw share: `13.33%` vs `12.90%`
- equal cost-adjusted score: `1.840207` vs `1.758840`
- capacity proxy median: `24.33M` vs `23.90M`

So the next candidate set should be:

- `J2_balanced`: baseline book-readiness candidate
- `J4_relaxed`: liquidity-aware book-readiness candidate

## Not Confirmed

- Production execution.
- Live capacity.
- True fill model.
- Slippage beyond current proxy.

This remains `HOLD_RESEARCH` for deployment until a proper book replay / execution model validates J2 vs J4_relaxed.
