# Phase3AV Fresh Neighbor Pack

decision: `PHASE3AV_FRESH_NEIGHBOR_PACK_READY`

## Counts

- candidate_count: `900`
- seed_count: `268`
- min_shard_coverage: `12`
- min_ic_count: `400`

## Factor Lanes

- av_capacity_context_interaction: `162`
- av_capacity_context_residual: `162`
- av_capacity_flow_acceleration: `72`
- av_capacity_flow_impulse: `132`
- av_capacity_flow_volatility: `132`
- av_capacity_normalized_flow: `120`
- av_capacity_residual_flow: `120`

## Rules

- True 1min input only; no old 1D kline route.
- Event/auction fields are not promoted into this direct formula pack.
- Existing Phase3AU expression hashes are excluded before writing candidates.
- X0/R3 remains read-only.
