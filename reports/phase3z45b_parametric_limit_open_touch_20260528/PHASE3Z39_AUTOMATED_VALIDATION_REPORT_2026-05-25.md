# Phase3Z39 Automated Validation Report

- decision: `PASS_AUTOMATED_VALIDATION_HAS_STRICT_LOW_CORR_CANDIDATES_NOT_PROMOTION`
- scope: `research_validation_only_no_alpha_promotion`
- search root: `D:\HermesWorker\runtime\phase3z45b_parametric_limit_open_touch_boost_20260528\strict_source`
- reward profile: `event_long_only_guard_v1`
- stage1 reports: `16`
- raw stage1 rows: `3619`
- deduped expression rows: `3523`
- strict audited rows: `192`
- strict pass rows: `57`
- low-corr strict pass clusters: `10`
- portfolio replay pass rows: `22`
- limit/event queue rows: `101`

This is an automated validation gate. It is not an alpha promotion or production proof.

## Selection Roles

| role | audited | strict pass | replay pass | low-corr pass |
|---|---:|---:|---:|---:|
| `family_diverse_reward` | 32 | 10 | 6 | 2 |
| `top_limit_event_reward` | 96 | 18 | 4 | 5 |
| `top_reward` | 64 | 29 | 12 | 6 |

## Limit/Event vs Non-Limit

| bucket | audited | strict pass | replay pass | low-corr pass |
|---|---:|---:|---:|---:|
| `limit_event` | 101 | 22 | 6 | 6 |
| `non_limit` | 91 | 35 | 16 | 7 |

## Signal Clusters

| cluster | candidates | strict pass | replay pass | representative |
|---|---:|---:|---:|---|
| `cluster_007` | 21 | 21 | 5 | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($limit_up_streak_ge9,1)` |
| `cluster_001` | 17 | 4 | 5 | `Neg(ZScore(Mean(Delay($market_high_board_leader_ge9,1),8)))` |
| `cluster_003` | 14 | 10 | 0 | `Neg(CSRank($post_market_high_board_leader_ge7_d1))` |
| `cluster_038` | 13 | 0 | 0 | `Neg(ZScore(Mean(Delay($limit_up_streak,1),5)))` |
| `cluster_036` | 12 | 0 | 0 | `CSRank(CSResidual(CSRank(Sub(Mean(Delay($limit_up_touch_not_close,1),2),Mean(Delay($limit_up_touch_not_close,1),24))),CS` |
| `cluster_017` | 10 | 0 | 5 | `Neg(CSRank(Mean(Delay($market_high_board_leader_ge8,1),15)))` |
| `cluster_008` | 9 | 9 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($volume,1),Mean($volume,5))),ZScore(Sub(Mean(Delay($market_high_board_leader_ge9,1),2),Me` |
| `cluster_002` | 6 | 0 | 3 | `Neg(CSRank(Mean(Delay($market_high_board_leader_ge8,1),7)))` |
| `cluster_009` | 6 | 2 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($amount,1),Mean($amount,5))),ZScore(Sub(Mean(Delay($market_high_board_leader_ge8,1),2),Me` |
| `cluster_011` | 6 | 0 | 3 | `Neg(CSRank($post_market_high_board_active_ge8_d1))` |
| `cluster_018` | 6 | 0 | 0 | `Neg(ZScore(Delay($market_high_board_coleader_ge5,1)))` |
| `cluster_027` | 6 | 0 | 0 | `Neg(ZScore(Mul(Mean(Delay($limit_up_touch_event,1),3),3)))` |
| `cluster_035` | 6 | 0 | 0 | `Neg(ZScore(Mean(Delay($limit_up_touch_not_close,1),5)))` |
| `cluster_039` | 6 | 0 | 0 | `Neg(ZScore(Mean(Delay($limit_up_streak,1),6)))` |
| `cluster_029` | 5 | 0 | 0 | `CSRank(CSResidual(CSRank(Sub(Mean(Delay($limit_up_open_not_close,1),2),Mean(Delay($limit_up_open_not_close,1),27))),CSRa` |
| `cluster_004` | 4 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($break_after_high_board_ge10,1),2),Mean(Delay($break_after_high_board_ge10,1` |
| `cluster_006` | 4 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($limit_up_streak_ge10,1),2),Mean(Delay($limit_up_streak_ge10,1),3))),CSRank(` |
| `cluster_025` | 4 | 2 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,25))),ZScore(Sub(Mean(Delay($limit_up_streak_ge8,1)` |
| `cluster_032` | 4 | 0 | 0 | `Neg(ZScore(Mul(Mean(Delay($limit_up_touch_event,1),12),12)))` |
| `cluster_014` | 3 | 3 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($amount,1),Mean($amount,4))),ZScore(Sub(Mean(Delay($break_after_high_board_ge9,1),2),Mean` |
| `cluster_016` | 3 | 3 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($turnover_rate,1),Mean($turnover_rate,11))),ZScore(Sub(Mean(Delay($limit_up_streak_ge8,1)` |
| `cluster_024` | 3 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($limit_up_streak_ge10,1),2),Mean(Delay($limit_up_streak_ge10,1),13))),CSRank` |
| `cluster_010` | 2 | 2 | 0 | `Neg(CSRank(Delay($market_high_board_coleader_ge6,1)))` |
| `cluster_012` | 2 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($market_high_board_active_ge3,1),2),Mean(Delay($market_high_board_active_ge3` |
| `cluster_013` | 2 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($limit_up_streak_ge10,1),2),Mean(Delay($limit_up_streak_ge10,1),3))),CSRank(` |
| `cluster_020` | 2 | 0 | 0 | `Neg(CSRank(Delay($market_high_board_nonleader_ge4,1)))` |
| `cluster_021` | 2 | 0 | 0 | `Neg(CSRank(Mul(ZScore(Div(Mean($volume,1),Mean($volume,7))),ZScore(Sub(Mean(Delay($limit_up_streak_ge8,1),2),Mean(Delay(` |
| `cluster_030` | 2 | 0 | 1 | `Neg(CSRank(Delay($limit_up_open_not_close,1)))` |
| `cluster_037` | 2 | 0 | 0 | `Neg(ZScore(Delay($limit_up_touch_event,1)))` |
| `cluster_005` | 1 | 0 | 0 | `Neg(CSRank(CSResidual(CSRank(Sub(Mean(Delay($market_high_board_active_ge4,1),2),Mean(Delay($market_high_board_active_ge4` |

## Required Next Action

- If strict low-corr candidates exist: run longer-window OOS/recent regime replay before any KEEP.
- If strict passes are concentrated in one cluster: do not promote; reroute reward memory with cluster-capped credit.
- If limit/event bucket fails strict replay: keep limit/event as diagnostic generator, not official book component.
