# Crypto A7.2 Core4 Fixed-Split Revalidation

- generated_at: `2026-05-19T10:32:40Z`
- decision: `HOLD_A7_2_CORE4_FIXED_SPLIT_REVALIDATION`
- blockers: `['A7_1_component_placebo_not_all_passed', 'R3_recent_compounded_dd_worse_than_30pct']`
- purge_embargo_bars: `24`

## 10bps Risk Variant Summary

| variant | split | ann mean | compounded DD | month pass | mean gross | mean turnover |
|---|---|---:|---:|---:|---:|---:|
| `R0_unscaled` | `validation_2025H1` | 4.3232 | -0.9374 | 0.500 | 1.993 | 0.384 |
| `R0_unscaled` | `recent_oos_2025H2_2026Apr` | 2.2315 | -0.9426 | 0.800 | 1.960 | 0.392 |
| `R0_unscaled` | `fresh_forward_2026May` | -10.9167 | -0.5414 | 0.000 | 1.985 | 0.382 |
| `R1_gross_1x_cap` | `validation_2025H1` | 2.1264 | -0.7432 | 0.500 | 1.000 | 0.193 |
| `R1_gross_1x_cap` | `recent_oos_2025H2_2026Apr` | 1.1616 | -0.7729 | 0.700 | 1.000 | 0.201 |
| `R1_gross_1x_cap` | `fresh_forward_2026May` | -5.5281 | -0.3219 | 0.000 | 1.000 | 0.192 |
| `R2_rolling_vol_target_50bp` | `validation_2025H1` | 2.6746 | -0.6585 | 0.500 | 0.935 | 0.180 |
| `R2_rolling_vol_target_50bp` | `recent_oos_2025H2_2026Apr` | 1.2035 | -0.8055 | 0.700 | 1.245 | 0.248 |
| `R2_rolling_vol_target_50bp` | `fresh_forward_2026May` | -9.8755 | -0.5309 | 0.000 | 1.454 | 0.282 |
| `R3_vol_target_gross_0p5x_cap` | `validation_2025H1` | 1.0632 | -0.4878 | 0.500 | 0.500 | 0.097 |
| `R3_vol_target_gross_0p5x_cap` | `recent_oos_2025H2_2026Apr` | 0.5808 | -0.5209 | 0.700 | 0.500 | 0.100 |
| `R3_vol_target_gross_0p5x_cap` | `fresh_forward_2026May` | -2.7641 | -0.1763 | 0.000 | 0.500 | 0.096 |

## LOO Gates

- symbol_loo_recent_positive_rate: `1.0`
- cluster_loo_recent_min_ann: `1.7129265003734993`

## Decision Rule

- A7.2 requires A7.1 all-pass, positive validation/recent R3 10bps, recent month pass >= 60%, R3 recent DD better than -30%, symbol LOO positive rate >= 75%, and cluster LOO min recent annualized > 0.
- Passing A7.2 would allow A7.3 generator/reward bakeoff. It would not authorize trading.
