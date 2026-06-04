from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("runtime/phase3ah_sparse_event_canary_v1_20260604")
DEFAULT_REPORT_ROOT = Path("reports/phase3ah_sparse_event_canary_v1_20260604")
VERSION = "phase3ah-sparse-event-canary-aggregate-v1-2026-06-04"
ARMS = {
    "true_sparse_event": Path("true_sparse_event/aa/phase3_repair_report.json"),
    "coverage_sparse_event": Path("coverage_sparse_event/aa/phase3_repair_report.json"),
    "same_count_sparse_event": Path("same_count_sparse_event/aa/phase3_repair_report.json"),
    "matched_sparse_event": Path("matched_sparse_event/aa/phase3_repair_report.json"),
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _summary(arm: str, report_path: Path) -> dict[str, Any]:
    report = _read_json(report_path)
    primary = ((report.get("main_kpi") or {}).get("primary") or {})
    secondary = ((report.get("main_kpi") or {}).get("secondary") or {})
    return {
        "arm": arm,
        "report_path": str(report_path),
        "ablation_arm": report.get("ablation_arm"),
        "audited": int(primary.get("audited_count") or 0),
        "deployable_clusters": int(primary.get("cost_turnover_deployable_unique_clusters") or 0),
        "deployable_per_audited": float(primary.get("cost_turnover_deployable_unique_clusters_per_audited") or 0.0),
        "raw_non_gap_pass": int(secondary.get("raw_non_gap_replay_pass") or 0),
        "raw_non_gap_pass_per_audited": float(secondary.get("raw_non_gap_replay_pass_per_audited") or 0.0),
        "unique_return_corr_clusters": int(secondary.get("unique_return_corr_clusters") or 0),
        "top_cluster_share": float(secondary.get("top_cluster_raw_pass_share") or 0.0),
        "top_cluster_id": secondary.get("top_cluster_id"),
    }


def _decision(rows: dict[str, dict[str, Any]]) -> tuple[str, list[str]]:
    true = rows["true_sparse_event"]["deployable_clusters"]
    coverage = rows["coverage_sparse_event"]["deployable_clusters"]
    same = rows["same_count_sparse_event"]["deployable_clusters"]
    matched = rows["matched_sparse_event"]["deployable_clusters"]
    blockers: list[str] = []
    if true <= coverage:
        blockers.append("true_sparse_value_not_better_than_sparse_coverage")
    if true <= same:
        blockers.append("true_sparse_value_not_better_than_same_count_control")
    if coverage <= same:
        blockers.append("sparse_coverage_not_better_than_same_count_control")
    if coverage <= matched:
        blockers.append("sparse_coverage_not_better_than_matched_control")
    if blockers:
        return "HOLD_PHASE3AH_SPARSE_EVENT_CANARY_CONTROLS_NOT_BEATEN", blockers
    return "PASS_PHASE3AH_SPARSE_EVENT_CANARY_BEATS_CONTROLS", blockers


def aggregate(*, root: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    rows = {arm: _summary(arm, root / rel) for arm, rel in ARMS.items()}
    decision, blockers = _decision(rows)
    table = list(rows.values())
    _write_csv(report_root / "phase3ah_sparse_event_canary_arm_summary.csv", table)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": VERSION,
        "decision": decision,
        "scope": "Sparse limit-event-only canary after broad coverage fields were excluded. This is not a large search.",
        "blockers": blockers,
        "arms": rows,
        "interpretation": {
            "numeric_sparse_event": "True sparse event values produced no deployable clusters in this canary.",
            "membership_sparse_event": "Sparse coverage membership produced deployables but did not beat same-count random.",
            "opportunity_count": "Same-count sparse control was strongest, so event opportunity/date-count effects remain the dominant explanation.",
        },
        "next_policy": {
            "large_search_allowed": False,
            "event_formula_expansion_allowed": False,
            "allowed_next": "Treat limit/event fields as regime/opportunity diagnostics or veto/intensifier candidates, not rank-alpha search budget.",
        },
        "outputs": {
            "summary_csv": str(report_root / "phase3ah_sparse_event_canary_arm_summary.csv"),
            "summary_json": str(report_root / "phase3ah_sparse_event_canary_aggregate_v1.json"),
            "markdown": str(report_root / "PHASE3AH_SPARSE_EVENT_CANARY_AGGREGATE_V1_2026-06-04.md"),
        },
    }
    _write_json(report_root / "phase3ah_sparse_event_canary_aggregate_v1.json", payload)
    _write_markdown(report_root / "PHASE3AH_SPARSE_EVENT_CANARY_AGGREGATE_V1_2026-06-04.md", payload, table)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], table: list[dict[str, Any]]) -> None:
    lines = [
        "# Phase3AH Sparse Event Canary Aggregate V1",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Arm Summary",
        "",
        "| arm | audited | deployable | raw non-gap | top share |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in table:
        lines.append(
            f"| `{row['arm']}` | {row['audited']} | {row['deployable_clusters']} | {row['raw_non_gap_pass']} | {row['top_cluster_share']:.4f} |"
        )
    lines.extend(["", "## Blockers", ""])
    for blocker in payload["blockers"]:
        lines.append(f"- `{blocker}`")
    lines.extend(["", "## Interpretation", ""])
    for key, value in payload["interpretation"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Next Policy", ""])
    for key, value in payload["next_policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    payload = aggregate(root=args.root, report_root=args.report_root)
    print(json.dumps({"decision": payload["decision"], "blockers": payload["blockers"], "arms": payload["arms"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
