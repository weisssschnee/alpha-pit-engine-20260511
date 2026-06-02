# CN Integrated Factor Pack v2 Coverage-Aware Replay Smoke

decision: `PASS_PHASE3AC_COVERAGE_AWARE_SMOKE_HOLD_PROMOTION`

## Why This Was Needed

The first v2 smoke proved that quality interactions were executable and had signal, but it also exposed a panel-risk issue:

- minute fields were moderately covered
- RZRQ fields were partially covered
- fundamental fields were very sparse in the controlled panel

So Phase3AC added candidate-level PIT field coverage before selection. This uses only field observability and does not use replay labels, deployable labels, PnL labels, or final clusters.

## Coverage Gate

- input v2 candidates: `355`
- coverage-aware candidates kept: `294`
- blocked as too sparse: `61`
- min joint coverage: `2%`
- missing panel fields: `0`

Coverage buckets across all v2 candidates:

- high: `14`
- medium: `36`
- fragile_sparse: `244`
- too_sparse: `61`

Main lane retention:

- `quality_x_minute_pressure`: `72 / 90`
- `quality_x_rzrq_flow`: `72 / 90`
- `rzrq_size_normalized`: `36 / 36`
- `minute_amount_share_daily`: `6 / 6`

## Selector-Only Result

- G2 selected integrated v2 coverage-aware rows: `19 / 64`
- selected direct/fundamental-only candidates: `0`
- forbidden replay-label use: `false`
- signal-vector proxy requirement: `pass`

Selected v2 lanes:

- `rzrq_size_normalized`: `15`
- `quality_x_rzrq_flow`: `3`
- `minute_amount_share_daily`: `1`

This is materially different from raw v2, where selection focused on sparse quality x minute/RZRQ interactions.

## Replay Result

- audited: `19`
- raw non-gap replay pass: `16`
- cost survive: `12`
- deployable clusters: `10`
- top cluster share: `6.25%`
- median replay sortino: `-0.126466`
- median turnover: `0.573237`

Comparison to raw v2 smoke:

| run | audited | raw pass | cost survive | deployable clusters | top cluster share |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw v2 | 20 | 11 | 8 | 3 | 27.27% |
| coverage-aware v2 | 19 | 16 | 12 | 10 | 6.25% |

## Interpretation

The coverage-aware selector materially improved both discovery yield and concentration.

The strongest new direction is not direct fundamental quality. It is:

`RZRQ flow normalized by float market cap or amount`

with a secondary signal in:

`fundamental quality x RZRQ flow`

This is a better use of the integrated data than v1 direct ranks or raw v2 sparse interactions.

## Boundaries

Not confirmed:

- official book promotion
- OOS stability
- new-vs-149 novelty
- marginal value versus X0/R3
- production/execution readiness

## Next Gate

Allowed next step:

`Phase3AC fresh-seed coverage-aware validation`

Run fixed coverage-aware pack without changing thresholds:

- fresh selector seed
- same coverage gate
- replay selected v2 stratum
- global novelty/concentration audit

Promotion remains blocked until fresh-seed replay confirms the effect.
