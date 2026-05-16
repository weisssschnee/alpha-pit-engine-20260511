# Phase3I Selector V2 Gate Record

- decision: `PASS_SELECTOR_V2_TO_OFFICIAL_GATE`
- date: `2026-05-16`
- scope: selector-only and smoke gate for Phase3I deployment-hardening selectors.

## Inputs

- baseline selector: `I0 = Phase3I_I0_G2_primary`
- candidate selector: `I1_v2 = Phase3I_I1_v2_turnover_tail_guard`
- diagnostic selector: `I3_v2 = Phase3I_I3_v2_queue_diversity`
- blocked selector: `I2 = Phase3I_I2_G2_capacity_liquidity`
- discovery baseline: `149`
- selector vector baseline: `137`
- execution mode: shared candidate pool -> frozen selection -> strict/replay only after gate

## Gate Evidence

### Delta Audit

- `I1` v1 failed because added candidates had worse turnover than removed candidates.
- `I1` v1 `turnover_penalty` had zero effective scale, so it did not control turnover.
- `I3` v1 failed because added candidates had higher selected-queue signal correlation than removed candidates.
- Turnover proxy calibration is weak as a scalar predictor (`Spearman = 0.136462`) but usable as coarse tail/bucket control.

### Selector-Only V2

Seed 41:

- `I0` p90 turnover proxy: `0.12558`
- `I1_v2` p90 turnover proxy: `0.097957`
- `I0` mean selected-queue signal corr: `0.410715`
- `I3_v2` mean selected-queue signal corr: `0.359162`

Seed 42:

- `I0` p90 turnover proxy: `0.110825`
- `I1_v2` p90 turnover proxy: `0.090913`
- `I0` mean selected-queue signal corr: `0.429`
- `I3_v2` mean selected-queue signal corr: `0.334803`

### Smoke

Seed 42 smoke, `16 audited / arm`:

- `I0`: deployable `6/16`, top cluster share `0.10`, median turnover proxy `0.0503735`
- `I1_v2`: deployable `6/16`, top cluster share `0.10`, median turnover proxy `0.042811`
- `I3_v2`: deployable `3/16`, top cluster share `0.20`, median turnover proxy `0.056112`

## Decision

### Promote To Official

`I1_v2` is promoted to Phase3I official replay:

- It passed two selector-only seeds.
- It preserved smoke deployable count versus `I0`.
- It reduced median turnover proxy in smoke.
- It directly targets the Phase3I deployment-hardening objective: tail turnover control without collapsing discovery.

### Diagnostic Only

`I3_v2` remains diagnostic only:

- It successfully reduced selected-queue signal correlation in selector-only.
- It failed smoke yield quality: deployable dropped from `6/16` to `3/16`.
- It is not promoted to official replay unless a later design restores deployable yield.

### Blocked

`I2` is blocked from official replay:

- It had high overlap with `I0` in the first selector-only run.
- Its liquidity/capacity improvement was not enough to justify replay budget.
- It remains a diagnostic source only.

## Next Execution

1. Run selector-only dry run for `I0 / I1_v2` on seeds `43,44,45,46`.
2. If all seeds pass:
   - run official replay for `I0 / I1_v2 x seeds43-46 x 64 audited`.
3. Aggregate globally across all seeds without seed-local cluster labels.
4. Promote `I1_v2` to `G2 deployment-hardened candidate` only if it improves turnover/tail risk without materially reducing deployable clusters or increasing concentration.

## Non-Goals

- Do not run `I3_v2` official replay in this gate.
- Do not run `I2` official replay in this gate.
- Do not interpret selector-only results as alpha deployment proof.
- Do not call any Phase3I selector a true book-marginal selector.
