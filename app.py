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
