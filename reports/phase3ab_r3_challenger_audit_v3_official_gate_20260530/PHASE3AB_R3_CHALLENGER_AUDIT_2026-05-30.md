# Phase3AB R3 Challenger Audit

- version: `phase3ab-r3-challenger-audit-v1-2026-05-30`
- input: `D:\p3ab\phase3ab_deep_deduped_best_20260530.csv`
- dataset: `D:\HermesWorker\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet`
- selected_candidates: `9`
- official_x0_r3_policy: `read_only_no_change`
- x0_r3_2026_ann: `1.175657`
- x0_r3_2026_sortino: `6.085253`

## Interpretation

- This is not a search run and does not modify the locked X0/R3 object.
- Candidates are treated as recent/R3 challengers, not all-history alpha.
- Promotion requires marginal value against X0/R3, sign-flip sanity, and low-order ablation checks.

## Candidate Audit

| rank | candidate | decision | cand R3 ann | cand R3 sortino | blend ann delta | blend sortino delta | corr X0 | sign flip | best ablation | expr_hash |
|---:|---|---|---:|---:|---:|---:|---:|---|---|---|
| 1 | `stockpit-ff-f14307093f3c` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.713611 | 2.892608 | -0.072918 | 0.03043 | 0.510304 | False | None | `e1abdc95261b225e` |
| 2 | `stockpit-ff-8e66bcc38105` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.703252 | 2.74047 | -0.074737 | 0.022318 | 0.509293 | False | None | `9398a32b91b5939d` |
| 3 | `stockpit-ff-fb78581d4f69` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.686084 | 2.544716 | -0.077773 | -0.114796 | 0.518985 | False | None | `224b5afae74cf5da` |
| 4 | `stockpit-ff-599a79d51d68` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.68369 | 2.648426 | -0.078198 | 0.143685 | 0.48688 | False | None | `e29c71b91ad724fd` |
| 5 | `stockpit-ff-f00820e82553` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.675758 | 2.5599 | -0.079612 | -0.10525 | 0.517965 | False | None | `8ed72d5b0e0ba4a8` |
| 6 | `stockpit-ff-ce89850c0e1f` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.673749 | 3.500433 | -0.07997 | -0.125199 | 0.529886 | False | None | `f63e15b7f590d668` |
| 7 | `stockpit-ff-606f4b69571c` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.672684 | 3.530649 | -0.080161 | -0.113291 | 0.524895 | False | None | `b267db2301841650` |
| 8 | `stockpit-ff-16aa6476fca8` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.49998 | 2.187253 | -0.112497 | 0.0346 | 0.437042 | False | None | `17d1d3efeb7f84fe` |
| 9 | `stockpit-ff-640fd3d1f3c2` | REJECT_OVERLAY_NO_MARGINAL_VALUE | 0.421859 | 1.746412 | -0.12818 | -0.023218 | 0.432072 | False | None | `80ed484b733f544c` |

## Bias Audit Summary

- Look-ahead: uses `SIGNAL_CLOCK_AFTER_OPEN`, one-day execution lag, and lagged R3 liquidity state inherited from the locked regime builder.
- Discovery status: Phase3AB candidates remain discovery/replay candidates from the recent mature-chain search; this audit is post-discovery challenger validation.
- OOS scope: 2026 slice is recent OOS only; pre-2025/full-history weakness remains a blocker for all-regime promotion.
- Cost: net returns use 10 bps turnover cost proxy; no minute slippage or real capacity is confirmed.

## Outputs

- audit_csv: `D:\p3ab\phase3ab_r3_challenger_audit_v3_official_gate_20260530\phase3ab_r3_challenger_audit.csv`
- daily_csv: `D:\p3ab\phase3ab_r3_challenger_audit_v3_official_gate_20260530\phase3ab_r3_challenger_daily.csv`
- ablation_csv: `D:\p3ab\phase3ab_r3_challenger_audit_v3_official_gate_20260530\phase3ab_r3_challenger_ablation.csv`
- json: `D:\p3ab\phase3ab_r3_challenger_audit_v3_official_gate_20260530\phase3ab_r3_challenger_audit.json`
