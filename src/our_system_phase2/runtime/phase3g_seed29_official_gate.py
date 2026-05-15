"""Gate Phase3G seed29 official before launching seeds30-32.

The gate is deliberately conservative:
- incomplete reports => WAIT_REPORTS
- missing aggregate/new-vs-134 evidence => WAIT_AGGREGATE
- duplicate G2/G3 queues => REVIEW, not automatic launch
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUN_ROOT = Path(
    r"G:\Project_V7_Rotation\.worktrees\our_system_phase1_repo\reports"
    r"\phase3g_official_seed29_local_20260514"
)
DEFAULT_OUTPUT_ROOT = Path("reports/phase3g_seed29_official_gate_20260515")

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
TARGET_ARMS = [
    "Phase3G_G2_E3_signal_vector_diversified",
    "Phase3G_G3_E3_strong_signal_vector_proxy",
]


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


def _report_metrics(arm_root: Path) -> dict[str, Any]:
    path = arm_root / "phase3_repair_report.json"
    if not path.exists():
        return {"report_exists": False}
    payload = _read_json(path)
    main = payload.get("main_kpi", {})
    primary = main.get("primary", {})
    secondary = main.get("secondary", {})
    return {
        "report_exists": True,
        "audited": primary.get("audited_count"),
        "deployable_clusters": primary.get("cost_turnover_deployable_unique_clusters"),
        "raw_non_gap_pass": secondary.get("raw_non_gap_replay_pass"),
        "top_cluster_share": secondary.get("top_cluster_raw_pass_share"),
        "top_cluster_id": secondary.get("top_cluster_id"),
        "selector_profile": payload.get("phase3e_selector_profile")
        or (payload.get("ablation_design") or {}).get("phase3e_selector_profile"),
        "book_marginal_mode": (payload.get("phase3e_selector_preflight") or {}).get("book_marginal_mode"),
    }


def _strict_rows(arm_root: Path) -> list[dict[str, Any]]:
    path = arm_root / "phase3_strict_rows.json"
    if not path.exists():
        return []
    payload = _read_json(path)
    if isinstance(payload, dict):
        rows = payload.get("strict_rows", [])
    else:
        rows = payload
    return [row for row in rows if isinstance(row, dict)]


def _raw_pass_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not _truthy(row.get("portfolio_replay_pass")):
            continue
        if row.get("is_gap_family") in {True, "true", "True", "1"}:
            continue
        out.append(row)
    return out


def _strict_row_metrics(arm_root: Path) -> dict[str, Any]:
    rows = _strict_rows(arm_root)
    passed = _raw_pass_rows(rows)
    cluster_counts = Counter(str(row.get("signal_cluster_id") or "") for row in passed)
    cluster_counts.pop("", None)
    total = sum(cluster_counts.values())
    turnovers = [
        val
        for val in (_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in rows)
        if val is not None
    ]
    return {
        "strict_rows_exists": bool(rows),
        "strict_row_count": len(rows),
        "raw_pass_row_count": len(passed),
        "cluster_001_share": (cluster_counts.get("cluster_001", 0) / total) if total else None,
        "cluster_003_share": (cluster_counts.get("cluster_003", 0) / total) if total else None,
        "strict_rows_top_cluster_id": cluster_counts.most_common(1)[0][0] if cluster_counts else None,
        "strict_rows_top_cluster_share": (cluster_counts.most_common(1)[0][1] / total) if total else None,
        "median_turnover": _median(turnovers),
        "cluster_counts": dict(cluster_counts.most_common(12)),
    }


def _find_aggregate_file(aggregate_root: Path | None, pattern: str) -> Path | None:
    if not aggregate_root:
        return None
    if aggregate_root.is_file() and aggregate_root.name.endswith(pattern):
        return aggregate_root
    if not aggregate_root.exists():
        return None
    matches = sorted(aggregate_root.glob(f"*{pattern}"))
    return matches[0] if matches else None


def _aggregate_per_arm_new_vs_baseline(clustered_rows_path: Path | None) -> dict[str, int]:
    if not clustered_rows_path or not clustered_rows_path.exists():
        return {}
    payload = _read_json(clustered_rows_path)
    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    baseline_clusters = {
        str(row.get("global_signal_cluster_id"))
        for row in rows
        if row.get("aggregate_source_kind") == "phase3_cumulative_baseline"
        and row.get("global_signal_cluster_id")
    }
    arm_clusters: dict[str, set[str]] = {}
    for row in rows:
        if row.get("aggregate_source_kind") != "phase3A_seed":
            continue
        if not _truthy(row.get("portfolio_replay_pass")):
            continue
        arm = str(row.get("ablation_arm") or "")
        cluster = row.get("global_signal_cluster_id")
        if not arm or not cluster:
            continue
        arm_clusters.setdefault(arm, set()).add(str(cluster))
    return {
        arm: len(clusters - baseline_clusters)
        for arm, clusters in arm_clusters.items()
    }


def _aggregate_per_arm_metrics(aggregate_root: Path | None) -> dict[str, dict[str, Any]]:
    path = _find_aggregate_file(aggregate_root, "per_arm_metrics.csv")
    if not path or not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            arm = str(row.get("ablation_arm") or row.get("arm") or "")
            if not arm:
                continue
            out[arm] = {
                "aggregate_per_arm_metrics_path": str(path),
                "audited": _float(row.get("audited")),
                "deployable_clusters": _float(row.get("deployable_clusters")),
                "raw_non_gap_pass": _float(row.get("raw_non_gap_pass")),
                "top_cluster_id": row.get("top_cluster_id"),
                "top_cluster_share": _float(row.get("top_cluster_share")),
                "median_turnover": _float(row.get("median_turnover")),
            }
    return out


def _read_queue_overlap(queue_watch_json: Path | None) -> dict[str, Any]:
    if not queue_watch_json or not queue_watch_json.exists():
        return {}
    try:
        payload = _read_json(queue_watch_json)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload.get("overlaps", {}) if isinstance(payload, dict) else {}


def _arm_status(run_root: Path, arm: str) -> dict[str, Any]:
    arm_root = run_root / arm
    if not arm_root.exists():
        short = ARM_SHORT_DIRS.get(arm)
        if short and (run_root / short).exists():
            arm_root = run_root / short
    metrics = _report_metrics(arm_root)
    row_metrics = _strict_row_metrics(arm_root)
    out = {"arm": arm, "arm_root": str(arm_root)}
    out.update(metrics)
    out.update(row_metrics)
    if out.get("median_turnover") is None:
        out["median_turnover"] = None
    return out


def _passes_gate(row: dict[str, Any], max_control_deployable: int | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    deployable = row.get("deployable_clusters")
    if row.get("top_cluster_share") is None or row["top_cluster_share"] > 0.45:
        reasons.append("top_cluster_share_gt_45pct")
    if row.get("cluster_001_share") is None or row["cluster_001_share"] > 0.25:
        reasons.append("cluster_001_share_gt_25pct")
    if row.get("cluster_003_share") is None or row["cluster_003_share"] > 0.25:
        reasons.append("cluster_003_share_gt_25pct")
    if row.get("median_turnover") is None or row["median_turnover"] > 0.20:
        reasons.append("median_turnover_gt_020")
    if deployable is None or max_control_deployable is None or deployable < max_control_deployable - 2:
        reasons.append("deployable_lt_max_G0_G1_minus_2")
    if row.get("new_vs_134") is None or row["new_vs_134"] < 1:
        reasons.append("new_vs_134_lt_1_or_missing")
    return (not reasons), reasons


def _fails_gate(row: dict[str, Any], g0_deployable: int | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    deployable = row.get("deployable_clusters")
    if row.get("top_cluster_share") is not None and row["top_cluster_share"] > 0.50:
        reasons.append("top_cluster_share_gt_50pct")
    if row.get("median_turnover") is not None and row["median_turnover"] > 0.25:
        reasons.append("median_turnover_gt_025")
    if deployable is not None and g0_deployable is not None and deployable < g0_deployable - 3:
        reasons.append("deployable_below_G0_by_more_than_3")
    return bool(reasons), reasons


def evaluate_gate(
    run_root: Path,
    aggregate_root: Path | None,
    queue_watch_json: Path | None,
) -> dict[str, Any]:
    arms = [_arm_status(run_root, arm) for arm in ARMS]
    missing_reports = [row["arm"] for row in arms if not row.get("report_exists")]
    clustered_rows_path = _find_aggregate_file(aggregate_root, "global_clustered_rows.json")
    per_arm_new = _aggregate_per_arm_new_vs_baseline(clustered_rows_path)
    aggregate_arm_metrics = _aggregate_per_arm_metrics(aggregate_root)
    for row in arms:
        aggregate_metrics = aggregate_arm_metrics.get(row["arm"], {})
        for key in (
            "audited",
            "deployable_clusters",
            "raw_non_gap_pass",
            "top_cluster_id",
            "top_cluster_share",
            "median_turnover",
            "aggregate_per_arm_metrics_path",
        ):
            if aggregate_metrics.get(key) is not None:
                value = aggregate_metrics[key]
                if key in {"audited", "deployable_clusters", "raw_non_gap_pass"} and isinstance(value, float):
                    value = int(value)
                row[key] = value
        row["new_vs_134"] = per_arm_new.get(row["arm"])

    by_arm = {row["arm"]: row for row in arms}
    g0 = by_arm["Phase3G_G0_E0_stable"].get("deployable_clusters")
    g1 = by_arm["Phase3G_G1_E3_current_proxy"].get("deployable_clusters")
    controls = [val for val in (g0, g1) if isinstance(val, int)]
    max_control = max(controls) if controls else None

    queue_overlaps = _read_queue_overlap(queue_watch_json)
    g2g3_overlap = (
        queue_overlaps.get("G2_vs_G3", {}).get("overlap_ratio_min_denom")
        if queue_overlaps
        else None
    )

    decisions: dict[str, Any] = {}
    for arm in TARGET_ARMS:
        row = by_arm[arm]
        ok, pass_reasons = _passes_gate(row, max_control)
        fail, fail_reasons = _fails_gate(row, g0 if isinstance(g0, int) else None)
        decisions[arm] = {
            "passes_seed29_gate": ok,
            "pass_blockers": pass_reasons,
            "triggers_fail_condition": fail,
            "fail_reasons": fail_reasons,
        }

    if missing_reports:
        status = "WAIT_REPORTS"
        reason = f"missing reports: {missing_reports}"
    elif not clustered_rows_path:
        status = "WAIT_AGGREGATE"
        reason = "global clustered rows missing; cannot evaluate per-arm new_vs_134"
    elif any(decisions[arm]["passes_seed29_gate"] for arm in TARGET_ARMS):
        if (
            all(decisions[arm]["passes_seed29_gate"] for arm in TARGET_ARMS)
            and g2g3_overlap is not None
            and g2g3_overlap > 0.90
        ):
            status = "REVIEW"
            reason = "G2 and G3 both pass but queue overlap exceeds 90pct"
        else:
            status = "PASS"
            reason = "at least one of G2/G3 satisfies seed29 official gate"
    elif all(decisions[arm]["triggers_fail_condition"] for arm in TARGET_ARMS):
        status = "FAIL"
        reason = "both G2/G3 trigger fail conditions"
    else:
        status = "REVIEW"
        reason = "reports complete but no automatic pass/fail"

    return {
        "created_at": _now(),
        "experiment_id": "20260515_phase3g_seed29_official_gate",
        "objective": "decide whether Phase3G seed29 justifies seeds30-32 launch",
        "status": status,
        "reason": reason,
        "run_root": str(run_root),
        "aggregate_root": str(aggregate_root) if aggregate_root else None,
        "clustered_rows_path": str(clustered_rows_path) if clustered_rows_path else None,
        "queue_watch_json": str(queue_watch_json) if queue_watch_json else None,
        "queue_overlaps": queue_overlaps,
        "arms": arms,
        "target_arm_decisions": decisions,
        "gate_rules": {
            "pass": {
                "top_cluster_share_lte": 0.45,
                "cluster_001_share_lte": 0.25,
                "cluster_003_share_lte": 0.25,
                "median_turnover_lte": 0.20,
                "deployable_gte_max_G0_G1_minus": 2,
                "new_vs_134_gte": 1,
            },
            "fail": {
                "top_cluster_share_gt": 0.50,
                "median_turnover_gt": 0.25,
                "deployable_below_G0_by_more_than": 3,
            },
        },
        "decision": status,
        "safety": {
            "does_not_launch_seeds30_32": True,
            "requires_explicit_launcher_after_pass": True,
        },
    }


def _write_arm_csv(path: Path, arms: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "arm",
        "report_exists",
        "audited",
        "deployable_clusters",
        "raw_non_gap_pass",
        "top_cluster_id",
        "top_cluster_share",
        "cluster_001_share",
        "cluster_003_share",
        "median_turnover",
        "new_vs_134",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in arms:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3G Seed29 Official Gate",
        "",
        f"- created_at: {report['created_at']}",
        f"- experiment_id: {report['experiment_id']}",
        f"- status: {report['status']}",
        f"- reason: {report['reason']}",
        f"- run_root: `{report['run_root']}`",
        f"- clustered_rows_path: `{report.get('clustered_rows_path')}`",
        "",
        "## Arm Metrics",
        "",
        "| arm | deployable | top_share | c001 | c003 | turnover | new_vs_134 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["arms"]:
        lines.append(
            "| {arm} | {deployable} | {top} | {c1} | {c3} | {turnover} | {new} |".format(
                arm=row["arm"],
                deployable=row.get("deployable_clusters"),
                top=row.get("top_cluster_share"),
                c1=row.get("cluster_001_share"),
                c3=row.get("cluster_003_share"),
                turnover=row.get("median_turnover"),
                new=row.get("new_vs_134"),
            )
        )
    lines.extend(["", "## Target Arm Decisions", ""])
    for arm, decision in report["target_arm_decisions"].items():
        lines.append(f"- {arm}: {decision}")
    lines.extend(["", "## Queue Overlap", ""])
    lines.append(json.dumps(report.get("queue_overlaps", {}), indent=2, ensure_ascii=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--aggregate-root", type=Path, default=None)
    parser.add_argument("--queue-watch-json", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = evaluate_gate(args.run_root, args.aggregate_root, args.queue_watch_json)
    _write_json(args.output_root / "phase3g_seed29_official_gate.json", report)
    _write_arm_csv(args.output_root / "phase3g_seed29_official_gate_arm_metrics.csv", report["arms"])
    _write_md(args.output_root / "PHASE3G_SEED29_OFFICIAL_GATE_2026-05-15.md", report)
    print(json.dumps({"status": report["status"], "reason": report["reason"], "output_root": str(args.output_root)}, ensure_ascii=False))
    return 0 if report["status"] in {"PASS", "REVIEW", "WAIT_REPORTS", "WAIT_AGGREGATE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
