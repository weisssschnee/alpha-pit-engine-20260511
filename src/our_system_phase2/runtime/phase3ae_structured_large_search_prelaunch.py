"""Build Phase3AE structured large-search prelaunch plan.

This command does not start search. It freezes the lane-based prelaunch gate
after field searcher adaptation and replay128-vs-149 consolidation.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SEARCHER_JSON = Path("reports/cn_field_searcher_adaptation_audit_v1_20260604/field_searcher_adaptation_audit.json")
DEFAULT_SEARCHER_SUMMARY = Path("reports/cn_field_searcher_adaptation_audit_v1_20260604/searcher_adaptation_summary.csv")
DEFAULT_RECLUSTER_JSON = Path("reports/phase3ae_replay128_recluster_vs_149_20260604/phase3ae_replay128_recluster_vs_149.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3ae_structured_large_search_prelaunch_20260604")
DEFAULT_RUNTIME_ROOT = Path("runtime/phase3ae_structured_large_search_prelaunch_20260604")
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3ae_structured_large_search_prelaunch_v1.json")


LANES: list[dict[str, Any]] = [
    {
        "arm": "AE0_mature_G2_baseline",
        "lane": "baseline",
        "role": "control",
        "input": "mature G2 selector with frozen 149 discovery baseline",
        "selector_only_selected": 256,
        "replay_canary_audited": 64,
        "primary_question": "Does the mature G2 baseline still behave under the AE shared-pool path?",
        "pass_criteria": [
            "no forbidden field hits",
            "top cluster share and turnover comparable to recent G2 controls",
            "new-vs-149 accounting available",
        ],
    },
    {
        "arm": "AE1_direct_lagged_formula",
        "lane": "direct_lagged_formula",
        "role": "structured_search_lane",
        "input": "1774 direct formula-ready fields, especially PE/PB/PS/volume_ratio/turnover_ratio",
        "selector_only_selected": 256,
        "replay_canary_audited": 64,
        "primary_question": "Do lagged ready fields create new-vs-149 incremental deployable clusters under mature G2?",
        "pass_criteria": [
            "new-vs-149 >= 2 / 64 audited",
            "top cluster share <= 20%",
            "no PIT/lag violation",
            "turnover/cost not materially worse than baseline",
        ],
    },
    {
        "arm": "AE2_bounded_factor_pack_repair",
        "lane": "bounded_factor_pack_repair",
        "role": "highest_priority_search_lane",
        "input": "1416 formula repair queue fields; priority BILLBOARD_NET_AMT, ACCUM_AMOUNT, DEAL_AMOUNT_RATIO, RZYEZB, amount_yuan, volume_shares, float_shares, fengdan_rate",
        "selector_only_selected": 256,
        "replay_canary_audited": 64,
        "primary_question": "Do repaired high-value fields create true new-vs-149 signal clusters beyond coverage masks?",
        "pass_criteria": [
            "new-vs-149 >= 2 / 64 audited",
            "true-field beats coverage-mask placebo",
            "true-field beats shuffled-field placebo",
            "no PIT, unit, or coverage leakage violation",
        ],
    },
    {
        "arm": "AE3_event_state_actor_motif",
        "lane": "event_state_actor_motif",
        "role": "event_module_lane",
        "input": "256 event-state fields: auction_money, fengdan_rate, lb_2_num, max_lb_num, up_limit_keep_times, open-board/high-board transitions",
        "selector_only_selected": 256,
        "replay_canary_audited": 64,
        "primary_question": "Do event-state features pass event-specific validation rather than ordinary formula replay only?",
        "pass_criteria": [
            "event_count sufficient",
            "same-count random placebo pass",
            "matched-control pass",
            "tradability pass",
            "no event cutoff leakage",
        ],
    },
    {
        "arm": "AE4_regime_context_interaction",
        "lane": "regime_context_interaction",
        "role": "gate_interaction_lane",
        "input": "395 regime/gate/context fields",
        "selector_only_selected": 256,
        "replay_canary_audited": 64,
        "primary_question": "Can regime/context fields improve full-calendar gated or interaction replay without active-day overclaim?",
        "pass_criteria": [
            "full-calendar gated replay improves no-gate",
            "random/block/circular placebo pass",
            "inverted and wrong-lag gates fail",
            "active-day annualized is not used as the promotion metric",
        ],
    },
]


FORBIDDEN_POLICIES = [
    "Do not throw all 4775 fields into one formula generator.",
    "Do not allow future labels, timestamps, text, keys, or same-day unavailable fields into alpha search.",
    "Do not treat event, regime, or tradability fields as ordinary direct rank formulas.",
    "Do not claim alpha proof from searcher adaptation classification.",
    "Do not claim new alpha without new-vs-149 signal-vector recluster.",
    "Do not update official baseline from replay canary alone.",
]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _lane_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in LANES:
        rows.append(
            {
                **lane,
                "pass_criteria": " | ".join(lane["pass_criteria"]),
            }
        )
    return rows


def run(
    *,
    searcher_json: Path,
    searcher_summary: Path,
    recluster_json: Path,
    output_root: Path,
    runtime_root: Path,
    run_plan_path: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    run_plan_path.parent.mkdir(parents=True, exist_ok=True)

    searcher_payload = _load_json(searcher_json)
    recluster_payload = _load_json(recluster_json)
    searcher_summary_frame = pd.read_csv(searcher_summary, encoding="utf-8-sig") if searcher_summary.exists() else pd.DataFrame()

    recluster_counts = recluster_payload.get("counts", {})
    searcher_decision = searcher_payload.get("decision")
    recluster_decision = recluster_payload.get("decision")
    new_vs_149_count = int(recluster_counts.get("new_vs_149_provisional_signal_space", 0) or 0)
    survivor_count = int(recluster_counts.get("survivor_representatives", 0) or 0)

    if searcher_decision != "PASS_SEARCHER_ADAPTATION_CLASSIFICATION_WITH_REPAIR_QUEUE":
        decision = "HOLD_SEARCHER_ADAPTATION_NOT_PASS"
    elif recluster_decision != "PASS_REPLAY128_RECLUSTER_VS_149_READY_FOR_PHASE3AE":
        decision = "HOLD_REPLAY128_RECLUSTER_NOT_PASS"
    else:
        decision = "PASS_PHASE3AE_STRUCTURED_LARGE_SEARCH_PRELAUNCH"

    lane_rows = _lane_rows()
    _write_csv(output_root / "phase3ae_lane_manifest.csv", lane_rows)
    _write_csv(runtime_root / "phase3ae_lane_manifest.csv", lane_rows)
    if not searcher_summary_frame.empty:
        searcher_summary_frame.to_csv(output_root / "source_searcher_adaptation_summary.csv", index=False, encoding="utf-8-sig")

    run_plan = {
        "phase": "Phase3AE",
        "run_type": "structured_large_search_prelaunch",
        "official_stats_allowed": False,
        "starts_search": False,
        "modifies_x0": False,
        "modifies_official_baseline": False,
        "requires_whitelist_staging": True,
        "discovery_baseline": 149,
        "selector_profile": "mature_G2_signal_vector_diversified",
        "matrix": [
            {
                "arm": lane["arm"],
                "lane": lane["lane"],
                "selector_only_selected": lane["selector_only_selected"],
                "replay_canary_audited": lane["replay_canary_audited"],
            }
            for lane in LANES
        ],
        "forbidden_policies": FORBIDDEN_POLICIES,
        "input_manifests_required": [
            str(searcher_json),
            str(searcher_summary),
            str(recluster_json),
        ],
        "output_root": str(output_root),
    }
    _write_json(run_plan_path, run_plan)

    summary = {
        "experiment_id": "phase3ae_structured_large_search_prelaunch_20260604",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "scope": "prelaunch gate only; no search launched",
        "inputs": {
            "searcher_json": str(searcher_json),
            "searcher_summary": str(searcher_summary),
            "recluster_json": str(recluster_json),
        },
        "evidence": {
            "searcher_decision": searcher_decision,
            "field_count": searcher_payload.get("field_count"),
            "direct_formula_search_ready_count": searcher_payload.get("direct_formula_search_ready_count"),
            "formula_search_repair_queue_count": searcher_payload.get("formula_search_repair_queue_count"),
            "event_state_machine_field_count": searcher_payload.get("event_state_machine_field_count"),
            "gate_or_regime_field_count": searcher_payload.get("gate_or_regime_field_count"),
            "blocked_or_key_field_count": searcher_payload.get("blocked_or_key_field_count"),
            "recluster_decision": recluster_decision,
            "replay128_survivor_representatives": survivor_count,
            "replay128_new_vs_149_provisional_signal_space": new_vs_149_count,
            "replay128_known_or_duplicate_signal_cluster": recluster_counts.get("known_or_duplicate_signal_cluster"),
        },
        "lanes": LANES,
        "forbidden_policies": FORBIDDEN_POLICIES,
        "outputs": {
            "lane_manifest": str(output_root / "phase3ae_lane_manifest.csv"),
            "run_plan": str(run_plan_path),
            "summary": str(output_root / "phase3ae_structured_large_search_prelaunch.json"),
        },
    }
    _write_json(output_root / "phase3ae_structured_large_search_prelaunch.json", summary)
    _write_json(runtime_root / "phase3ae_structured_large_search_prelaunch.json", summary)

    lines = [
        "# Phase3AE Structured Large-Search Prelaunch",
        "",
        f"decision: `{decision}`",
        "",
        "## Evidence",
        "",
        f"- searcher adaptation: `{searcher_decision}`",
        f"- direct formula-ready fields: `{searcher_payload.get('direct_formula_search_ready_count')}`",
        f"- formula repair queue fields: `{searcher_payload.get('formula_search_repair_queue_count')}`",
        f"- event-state fields: `{searcher_payload.get('event_state_machine_field_count')}`",
        f"- regime/gate fields: `{searcher_payload.get('gate_or_regime_field_count')}`",
        f"- blocked/key/cutoff fields: `{searcher_payload.get('blocked_or_key_field_count')}`",
        f"- replay128 survivors: `{survivor_count}`",
        f"- replay128 provisional new-vs-149 signal-space survivors: `{new_vs_149_count}`",
        f"- replay128 known/duplicate signal survivors: `{recluster_counts.get('known_or_duplicate_signal_cluster')}`",
        "",
        "## Matrix",
        "",
        "| arm | lane | selector-only | replay canary | role |",
        "|---|---|---:|---:|---|",
    ]
    for lane in LANES:
        lines.append(
            f"| `{lane['arm']}` | `{lane['lane']}` | {lane['selector_only_selected']} | {lane['replay_canary_audited']} | {lane['role']} |"
        )
    lines.extend(
        [
            "",
            "## Forbidden",
            "",
        ]
    )
    for item in FORBIDDEN_POLICIES:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Decision Logic",
            "",
            "Phase3AE is ready for lane-specific selector-only dry runs and replay canaries. It is not permission for full-field, one-pot formula search. Lane B is the highest-value next lane because it converts high-value repair-queue fields into bounded factor packs while explicitly defending against PIT, unit, coverage-mask, and shuffled-field artifacts.",
            "",
            "## Outputs",
            "",
            f"- lane manifest: `{output_root / 'phase3ae_lane_manifest.csv'}`",
            f"- run plan: `{run_plan_path}`",
            f"- machine summary: `{output_root / 'phase3ae_structured_large_search_prelaunch.json'}`",
        ]
    )
    (output_root / "PHASE3AE_STRUCTURED_LARGE_SEARCH_PRELAUNCH_2026-06-04.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--searcher-json", type=Path, default=DEFAULT_SEARCHER_JSON)
    parser.add_argument("--searcher-summary", type=Path, default=DEFAULT_SEARCHER_SUMMARY)
    parser.add_argument("--recluster-json", type=Path, default=DEFAULT_RECLUSTER_JSON)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--run-plan-path", type=Path, default=DEFAULT_RUN_PLAN)
    args = parser.parse_args()
    summary = run(
        searcher_json=args.searcher_json,
        searcher_summary=args.searcher_summary,
        recluster_json=args.recluster_json,
        output_root=args.output_root,
        runtime_root=args.runtime_root,
        run_plan_path=args.run_plan_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
