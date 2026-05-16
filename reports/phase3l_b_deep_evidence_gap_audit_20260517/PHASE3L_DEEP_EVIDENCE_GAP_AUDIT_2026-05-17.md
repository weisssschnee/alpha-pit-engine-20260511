# Phase3L Deep Evidence Gap Audit

- generated_at: 2026-05-17T03:31:20+08:00
- decision: `HOLD_KEEP_PROMOTION_PENDING_DEEP_TESTS`
- l2_cluster_count: 12
- sign_flip_queue_count: 12
- low_order_queue_count: 22
- deep_test_queue_count: 61

## Main Finding

The current L2 book is large enough for a daily-proxy proof pack, but no L2 cluster is eligible for KEEP/promotion until subperiod, regime, sign-flip, and low-order ablation tests are run.

## L2 Source Mix

- formula_gen_v2_repair_expansion: 6
- agnostic_freeform_ast: 4
- r0_cem_led: 2

## Blocking Tests

- subperiod stability replay
- regime bucket replay
- sign-flip placebo
- low-order ablation
- minute execution/capacity remains outside daily proof scope

## Decision

`HOLD_KEEP_PROMOTION_PENDING_DEEP_TESTS`: proceed to Phase3L-E deep test batch; do not expand search yet.
