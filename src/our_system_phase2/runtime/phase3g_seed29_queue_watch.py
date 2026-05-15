"""Read-only early watcher for Phase3G seed29 official queues.

This script intentionally writes only to its own output directory. It never
modifies the active seed29 run root.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUN_ROOT = Path(
    r"G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\reports"
    r"\phase3g_official_seed29_local_20260514"
)
DEFAULT_OUTPUT_ROOT = Path("reports/phase3g_seed29_queue_watch_20260515")

ARMS = [
    "Phase3G_G0_E0_stable",
    "Phase3G_G1_E3_current_proxy",
    "Phase3G_G2_E3_signal_vector_diversified",
    "Phase3G_G3_E3_strong_signal_vector_proxy",
]
ARM_SHORT_DIRS = {
    "Phase3G_G0_E0_stable": "g0",
    "Phase3G_G1_E3_current_proxy": "g1",
    "Phase3G_G2_E3_signal_vector_diversified": "g2",
    "Phase3G_G3_E3_strong_signal_vector_proxy": "g3",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _last_progress(arm_root: Path) -> dict[str, Any]:
    progress_path = arm_root / "phase3_progress.jsonl"
    if not progress_path.exists():
        return {"progress_ready": False}
    last: dict[str, Any] | None = None
    line_count = 0
    with progress_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                last = json.loads(line)
            except json.JSONDecodeError:
                last = {"stage": "JSON_DECODE_ERROR", "raw": line[:200]}
    return {
        "progress_ready": True,
        "progress_line_count": line_count,
        "last_progress": last or {},
    }


def _candidate_key(row: dict[str, Any]) -> str:
    for key in ("candidate_id", "expr_hash", "expression"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _cluster_id(row: dict[str, Any]) -> str:
    for key in (
        "known_signal_cluster_id",
        "nearest_134_signal_cluster_id",
        "known_cluster_id",
        "nearest_134_cluster_id",
        "provisional_signal_cluster_id",
        "provisional_cluster_id",
    ):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _read_selected_audit_rows(arm_root: Path) -> tuple[bool, list[dict[str, Any]]]:
    audit_path = arm_root / "phase3e_selector_audit.csv"
    if not audit_path.exists():
        return False, []
    rows: list[dict[str, Any]] = []
    with audit_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if _truthy(row.get("selected_for_audit")):
                rows.append(row)
    return True, rows


def _read_selection_input_ids(arm_root: Path) -> list[str]:
    path = arm_root / "phase3_strict_selection_inputs.json"
    if not path.exists():
        return []
    try:
        payload = _read_json(path)
    except (OSError, json.JSONDecodeError):
        return []
    selected = payload.get("selected", []) if isinstance(payload, dict) else []
    ids: list[str] = []
    for row in selected:
        if isinstance(row, dict):
            value = row.get("candidate_id") or row.get("expr_hash") or row.get("expression")
            if value:
                ids.append(str(value))
    return ids


def _source_lane_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("source_lane") or row.get("source_generator") or "unknown") for row in rows)
    return dict(sorted(counts.items()))


def _summarize_arm(run_root: Path, arm: str) -> dict[str, Any]:
    arm_root = run_root / arm
    if not arm_root.exists():
        short = ARM_SHORT_DIRS.get(arm)
        if short and (run_root / short).exists():
            arm_root = run_root / short
    progress = _last_progress(arm_root)
    audit_ready, rows = _read_selected_audit_rows(arm_root)
    fallback_ids = _read_selection_input_ids(arm_root) if not rows else []
    ids = [_candidate_key(row) for row in rows]
    ids = [item for item in ids if item] or fallback_ids

    turnover_values = [
        value
        for value in (_float(row.get("turnover_proxy")) for row in rows)
        if value is not None
    ]
    max_signal_corr_values = [
        value
        for value in (
            _float(row.get("max_corr_to_selected_queue_signal_before_pick"))
            or _float(row.get("max_corr_to_selected_queue_signal"))
            for row in rows
        )
        if value is not None
    ]
    mean_signal_corr_values = [
        value
        for value in (
            _float(row.get("mean_corr_to_selected_queue_signal_before_pick"))
            or _float(row.get("mean_corr_to_selected_queue_signal"))
            for row in rows
        )
        if value is not None
    ]

    cluster_counts = Counter(_cluster_id(row) for row in rows)
    cluster_counts.pop("", None)
    selected_count = len(ids)
    result: dict[str, Any] = {
        "arm": arm,
        "arm_root": str(arm_root),
        **progress,
        "selector_audit_ready": audit_ready,
        "selected_count": selected_count,
        "candidate_ids": ids,
        "cluster_001_selected_count": int(cluster_counts.get("cluster_001", 0)),
        "cluster_003_selected_count": int(cluster_counts.get("cluster_003", 0)),
        "known_signal_cluster_distribution": dict(cluster_counts.most_common(12)),
        "source_lane_distribution": _source_lane_distribution(rows),
        "median_turnover_proxy": _median(turnover_values),
        "mean_selected_queue_signal_corr": _mean(max_signal_corr_values),
        "median_selected_queue_signal_corr": _median(max_signal_corr_values),
        "mean_selected_queue_signal_corr_field": _mean(mean_signal_corr_values),
        "median_selected_queue_signal_corr_field": _median(mean_signal_corr_values),
    }
    if not audit_ready:
        result["status"] = "WAIT_SELECTOR_AUDIT"
    elif selected_count == 0:
        result["status"] = "AUDIT_READY_EMPTY_SELECTION"
    else:
        result["status"] = "QUEUE_READY"
    return result


def _overlap(left: list[str], right: list[str]) -> dict[str, Any]:
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    inter = left_set & right_set
    denom = min(len(left_set), len(right_set)) or 0
    ratio = (len(inter) / denom) if denom else None
    return {
        "left_count": len(left_set),
        "right_count": len(right_set),
        "intersection_count": len(inter),
        "overlap_ratio_min_denom": ratio,
    }


def _summarize(run_root: Path) -> dict[str, Any]:
    arms = [_summarize_arm(run_root, arm) for arm in ARMS]
    by_arm = {row["arm"]: row for row in arms}
    overlaps: dict[str, Any] = {}
    pairs = [
        ("G1_vs_G2", "Phase3G_G1_E3_current_proxy", "Phase3G_G2_E3_signal_vector_diversified"),
        ("G1_vs_G3", "Phase3G_G1_E3_current_proxy", "Phase3G_G3_E3_strong_signal_vector_proxy"),
        ("G2_vs_G3", "Phase3G_G2_E3_signal_vector_diversified", "Phase3G_G3_E3_strong_signal_vector_proxy"),
    ]
    for label, left, right in pairs:
        overlaps[label] = _overlap(by_arm[left]["candidate_ids"], by_arm[right]["candidate_ids"])

    g2_g3_ratio = overlaps["G2_vs_G3"].get("overlap_ratio_min_denom")
    ready_count = sum(1 for row in arms if row["status"] == "QUEUE_READY")
    decision = "WAIT_SELECTOR_AUDIT"
    if ready_count == len(ARMS):
        decision = "QUEUE_READY"
        if g2_g3_ratio is not None and g2_g3_ratio > 0.90:
            decision = "REVIEW_DUPLICATE_G2_G3_ARMS"
    return {
        "created_at": _now(),
        "experiment_id": "20260515_phase3g_seed29_queue_watch",
        "objective": "early read-only audit of Phase3G seed29 selector queues before replay reports finish",
        "status": decision,
        "run_root": str(run_root),
        "arms": arms,
        "overlaps": overlaps,
        "decision": decision,
        "safety": {
            "read_only_run_root": True,
            "writes_only_to_output_root": True,
            "does_not_launch_seeds30_32": True,
        },
    }


def _write_csv(path: Path, arms: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "arm",
        "status",
        "selector_audit_ready",
        "selected_count",
        "cluster_001_selected_count",
        "cluster_003_selected_count",
        "median_turnover_proxy",
        "mean_selected_queue_signal_corr",
        "median_selected_queue_signal_corr",
        "last_stage",
        "last_time",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in arms:
            last = row.get("last_progress") or {}
            writer.writerow(
                {
                    "arm": row.get("arm"),
                    "status": row.get("status"),
                    "selector_audit_ready": row.get("selector_audit_ready"),
                    "selected_count": row.get("selected_count"),
                    "cluster_001_selected_count": row.get("cluster_001_selected_count"),
                    "cluster_003_selected_count": row.get("cluster_003_selected_count"),
                    "median_turnover_proxy": row.get("median_turnover_proxy"),
                    "mean_selected_queue_signal_corr": row.get("mean_selected_queue_signal_corr"),
                    "median_selected_queue_signal_corr": row.get("median_selected_queue_signal_corr"),
                    "last_stage": last.get("stage"),
                    "last_time": last.get("time"),
                }
            )


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3G Seed29 Queue Watch",
        "",
        f"- created_at: {report['created_at']}",
        f"- experiment_id: {report['experiment_id']}",
        f"- status: {report['status']}",
        f"- run_root: `{report['run_root']}`",
        "- safety: read-only seed29 run root; no seeds30-32 launch",
        "",
        "## Arm Summary",
        "",
        "| arm | status | selected | cluster_001 | cluster_003 | median_turnover | mean_signal_corr | last_stage |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["arms"]:
        last = row.get("last_progress") or {}
        lines.append(
            "| {arm} | {status} | {selected} | {c1} | {c3} | {turnover} | {corr} | {stage} |".format(
                arm=row.get("arm"),
                status=row.get("status"),
                selected=row.get("selected_count"),
                c1=row.get("cluster_001_selected_count"),
                c3=row.get("cluster_003_selected_count"),
                turnover=row.get("median_turnover_proxy"),
                corr=row.get("mean_selected_queue_signal_corr"),
                stage=last.get("stage"),
            )
        )
    lines.extend(["", "## Queue Overlap", ""])
    for label, item in report["overlaps"].items():
        lines.append(f"- {label}: {item}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_once(run_root: Path, output_root: Path) -> dict[str, Any]:
    report = _summarize(run_root)
    _write_json(output_root / "phase3g_seed29_queue_watch.json", report)
    _write_csv(output_root / "phase3g_seed29_queue_watch_per_arm.csv", report["arms"])
    _write_md(output_root / "PHASE3G_SEED29_QUEUE_WATCH_2026-05-15.md", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--watch-interval-seconds", type=int, default=300)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        report = run_once(args.run_root, args.output_root)
        print(json.dumps({"status": report["status"], "output_root": str(args.output_root)}, ensure_ascii=False))
        if args.once:
            return 0
        time.sleep(max(1, args.watch_interval_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
