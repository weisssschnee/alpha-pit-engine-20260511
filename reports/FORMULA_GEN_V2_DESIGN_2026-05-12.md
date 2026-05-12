# Formula Generator V2

Date: 2026-05-12

## Status

Standalone implementation added. It is not wired into the current Phase3B B0-B3 runner, so the active ablation remains clean.

## Scope

New package:

```text
src/our_system_phase2/formula_gen_v2/
  __init__.py
  macros.py
  motif_pack_core.yaml
  motif_pack_external_public.yaml
  paired_ablation.py
  sampler.py
  typed_ast.py
```

## Design

The generator is motif-first and role-based.

Roles:

- `B`: base signal
- `C`: confirmation
- `S`: state / gate
- `N`: normalizer, currently represented by wrappers
- `R`: risk / neutralization wrapper, kept outside formula tree for now

Primary formula shape:

```text
base signal * confirmation * state/gate * normalizer
```

The sampler no longer needs to start from random `x/y/operator` composition. It samples:

```text
complexity tier
-> compose motif
-> role family
-> field family
-> windows
-> wrapper
-> constraint check
```

## Implemented Macros

- `delta_persistence(x, n)`
- `delta_autocorr(x, n)`
- `second_diff(x)`
- `signed_square(x)`
- `price_volume_confirm(price, flow, n)`
- `price_volume_diverge(price, flow, n)`

## Motif Pack

`motif_pack_core.yaml` includes:

- temporal autoregression
- liquidity acceleration
- price-volume confirmation
- nonlinear signed magnitude
- signal-confirm-state triple interaction
- 20 seed motif templates

`motif_pack_external_public.yaml` is a dictionary-only motif source. It stores public-project grammar bias categories, not scores or benchmark results.

## Paired Ablation

For a full formula with slots:

```text
F = B * C * S
```

the module can emit:

```text
B
C
S
B*C
B*S
C*S
B*C*S
```

Promotion rule intended for Phase3C:

```text
full_score > max(low_order_scores) + margin
```

or full produces a new cluster / lower correlation / lower turnover.

## Hard Constraints

Implemented first-pass checks:

- max tree depth
- max temporal ops
- max Corr ops
- no nested Corr
- max signed-square patterns
- product inputs must be normalized or sign-bounded

## AST Repair Extensions

Standalone helper added:

- `add_confirmation`
- `add_state_gate`
- `temporalize`
- `nonlinearize`
- `add_confirmation_state`
- `add_second_diff_confirmation`

These are not yet wired into the active AST repair lane.

## CEM Slot-Level Credit

Implemented helper:

```text
update_motif_slot_distribution(...)
```

Credit terms:

- deployable cluster success
- new cluster bonus
- AST repair escape bonus
- duplicate cluster penalty
- turnover penalty
- complexity penalty
- operator pathology penalty
- low-order ablation failure penalty
- marginal complexity win bonus

Duplicate clusters are downweighted by:

```text
1 / sqrt(1 + cluster_seen_count)
```

## Tests

```text
pytest tests/test_formula_gen_v2.py tests/test_stock_pit_phase3_repair_quota.py -q
```

Current result:

```text
10 passed
```

## Phase3C Integration Plan

After Phase3B aggregate completes:

1. Add `formula_gen_v2` as a new search lane.
2. Keep existing CEM/R0 at 40%.
3. Keep AST repair at 30%.
4. Allocate formula_gen_v2 motif sampler 20%.
5. Allocate external public motif pack 10%.
6. Require paired ablation report for every high-order candidate before promotion.
7. Judge by deployable unique clusters, non-gap replay, top cluster share, and low-order marginal value.

