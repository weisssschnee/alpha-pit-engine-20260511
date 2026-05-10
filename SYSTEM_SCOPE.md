# Our System Scope

## What This System Is

This repository is the independent workspace for `Our System Phase 1`.

Note: the repository name and some historical scope text still say Phase 1.
As of 2026-04-25, active implementation work in this worktree is Phase 2
generation/runtime work under `src/our_system_phase2`. The Phase 1 language
below remains the historical boundary condition: do not turn this repository
into an AlphaCFG fork, AlphaGPT fork, latent-first experiment, or baseline
retraining workspace.

It is a new research-system layer built on top of an existing local AlphaCFG-style baseline result, without modifying the official AlphaCFG baseline code and without restoring archived A5 code into mainline.

The current phase is `CFG-first / system-layer-first`.

The current phase is explicitly designed to:

- keep search control and evaluation separated
- keep diversity on an independent track
- preserve a strict evaluator funnel
- separate archive storage from frontier scheduling
- preserve multi-head scoring instead of collapsing back into one reward

## What This System Is Not

This repository is not:

- an AlphaCFG fork
- an AlphaGPT fork
- an `alphagpt_a5` recovery workspace
- a latent-first experiment
- a benchmark-redefinition project
- a rewrite of the baseline training engine

This repository must never be used to:

- modify the official AlphaCFG snapshot into Our System
- copy the A5 archive into active source code
- blend official baseline code and Our System in one code layer

## Current Phase Does

Phase 1 lands the minimum research-system skeleton around an existing baseline result.

Allowed work in this phase:

- behavior grid independent track
- multi-fidelity evaluator interfaces
- archive / frontier / lineage minimum viable skeleton
- run registry / benchmark entry / trace schema
- core objects such as `SearchState`, `ActionProposal`, `EvaluationRecord`, `FrontierEntry`
- a minimal research loop that can ingest an existing baseline result and write trace, registry, archive, and frontier artifacts

## Current Phase Does Not

Phase 1 must not implement:

- latent encoder
- latent decoder
- latent MCTS
- any latent-first attempt
- behavior grid mixed back into reward
- final large-scale archive/frontier system
- benchmark protocol changes
- baseline retraining as the main task
- direct edits to the AlphaCFG codebase
- direct recovery of A5 into mainline

## Phase 1 Exit Criteria

Phase 1 is considered landed when this repository contains:

- an explicit readonly source registry
- the minimum object layer
- the minimum service layer
- a runnable minimal entrypoint
- a smoke or contract test
- artifact output for trace, registry, archive, and frontier state
