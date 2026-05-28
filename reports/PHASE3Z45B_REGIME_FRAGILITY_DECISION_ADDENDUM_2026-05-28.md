# Phase3Z45b Regime Fragility Decision Addendum

Date: 2026-05-28

Decision: `HOLD_RESEARCH_REGIME_FRAGILITY_AUDIT_COMPLETE`

Parent records:

- `PHASE3Z45B_RESEARCH_DECISION_RECORD_2026-05-28`
- `PHASE3Z45B_REGIME_TIMING_DECISION_ADDENDUM_2026-05-28`

This addendum answers whether the best-looking Phase3Z45b regime slices are stable enough to interpret. The answer is mostly no.

## Outputs

- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_fragility_audit/PHASE3Z45B_REGIME_FRAGILITY_AUDIT_2026-05-28.md`
- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_fragility_audit/phase3z45b_regime_fragility.csv`
- `reports/phase3z45b_parametric_limit_open_touch_20260528/regime_fragility_audit/phase3z45b_best_slice_daily_returns.csv`

## Result

All five best OOS slices were flagged fragile.

| cluster | best OOS slice | OOS days | OOS annualized | remove-top1 annualized | random p95 | main issue |
|---|---|---:|---:|---:|---:|---|
| `cluster_001` | `limit_density_low` | `8` | `133.9791%` | `-11.3414%` | `305.3138%` | small sample, top-day concentration, fails random p95 |
| `cluster_002` | `breadth_low` | `10` | `445.4866%` | `182.5995%` | `425.7932%` | small sample, top-day concentration |
| `cluster_007` | `limit_density_low` | `8` | `326.2919%` | `85.3988%` | `693.3446%` | small sample, top-day concentration, fails random p95, high turnover |
| `cluster_017` | `limit_density_low` | `9` | `243.7320%` | `54.5363%` | `366.1829%` | small sample, top-day concentration, fails random p95 |
| `cluster_030` | `breadth_mid` | `16` | `106.2222%` | `66.9523%` | `162.6839%` | fails random p95 |

## Interpretation

The regime/timing audit showed plausible structure, but the fragility audit prevents promotion.

Important distinctions:

- `cluster_002` is still the cleanest short-horizon diagnostic. It beats random p95 on its best OOS slice, but the slice has only `10` days and top-3 positive days explain about `73%` of positive contribution.
- `cluster_007` remains structurally interesting because its horizon profile is persistent, but its best slice does not beat random p95 and its turnover is prohibitive.
- `cluster_001`, `cluster_017`, and `cluster_030` do not clear same-active-count random-slice robustness.

## Promotion Boundary

No Phase3Z45b candidate can be promoted from regime slices.

Allowed:

- Keep `cluster_002` as a short-horizon diagnostic candidate.
- Keep `cluster_007` as a structural but cost-killed reformulation target.
- Use these results to design a future locked diagnostic, not an official overlay.

Blocked:

- Do not cite the 200%-400% regime-slice annualized figures as strategy returns.
- Do not promote any Z45b cluster into X0/R3.
- Do not use OOS-selected best slices as rules without a new locked-forward protocol.
- Do not continue direct limit standalone search under the old reward.

## Bias Boundary

- Best slices were selected from OOS diagnostics, so this audit is explicitly posthoc.
- Same-active-count random placebo was used only as a fragility check, not as a formal p-value.
- OOS sample remains weak recent daily evidence.
- No search, formula changes, or book changes were performed.

