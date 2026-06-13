# Phase3BE Backend Decision Record

## Decision

`KEEP_PANDAS_AS_DEFAULT_PROOF_EVALUATOR`

The Phase3AS/true-1min proof and replay path remains pandas-backed. The numba work is useful, but it is not yet allowed to replace the proof evaluator or produce promotion evidence.

## Evidence

### Phase3BC Kernel Canary

Single-kernel acceleration is promising:

- grouped rank, zscore, rolling mean, delta, and mom parity passed in the kernel canary
- warm benchmarks showed large speedups for isolated hot loops

This proves that numba can accelerate specific kernels. It does not prove that full nested formula evaluation is safe.

### Phase3BC Expression Parity Canary

Expression-level parity failed:

- input: fixed Phase3BA/BB expressions
- panel: true-1min sidecar panel
- `date == trade_time`: true
- pass: `0/16`
- nonfinite mismatches: zero

Reading: this is not a missing-field issue, and not an old 1D kline issue. The divergence is finite-value rank divergence in nested `CSRank` expressions, likely caused by tiny floating-point differences in rolling/zscore subexpressions changing pandas exact-tie rank behavior.

### Phase3BD Replay Metric-Diff Canary

Replay-level ranking was stable, but strict metric tolerance still failed:

- panel rows: `1,306,461`
- candidates: `16`
- horizons: `1,5,15,30`
- top5 ranking: pass on all horizons
- eval speedup: `5.1033x`
- max metric absolute diff: `0.00033895113454474046`
- tolerance: `0.0001`
- largest diff source: `spread_hit_rate`

This is encouraging for future diagnostic acceleration, but it is not clean enough for proof-default replacement.

## Locked Policy

Allowed:

- continue large searches with pandas proof evaluator
- use numba kernels in isolated acceleration audits
- use numba-hybrid only behind an explicit diagnostic flag after stronger replay metric-diff evidence
- use numba for non-proof prefiltering only when final candidate ranking is revalidated by pandas

Forbidden:

- make numba-hybrid the default proof evaluator
- claim Phase3BC or Phase3BD as alpha proof
- promote any candidate using numba-hybrid-only metrics
- modify X0/R3 or official chain state from BC/BD/BE

## Stable Object

- object: `runtime/baselines/phase3be_backend_decision_record_v1.json`
- stable hash: `4673a6cce15838e5135825c6c6ff7968f540381dd254d798d3ab1628a2d867e4`
- hash excludes `created_at` and the hash field itself

## Next Search Contract

The next large search can proceed only with this boundary:

- pandas remains the final replay/proof evaluator
- numba may be used only for diagnostic kernel profiling or non-proof prefilter experiments
- every candidate that matters must be replayed under pandas before being called a result
- X0/R3 remains read-only
