# Phase3I Design Record

Date: 2026-05-16

## Decision

Phase3I is `G2 deployment hardening / book-readiness`, not another broad formula-search phase.

Confirmed input state:

- Phase3H promoted `H1_G2_signal_vector_selector` as discovery primary.
- Discovery baseline advanced from `134` to `149`.
- Selector vector baseline is not assumed to be `149`; current estimate is `137` until the next canonical vector registry run.
- `H2_turnover_calibrated` is not promoted.

## Goal

Answer whether G2-discovered clusters can survive deployment-oriented constraints:

- cost and turnover
- liquidity/capacity proxy
- registry/book correlation proxy
- cluster-level concentration

This phase does not claim true book marginal unless return-vector coverage is later proven sufficient.

## Proposed Arms

| Arm | Purpose |
| --- | --- |
| I0_G2_primary | Fresh-seed G2 discovery primary control |
| I1_G2_cost_turnover_constrained | Test cluster-level turnover/cost hardening |
| I2_G2_capacity_liquidity_constrained | Test liquidity/capacity-aware hardening |
| I3_G2_book_proxy_hardened | Test stronger registry/queue correlation proxy; not true residual book marginal |

Suggested official scale after smoke:

- seeds: `37,38,39,40`
- audited: `64 / arm / seed`
- total: `1024`

## Arm Definitions

I0:

- profile: `H1_G2_signal_vector_selector`
- selector: current G2 signal-vector diversified selector

I1:

- base: G2
- add cluster-level turnover cap/penalty
- add p90 turnover penalty
- raw pass credit remains cluster-capped only

I2:

- base: G2
- require liquidity/capacity proxy when available
- penalize high-turnover low-capacity clusters
- reject extreme capacity risk only when the proxy is present and reliable

I3:

- base: G2
- stronger corr-to-149-registry proxy
- stronger selected-queue signal-corr penalty
- turnover/cost penalty
- new-cluster score is secondary

## Pass Criteria

I1/I2 pass if:

- deployable clusters `>= I0 - 3 / 256`
- top cluster share `<= 15%`
- median turnover `< I0`
- p90 turnover `< I0`
- new vs 149 does not materially degrade

I3 passes if:

- deployable clusters `>= I0 - 3 / 256`
- top cluster share `<= I0`
- mean/max corr to the registry improves
- selected-queue signal corr improves
- turnover does not worsen

## Current No-Run Findings

From Phase3H no-run audits:

- G2 deployable clusters: `34`
- G2 new clusters vs 134: `15`
- G2-only clusters vs H0: `8`
- G2/H0 overlap: `26`
- G2 median cluster turnover: `0.169768`
- G2 p90 cluster turnover: `0.61568`
- shared pool forbidden field hits: `0`
- selection forbidden field hits: `0`

Interpretation:

- G2 discovery/decongestion is credible.
- G2 still has deployment risk, especially high-tail turnover.
- Phase3I should harden selection quality rather than expand formula space.

## Do Not Do

- Do not restart H2 as production candidate.
- Do not call G2 true book marginal.
- Do not launch TokenAlphaLM official.
- Do not expand formula search before deployment hardening.
- Do not decide Phase3I from raw pass count alone.
