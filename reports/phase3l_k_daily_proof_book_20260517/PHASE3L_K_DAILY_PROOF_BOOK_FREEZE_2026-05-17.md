# Phase3L-K Daily Proof Book Freeze

- generated_at: 2026-05-17T05:04:41+08:00
- decision: `PASS_PHASE3L_K_DAILY_STRONG_PROOF_BOOK_EX_REGIME`
- book_cluster_count: 9
- median_turnover: 0.073418
- p90_turnover: 0.15451
- source_lane_top_share: 0.555556
- sign_flip_pass_count: 0

## Interpretation

- This is a daily strong proof book, ex-regime and ex-minute-execution.
- One representative is kept per global survivor signal cluster.
- This should not be described as production-ready or capacity validated.

## Book

| global_cluster | source_cluster | type | score | turnover | source_lane | expression |
| --- | --- | --- | ---: | ---: | --- | --- |
| cluster_001 | s47_cluster_005 | low_order_rescue | 1.671616 | 0.073418 | agnostic_freeform_ast | `CSRank(ZScore(Mean(Abs(Delta($vwap,1)),21)))` |
| cluster_005 | s47_cluster_005 | low_order_rescue | 1.617685 | 0.199872 | agnostic_freeform_ast | `CSRank(Mul(CSRank(Std($open,8)),ZScore(Mean(Abs(Delta($vwap,1)),21))))` |
| cluster_008 | s50_cluster_005 | full_formula_survivor | 1.590935 | 0.065529 | formula_gen_v2_repair_expansion | `CSRank(Mul(CSRank(Mul(ZScore(Mean($amount,34)),ZScore(Mean($final_float_market_cap,8)))),ZScore(Mean(Abs(Delta($close...` |
| cluster_006 | s48_cluster_008 | full_formula_survivor | 1.564433 | 0.051814 | r0_cem_led | `CSRank(Mul(ZScore(Mean(Abs($close),8)),ZScore(Mean(Abs($amount),21))))` |
| cluster_009 | cluster_031 | full_formula_survivor | 1.541851 | 0.103397 | formula_gen_v2_repair_expansion | `CSRank(Mul(CSRank(CSResidual(CSRank(CSRank($close)),CSRank(Log($final_total_market_cap)))),ZScore(Mean(Abs(Delta($clo...` |
| cluster_003 | s52_cluster_013 | full_formula_survivor | 1.507126 | 0.069113 | agnostic_freeform_ast | `CSRank(CSResidual(ZScore(Mean(Abs(Delta($open,1)),34)),CSRank($high)))` |
| cluster_002 | cluster_017 | low_order_rescue | 1.462002 | 0.076805 | agnostic_freeform_ast | `CSRank(Mul(CSRank($open),CSRank(Mean($amount,8))))` |
| cluster_007 | s53_cluster_002 | full_formula_survivor | 1.420147 | 0.143169 | agnostic_freeform_ast | `CSRank(Add(Sign(Mom($final_total_market_cap,34)),CSRank(Mean(Abs(Delta($open,1)),34))))` |
| cluster_004 | cluster_014 | full_formula_survivor | 1.229064 | 0.027425 | formula_gen_v2_repair_expansion | `CSRank(Mul(ZScore(Mean($close,8)),ZScore(Mean($final_float_market_cap,34))))` |
