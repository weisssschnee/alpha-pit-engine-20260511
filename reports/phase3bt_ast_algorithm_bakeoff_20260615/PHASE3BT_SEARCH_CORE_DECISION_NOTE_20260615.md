# Phase3BT Search Core Decision Note 2026-06-15

Decision: `LOCK_AST_AWARE_FRESH_PRESERVING_HYBRID_AS_PRIMARY_DIAGNOSTIC_ONLY`

## What Ran

Phase3BT ran a five-arm true-1min AST-aware algorithm bakeoff:

- `round1_seed_ast_rx_ucb_fresh`
- `round2_ast_feedback_cem`
- `round3_ast_feedback_hybrid`
- `round4_ast_cem_dominant_ucb`
- `round5_ast_fresh_preserving_hybrid`

All arms used real `trade_time` minute panels from `runtime/phase3au_aq_only_true1min_sharded_20260611`.
No old daily stock-PIT panel was used.

## Result

| arm | score | research pool | hard blocked | AST shapes |
|---|---:|---:|---:|---:|
| `round5_ast_fresh_preserving_hybrid` | 0.6312 | 42 | 0.9821 | 8 |
| `round1_seed_ast_rx_ucb_fresh` | 0.5916 | 34 | 0.9643 | 9 |
| `round2_ast_feedback_cem` | 0.5762 | 29 | 0.9732 | 12 |
| `round3_ast_feedback_hybrid` | 0.4895 | 23 | 1.0000 | 9 |
| `round4_ast_cem_dominant_ucb` | 0.4680 | 15 | 0.9464 | 11 |

## Interpretation

The strongest arm was not pure CEM and not pure RX/UCB. The winner was a blended arm that kept feedback from AST-aware CEM but preserved fresh exploration entropy.

This means:

- AST variables are useful.
- CEM feedback is useful.
- CEM-dominant allocation is still not justified.
- Fresh exploration should stay as a dedicated budget line.

## Next Large-search Allocation

Recommended first large-search split:

- `round5_ast_fresh_preserving_hybrid`: 45%
- `round2_ast_feedback_cem`: 25%
- `round1_seed_ast_rx_ucb_fresh`: 20%
- control / residual probe: 10%

This is a search-core allocation decision only. It is not alpha promotion evidence.

## Boundary

- X0/R3 remains read-only.
- No candidate from Phase3BT enters production.
- `research_pool` means deeper review queue, not deployable proof.
- Any future promotion still needs new-vs-memory, signal-vector recluster, cost replay, OOS/regime review, and marginal book audit.
