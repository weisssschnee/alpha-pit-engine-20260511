# Crypto A6.4 Core4 Conservative Robustness

- generated_at: `2026-05-19T08:26:12Z`
- decision: `PASS_A6_4_CONSERVATIVE_ROBUSTNESS`
- gross_cap: `0.2`

## Recent OOS 10bp Cluster Leave-One-Out

| subset | removed | ann mean | compounded max DD | month pass | mean turnover | min hour |
|---|---|---:|---:|---:|---:|---:|
| `Core4_full` | `` | 0.2359 | -0.2496 | 0.700 | 0.0381 | -0.0042 |
| `LOO_without_crypto_a4_1h_001` | `crypto_a4_1h_001` | 0.2579 | -0.2900 | 0.700 | 0.0399 | -0.0049 |
| `LOO_without_crypto_a4_1h_002` | `crypto_a4_1h_002` | 0.1885 | -0.2270 | 0.700 | 0.0330 | -0.0042 |
| `LOO_without_crypto_a4_1h_003` | `crypto_a4_1h_003` | 0.2449 | -0.2698 | 0.600 | 0.0445 | -0.0048 |
| `LOO_without_crypto_a4_1h_004` | `crypto_a4_1h_004` | 0.2520 | -0.2141 | 0.700 | 0.0350 | -0.0047 |

## Boundary

- This checks whether the conservative dry-shadow result depends on a single Core4 cluster.
- Passing A6.4 does not authorize live trading; it only supports append-only dry shadow observation.
