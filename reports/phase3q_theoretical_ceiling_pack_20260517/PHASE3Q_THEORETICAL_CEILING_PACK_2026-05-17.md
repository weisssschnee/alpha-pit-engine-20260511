# Phase3Q Theoretical Ceiling Pack

- decision: `PASS_PHASE3Q_THEORETICAL_CEILING_PACK_CREATED`
- scope: `daily_proxy_theoretical_ceiling_no_execution_no_capacity`

## Key Ceilings

- best formal: `X0_official_6 + R3_liquidity_low` ann `1.175657` sharpe `4.547115` max_dd `-0.03442312`
- best non-oracle: `X1_research_9 + R3_liquidity_low` ann `1.272218` sharpe `4.491351` max_dd `-0.03901198`
- best any/oracle-inclusive: `X1_research_9 + R3_liquidity_low` ann `1.272218` sharpe `4.491351` max_dd `-0.03901198`

## Top 2026 OOS Daily Proxy Rows

| variant | status | gate | ann | sharpe | max dd | total return | active ratio |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| X1_research_9 | research_pool | R3_liquidity_low | 1.272218 | 4.491351 | -0.03901198 | 0.282624 | 0.487179 |
| X1_research_9 | research_pool | R5_vol_or_trendlow_or_liqlow | 1.241418 | 3.828726 | -0.05255119 | 0.275048 | 0.666667 |
| X4_official_6_plus_003_minus_002 | research_diagnostic | R3_liquidity_low | 1.233439 | 4.654946 | -0.03200173 | 0.276518 | 0.487179 |
| X2_official_6_plus_003 | research_diagnostic | R3_liquidity_low | 1.232187 | 4.600898 | -0.03557461 | 0.276165 | 0.487179 |
| X2_official_6_plus_003 | research_diagnostic | R5_vol_or_trendlow_or_liqlow | 1.203128 | 3.933869 | -0.04481682 | 0.269071 | 0.666667 |
| X4_official_6_plus_003_minus_002 | research_diagnostic | R5_vol_or_trendlow_or_liqlow | 1.191343 | 3.957584 | -0.04254272 | 0.267166 | 0.666667 |
| X0_official_6 | formal_shadow | R3_liquidity_low | 1.175657 | 4.547115 | -0.03442312 | 0.266314 | 0.487179 |
| X3_official_6_minus_002 | research_diagnostic | R3_liquidity_low | 1.165981 | 4.600731 | -0.02990281 | 0.264765 | 0.487179 |
| X5_oracle_005_003_004 | oracle_diagnostic_only | R3_liquidity_low | 1.164205 | 4.638039 | -0.02564761 | 0.264549 | 0.487179 |
| X0_official_6 | formal_shadow | R5_vol_or_trendlow_or_liqlow | 1.128189 | 3.827856 | -0.04184402 | 0.255818 | 0.666667 |
| X5_oracle_005_003_004 | oracle_diagnostic_only | R5_vol_or_trendlow_or_liqlow | 1.12476 | 4.02354 | -0.03519963 | 0.25594 | 0.666667 |
| X3_official_6_minus_002 | research_diagnostic | R5_vol_or_trendlow_or_liqlow | 1.099947 | 3.833085 | -0.03851379 | 0.250918 | 0.666667 |

## Boundary

- The daily proxy blotter is not a broker execution blotter.
- Oracle diagnostic rows are theoretical ceilings only and must not be used as formal selection rules.
- No minute slippage, true capacity, live survival, or fill feasibility is confirmed.
