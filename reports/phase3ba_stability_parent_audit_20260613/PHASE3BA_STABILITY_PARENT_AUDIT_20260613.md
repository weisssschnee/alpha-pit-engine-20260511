# Phase3BA Stability And Parent Audit

decision: `PHASE3BA_STABILITY_PARENT_AUDIT_HOLD_RESEARCH`

## Scope

- run root: `G:\Project_V7_Rotation\alpha_pit_data_feature_workspace_20260531\runtime\phase3ba_company_focused_minute_expansion_20260612`
- shard rows: `49152`
- candidates audited: `768`
- horizons audited: `3072`
- X0/R3: read-only

## Parent Benchmarks

- AX capacity-flow: top `phase3ax_capacity_refine_00325` lane `ax_inverse_capacity_flow_level` mean_abs_ic `0.15970064510437587`
- AZB opening-window: top `phase3azb_opening_window_corrected_00105` lane `azb_opening_direct` mean_abs_ic `0.12403355807298115`
- AY X0/core minute transfer: top `phase3ay_x0_minute_transfer_00499` lane `ay_old_family_capacity_add` mean_abs_ic `0.14707123143453601`

## Lane Stability

| lane | count | mean stability | max abs IC | top candidate | top fields |
|---|---:|---:|---:|---|---|
| `ba_triple_add` | 232 | 0.124886 | 0.163647 | `phase3ba_focused_minute_expansion_00663` | `amount|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| `ba_ay_ax_add` | 160 | 0.124725 | 0.171042 | `phase3ba_focused_minute_expansion_00296` | `amount|final_total_market_cap|vwap` |
| `ba_ax_resid_opening` | 212 | 0.116994 | 0.148116 | `phase3ba_focused_minute_expansion_00079` | `amount|float_share|m1_first5_amount` |
| `ba_ay_resid_opening` | 352 | 0.111004 | 0.141524 | `phase3ba_focused_minute_expansion_00597` | `amount|amount_yuan|close|final_float_market_cap|float_share|m1_first15_range` |
| `ba_ay_azb_add` | 352 | 0.101484 | 0.152202 | `phase3ba_focused_minute_expansion_00380` | `m1_first30_high|m1_first30_low|open|vwap` |
| `ba_ay_resid_ax` | 160 | 0.099553 | 0.135940 | `phase3ba_focused_minute_expansion_00360` | `amount|close|final_total_market_cap|vwap` |
| `ba_triple_interaction` | 232 | 0.099022 | 0.123717 | `phase3ba_focused_minute_expansion_00712` | `amount|float_share|m1_first30_range|m1_first30_vol|vwap` |
| `ba_ax_azb_add_inverse` | 216 | 0.093308 | 0.156402 | `phase3ba_focused_minute_expansion_00027` | `amount|float_share|m1_first30_high|m1_first30_low|open` |
| `ba_ax_azb_add` | 216 | 0.093308 | 0.156402 | `phase3ba_focused_minute_expansion_00026` | `amount|float_share|m1_first30_high|m1_first30_low|open` |
| `ba_ax_resid_ay` | 160 | 0.091943 | 0.127759 | `phase3ba_focused_minute_expansion_00298` | `amount|final_total_market_cap|vwap` |
| `ba_opening_resid_ay` | 352 | 0.083090 | 0.109908 | `phase3ba_focused_minute_expansion_00562` | `amount|close|final_float_market_cap|float_share|m1_first30_range|m1_first30_vol` |
| `ba_opening_resid_ax` | 212 | 0.075392 | 0.109017 | `phase3ba_focused_minute_expansion_00005` | `amount|float_share|m1_first30_amount` |

## Top Stable Candidates

| rank | candidate | horizon | lane | stability | mean abs IC | sign consistency | fields |
|---:|---|---:|---|---:|---:|---:|---|
| 1 | `phase3ba_focused_minute_expansion_00296` | 30 | `ba_ay_ax_add` | 0.170015 | 0.171042 | 1.000 | `amount|final_total_market_cap|vwap` |
| 2 | `phase3ba_focused_minute_expansion_00302` | 30 | `ba_ay_ax_add` | 0.169652 | 0.170684 | 1.000 | `amount|final_total_market_cap|vwap` |
| 3 | `phase3ba_focused_minute_expansion_00287` | 30 | `ba_ay_ax_add` | 0.169422 | 0.170444 | 1.000 | `amount|final_float_market_cap|vwap` |
| 4 | `phase3ba_focused_minute_expansion_00290` | 30 | `ba_ay_ax_add` | 0.169111 | 0.170138 | 1.000 | `amount|final_float_market_cap|vwap` |
| 5 | `phase3ba_focused_minute_expansion_00359` | 30 | `ba_ay_ax_add` | 0.166875 | 0.167885 | 1.000 | `amount|close|final_total_market_cap|vwap` |
| 6 | `phase3ba_focused_minute_expansion_00317` | 30 | `ba_ay_ax_add` | 0.166238 | 0.167230 | 1.000 | `amount|close|final_float_market_cap|vwap` |
| 7 | `phase3ba_focused_minute_expansion_00323` | 30 | `ba_ay_ax_add` | 0.166042 | 0.167033 | 1.000 | `amount|close|final_float_market_cap|vwap` |
| 8 | `phase3ba_focused_minute_expansion_00329` | 30 | `ba_ay_ax_add` | 0.165184 | 0.166175 | 1.000 | `amount|close|final_float_market_cap|vwap` |
| 9 | `phase3ba_focused_minute_expansion_00341` | 30 | `ba_ay_ax_add` | 0.164972 | 0.165988 | 1.000 | `amount|final_total_market_cap|vwap` |
| 10 | `phase3ba_focused_minute_expansion_00305` | 30 | `ba_ay_ax_add` | 0.164752 | 0.165771 | 1.000 | `amount|final_float_market_cap|vwap` |
| 11 | `phase3ba_focused_minute_expansion_00338` | 30 | `ba_ay_ax_add` | 0.164719 | 0.165710 | 1.000 | `amount|close|final_float_market_cap|vwap` |
| 12 | `phase3ba_focused_minute_expansion_00356` | 30 | `ba_ay_ax_add` | 0.164381 | 0.165407 | 1.000 | `amount|final_total_market_cap|vwap` |
| 13 | `phase3ba_focused_minute_expansion_00311` | 30 | `ba_ay_ax_add` | 0.164183 | 0.165214 | 1.000 | `amount|final_float_market_cap|vwap` |
| 14 | `phase3ba_focused_minute_expansion_00320` | 30 | `ba_ay_ax_add` | 0.164009 | 0.165045 | 1.000 | `amount|final_float_market_cap|vwap` |
| 15 | `phase3ba_focused_minute_expansion_00350` | 30 | `ba_ay_ax_add` | 0.163824 | 0.164824 | 1.000 | `amount|close|final_float_market_cap|vwap` |
| 16 | `phase3ba_focused_minute_expansion_00353` | 30 | `ba_ay_ax_add` | 0.163307 | 0.164351 | 1.000 | `amount|final_float_market_cap|vwap` |
| 17 | `phase3ba_focused_minute_expansion_00269` | 30 | `ba_ay_ax_add` | 0.163190 | 0.164252 | 1.000 | `amount|float_share|vwap` |
| 18 | `phase3ba_focused_minute_expansion_00272` | 30 | `ba_ay_ax_add` | 0.163063 | 0.164127 | 1.000 | `amount|float_share|vwap` |
| 19 | `phase3ba_focused_minute_expansion_00663` | 30 | `ba_triple_add` | 0.162687 | 0.163647 | 1.000 | `amount|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 20 | `phase3ba_focused_minute_expansion_00667` | 30 | `ba_triple_add` | 0.162618 | 0.163578 | 1.000 | `amount|float_share|m1_first30_range|vwap` |
| 21 | `phase3ba_focused_minute_expansion_00683` | 30 | `ba_triple_add` | 0.162576 | 0.163539 | 1.000 | `amount|float_share|m1_first30_high|m1_first30_low|open|vwap` |
| 22 | `phase3ba_focused_minute_expansion_00687` | 30 | `ba_triple_add` | 0.162502 | 0.163464 | 1.000 | `amount|float_share|m1_first30_range|vwap` |
| 23 | `phase3ba_focused_minute_expansion_00659` | 30 | `ba_triple_add` | 0.161353 | 0.162371 | 1.000 | `amount|float_share|m1_first15_amount|vwap` |
| 24 | `phase3ba_focused_minute_expansion_00655` | 30 | `ba_triple_add` | 0.161097 | 0.162102 | 1.000 | `amount|float_share|m1_first30_amount|vwap` |
| 25 | `phase3ba_focused_minute_expansion_00679` | 30 | `ba_triple_add` | 0.161045 | 0.162063 | 1.000 | `amount|float_share|m1_first15_amount|vwap` |

## Interpretation

- Phase3BA should be treated as research evidence, not deployable alpha proof.
- The strongest direction is old/core minute transfer plus capacity-flow.
- Opening-window features are useful mainly as interaction or residual controls.
- Next follow-up should test parent overlap, polarity, and horizon stability before any X0/R3 marginal audit.
