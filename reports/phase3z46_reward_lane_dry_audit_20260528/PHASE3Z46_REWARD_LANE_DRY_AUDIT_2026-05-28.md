# Phase3Z46 Reward Lane Dry Audit

- decision: `PASS_Z46_REWARD_DRY_AUDIT`
- candidate_count: `5`
- scope: diagnostic only; no search; no official promotion.

## Checks

- overlay_rejects_not_overlay_top: `True`
- cluster_007_event_module_or_veto_not_overlay: `True`
- cluster_002_not_overlay_promoted: `True`
- fragile_candidates_receive_penalty: `True`
- cluster_030_short_horizon_diagnostic: `True`

## Lane Scores

| cluster | top lane | decision | overlay | challenger | event module | veto/intensifier | evidence penalty |
|---|---|---|---:|---:|---:|---:|---:|
| cluster_030 | `veto_intensifier` | `VERY_SHORT_HORIZON_DIAGNOSTIC_ONLY` | -0.698765 | -0.793126 | -1.04526 | -0.63442 | 0.65 |
| cluster_001 | `veto_intensifier` | `REJECT_OR_DIAGNOSTIC_ONLY` | -0.670638 | -0.897911 | -1.299263 | -0.732644 | 0.85 |
| cluster_017 | `veto_intensifier` | `REJECT_OR_DIAGNOSTIC_ONLY` | -0.678684 | -0.911992 | -1.177448 | -0.87704 | 1.0 |
| cluster_002 | `challenger` | `REJECT_OR_DIAGNOSTIC_ONLY` | -0.704489 | -0.899398 | -0.915151 | -1.31049 | 1.35 |
| cluster_007 | `veto_intensifier` | `REJECT_OR_DIAGNOSTIC_ONLY` | -0.881113 | -1.843487 | -1.612746 | -1.341952 | 1.45 |

## Interpretation

- Z45b remains failed as X0/R3 overlay.
- Z46 canary is allowed only if reward dry audit passes and remains diagnostic.
- Positive event-module or challenger labels are not promotion decisions.
