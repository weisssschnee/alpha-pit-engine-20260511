# Crypto A7.1 Baseline / Placebo Suite

- generated_at: `2026-05-19T10:30:33Z`
- decision: `HOLD_A7_1_BASELINE_PLACEBO_SUITE`
- pass_count: `1/4`
- cost_bps: `10.0`

## Cluster Decisions

| cluster | validation ann | recent ann | best component | component margin | best placebo | sign flip | decision |
|---|---:|---:|---:|---:|---:|---:|---|
| `crypto_a4_1h_001` | 3.5044 | 1.7110 | 3.7077 | -1.9967 | -1.5534 | -7.5903 | `HOLD_COMPONENT_PLACEBO_GATE` |
| `crypto_a4_1h_002` | 5.4530 | 3.7870 | 6.7792 | -2.9921 | -0.9258 | -13.3976 | `HOLD_COMPONENT_PLACEBO_GATE` |
| `crypto_a4_1h_003` | 4.1123 | 1.5515 | 0.5141 | 1.0374 | 0.0239 | -5.7018 | `PASS_COMPONENT_PLACEBO_GATE` |
| `crypto_a4_1h_004` | 4.2232 | 1.8763 | 6.7792 | -4.9029 | -1.7806 | -10.3497 | `HOLD_COMPONENT_PLACEBO_GATE` |

## Boundary

- This validates fixed Core4 formulas against component baselines and placebo variants.
- `future_lag_probe_24h` is recorded in the CSV as a leakage probe, not a valid trading variant.
- Passing A7.1 does not validate book risk scaling; A7.2 handles that.
