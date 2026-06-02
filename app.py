"""Unified entrypoint for the locked Alpha PIT research chain.

This file intentionally stays thin. It routes to existing Git-tracked
runtime modules and prevents diagnostic scripts from looking official.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
LOCK_FILE = ROOT / "runtime" / "baselines" / "phase3_algorithm_chain_lock_v1.json"


COMMANDS: dict[str, dict[str, str | bool]] = {
    "proof-suite": {
        "module": "our_system_phase2.runtime.stock_pit_proof_suite",
        "diagnostic": False,
        "description": "Run stock PIT proof suite.",
    },
    "phase3h-official": {
        "module": "our_system_phase2.runtime.phase3h_run_shared_official",
        "diagnostic": False,
        "description": "Run Phase3H shared-pool official path.",
    },
    "phase3h-aggregate": {
        "module": "our_system_phase2.runtime.phase3h_official_shared_aggregate",
        "diagnostic": False,
        "description": "Aggregate Phase3H official shared path.",
    },
    "phase3j-filter-audit": {
        "module": "our_system_phase2.runtime.phase3j_cluster_book_filter_audit",
        "diagnostic": False,
        "description": "Run Phase3J cluster book filter audit.",
    },
    "phase3k-locked-validation": {
        "module": "our_system_phase2.runtime.phase3k_locked_book_validation",
        "diagnostic": False,
        "description": "Run Phase3K locked book validation.",
    },
    "phase3o-freeze-x0": {
        "module": "our_system_phase2.runtime.phase3o_freeze_x0_shadow_object",
        "diagnostic": False,
        "description": "Rebuild/freeze X0 official shadow object.",
    },
    "phase3p-forward": {
        "module": "our_system_phase2.runtime.phase3p_locked_daily_forward",
        "diagnostic": False,
        "description": "Run locked daily forward export.",
    },
    "phase3s-time-split-audit": {
        "module": "our_system_phase2.runtime.phase3s_time_split_research_freedom_audit",
        "diagnostic": False,
        "description": "Run Phase3S time split / research freedom audit.",
    },
    "runtime-state": {
        "module": "our_system_phase2.runtime.phase3_runtime_state_registry",
        "diagnostic": False,
        "description": "Inspect or update the lightweight runtime state registry.",
    },
    "phase3aa-mature-chain": {
        "module": "our_system_phase2.runtime.phase3aa_run_mature_chain",
        "diagnostic": False,
        "description": "Run Phase3AA through shared pool, event-derived factor injection, source-priority G2 selection, and optional replay.",
    },
    "phase3aa-cached-mature-pool": {
        "module": "our_system_phase2.runtime.phase3aa_run_cached_mature_pool",
        "diagnostic": False,
        "description": "Run Phase3AA from an existing mature shared pool without fresh pool generation.",
    },
    "phase3aa-smoke-from-selection": {
        "module": "our_system_phase2.runtime.phase3aa_smoke_from_shared_selection",
        "diagnostic": False,
        "description": "Replay Phase3AA frozen selector output without regenerating candidates.",
    },
    "phase3aa-asset-preflight": {
        "module": "our_system_phase2.runtime.phase3aa_asset_preflight",
        "diagnostic": False,
        "description": "Verify mature-chain assets before launching Phase3AA searches.",
    },
    "phase3aa-result-audit": {
        "module": "our_system_phase2.runtime.phase3aa_cached_result_audit",
        "diagnostic": False,
        "description": "Audit Phase3AA cached-pool selection and replay source attribution.",
    },
    "cn-controlled-data-smoke": {
        "module": "our_system_phase2.runtime.cn_controlled_data_smoke",
        "diagnostic": False,
        "description": "Smoke-test controlled CN data sources and emit the field registry.",
    },
    "cn-event-derived-feature-smoke": {
        "module": "our_system_phase2.runtime.cn_event_derived_feature_smoke",
        "diagnostic": False,
        "description": "Build a controlled CN event-derived daily feature smoke panel.",
    },
    "cn-field-factor-pack": {
        "module": "our_system_phase2.runtime.cn_field_factor_pack",
        "diagnostic": False,
        "description": "Build the CN field-to-factor conversion plan and candidate factor pack.",
    },
    "cn-factor-pack-preflight": {
        "module": "our_system_phase2.runtime.cn_factor_pack_shared_pool_preflight",
        "diagnostic": False,
        "description": "Preflight CN field/factor pack integration into mature shared pool without replay.",
    },
    "cn-build-augmented-signal-panel": {
        "module": "our_system_phase2.runtime.cn_build_augmented_signal_panel",
        "diagnostic": False,
        "description": "Build the mature signal-vector/evaluator panel augmented with CN event-derived fields.",
    },
    "cn-signal-vector-event-smoke": {
        "module": "our_system_phase2.runtime.cn_signal_vector_event_field_smoke",
        "diagnostic": False,
        "description": "Smoke-test event-derived factor expressions through the Phase3G signal-vector store.",
    },
    "cn-fundamental-controlled-smoke": {
        "module": "our_system_phase2.runtime.cn_fundamental_controlled_smoke",
        "diagnostic": False,
        "description": "Smoke-test aggregated CN fundamental data and emit PIT field contracts.",
    },
    "cn-fundamental-pit-panel": {
        "module": "our_system_phase2.runtime.cn_fundamental_pit_feature_panel",
        "diagnostic": False,
        "description": "Build a conservative PIT daily feature panel from aggregated CN fundamentals.",
    },
    "cn-research-factor-pack-v2": {
        "module": "our_system_phase2.runtime.cn_research_factor_pack_v2",
        "diagnostic": False,
        "description": "Build the combined CN event plus PIT fundamental research factor pack.",
    },
    "cn-build-research-signal-panel-v2": {
        "module": "our_system_phase2.runtime.cn_build_research_signal_panel_v2",
        "diagnostic": False,
        "description": "Build the mature evaluator panel augmented with CN event and PIT fundamental fields.",
    },
    "cn-field-utilization-audit": {
        "module": "our_system_phase2.runtime.cn_field_utilization_audit",
        "diagnostic": False,
        "description": "Audit panel fields through encoder, factor pack, shared pool, selector queue, and replay rows.",
    },
    "cn-flow-liquidity-factor-pack-v1": {
        "module": "our_system_phase2.runtime.cn_flow_liquidity_factor_pack_v1",
        "diagnostic": False,
        "description": "Build a dedicated CN flow/liquidity/capacity-normalized research factor pack.",
    },
    "cn-underutilized-field-factor-pack-v1": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_factor_pack_v1",
        "diagnostic": False,
        "description": "Build a broad CN underutilized-field factor pack across flow, seal, capacity, theme, price, and fundamental activity fields.",
    },
    "cn-underutilized-field-family-smoke": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_family_smoke",
        "diagnostic": False,
        "description": "Run a family-balanced signal-vector smoke for underutilized CN field factor packs without replay.",
    },
    "cn-underutilized-field-batched-selector-smoke": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_batched_selector_smoke",
        "diagnostic": False,
        "description": "Run batched mature G2 selector-only smoke for underutilized CN field factor packs without replay.",
    },
    "cn-underutilized-field-replay-smoke-gate": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_replay_smoke_gate",
        "diagnostic": False,
        "description": "Freeze batched selector256 unique rows and run a replay smoke gate without regenerating candidates.",
    },
    "cn-underutilized-field-survivor-attribution": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_survivor_attribution",
        "diagnostic": False,
        "description": "Attribute underutilized-field replay survivors by source, factor lane, skeleton, field family, and registry proxy.",
    },
    "cn-underutilized-field-registry-recluster": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_registry_recluster",
        "diagnostic": False,
        "description": "Compare underutilized-field deployable survivor representatives against the frozen 149 registry with sampled signal vectors.",
    },
    "cn-underutilized-field-registry-review-queue": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_registry_review_queue",
        "diagnostic": False,
        "description": "Create a baseline-safe registry review queue from provisional-new underutilized-field survivor representatives.",
    },
    "cn-underutilized-field-global-cluster-integration": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_global_cluster_integration",
        "diagnostic": False,
        "description": "Build a candidate 149+13 integrated registry after signal-vector collision checks.",
    },
    "cn-underutilized-field-promote-162-baseline": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_promote_162_baseline",
        "diagnostic": False,
        "description": "Promote the candidate 162 registry to a discovery-only baseline with a stable hash.",
    },
    "cn-underutilized-field-book-readiness-audit": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_book_readiness_audit",
        "diagnostic": False,
        "description": "Run a no-replay book-readiness screen for the 13 newly promoted discovery clusters.",
    },
    "cn-underutilized-field-book-marginal-audit": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_book_marginal_audit",
        "diagnostic": False,
        "description": "Run a no-search B0/B1/B2/B3 book-level marginal audit against locked X0/R3.",
    },
    "cn-underutilized-field-freeze-b2-forward": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_freeze_b2_forward_object",
        "diagnostic": False,
        "description": "Freeze B2 X0/R3 plus six core new field clusters as a diagnostic forward candidate.",
    },
    "cn-underutilized-field-minute-execution-calibration": {
        "module": "our_system_phase2.runtime.cn_underutilized_field_minute_execution_calibration",
        "diagnostic": False,
        "description": "Calibrate X0/R3 and B2 diagnostic forward against available 1-minute execution proxies.",
    },
    "cn-minute-feature-alignment-audit": {
        "module": "our_system_phase2.runtime.cn_minute_feature_alignment_audit",
        "diagnostic": False,
        "description": "Audit 1-minute native fields, lagged daily/enrichment context alignment, and forbidden future-label routes.",
    },
    "cn-minute-feature-panel-v1": {
        "module": "our_system_phase2.runtime.cn_minute_feature_panel_builder",
        "diagnostic": False,
        "description": "Build the minute-native feature panel with prior-day daily/enrichment context and separated execution labels.",
    },
    "cn-minute-feature-panel-v2": {
        "module": "our_system_phase2.runtime.cn_minute_feature_panel_v2_builder",
        "diagnostic": False,
        "description": "Build the multi-year 2023-2026 minute-native code-date feature panel from validated 1min parquet v2.",
    },
    "cn-minute-feature-panel-v2-final-qa": {
        "module": "our_system_phase2.runtime.cn_minute_feature_panel_v2_final_qa",
        "diagnostic": False,
        "description": "Run read-only final QA for the multi-year minute feature panel v2.",
    },
    "cn-minute-feature-signal-scan": {
        "module": "our_system_phase2.runtime.cn_minute_feature_signal_scan",
        "diagnostic": False,
        "description": "Run a diagnostic cross-sectional scan of minute-native and lagged-context features against minute execution labels.",
    },
    "cn-minute-2023-2025-reconvert": {
        "module": "our_system_phase2.runtime.cn_minute_2023_2025_reconvert",
        "diagnostic": False,
        "description": "Reconvert broken 2023-2025 1-minute source zips into valid symbol parquet with OHLCV/amount fields.",
    },
    "cn-multifrequency-field-route-audit": {
        "module": "our_system_phase2.runtime.cn_multifrequency_field_route_audit",
        "diagnostic": False,
        "description": "Route all CN data families into minute-native, timestamped event, lagged daily, announcement/PIT, or diagnostic use classes.",
    },
    "cn-public-enrichment-global-field-route-v1": {
        "module": "our_system_phase2.runtime.cn_public_enrichment_global_field_route_v1",
        "diagnostic": False,
        "description": "Build a global route ledger for all CN public-enrichment fields, probes, 1min schemas, and high-value unwired gaps.",
    },
    "cn-minute-limit-event-alignment": {
        "module": "our_system_phase2.runtime.cn_minute_limit_event_alignment_panel",
        "diagnostic": False,
        "description": "Build timestamp-safe up_limit_time and uplimit_trend event features aligned to the 1-minute panel.",
    },
    "cn-nonminute-field-integration-registry": {
        "module": "our_system_phase2.runtime.cn_nonminute_field_integration_registry",
        "diagnostic": False,
        "description": "Build the non-1min field routing and PIT integration registry for daily, event, disclosure, RZRQ, and fundamental fields.",
    },
    "cn-nonminute-system-integration-audit": {
        "module": "our_system_phase2.runtime.cn_nonminute_system_integration_audit",
        "diagnostic": False,
        "description": "Audit which non-1min registry fields are wired into minute/context/event panels and which remain panelization gaps.",
    },
    "cn-nonminute-pit-context-panel-v1": {
        "module": "our_system_phase2.runtime.cn_nonminute_pit_context_panel_v1",
        "diagnostic": False,
        "description": "Build a PIT-safe non-1min context panel from RZRQ, fundamentals, holders, billboard diagnostics, and market distribution.",
    },
    "cn-nonminute-pit-context-panel-v1-qa": {
        "module": "our_system_phase2.runtime.cn_nonminute_pit_context_panel_v1_qa",
        "diagnostic": False,
        "description": "Run read-only QA for the non-1min PIT context panel v1.",
    },
    "cn-integrated-feature-transform-plan-v1": {
        "module": "our_system_phase2.runtime.cn_integrated_feature_transform_plan_v1",
        "diagnostic": False,
        "description": "Build the selector-facing transform plan across 1min fields, non-1min PIT context, and remaining high-value gaps.",
    },
    "cn-integrated-factor-pack-v1": {
        "module": "our_system_phase2.runtime.cn_integrated_factor_pack_v1",
        "diagnostic": False,
        "description": "Build integrated candidate expressions from 1min and non-1min PIT context fields with search-memory metadata.",
    },
    "cn-integrated-factor-pack-selector-preflight": {
        "module": "our_system_phase2.runtime.cn_integrated_factor_pack_selector_preflight",
        "diagnostic": False,
        "description": "Run no-replay shared-pool safety preflight for the integrated factor pack before heavier G2 selector execution.",
    },
    "cn-integrated-factor-pack-field-availability-audit": {
        "module": "our_system_phase2.runtime.cn_integrated_factor_pack_field_availability_audit",
        "diagnostic": False,
        "description": "Audit whether integrated factor-pack selections are executable on the current replay PIT panel.",
    },
    "cn-integrated-pit-join-preflight": {
        "module": "our_system_phase2.runtime.cn_integrated_pit_join_preflight",
        "diagnostic": False,
        "description": "Preflight the PIT panel join needed to replay CN integrated factor-pack selections.",
    },
    "cn-integrated-pit-selected-panel-builder": {
        "module": "our_system_phase2.runtime.cn_integrated_pit_selected_panel_builder",
        "diagnostic": False,
        "description": "Build selected-field sidecars and joined replay panels for CN integrated factor-pack replay.",
    },
    "cn-zzshare-limit-sentiment-route-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_route_v1",
        "diagnostic": False,
        "description": "Route the ZZShare limit/sentiment pack into PIT-safe event, context, blocked-label, and transform-plan roles.",
    },
    "cn-zzshare-limit-sentiment-factor-pack-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_factor_pack_v1",
        "diagnostic": False,
        "description": "Build ZZShare limit/sentiment candidate expressions from the PIT-safe route plan.",
    },
    "cn-zzshare-limit-sentiment-canonicalize-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_canonicalize_v1",
        "diagnostic": False,
        "description": "Canonicalize ZZShare limit/sentiment raw silver into stock-date event and daily context grains.",
    },
    "cn-zzshare-limit-sentiment-selected-sidecar-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_selected_sidecar_v1",
        "diagnostic": False,
        "description": "Build selected-row PIT sidecar for canonical ZZShare event and sentiment fields.",
    },
    "cn-zzshare-limit-sentiment-joined-panel-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_joined_panel_v1",
        "diagnostic": False,
        "description": "Join ZZShare selected sidecar fields into an existing integrated replay panel.",
    },
    "cn-zzshare-limit-sentiment-field-availability-gate": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_field_availability_gate",
        "diagnostic": False,
        "description": "Check ZZShare factor-pack expression fields against the joined replay panel before selector/replay.",
    },
    "cn-zzshare-limit-sentiment-selector-pool-preflight-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_selector_pool_preflight_v1",
        "diagnostic": False,
        "description": "Verify ZZShare factor candidates are safely visible in the mature shared pool before full G2 selector-only runs.",
    },
    "cn-zzshare-limit-sentiment-selector-only-gate-v1": {
        "module": "our_system_phase2.runtime.cn_zzshare_limit_sentiment_selector_only_gate_v1",
        "diagnostic": False,
        "description": "Aggregate the company-machine mature G2 selector-only gate for ZZShare limit/sentiment candidates.",
    },
    "cn-workspace-key-artifacts": {
        "module": "our_system_phase2.runtime.cn_workspace_key_artifact_manifest",
        "diagnostic": False,
        "description": "Write a non-destructive key-artifact manifest for workspace cleanup.",
    },
    "cn-workspace-cleanup-archive": {
        "module": "our_system_phase2.runtime.cn_workspace_cleanup_archive",
        "diagnostic": False,
        "description": "Archive superseded CN workspace runtime intermediates and remove cache-only directories with protected artifact checks.",
    },
    "phase3ab-large-search": {
        "module": "our_system_phase2.runtime.phase3ab_launch_large_search",
        "diagnostic": False,
        "description": "Launch Phase3AB through mature stock-PIT large-search supervisor with memory and reward controls.",
    },
    "phase3ab-aggregate": {
        "module": "our_system_phase2.runtime.phase3ab_large_search_aggregate",
        "diagnostic": False,
        "description": "Aggregate Phase3AB large-search shard outputs into top-candidate and source-attribution reports.",
    },
    "phase3ab-deep-validate": {
        "module": "our_system_phase2.runtime.phase3ab_candidate_deep_validation",
        "diagnostic": False,
        "description": "Deep-validate Phase3AB aggregate top candidates across long history, OOS, R3, turnover, and cost splits.",
    },
    "phase3ab-deep-compare": {
        "module": "our_system_phase2.runtime.phase3ab_deep_validation_compare",
        "diagnostic": False,
        "description": "Compare completed Phase3AB deep-validation output roots into a combined scoreboard.",
    },
    "phase3ab-r3-challenger-audit": {
        "module": "our_system_phase2.runtime.phase3ab_r3_challenger_audit",
        "diagnostic": False,
        "description": "Audit Phase3AB recent/R3 challengers against the locked X0/R3 incumbent.",
    },
    "phase3ab-challenger-family-audit": {
        "module": "our_system_phase2.runtime.phase3ab_challenger_family_audit",
        "diagnostic": False,
        "description": "Audit Phase3AB R3 challenger family correlation and standalone book value.",
    },
    "diagnostic-catalog": {
        "module": "our_system_phase2.runtime.phase3_diagnostic_asset_catalog",
        "diagnostic": False,
        "description": "Catalog local diagnostic assets without promoting them.",
    },
    "promotion-triage": {
        "module": "our_system_phase2.runtime.phase3_promotion_queue_triage",
        "diagnostic": False,
        "description": "Triage diagnostic assets for promotion gate readiness.",
    },
    "event-derived-feature-audit": {
        "module": "our_system_phase2.runtime.phase3_event_derived_feature_audit",
        "diagnostic": True,
        "description": "Audit limit/event derived feature layer coverage, lag policy, and tradability metadata.",
    },
    "event-adapter-integration-smoke": {
        "module": "our_system_phase2.runtime.phase3_event_adapter_integration_smoke",
        "diagnostic": True,
        "description": "Smoke-test event-derived fields inside the mature diagnostic candidate path.",
    },
    "phase3r-limit-diagnostic": {
        "module": "our_system_phase2.runtime.phase3r_limit_motif_pack_diagnostic",
        "diagnostic": True,
        "description": "Run Phase3R limit motif diagnostic.",
    },
    "phase3r-limit-cheap-eval": {
        "module": "our_system_phase2.runtime.phase3r_limit_diagnostic_cheap_eval",
        "diagnostic": True,
        "description": "Run cheap diagnostic validation for Phase3R limit/event motif formulas.",
    },
    "z39-validate": {
        "module": "our_system_phase2.runtime.phase3z39_automated_validation_flow",
        "diagnostic": True,
        "description": "Run Phase3Z39 automated validation flow.",
    },
    "z45b-result-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_parametric_limit_result_audit",
        "diagnostic": True,
        "description": "Audit Phase3Z45b parametric limit/open/touch strict-validation results.",
    },
    "z45b-deep-identity-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_deep_identity_audit",
        "diagnostic": True,
        "description": "Route Phase3Z45b candidate clusters to OOS/regime, turnover, or sample-expansion audits.",
    },
    "z45b-oos-regime-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_oos_regime_candidate_audit",
        "diagnostic": True,
        "description": "Replay Phase3Z45b deep-identity candidate representatives by OOS/regime/cost splits.",
    },
    "z45b-vs-x0-marginal-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_vs_x0_marginal_audit",
        "diagnostic": True,
        "description": "Compare Phase3Z45b representatives against the locked X0/R3 incumbent as marginal overlays.",
    },
    "z45b-regime-timing-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_regime_timing_audit",
        "diagnostic": True,
        "description": "Measure Phase3Z45b diagnostic candidates by regime slice and holding-horizon decay.",
    },
    "z45b-regime-fragility-audit": {
        "module": "our_system_phase2.runtime.phase3z45b_regime_fragility_audit",
        "diagnostic": True,
        "description": "Check whether Phase3Z45b best regime slices are small-sample, top-day, or random-slice fragile.",
    },
    "z46-reward-dry-audit": {
        "module": "our_system_phase2.runtime.phase3z46_reward_lane_dry_audit",
        "diagnostic": True,
        "description": "Dry-audit Phase3Z46 lane-specific event alpha reward on known Z45b cases.",
    },
    "event-alpha-validation": {
        "module": "our_system_phase2.runtime.phase3_event_alpha_validation",
        "diagnostic": True,
        "description": "Validate event alpha candidates with event counts, placebo, concentration, and tradability metadata.",
    },
    "z46-eventalpha-canary": {
        "module": "our_system_phase2.runtime.phase3z46_eventalpha_canary",
        "diagnostic": True,
        "description": "Run bounded Phase3Z46 EventAlpha canary using event-state candidates and search memory.",
    },
    "z47-event-study": {
        "module": "our_system_phase2.runtime.phase3z47_event_study",
        "diagnostic": True,
        "description": "Run sparse event-study diagnostics with matched controls and placebo.",
    },
    "z48-event-veto-gate-audit": {
        "module": "our_system_phase2.runtime.phase3z48_event_veto_gate_audit",
        "diagnostic": True,
        "description": "Audit Z47 negative-event triggers as stock-level vetoes against locked X0/R3.",
    },
    "z49-event-long-selection-overlap": {
        "module": "our_system_phase2.runtime.phase3z49_event_long_selection_overlap",
        "diagnostic": True,
        "description": "Check whether Z47 negative-event stocks enter locked X0/R3 long selections.",
    },
}


def _load_lock() -> dict[str, Any]:
    with LOCK_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _print_status() -> int:
    lock = _load_lock()
    official = lock["official_algorithm_chain"]
    diagnostic = lock["diagnostic_only_assets"]
    print(f"lock_id: {lock['lock_id']}")
    print(f"authority_commit: {lock['authority']['authority_commit']}")
    print(f"authority_remote: {lock['authority']['git_remote']}")
    print("")
    print("official:")
    print(f"  discovery_primary: {official['discovery_primary']['name']}")
    print(f"  official_shadow: {official['official_shadow']['name']}")
    print(f"  shadow_hash: {official['official_shadow']['stable_object_hash']}")
    print(f"  book_filters: {official['book_filters']['baseline_book_candidate']} + {official['book_filters']['overlay_candidate']}")
    print(f"  forward_shadow: {official['forward_shadow']['name']}")
    print("")
    print("diagnostic_only:")
    for name, payload in diagnostic.items():
        print(f"  {name}: {payload['status']}")
    print("")
    print("policy: diagnostic commands require --allow-diagnostic")
    return 0


def _print_list() -> int:
    print("official commands:")
    for name, payload in COMMANDS.items():
        if not payload["diagnostic"]:
            print(f"  {name}: {payload['description']}")
    print("")
    print("diagnostic commands:")
    for name, payload in COMMANDS.items():
        if payload["diagnostic"]:
            print(f"  {name}: {payload['description']}")
    return 0


def _run_module(command: str, passthrough: list[str], allow_diagnostic: bool) -> int:
    payload = COMMANDS[command]
    if payload["diagnostic"] and not allow_diagnostic:
        print(
            f"Refusing diagnostic command '{command}'. "
            "Re-run with --allow-diagnostic if this is intentional.",
            file=sys.stderr,
        )
        return 2

    module = str(payload["module"])
    src_str = str(SRC)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    old_argv = sys.argv[:]
    sys.argv = [module, *passthrough]
    try:
        runpy.run_module(module, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    finally:
        sys.argv = old_argv
    return 0


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    allow_diagnostic = False
    if "--allow-diagnostic" in raw_argv:
        allow_diagnostic = True
        raw_argv = [arg for arg in raw_argv if arg != "--allow-diagnostic"]

    parser = argparse.ArgumentParser(
        description="Unified entrypoint for the locked Alpha PIT research chain."
    )
    parser.add_argument("command", choices=["status", "list", *COMMANDS.keys()])
    parser.add_argument(
        "--allow-diagnostic",
        action="store_true",
        help="Allow diagnostic-only commands that cannot promote official chain state.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to the selected command. Use '--' before command args.",
    )
    ns = parser.parse_args(raw_argv)
    if ns.allow_diagnostic:
        allow_diagnostic = True

    if ns.command == "status":
        return _print_status()
    if ns.command == "list":
        return _print_list()
    return _run_module(ns.command, ns.args, allow_diagnostic)


if __name__ == "__main__":
    raise SystemExit(main())
