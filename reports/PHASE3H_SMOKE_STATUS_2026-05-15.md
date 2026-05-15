# Phase3H Smoke Status

Date: 2026-05-15

## Decision

Decision: `PASS_PHASE3H_SMOKE_FROM_SHARED_SELECTION`.

This is a smoke result, not an official Phase3H matrix.

## What Changed

The smoke no longer uses the old heavy per-arm runner path.

The execution path is now:

```text
1. Generate one shared pre-replay candidate pool.
2. Apply H0/H1/H2/H3 selectors to that frozen pool.
3. Run strict/replay/cluster only for the selected smoke rows.
```

This fixes the earlier issue where `--selection-only` repeated candidate/stage1 generation for every arm.

## Shared Selector Dry Run

Dry-run decision: `PASS_SELECTOR_ONLY_DRYRUN`.

Shared candidate pool:

- candidate pool count: `388`
- default selected count: `64`

Selector-only queue metrics:

| Arm | Selector | Selected | H1 overlap | Median turnover proxy | Mean selected-queue signal corr | Agnostic selected | Repair expansion selected |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H0 | `standard_D3` | 64 | n/a | 0.056112 | 0.0 | 12 | 8 |
| H1 | `signal_vector_diversified_proxy` | 64 | 1.0 | 0.057411 | 0.448196 | 16 | 8 |
| H2 | `signal_vector_turnover_calibrated_proxy` | 64 | 0.921875 | 0.056112 | 0.471939 | 14 | 8 |
| H3 | `signal_vector_diversified_proxy` | 64 | 1.0 | 0.057411 | 0.448196 | 16 | 8 |

Interpretation:

- H2 is not identical to H1.
- H2 turnover proxy is slightly lower than H1.
- H3 is expected to match H1 behaviorally; its purpose is canonical baseline metadata validation.
- No selector replay-label leakage was detected.

## Smoke Result

Smoke scale:

```text
H0/H1/H2/H3 x seed33 x 16 audited
```

Smoke metrics:

| Arm | Audited | Deployable clusters | Top cluster share |
| --- | ---: | ---: | ---: |
| H0 G0 stable | 16 | 3 | 66.6667% |
| H1 G2 signal-vector control | 16 | 7 | 11.1111% |
| H2 G2 turnover calibrated | 16 | 7 | 11.1111% |
| H3 G2 registry canonicalized | 16 | 7 | 11.1111% |

Interpretation:

- G2-based arms clearly beat H0 in smoke.
- H1/H2/H3 all preserve low concentration at smoke scale.
- H2 does not lose deployable clusters relative to H1 in smoke.
- H3 matches H1, which is expected because canonicalization is currently a metadata policy, not a new vector artifact.

## Runtime Finding

The source shared pool generation is still expensive:

- base/stage1 path took roughly one hour locally.
- applying selectors to the shared pool took roughly 29 minutes because H1/H2/H3 compute signal-vector features.
- strict/replay/cluster smoke took roughly 17 minutes.

The expensive part is now isolated. Official Phase3H should use this shared-pool path or run detached on the company machine, not the old four-arm repeated runner.

## Next Action

Proceed to Phase3H official only through shared candidate pool execution.

Recommended official path:

```text
H0/H1/H2/H3 x seeds33-36 x 64 audited
```

Run condition:

- Use detached company-machine execution or a shared-cache local runner.
- Do not use the old per-arm generation path.

Primary decision target:

- If H1 stays materially above H0, G2 becomes primary incumbent.
- If H2 keeps H1-level deployable count with lower turnover, H2 becomes the production candidate.
- If H3 diverges materially from H1, registry canonicalization has selector impact and requires deeper audit.
