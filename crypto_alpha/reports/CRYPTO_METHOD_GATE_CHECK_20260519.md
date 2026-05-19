# Crypto Method Gate Check

- generated_at: `2026-05-19T05:12:54Z`
- decision: `PASS_METHOD_GATE`
- method: `G:\AlphaFactory_CryptoData\alphafactory_crypto\config\crypto_alphafactory_method_v1.json`

## Panel Checks

| interval | rows | symbols | duplicate keys | timestamp gaps | positioning columns | label columns in panel |
|---|---:|---:|---:|---:|---:|---|
| `5m` | 2941056 | 12 | 0 | 0 | 0 | `['fwd_ret_1', 'fwd_ret_12', 'fwd_ret_24', 'fwd_ret_3', 'fwd_ret_6']` |
| `1h` | 245088 | 12 | 0 | 0 | 0 | `['fwd_ret_1', 'fwd_ret_12', 'fwd_ret_24', 'fwd_ret_3', 'fwd_ret_6']` |

## Blockers

- none

## Warnings

- none

## Interpretation

- `fwd_ret_*` columns are allowed to exist only as labels for evaluation.
- Search/generator code must consume an explicit feature allowlist, not all panel columns.
- CN references remain reference-only until a crypto-native generator/reward implementation is used.
