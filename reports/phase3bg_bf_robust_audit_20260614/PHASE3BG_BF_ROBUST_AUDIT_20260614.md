# Phase3BG BF Robust Audit

decision: `PHASE3BG_BF_ROBUST_AUDIT_COMPLETE_HOLD_RESEARCH`

- completed chunks: `128 / 128`
- raw result rows: `73728`
- audited candidate-horizon rows: `4608`
- stable rows: `2715`

## Guardrails

- Input is Phase3BF true 1min shard output with real `trade_time`.
- This is robustness triage, not promotion evidence.
- X0/R3 remains read-only.

## Lane Summary

| source | factor lane | rows | stable | best | stable mean spread t |
|---|---|---:|---:|---|---:|
| `phase3bf_exploit` | `bf_exploit_ba_ay_ax_add_capacity_add` | 940 | 713 | `phase3bf_ba_exploit_fresh_00372` | 0.981741 |
| `phase3bf_exploit` | `bf_exploit_ba_ay_ax_add_capacity_resid` | 940 | 445 | `phase3bf_ba_exploit_fresh_00483` | 0.570346 |
| `phase3bf_pure_fresh` | `bf_fresh_capacity_price_resid` | 572 | 359 | `phase3bf_ba_exploit_fresh_01000` | 1.173702 |
| `phase3bf_exploit` | `bf_exploit_ba_triple_add_capacity_add` | 288 | 288 | `phase3bf_ba_exploit_fresh_00608` | 1.820852 |
| `phase3bf_exploit` | `bf_exploit_ba_triple_add_capacity_resid` | 288 | 278 | `phase3bf_ba_exploit_fresh_00515` | 1.111837 |
| `phase3bf_exploit` | `bf_exploit_ba_ay_ax_add_opening_intensifier` | 580 | 182 | `phase3bf_ba_exploit_fresh_00314` | 0.622263 |
| `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 572 | 166 | `phase3bf_ba_exploit_fresh_00820` | 1.801950 |
| `phase3bf_exploit` | `bf_exploit_ba_triple_add_opening_intensifier` | 192 | 142 | `phase3bf_ba_exploit_fresh_00447` | 0.849784 |
| `phase3bf_pure_fresh` | `bf_fresh_capacity_opening_add` | 236 | 142 | `phase3bf_ba_exploit_fresh_00984` | 0.692580 |

## Robust Top

| rank | candidate | h | source | factor | pos spread ratio | mean spread t | mean IC abs | score |
|---:|---|---:|---|---|---:|---:|---:|---:|
| 1 | `phase3bf_ba_exploit_fresh_00820` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.626438 | 0.102487 | 2.959025 |
| 2 | `phase3bf_ba_exploit_fresh_00812` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.583279 | 0.101949 | 2.949641 |
| 3 | `phase3bf_ba_exploit_fresh_00999` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.804191 | 0.089221 | 2.925210 |
| 4 | `phase3bf_ba_exploit_fresh_00939` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.713380 | 0.094355 | 2.899418 |
| 5 | `phase3bf_ba_exploit_fresh_00879` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.672106 | 0.099040 | 2.872220 |
| 6 | `phase3bf_ba_exploit_fresh_00871` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.633704 | 0.098534 | 2.846656 |
| 7 | `phase3bf_ba_exploit_fresh_00991` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.903360 | 0.089014 | 2.809835 |
| 8 | `phase3bf_ba_exploit_fresh_01111` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.786271 | 0.087898 | 2.797670 |
| 9 | `phase3bf_ba_exploit_fresh_01059` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.619631 | 0.093012 | 2.792330 |
| 10 | `phase3bf_ba_exploit_fresh_00931` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.714135 | 0.093987 | 2.768173 |
| 11 | `phase3bf_ba_exploit_fresh_01051` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.616661 | 0.092682 | 2.755381 |
| 12 | `phase3bf_ba_exploit_fresh_01119` | 5 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.763369 | 0.088064 | 2.754242 |
| 13 | `phase3bf_ba_exploit_fresh_00820` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.558248 | 0.115548 | 2.460611 |
| 14 | `phase3bf_ba_exploit_fresh_00879` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.585089 | 0.111524 | 2.439189 |
| 15 | `phase3bf_ba_exploit_fresh_00879` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.089916 | 0.117593 | 2.419350 |
| 16 | `phase3bf_ba_exploit_fresh_01119` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.149447 | 0.105678 | 2.415208 |
| 17 | `phase3bf_ba_exploit_fresh_00999` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.236117 | 0.106787 | 2.391649 |
| 18 | `phase3bf_ba_exploit_fresh_00999` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.718201 | 0.101077 | 2.381715 |
| 19 | `phase3bf_ba_exploit_fresh_00939` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.681631 | 0.107048 | 2.375890 |
| 20 | `phase3bf_ba_exploit_fresh_01119` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.623047 | 0.099839 | 2.371767 |
| 21 | `phase3bf_ba_exploit_fresh_01059` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.060552 | 0.111490 | 2.361294 |
| 22 | `phase3bf_ba_exploit_fresh_00820` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.944249 | 0.122028 | 2.343919 |
| 23 | `phase3bf_ba_exploit_fresh_00939` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 4.188061 | 0.113040 | 2.334813 |
| 24 | `phase3bf_ba_exploit_fresh_01059` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.546898 | 0.105575 | 2.328006 |
| 25 | `phase3bf_ba_exploit_fresh_01111` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.852082 | 0.104640 | 2.323873 |
| 26 | `phase3bf_ba_exploit_fresh_01111` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.370877 | 0.099215 | 2.298720 |
| 27 | `phase3bf_ba_exploit_fresh_00871` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.716667 | 0.116977 | 2.259088 |
| 28 | `phase3bf_ba_exploit_fresh_00991` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.441199 | 0.100645 | 2.223151 |
| 29 | `phase3bf_ba_exploit_fresh_00871` | 15 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.203568 | 0.111246 | 2.205504 |
| 30 | `phase3bf_ba_exploit_fresh_01051` | 30 | `phase3bf_pure_fresh` | `bf_fresh_capacity_price_add` | 1.000 | 3.508544 | 0.111023 | 2.201339 |
