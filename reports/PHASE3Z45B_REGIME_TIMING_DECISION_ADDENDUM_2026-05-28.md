# Phase3Z45b Regime / Timing Decision Addendum

Date: 2026-05-28

Decision: `HOLD_RESEARCH_REGIME_TIMING_AUDIT_COMPLETE`

Parent decision: `PHASE3Z45B_RESEARCH_DECISION_RECORD_2026-05-28`

This addendum records the regime and holding-horizon behavior of the five Phase3Z45b diagnostic candidates. It does not change the official X0/R3 shadow object and does not promote any candidate.

## Outputs

- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit/PHASE3Z45B_REGIME_TIMING_AUDIT_2026-05-28.md`
- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit/phase3z45b_regime_effectiveness.csv`
- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit/phase3z45b_horizon_decay.csv`
- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_timing_audit/phase3z45b_timing_profile.csv`

## Main Findings

1. The event morphology branch is regime-sensitive, but not in the naive direction.

   Most stronger slices occur in `limit_density_low` or R3-like liquidity regimes, not in `limit_density_high`. This means direct limit/high-board features are not simply "buy the hot limit tape"; the cleaner behavior is often post-event or crowding-unwind behavior.

2. `cluster_002` is the strongest standalone timing candidate, but still not an X0/R3 overlay.

   - Representative: `Neg(ZScore(Mean(Delay($limit_up_streak_ge8,1),7)))`
   - 2026 h1 annualized daily-equivalent: `68.7009%`
   - Best OOS slice: `breadth_low`, `10` days, annualized daily-equivalent `445.4866%`
   - Timing profile: `front_loaded`
   - h3/h1 mean ratio: `0.4779`
   - First horizon below half of h1: `3`

   Interpretation: signal is short-lived. It is not a persistent event book; it is a 1-day response around weak breadth / limit-streak unwind conditions.

3. `cluster_007` has the most interesting persistence, but remains cost-killed.

   - 2026 h1 annualized daily-equivalent: `20.3679%`
   - Best horizon: `3` days, annualized daily-equivalent `41.3526%`
   - h3/h1 mean ratio: `1.8675`
   - R3-on annualized daily-equivalent: `115.6387%`
   - Median turnover: about `70%`

   Interpretation: the structure is real enough to study, but not deployable under the current daily proxy cost model. Any future use requires an execution/cost breakthrough or a lower-turnover reformulation.

4. `cluster_030` is pure short-horizon and should not be expanded into a medium-horizon thesis.

   - 2026 h1 annualized daily-equivalent: `9.8834%`
   - h2 annualized daily-equivalent: `-8.1439%`
   - h3 annualized daily-equivalent: `-11.5978%`
   - Timing profile: `front_loaded`

   Interpretation: open-not-close morphology, if useful, is a very short-lived effect. It should only be studied as a narrow event diagnostic.

5. `cluster_001` and `cluster_017` are supportive diagnostics, not promotion candidates.

   `cluster_001` is mildly persistent with best horizon `3`, but standalone strength is weak and marginal overlay value is absent.

   `cluster_017` is short-horizon, improves under R3 and `limit_density_low`, but remains insufficient versus X0/R3.

## Regime Notes

R3/liquidity behavior in 2026:

| cluster | R3-on annualized | R3-off annualized | interpretation |
|---|---:|---:|---|
| `cluster_001` | `58.2544%` | `-0.9919%` | R3-dependent |
| `cluster_002` | `56.2556%` | `71.7441%` | not R3-specific |
| `cluster_007` | `115.6387%` | `0.6983%` | R3-dependent but cost-killed |
| `cluster_017` | `52.8131%` | `16.5754%` | R3-enhanced |
| `cluster_030` | `49.0719%` | `-1.1351%` | R3-dependent short event |

Limit-density behavior in 2026:

| cluster | best limit-density bucket | interpretation |
|---|---|---|
| `cluster_001` | `limit_density_low` | post-crowding condition, not hot-tape condition |
| `cluster_002` | `limit_density_low` by intensity, but also positive in high | short-lived breadth/limit-streak unwind |
| `cluster_007` | `limit_density_low` | persistent but untradeable turnover |
| `cluster_017` | `limit_density_low` | R3-enhanced short event |
| `cluster_030` | high and low positive, mid negative | unstable event morphology |

## Promotion Boundary

Allowed:

- Keep the regime/timing tables as diagnostic evidence.
- Use the findings to design future cost-aware, R3-conditioned event-interaction research.
- Treat `cluster_002` as the cleanest standalone short-horizon event diagnostic.
- Treat `cluster_007` as the main structural candidate for lower-turnover reformulation.

Blocked:

- Do not promote any Z45b cluster into X0/R3.
- Do not use the high annualized regime slices as full-calendar strategy returns.
- Do not interpret `limit_density_low` slices as proof that limit factors are production-ready.
- Do not rerun broad direct-limit search without a marginal-value and turnover-aware reward.

## Bias Boundary

- No new search was performed.
- Regime buckets used 2025H2 thresholds and reported 2026 behavior.
- Execution assumption: T+1 daily proxy.
- Cost assumption: `10bps * average_one_way_turnover`.
- Multi-day horizons use overlapping labels and are timing diagnostics, not production PnL.
- OOS sample grade remains `WEAK`; this is recent daily diagnostic evidence only.

