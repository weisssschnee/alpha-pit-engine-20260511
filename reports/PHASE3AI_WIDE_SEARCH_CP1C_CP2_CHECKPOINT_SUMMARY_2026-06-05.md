# Phase3AI Wide Search CP1c/CP2 Checkpoint Summary

date: 2026-06-05

## Scope

Company-machine checkpoint search only. This is not alpha promotion evidence.

## CP1c

Purpose: fix CP1/CP1b sharding stride and verify mature search/evaluation path.

Configuration:

- `rx_typed_beam`
- 8 shards
- 256 candidates per shard
- max active workers: 4
- successive halving enabled
- search memory enabled

Result:

- completed shards: 8/8
- failed shards: 0
- total ledger: 926
- total evaluated: 460
- top Sortino: 4.603697
- top expression family: `rx_beam_open_gap_x_vol_curve`

Interpretation:

CP1c fixed the empty-shard issue. Mature worker/evaluator chain is functional.

## CP2a

Purpose: expand beam/window search and tighten family cap after CP1c.

Configuration:

- `rx_typed_beam`
- 16 shards
- 192 candidates per shard
- target window count: 36
- beam width: 384
- max beam records: 65536
- max family share: 0.08
- memory includes CP1c

Result:

- completed shards: 16/16
- failed shards: 0
- total ledger: 1378
- total evaluated: 785
- top Sortino: 7.593864
- top return: 0.001621
- top candidate: `stockpit-ff-319bd1146b44`
- top expression: `CSRank(CSResidual(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))),CSRank(Div(Mean(Abs($ret),3),Mean(Abs($ret),6)))))`
- top family: `rx_beam_open_gap_x_vol_curve`

Interpretation:

CP2a is a strong-family reconfirmation, not broad-family discovery. The best candidates concentrate in open-gap residual versus short volatility curve.

## CP2b

Purpose: orthogonal checkpoint after CP2a, with tighter family cap and CP1c/CP2a memory.

Configuration:

- `rx_typed_beam`
- 24 shards
- 128 candidates per shard
- target window count: 48
- beam width: 512
- max beam records: 98304
- max family share: 0.02
- memory includes CP1c and CP2a

Result:

- completed shards: 24/24
- failed shards: 0
- total ledger: 381
- total evaluated: 374
- top Sortino: 4.976787
- top return: 0.001179
- top candidate: `stockpit-ff-b397a210add8`
- top expression: `CSRank(CSResidual(CSRank(Div(Sub($open,Delay($close,1)),Delay($close,1))),CSRank(Div(Mean(Abs($ret),1),Mean(Abs($ret),78)))))`
- top family: `rx_beam_open_gap_x_vol_curve`

Interpretation:

Even aggressive family pressure still returns to the same family among top results. Strict orthogonal pressure reduces throughput and quality before it discovers a clearly better non-dominant family.

## Current Technical Conclusion

The immediate wide-search checkpoint did not reveal a stronger broad-family frontier. It found a robust dominant family:

`open gap residual / volatility curve normalization`

This should be treated as a family requiring deep audit, OOS/regime validation, and cluster/new-vs-baseline checks. Continuing to blindly suppress this family is not currently efficient.

## Next Work

1. Pull checkpoint aggregate CSVs from company machine.
2. Run duplicate/new-vs-baseline and family-level audit.
3. Deep-audit the dominant open-gap x volatility family.
4. Separately wire the new enrichment/minute feature panel into mature search; current CP runs used the mature PIT stock dataset, not the full new enrichment matrix.

## Boundaries

- no promotion from these checkpoints
- no X0/R3 modification
- no production claim
- top Sortino values are cheap/recent validation diagnostics only
