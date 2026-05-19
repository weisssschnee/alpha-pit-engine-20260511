# Crypto A7B Funding Baseline Audit

- generated_at: `2026-05-19T11:14:02Z`
- decision: `HOLD_A7B_FUNDING_BASELINE_DOMINANCE_RISK`
- blockers: `['Core4_recent_not_above_funding_only', 'Core4_validation_not_above_funding_only']`
- risk_variant: `R3_vol_target_gross_0p5x_cap`

## 10bps Baseline Comparison

| object | split | ann mean | compounded DD | month pass | mean gross | mean turnover |
|---|---|---:|---:|---:|---:|---:|
| `B0_Core4` | `validation_2025H1` | 1.0632 | -0.4878 | 0.500 | 0.500 | 0.097 |
| `B0_Core4` | `recent_oos_2025H2_2026Apr` | 0.5808 | -0.5209 | 0.700 | 0.500 | 0.100 |
| `B0_Core4` | `fresh_forward_2026May` | -2.7641 | -0.1763 | 0.000 | 0.500 | 0.096 |
| `B1_funding_only` | `validation_2025H1` | 1.9697 | -0.3767 | 0.833 | 0.493 | 0.029 |
| `B1_funding_only` | `recent_oos_2025H2_2026Apr` | 0.7863 | -0.6195 | 0.800 | 0.495 | 0.031 |
| `B1_funding_only` | `fresh_forward_2026May` | -2.8562 | -0.1808 | 0.000 | 0.500 | 0.033 |
| `B2_price_only` | `validation_2025H1` | -1.4115 | -0.5273 | 0.167 | 0.500 | 0.141 |
| `B2_price_only` | `recent_oos_2025H2_2026Apr` | -1.2631 | -0.6511 | 0.000 | 0.500 | 0.157 |
| `B2_price_only` | `fresh_forward_2026May` | -1.4050 | -0.1156 | 0.000 | 0.500 | 0.152 |
| `B3_basis_only` | `validation_2025H1` | -0.0083 | -0.3700 | 0.333 | 0.500 | 0.172 |
| `B3_basis_only` | `recent_oos_2025H2_2026Apr` | -1.0524 | -0.6039 | 0.200 | 0.500 | 0.141 |
| `B3_basis_only` | `fresh_forward_2026May` | -4.0260 | -0.1684 | 0.000 | 0.500 | 0.142 |
| `B4_price_x_funding` | `validation_2025H1` | 0.9659 | -0.5591 | 0.667 | 0.500 | 0.090 |
| `B4_price_x_funding` | `recent_oos_2025H2_2026Apr` | 0.4484 | -0.5108 | 0.700 | 0.500 | 0.100 |
| `B4_price_x_funding` | `fresh_forward_2026May` | -2.5130 | -0.1752 | 0.000 | 0.500 | 0.094 |
| `B5_basis_x_funding` | `validation_2025H1` | 1.1781 | -0.4021 | 0.667 | 0.496 | 0.102 |
| `B5_basis_x_funding` | `recent_oos_2025H2_2026Apr` | 0.7069 | -0.5424 | 0.800 | 0.499 | 0.102 |
| `B5_basis_x_funding` | `fresh_forward_2026May` | -3.0462 | -0.1816 | 0.000 | 0.500 | 0.099 |
| `B6_Core4_residual_vs_funding` | `validation_2025H1` | 0.1914 | -0.4068 | 0.667 | 0.500 | 0.097 |
| `B6_Core4_residual_vs_funding` | `recent_oos_2025H2_2026Apr` | 0.4433 | -0.1492 | 0.700 | 0.500 | 0.100 |
| `B6_Core4_residual_vs_funding` | `fresh_forward_2026May` | -0.6414 | -0.0673 | 0.000 | 0.500 | 0.096 |

## May Failure Attribution

| object | May total | May ann proxy | worst hour | top3 loss sum | mean turnover |
|---|---:|---:|---:|---:|---:|
| `B0_Core4` | -0.1222 | -2.4324 | -0.0073 | -0.0197 | 0.0960 |
| `B1_funding_only` | -0.1066 | -2.1215 | -0.0081 | -0.0222 | 0.0331 |
| `B2_price_only` | -0.0824 | -1.6404 | -0.0071 | -0.0191 | 0.1496 |
| `B3_basis_only` | -0.1453 | -2.8925 | -0.0121 | -0.0286 | 0.1389 |
| `B4_price_x_funding` | -0.1138 | -2.2651 | -0.0074 | -0.0204 | 0.0927 |
| `B5_basis_x_funding` | -0.1315 | -2.6178 | -0.0071 | -0.0202 | 0.1001 |
| `B6_Core4_residual_vs_funding` | -0.0385 | -0.7656 | -0.0046 | -0.0112 | 0.0960 |

## Interpretation

- If Core4 does not beat funding-only under the same R3 scaling and costs, it cannot be promoted as independent alpha proof.
- Residual vs funding is computed using train-period linear residualization only.
- This audit does not search or tune new formulas.
