"""Audit Phase3H selector-only dry-run queues.

This is a no-replay gate. It checks whether H0/H1/H2/H3 routing actually
changes selected queues and whether Phase3H metadata is attached correctly.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUN_ROOT = Path("runtime/phase3h_selector_only_dryrun_s33_20260515")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3h_selector_only_dryrun_s33_20260515")

ARMS = {
    "H0": ("h0", "Phase3H_H0_G0_stable"),
    "H1": ("h1", "Phase3H_H1_G2_signal_vector_control"),
    "H2": ("h2", "Phase3H_H2_G2_turnover_calibrated"),
    "H3": ("h3", "Phase3H_H3_G2_registry_canonicalized"),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _queue_key(row: dict[str, Any]) -> str:
    return str(row.get("expr_hash") or row.get("expression") or row.get("candidate_id") or "")


def _overlap(left: set[str], right: set[str]) -> dict[str, Any]:
    inter = left & right
    denom = min(len(left), len(right)) or 1
    return {
        "left_count": len(left),
        "right_count": len(right),
        "overlap_count": len(inter),
        "overlap_ratio_min_denom": round(len(inter) / denom, 6),
    }


def _selected_rows(audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in audit_rows if _truthy(row.get("selected_for_audit"))]


def _arm_root(run_root: Path, short: str, arm_name: str) -> Path:
    for candidate in [run_root / short, run_root / arm_name, run_root]:
        if (candidate / "phase3_selection_only_report.json").exists() or (candidate / "phase3e_selector_audit.csv").exists():
            return candidate
    return run_root / short


def _summarize_arm(run_root: Path, short: str, arm_name: str) -> dict[str, Any]:
    root = _arm_root(run_root, short, arm_name)
    report_path = root / "phase3_selection_only_report.json"
    audit_path = root / "phase3e_selector_audit.csv"
    inputs_path = root / "phase3_strict_selection_inputs.json"
    report = _read_json(report_path) if report_path.exists() else {}
    inputs = _read_json(inputs_path) if inputs_path.exists() else {}
    audit_rows = _read_csv(audit_path)
    selected = _selected_rows(audit_rows)
    selected_inputs = list(inputs.get("selected") or [])
    selected_for_counts = selected_inputs or selected

    selected_keys = {_queue_key(row) for row in selected_for_counts if _queue_key(row)}
    turnover_proxy = [_safe_float(row.get("turnover_proxy")) for row in selected]
    turnover_proxy_values = [value for value in turnover_proxy if value is not None]
    turnover_structure = [_safe_float(row.get("turnover_structure_risk")) for row in selected]
    turnover_structure_values = [value for value in turnover_structure if value is not None]
    selected_signal_corr = [_safe_float(row.get("max_corr_to_selected_queue_signal")) for row in selected]
    selected_signal_corr_values = [value for value in selected_signal_corr if value is not None]
    source_lanes = Counter(str(row.get("source_lane") or row.get("phase3_budget_bucket") or "unknown") for row in selected_for_counts)
    known_signal_clusters = Counter(str(row.get("known_signal_cluster_id") or "") for row in selected if row.get("known_signal_cluster_id"))
    cap_hits = sum(1 for row in audit_rows if str(row.get("cap_reject_reason") or ""))
    selected_cap_relaxed = sum(1 for row in selected if _truthy(row.get("cap_relaxed_for_backfill")))
    design = report.get("ablation_design") or {}

    return {
        "short": short,
        "arm": arm_name,
        "root": str(root),
        "report_exists": report_path.exists(),
        "audit_exists": audit_path.exists(),
        "selection_inputs_exists": inputs_path.exists(),
        "status": report.get("status"),
        "selector_profile": design.get("phase3e_selector_profile"),
        "generation_profile": design.get("phase3e_generation_profile"),
        "metadata_policy": design.get("phase3_metadata_policy"),
        "discovery_baseline_count": design.get("phase3_discovery_baseline_count"),
        "selector_vector_baseline_count": design.get("phase3_selector_vector_baseline_count"),
        "selector_vector_baseline_name": design.get("phase3_selector_vector_baseline_name"),
        "strict_vector_cluster_cap": design.get("strict_vector_cluster_cap"),
        "target_median_turnover": design.get("target_median_turnover"),
        "audit_rows": len(audit_rows),
        "selected_count": len(selected_for_counts),
        "selector_audit_selected_count": len(selected),
        "selected_keys": selected_keys,
        "median_turnover_proxy": _median(turnover_proxy_values),
        "median_turnover_structure_risk": _median(turnover_structure_values),
        "mean_selected_queue_signal_corr": round(sum(selected_signal_corr_values) / len(selected_signal_corr_values), 6) if selected_signal_corr_values else None,
        "median_selected_queue_signal_corr": _median(selected_signal_corr_values),
        "cap_hit_count": cap_hits,
        "selected_cap_relaxed_count": selected_cap_relaxed,
        "agnostic_selected_count": source_lanes.get("agnostic_freeform_ast", 0),
        "repair_expansion_selected_count": source_lanes.get("formula_gen_v2_repair_expansion", 0),
        "source_lane_counts": dict(sorted(source_lanes.items())),
        "known_signal_cluster_counts": dict(sorted(known_signal_clusters.items())),
        "leakage_flag_count": sum(1 for row in audit_rows if _truthy(row.get("uses_forbidden_replay_labels"))),
    }


def audit_dryrun(run_root: Path) -> dict[str, Any]:
    arms = [_summarize_arm(run_root, short, name) for short, (directory, name) in ARMS.items()]
    by_short = {row["short"]: row for row in arms}

    overlaps = {}
    for label, left, right in [
        ("H1_vs_H2", "H1", "H2"),
        ("H1_vs_H3", "H1", "H3"),
        ("H0_vs_H1", "H0", "H1"),
    ]:
        overlaps[label] = _overlap(by_short[left]["selected_keys"], by_short[right]["selected_keys"])

    fail_reasons: list[str] = []
    if any(not row["report_exists"] or not row["audit_exists"] for row in arms):
        fail_reasons.append("missing_report_or_selector_audit")
    if any(row["selected_count"] != 64 for row in arms):
        fail_reasons.append("selected_count_not_64")
    if overlaps["H1_vs_H2"]["overlap_ratio_min_denom"] > 0.95:
        fail_reasons.append("H2_queue_overlap_gt_95pct_with_H1")
    h1_turnover = by_short["H1"]["median_turnover_proxy"]
    h2_turnover = by_short["H2"]["median_turnover_proxy"]
    h1_structure = by_short["H1"]["median_turnover_structure_risk"]
    h2_structure = by_short["H2"]["median_turnover_structure_risk"]
    if h1_turnover is not None and h2_turnover is not None and h1_structure is not None and h2_structure is not None:
        if h2_turnover >= h1_turnover and h2_structure >= h1_structure:
            fail_reasons.append("H2_turnover_calibration_no_observable_effect")
    if by_short["H3"].get("metadata_policy") != "DUAL_BASELINE_ACCEPTED":
        fail_reasons.append("H3_missing_dual_baseline_policy")
    if int(by_short["H3"].get("selector_vector_baseline_count") or 0) != 122:
        fail_reasons.append("H3_selector_vector_baseline_not_122")
    if int(by_short["H3"].get("discovery_baseline_count") or 0) != 134:
        fail_reasons.append("H3_discovery_baseline_not_134")
    if any(row["leakage_flag_count"] for row in arms):
        fail_reasons.append("selector_audit_reports_forbidden_replay_label_usage")
    for short in ["H1", "H2", "H3"]:
        if by_short[short]["agnostic_selected_count"] <= 0:
            fail_reasons.append(f"{short}_agnostic_freeform_starved")
        if by_short[short]["repair_expansion_selected_count"] <= 0:
            fail_reasons.append(f"{short}_repair_expansion_starved")

    decision = "PASS_SELECTOR_ONLY_DRYRUN" if not fail_reasons else "HOLD_SELECTOR_ONLY_DRYRUN"
    return {
        "created_at": _now(),
        "experiment_id": "20260515_phase3h_selector_only_dryrun_s33",
        "decision": decision,
        "run_root": str(run_root),
        "objective": "Gate Phase3H smoke by checking H0-H3 routing, turnover calibration, dual-baseline metadata, and queue diversity before replay.",
        "arms": [
            {key: value for key, value in row.items() if key != "selected_keys"}
            for row in arms
        ],
        "queue_overlaps": overlaps,
        "fail_reasons": fail_reasons,
        "commands": {
            "expected_generation": "python -m our_system_phase2.runtime.stock_pit_phase3_repair --selection-only --ablation-arm <H0-H3> --strict-audit-budget 64 --seed 33",
            "audit": "python -m our_system_phase2.runtime.phase3h_selector_only_dryrun_audit --run-root <run-root>",
        },
        "next_action": "Run Phase3H smoke only if decision is PASS_SELECTOR_ONLY_DRYRUN.",
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3H Selector-Only Dry Run Audit",
        "",
        f"- created_at: `{report['created_at']}`",
        f"- decision: `{report['decision']}`",
        f"- run_root: `{report['run_root']}`",
        "",
        "## Arm Metrics",
        "",
        "| arm | selected | selector | median_turnover | median_turnover_structure | mean_signal_corr | agnostic | repair_expansion | metadata |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["arms"]:
        lines.append(
            "| {arm} | {selected} | {selector} | {turnover} | {structure} | {signal_corr} | {agnostic} | {repair} | {metadata} |".format(
                arm=row["short"],
                selected=row["selected_count"],
                selector=row.get("selector_profile"),
                turnover=row.get("median_turnover_proxy"),
                structure=row.get("median_turnover_structure_risk"),
                signal_corr=row.get("mean_selected_queue_signal_corr"),
                agnostic=row.get("agnostic_selected_count"),
                repair=row.get("repair_expansion_selected_count"),
                metadata=row.get("metadata_policy"),
            )
        )
    lines.extend(["", "## Queue Overlap", "", "| pair | overlap | left | right |", "| --- | ---: | ---: | ---: |"])
    for label, row in report["queue_overlaps"].items():
        lines.append(f"| {label} | {row['overlap_ratio_min_denom']} | {row['left_count']} | {row['right_count']} |")
    lines.extend(["", "## Fail Reasons", ""])
    if report["fail_reasons"]:
        lines.extend(f"- `{reason}`" for reason in report["fail_reasons"])
    else:
        lines.append("- none")
    lines.extend(["", "## Decision", "", report["next_action"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = audit_dryrun(args.run_root)
    _write_json(args.output_root / "phase3h_selector_only_dryrun_audit.json", report)
    _write_csv(args.output_root / "phase3h_selector_only_dryrun_arms.csv", report["arms"])
    _write_markdown(args.output_root / "PHASE3H_SELECTOR_ONLY_DRYRUN_AUDIT_2026-05-15.md", report)
    print(json.dumps({key: report[key] for key in ["created_at", "decision", "fail_reasons"]}, ensure_ascii=False, indent=2))
    return 0 if report["decision"] == "PASS_SELECTOR_ONLY_DRYRUN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
