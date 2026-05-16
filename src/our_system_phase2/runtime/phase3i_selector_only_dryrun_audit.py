"""Audit Phase3I selector-only dry-run queues."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUN_ROOT = Path("runtime/phase3i_selector_only_s41_20260516")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3i_selector_only_s41_20260516")

ARMS = {
    "I0": ("i0", "Phase3I_I0_G2_primary"),
    "I1": ("i1", "Phase3I_I1_G2_cost_turnover_constrained"),
    "I2": ("i2", "Phase3I_I2_G2_capacity_liquidity"),
    "I3": ("i3", "Phase3I_I3_G2_book_proxy_hardened"),
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
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 6)


def _p90(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    index = min(len(clean) - 1, math.ceil(0.9 * len(clean)) - 1)
    return round(clean[index], 6)


def _queue_key(row: dict[str, Any]) -> str:
    expression = str(row.get("expression") or "")
    if expression:
        return hashlib.sha256(expression.encode("utf-8")).hexdigest()
    return str(row.get("candidate_id") or "")


def _selected_rows(audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in audit_rows if _truthy(row.get("selected_for_audit"))]


def _selected_inputs(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path) if path.exists() else {}
    return list(payload.get("selected") or [])


def _arm_root(run_root: Path, short: str) -> Path:
    return run_root / short


def _summarize_arm(run_root: Path, label: str, short: str, arm_name: str) -> dict[str, Any]:
    root = _arm_root(run_root, short)
    report_path = root / "phase3_selection_only_report.json"
    audit_path = root / "phase3e_selector_audit.csv"
    inputs_path = root / "phase3_strict_selection_inputs.json"
    report = _read_json(report_path) if report_path.exists() else {}
    audit_rows = _read_csv(audit_path)
    selected = _selected_rows(audit_rows)
    selected_inputs = _selected_inputs(inputs_path)
    selected_for_counts = selected_inputs or selected
    keys = {_queue_key(row) for row in selected_for_counts if _queue_key(row)}

    turnover_values = [value for value in (_safe_float(row.get("turnover_proxy")) for row in selected) if value is not None]
    structure_values = [value for value in (_safe_float(row.get("turnover_structure_risk")) for row in selected) if value is not None]
    signal_corr_values = [value for value in (_safe_float(row.get("max_corr_to_selected_queue_signal")) for row in selected) if value is not None]
    liquidity_values = [value for value in (_safe_float(row.get("liquidity_proxy")) for row in selected) if value is not None]
    capacity_values = [value for value in (_safe_float(row.get("capacity_proxy")) for row in selected) if value is not None]
    source_lanes = Counter(str(row.get("source_lane") or row.get("phase3_budget_bucket") or "unknown") for row in selected_for_counts)
    design = report.get("ablation_design") or {}

    return {
        "label": label,
        "short": short,
        "arm": arm_name,
        "report_exists": report_path.exists(),
        "audit_exists": audit_path.exists(),
        "selection_inputs_exists": inputs_path.exists(),
        "selector_profile": design.get("phase3e_selector_profile"),
        "generation_profile": design.get("phase3e_generation_profile"),
        "discovery_baseline_count": design.get("phase3_discovery_baseline_count"),
        "selector_vector_baseline_count": design.get("phase3_selector_vector_baseline_count"),
        "selected_count": len(selected_for_counts),
        "selector_audit_selected_count": len(selected),
        "selected_keys": keys,
        "median_turnover_proxy": _median(turnover_values),
        "p90_turnover_proxy": _p90(turnover_values),
        "median_turnover_structure_risk": _median(structure_values),
        "mean_selected_queue_signal_corr": round(sum(signal_corr_values) / len(signal_corr_values), 6) if signal_corr_values else None,
        "median_selected_queue_signal_corr": _median(signal_corr_values),
        "median_liquidity_proxy": _median(liquidity_values),
        "median_capacity_proxy": _median(capacity_values),
        "agnostic_selected_count": source_lanes.get("agnostic_freeform_ast", 0),
        "repair_expansion_selected_count": source_lanes.get("formula_gen_v2_repair_expansion", 0),
        "source_lane_counts": dict(sorted(source_lanes.items())),
        "leakage_flag_count": sum(1 for row in audit_rows if _truthy(row.get("uses_forbidden_replay_labels"))),
        "cap_hit_count": sum(1 for row in audit_rows if str(row.get("cap_reject_reason") or "")),
    }


def _overlap(left: set[str], right: set[str]) -> dict[str, Any]:
    inter = left & right
    denom = min(len(left), len(right)) or 1
    return {
        "left_count": len(left),
        "right_count": len(right),
        "overlap_count": len(inter),
        "overlap_ratio_min_denom": round(len(inter) / denom, 6),
    }


def audit_dryrun(run_root: Path, feature_preflight: Path | None = None) -> dict[str, Any]:
    arms = [_summarize_arm(run_root, label, short, name) for label, (short, name) in ARMS.items()]
    by_label = {row["label"]: row for row in arms}
    overlaps = {
        "I0_vs_I1": _overlap(by_label["I0"]["selected_keys"], by_label["I1"]["selected_keys"]),
        "I0_vs_I3": _overlap(by_label["I0"]["selected_keys"], by_label["I3"]["selected_keys"]),
        "I0_vs_I2": _overlap(by_label["I0"]["selected_keys"], by_label["I2"]["selected_keys"]),
    }
    feature_report = _read_json(feature_preflight) if feature_preflight and feature_preflight.exists() else {}
    i2_status = ((feature_report.get("requirements") or {}).get("I2") or {}).get("status") or "unknown"

    fail_reasons: list[str] = []
    if any(not row["report_exists"] or not row["audit_exists"] for row in arms):
        fail_reasons.append("missing_report_or_selector_audit")
    if any(row["selected_count"] != 64 for row in arms):
        fail_reasons.append("selected_count_not_64")
    if overlaps["I0_vs_I1"]["overlap_ratio_min_denom"] > 0.95:
        fail_reasons.append("I1_queue_overlap_gt_95pct_with_I0")
    if by_label["I1"]["p90_turnover_proxy"] is not None and by_label["I0"]["p90_turnover_proxy"] is not None:
        if by_label["I1"]["p90_turnover_proxy"] >= by_label["I0"]["p90_turnover_proxy"]:
            fail_reasons.append("I1_p90_turnover_not_below_I0")
    if by_label["I3"]["mean_selected_queue_signal_corr"] is not None and by_label["I0"]["mean_selected_queue_signal_corr"] is not None:
        if by_label["I3"]["mean_selected_queue_signal_corr"] >= by_label["I0"]["mean_selected_queue_signal_corr"]:
            fail_reasons.append("I3_selected_queue_signal_corr_not_below_I0")
    if any(row["leakage_flag_count"] for row in arms):
        fail_reasons.append("selector_audit_reports_forbidden_replay_label_usage")
    if i2_status == "diagnostic_only":
        # Not a dry-run blocker; it only limits Phase3I promotion interpretation.
        pass

    decision = "PASS_PHASE3I_SELECTOR_ONLY_DRYRUN" if not fail_reasons else "HOLD_PHASE3I_SELECTOR_ONLY_DRYRUN"
    return {
        "created_at": _now(),
        "decision": decision,
        "run_root": str(run_root),
        "feature_preflight_path": str(feature_preflight) if feature_preflight else "",
        "i2_status": i2_status,
        "arms": [{key: value for key, value in row.items() if key != "selected_keys"} for row in arms],
        "queue_overlaps": overlaps,
        "fail_reasons": fail_reasons,
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3I Selector-Only Dry Run Audit",
        "",
        f"- decision: `{report['decision']}`",
        f"- i2_status: `{report['i2_status']}`",
        "",
        "## Arm Metrics",
        "",
        "| arm | selected | selector | median_turnover | p90_turnover | mean_signal_corr | median_liquidity | median_capacity |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["arms"]:
        lines.append(
            "| {label} | {selected} | {selector} | {median} | {p90} | {corr} | {liq} | {cap} |".format(
                label=row["label"],
                selected=row["selected_count"],
                selector=row.get("selector_profile"),
                median=row.get("median_turnover_proxy"),
                p90=row.get("p90_turnover_proxy"),
                corr=row.get("mean_selected_queue_signal_corr"),
                liq=row.get("median_liquidity_proxy"),
                cap=row.get("median_capacity_proxy"),
            )
        )
    lines.extend(["", "## Queue Overlap", "", "| pair | overlap |", "| --- | ---: |"])
    for key, value in report["queue_overlaps"].items():
        lines.append(f"| {key} | {value['overlap_ratio_min_denom']} |")
    lines.extend(["", "## Fail Reasons", ""])
    if report["fail_reasons"]:
        lines.extend(f"- `{reason}`" for reason in report["fail_reasons"])
    else:
        lines.append("- none")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--feature-preflight", type=Path, default=None)
    args = parser.parse_args()
    report = audit_dryrun(args.run_root, feature_preflight=args.feature_preflight)
    _write_json(args.output_root / "phase3i_selector_only_dryrun_audit.json", report)
    _write_csv(args.output_root / "phase3i_selector_only_dryrun_arms.csv", report["arms"])
    _write_markdown(args.output_root / "PHASE3I_SELECTOR_ONLY_DRYRUN_AUDIT_2026-05-16.md", report)
    print(json.dumps({key: report[key] for key in ["created_at", "decision", "i2_status", "fail_reasons"]}, ensure_ascii=False, indent=2))
    return 0 if report["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
