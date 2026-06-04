from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CANARY_AGGREGATE = Path(
    "reports/phase3ae_bounded_repair_replay_canary_v1_20260604/phase3ae_bounded_repair_replay_canary_aggregate_v1.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/phase3af_split_lane_prelaunch_v1_20260604")
VERSION = "phase3af-split-lane-prelaunch-v1-2026-06-04"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_plan(*, canary_aggregate: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    aggregate = _read_json(canary_aggregate)
    arms = aggregate.get("arms") or {}
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": "PASS_PHASE3AF_SPLIT_LANE_PRELAUNCH_NO_SEARCH",
        "basis": {
            "phase3ae_canary_decision": aggregate.get("decision"),
            "blockers": aggregate.get("blockers") or [],
            "paired_true_deployable": arms.get("paired_true_ae2", {}).get("deployable_clusters"),
            "coverage_mask_deployable": arms.get("coverage_mask_placebo", {}).get("deployable_clusters"),
            "shuffled_value_deployable": arms.get("shuffled_value_placebo", {}).get("deployable_clusters"),
        },
        "lanes": {
            "AF_A_coverage_event_membership": {
                "objective": "Turn the coverage-mask result into a first-class event/coverage-membership lane.",
                "allowed_inputs": [
                    "coverage mask fields",
                    "event membership fields",
                    "coverage-conditioned actor motifs",
                    "matched-control and same-count random controls",
                ],
                "not_allowed": [
                    "claim numeric field value edge",
                    "promote to official book",
                    "skip event count/tradability checks",
                ],
                "first_gate": {
                    "canary_scale": "64 audited",
                    "must_beat": "same-count random and matched-control, not the original numeric expression",
                    "required_outputs": [
                        "event_count",
                        "matched_control_excess",
                        "same_count_random_p95",
                        "tradability_failure_rate",
                        "new_vs_149_signal_cluster",
                    ],
                },
            },
            "AF_B_numeric_value_repair": {
                "objective": "Retain only bounded numeric formulas whose true values beat coverage-mask and shuffled-value controls.",
                "allowed_inputs": [
                    "nonzero value-coverage fields",
                    "residualized numeric transforms",
                    "field-value-minus-coverage controls",
                ],
                "not_allowed": [
                    "use schema visibility as success",
                    "use coverage-only effect as numeric proof",
                    "full large search before true-vs-coverage canary pass",
                ],
                "first_gate": {
                    "canary_scale": "64 audited",
                    "pass_condition": [
                        "true_field_deployable > coverage_mask_deployable",
                        "true_field_deployable > shuffled_value_deployable",
                        "top_cluster_share <= 20%",
                        "no PIT/cutoff violation",
                    ],
                },
            },
        },
        "large_search_policy": {
            "phase3ae_full_large_search_allowed_now": False,
            "reason": "AE2 true fields did not beat coverage-mask placebo.",
            "next_large_search_candidate": "only after AF_A or AF_B passes its own canary",
        },
        "outputs": {
            "summary_json": str(output_root / "phase3af_split_lane_prelaunch_v1.json"),
            "markdown": str(output_root / "PHASE3AF_SPLIT_LANE_PRELAUNCH_V1_2026-06-04.md"),
        },
    }
    _write_json(output_root / "phase3af_split_lane_prelaunch_v1.json", payload)
    _write_markdown(output_root / "PHASE3AF_SPLIT_LANE_PRELAUNCH_V1_2026-06-04.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3AF Split-Lane Prelaunch V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Basis",
        "",
    ]
    for key, value in payload["basis"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Lanes", ""])
    for lane, config in payload["lanes"].items():
        lines.extend([f"### {lane}", "", config["objective"], "", "Allowed inputs:"])
        for item in config["allowed_inputs"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Not allowed:")
        for item in config["not_allowed"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(f"First gate: `{config['first_gate']}`")
        lines.append("")
    lines.extend(["## Policy", ""])
    for key, value in payload["large_search_policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-aggregate", type=Path, default=DEFAULT_CANARY_AGGREGATE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    payload = build_plan(canary_aggregate=args.canary_aggregate, output_root=args.output_root)
    print(json.dumps({"decision": payload["decision"], "basis": payload["basis"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
