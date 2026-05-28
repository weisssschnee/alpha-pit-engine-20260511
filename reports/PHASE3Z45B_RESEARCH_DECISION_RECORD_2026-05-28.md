# Phase3Z45b Research Decision Record

Date: 2026-05-28

Decision: `FAIL_PROMOTION_HOLD_DIAGNOSTIC`

Scope: Parametric limit/open/touch/high-board morphology search and strict validation.

## Decision

Phase3Z45b is not promoted into the official X0/R3 shadow object, not promoted as an overlay, and not promoted as a new book component.

The branch is retained as a diagnostic event-morphology research asset only.

## Evidence Summary

- Stage1 raw rows: `3619`
- Deduped expressions: `3523`
- Strict audited: `192`
- Strict pass: `57`
- Portfolio replay pass: `22`
- Cost survival: `84`
- Low-corr strict pass clusters: `10`

Limit/event candidates were weaker than non-limit candidates after replay/cost checks:

- limit/event strict pass: `22 / 101`
- limit/event portfolio replay pass: `6 / 101`
- limit/event cost survival: `27 / 101`
- non-limit strict pass: `35 / 91`
- non-limit portfolio replay pass: `16 / 91`
- non-limit cost survival: `57 / 91`

## Candidate Routing

Five limit-related clusters survived into deep audit:

| cluster | routing | primary issue |
|---|---|---|
| `cluster_001` | `ALLOW_OOS_REGIME_REPLAY` | positive but no marginal overlay value versus X0/R3 |
| `cluster_002` | `ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG` | strongest standalone 2026 OOS, but strict/replay mismatch and no X0/R3 marginal value |
| `cluster_017` | `ALLOW_OOS_REGIME_REPLAY_WITH_STRICT_MISMATCH_FLAG` | positive standalone, strict/replay mismatch, no X0/R3 marginal value |
| `cluster_007` | `HOLD_TURNOVER_COST_STRESS_BEFORE_OOS` | structurally interesting but turnover/cost killed |
| `cluster_030` | `HOLD_EXPAND_SAMPLE_BEFORE_REPLAY` | open-not-close signal is low-sample and weak as overlay |

## Standalone OOS Read

The best standalone 2026 OOS candidate was `cluster_002`:

- Representative: `Neg(ZScore(Mean(Delay($limit_up_streak_ge8,1),7)))`
- 2026 active-day annualized proxy: `68.7009%`
- Sortino: `6.7831`
- Max drawdown: `-3.8794%`
- Median turnover: `1.3804%`

This is not sufficient for promotion because the official gate is marginal value versus the locked X0/R3 object, not standalone positivity.

## X0/R3 Marginal Overlay Gate

All five deep-audit candidates failed as X0/R3 overlays.

| cluster | overlay decision | candidate R3 annualized | blend annualized delta vs X0/R3 | median turnover |
|---|---|---:|---:|---:|
| `cluster_007` | `REJECT_OVERLAY_HIGH_TURNOVER` | `11.4617%` | `-10.4024%` | `70.0136%` |
| `cluster_030` | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | `9.6576%` | `-10.7790%` | `3.6532%` |
| `cluster_001` | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | `9.2360%` | `-10.8678%` | `1.3678%` |
| `cluster_017` | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | `7.9139%` | `-11.1480%` | `1.3720%` |
| `cluster_002` | `REJECT_OVERLAY_NO_MARGINAL_VALUE` | `4.0901%` | `-11.9755%` | `1.3804%` |

The X0/R3 comparison frame annualized at `72.3808%` with Sortino `6.2092`; every tested Z45b overlay reduced the seven-component blend.

## Bias / Promotion Assessment

- Discovery status: generated search followed by strict replay and posthoc diagnostic audits.
- Promotion evidence: insufficient.
- OOS evidence: recent daily OOS only; useful for diagnostics, not promotion.
- Costs: included in strict validation and standalone stress; `cluster_007` fails cost robustness.
- Turnover: `cluster_007` has prohibitive turnover; the lower-turnover candidates do not add marginal value.
- Replay vs discovery: this branch can inform future generator/reward design, but cannot alter the locked X0/R3 object.

Decision under candidate review: `HOLD_RESEARCH`.

Decision under bias/promotion audit: `HOLD_RESEARCH`, with explicit `FAIL_PROMOTION`.

## Confirmed

- The parametric event morphology generator can produce valid limit/open/touch/high-board candidates.
- Limit-event structures can show standalone recent OOS signal.
- The most interesting structural family is high-board/limit interaction with flow/turnover, but current versions are cost-killed.
- Open-not-close morphology deserves only sample-expansion diagnostics, not promotion.

## Not Confirmed

- No Z45b candidate improves the locked X0/R3 shadow book.
- No direct limit/open/touch candidate is production-ready.
- No candidate is approved for the official keep list or official shadow.
- No evidence supports retraining or rewriting the official chain around direct limit factors.

## Next Allowed Actions

Allowed:

- Keep Z45b as a diagnostic asset.
- Use its results to design a future cost-aware, X0-marginal reward.
- Expand open-not-close sample only as a diagnostic lane.
- Test R3-conditioned event interactions only with strict marginal-value gates.

Blocked:

- Do not add any Z45b candidate to X0/R3.
- Do not promote `cluster_002` based on standalone OOS.
- Do not promote `cluster_007` without a realistic execution/cost breakthrough.
- Do not run more direct limit standalone search without changing the reward to penalize turnover and require marginal value versus X0/R3.

