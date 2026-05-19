# Crypto A6.2 Core4 Risk Scaling

- generated_at: `2026-05-19T08:19:25Z`
- decision: `HOLD_A6_2_NO_RISK_SCALED_SHADOW_CANDIDATE`
- selected_variant: `none`
- scope: fixed Core4 only; no formula changes, no cluster changes, no OOS parameter optimization

## Fixed Variants

| variant | rule |
|---|---|
| `R0_unscaled` | multiplier = 1 |
| `R1_gross_1x_cap` | multiplier = min(1, 1.0 / current gross exposure) |
| `R2_rolling_vol_target_50bp` | multiplier = min(1, 0.5% hourly target / lagged rolling 20d vol) |
| `R3_vol_target_gross_0p5x_cap` | R2 plus multiplier capped by 0.5 gross exposure |

## Recent OOS Summary

| variant | cost | ann mean | compounded max DD | additive max DD | month pass | mean multiplier | mean gross | mean turnover | min hour |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `R0_unscaled` | `normal_5bp` | 3.9461 | -0.9334 | -2.6663 | 0.800 | 1.000 | 1.990 | 0.379 | -0.0422 |
| `R0_unscaled` | `severe_20bp` | -1.0322 | -0.9705 | -3.4467 | 0.400 | 1.000 | 1.990 | 0.379 | -0.0426 |
| `R0_unscaled` | `stress_10bp` | 2.2867 | -0.9441 | -2.8397 | 0.700 | 1.000 | 1.990 | 0.379 | -0.0423 |
| `R1_gross_1x_cap` | `normal_5bp` | 2.0144 | -0.7423 | -1.3447 | 0.800 | 0.502 | 0.999 | 0.191 | -0.0211 |
| `R1_gross_1x_cap` | `severe_20bp` | -0.4904 | -0.8215 | -1.7027 | 0.400 | 0.502 | 0.999 | 0.191 | -0.0213 |
| `R1_gross_1x_cap` | `stress_10bp` | 1.1795 | -0.7642 | -1.4334 | 0.700 | 0.502 | 0.999 | 0.191 | -0.0212 |
| `R2_rolling_vol_target_50bp` | `normal_5bp` | 2.3889 | -0.7830 | -1.5156 | 0.900 | 0.647 | 1.287 | 0.243 | -0.0300 |
| `R2_rolling_vol_target_50bp` | `severe_20bp` | -0.8091 | -0.8625 | -1.9596 | 0.400 | 0.647 | 1.287 | 0.243 | -0.0303 |
| `R2_rolling_vol_target_50bp` | `stress_10bp` | 1.3229 | -0.8016 | -1.6047 | 0.700 | 0.647 | 1.287 | 0.243 | -0.0301 |
| `R3_vol_target_gross_0p5x_cap` | `normal_5bp` | 1.0072 | -0.4909 | -0.6724 | 0.800 | 0.251 | 0.500 | 0.095 | -0.0105 |
| `R3_vol_target_gross_0p5x_cap` | `severe_20bp` | -0.2452 | -0.5753 | -0.8513 | 0.400 | 0.251 | 0.500 | 0.095 | -0.0106 |
| `R3_vol_target_gross_0p5x_cap` | `stress_10bp` | 0.5897 | -0.5130 | -0.7167 | 0.700 | 0.251 | 0.500 | 0.095 | -0.0106 |

## Gate

- A6.2 pass requires a fixed variant with recent OOS 10bp annualized > 30%, compounded max DD better than -30%, and monthly pass rate >= 70%.
- Passing A6.2 only allows A6.3 tradable book replay / execution calibration. It does not allow live trading.
