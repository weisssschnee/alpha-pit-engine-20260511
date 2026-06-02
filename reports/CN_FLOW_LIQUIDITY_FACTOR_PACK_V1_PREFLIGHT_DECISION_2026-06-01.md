# CN Flow Liquidity Factor Pack V1 Preflight Decision

decision: `PASS_FLOW_LIQUIDITY_PACK_AND_SELECTOR_ONLY_GATE_NO_REPLAY`

## Confirmed

- Dedicated flow/liquidity/capacity-normalized factor pack was built.
- The pack is independent from event/fundamental lanes and uses `source_lane = cn_flow_liquidity_feature_layer`.
- Shared-pool injection supports explicit research-factor candidates instead of mislabeling flow fields as event candidates.
- All 306 flow/liquidity candidate rows were found in the enriched shared pool after safe-division regeneration.
- Field coverage preflight passed with no missing panel or mature signal-vector fields.
- `turnover_ratio`, `turnover_ratio_real`, seal-flow fields, `daily_ret`, and `actual_circulation_value` are now explicit evaluator optional/full-day fields.
- Signal-vector runtime disk caching is active for newly injected expression families.
- Tiny and 64-budget selector-only gates completed without replay-label leakage.
- Key-artifact manifest was written to preserve important reports and runtime outputs before workspace cleanup.

## Counts

- factor pack rows: 306
- enriched pool rows: 1937
- factor pack rows in enriched pool: 306
- factor fields used: 26
- missing from derived/panel fields: 0
- missing from mature signal-vector panel: 0

## Factor Lanes

- flow_relative_activity: 32
- flow_impulse: 16
- flow_volatility: 16
- price_flow_divergence: 8
- price_flow_confirmation: 8
- capacity_normalized_flow: 8
- capacity_residual_flow: 4
- amihud_illiquidity: 4
- event_x_flow_liquidity: 180
- fundamental_x_flow: 30

## Selector Gate Status

Initial selector-only attempts were stopped because signal-vector computation did not finish within the interactive gate window:

- 64-budget / pool-cap 256 / signal-sample 384 timed out before writing artifacts.
- 32-budget / pool-cap 96 / signal-sample 96 also timed out before writing artifacts.

Those attempts are superseded by the cached safe-div selector gates below.

Tiny gate:

- output: `runtime/cn_flow_liquidity_factor_pack_v1_tiny_selector_20260601/selector_safe_v2/aa/phase3_selection_only_report.json`
- total selected: 16
- selected source counts:
  - `cn_flow_liquidity_feature_layer`: 8
  - `cn_research_feature_layer_v2`: 2
  - `unknown`: 6
- research bucket selected: 5 / 16
- selected signal-vector errors: 0
- selected hard rejects: 0
- forbidden replay-label usage: false

64 selector-only gate:

- output: `runtime/cn_flow_liquidity_factor_pack_v1_selector64_20260601/selector_safe_v2/aa/phase3_selection_only_report.json`
- total selected: 64
- selected source counts:
  - `cn_flow_liquidity_feature_layer`: 32
  - `cn_research_feature_layer_v2`: 9
  - `unknown`: 23
- research bucket selected: 19 / 64
- selected signal-vector errors: 0
- selected hard rejects: 0
- missing `turnover_ratio` signal-vector errors: 0
- pool-level operator-pathology rejects: 3 / 160, none selected
- runtime signal-vector disk cache entries: 127 vectors
- forbidden replay-label usage: false

Interpretation:

- The previous flow lane starvation was an engineering issue: stale priority, missing evaluator fields, and unsafe `Div()` expressions.
- The flow/liquidity lane now reaches frozen selection under the mature G2 selector path.
- This is still selector-only. It does not prove alpha performance, deployability, or replay survival.
- Replay should only be run as an explicit next gate with frozen queues and attribution.

## Next Required Step

Run a replay smoke only if the next phase explicitly accepts selector-only evidence:

```text
cn_flow_liquidity_factor_pack_v1
-> enriched shared pool
-> cached signal-vector selector-only
-> source/family attribution
-> frozen 64 queue replay smoke
-> source/family/replay attribution
```

## Protected Artifacts

- `runtime/factor_packs/cn_flow_liquidity_factor_candidate_pack_v1_20260601.json`
- `reports/cn_flow_liquidity_factor_pack_v1_20260601/CN_FLOW_LIQUIDITY_FACTOR_PACK_V1_2026-06-01.md`
- `runtime/cn_flow_liquidity_factor_pack_v1_phase3aa_preflight_20260601/shared_candidate_pool_event_fund_flow_enriched.json`
- `reports/cn_flow_liquidity_factor_pack_v1_preflight_20260601/CN_FACTOR_PACK_SHARED_POOL_PREFLIGHT_2026-05-31.md`
- `runtime/cn_flow_liquidity_factor_pack_v1_selector64_20260601/selector_safe_v2/aa/phase3_selection_only_report.json`
- `runtime/cn_flow_liquidity_factor_pack_v1_selector64_20260601/selector_safe_v2/aa/phase3e_selector_audit.csv`
- `runtime/phase3g_signal_vectors/runtime_eval_cache_flow_v1_selector64_safe_v2/`
- `runtime/manifests/cn_data_feature_workspace_key_artifacts_20260601.json`
