# Phase3L-N Factor Strength Frontier

- generated_at: 2026-05-17T11:47:38+08:00
- decision: `PASS_PHASE3L_N_DAILY_FACTOR_STRENGTH_FRONTIER`
- cluster_count: 9
- daily_window: 2025-08-18 to 2026-05-06

## Conclusions

- Strongest single cluster: `cluster_005` score=0.6975 source=agnostic_freeform_ast.
- Theoretical in-sample best equal-weight subset: `cluster_005|cluster_003|cluster_004` sortino=2.910011 p90_turnover=0.17372.
- Best current selectable subset: `cluster_001|cluster_005|cluster_006|cluster_009|cluster_002|cluster_004` sortino=1.543331 p90_turnover=0.151635 source_top_share=0.5.
- Current evidence level: `LEVEL_2_5_DAILY_STRONG_PROOF_BOOK_NO_EXECUTION_CAPACITY`.

## Evidence Boundary

- This is daily-only, in-sample over the available validation window.
- The oracle subset is a theoretical upper bound, not a deployable selection rule.
- Minute execution, true capacity, and live validation remain unconfirmed.

## Top Clusters

| rank | cluster | strength | score | strict_sortino | daily_sortino | turnover | source | expression |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | cluster_005 | 0.6975 | 1.617685 | 4.458059 | 2.203211 | 0.199872 | agnostic_freeform_ast | `CSRank(Mul(CSRank(Std($open,8)),ZScore(Mean(Abs(Delta($vwap,1)),21))))` |
| 2 | cluster_003 | 0.68 | 1.507126 | 4.11471 | 2.347818 | 0.069113 | agnostic_freeform_ast | `CSRank(CSResidual(ZScore(Mean(Abs(Delta($open,1)),34)),CSRank($high)))` |
| 3 | cluster_001 | 0.5375 | 1.671616 | 3.82282 | 1.574226 | 0.073418 | agnostic_freeform_ast | `CSRank(ZScore(Mean(Abs(Delta($vwap,1)),21)))` |
| 4 | cluster_006 | 0.5075 | 1.564433 | 2.484331 | 1.799638 | 0.051814 | r0_cem_led | `CSRank(Mul(ZScore(Mean(Abs($close),8)),ZScore(Mean(Abs($amount),21))))` |
| 5 | cluster_008 | 0.5 | 1.590935 | 3.945348 | 0.980899 | 0.065529 | formula_gen_v2_repair_expansion | `CSRank(Mul(CSRank(Mul(ZScore(Mean($amount,34)),ZScore(Mean($final_float_market_cap,8)))...` |
| 6 | cluster_009 | 0.4975 | 1.541851 | 3.286319 | 2.179256 | 0.103397 | formula_gen_v2_repair_expansion | `CSRank(Mul(CSRank(CSResidual(CSRank(CSRank($close)),CSRank(Log($final_total_market_cap)...` |
| 7 | cluster_004 | 0.3875 | 1.229064 | 2.81205 | 1.330699 | 0.027425 | formula_gen_v2_repair_expansion | `CSRank(Mul(ZScore(Mean($close,8)),ZScore(Mean($final_float_market_cap,34))))` |
| 8 | cluster_002 | 0.383 | 1.462002 | 3.146535 | 1.273684 | 0.076805 | agnostic_freeform_ast | `CSRank(Mul(CSRank($open),CSRank(Mean($amount,8))))` |
| 9 | cluster_007 | 0.2175 | 1.420147 | 3.486701 | 0.815117 | 0.143169 | agnostic_freeform_ast | `CSRank(Add(Sign(Mom($final_total_market_cap,34)),CSRank(Mean(Abs(Delta($open,1)),34))))` |

## Outputs

- report_json: `reports\phase3l_n_factor_strength_frontier_20260517\phase3l_n_factor_strength_frontier.json`
- report_md: `reports\phase3l_n_factor_strength_frontier_20260517\PHASE3L_N_FACTOR_STRENGTH_FRONTIER_2026-05-17.md`
- cluster_strength_csv: `reports\phase3l_n_factor_strength_frontier_20260517\phase3l_n_cluster_strength.csv`
- book_frontier_csv: `reports\phase3l_n_factor_strength_frontier_20260517\phase3l_n_book_frontier.csv`
