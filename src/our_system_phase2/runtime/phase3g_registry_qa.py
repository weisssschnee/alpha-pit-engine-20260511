"""Audit Phase3G cumulative registry metadata.

This checks the Phase3E declared 134-cluster registry against the rows that are
actually matchable in a Phase3G aggregate. It is intentionally metadata-only:
no search, replay, or selector behavior is changed.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASELINE = Path("src/our_system_phase2/runtime/baselines/phase3E_cumulative_deployable_clusters_20260514.json")
DEFAULT_CLUSTERED_ROWS = Path(
    "reports/phase3g_s29_s32_company_fixed_mixed_aggregate_20260515/"
    "phase3g_s29_s32_company_fixed_mixed_global_clustered_rows.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/phase3g_registry_qa_20260515")


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


def _load_clustered_baseline_rows(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    payload = _read_json(path)
    rows = payload.get("rows", []) if isinstance(payload, dict) else payload
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("aggregate_source_kind") != "phase3_cumulative_baseline":
            continue
        cluster_id = str(row.get("baseline_phase3_cumulative_cluster_id") or "")
        if cluster_id:
            out[cluster_id] = row
    return out


def audit_registry(baseline_path: Path, clustered_rows_path: Path | None = None) -> dict[str, Any]:
    baseline = _read_json(baseline_path)
    representatives = baseline.get("deployable_representatives") or []
    declared_count = baseline.get("declared_cluster_count")
    if declared_count is None:
        declared_count = baseline.get("declared_cumulative_cluster_count")
    declared_count = int(declared_count or len(representatives))

    clustered_by_registry_id = _load_clustered_baseline_rows(clustered_rows_path)
    global_to_registry_ids: dict[str, list[str]] = defaultdict(list)
    for cluster_id, row in clustered_by_registry_id.items():
        global_cluster = str(row.get("global_signal_cluster_id") or "")
        if global_cluster:
            global_to_registry_ids[global_cluster].append(cluster_id)

    collision_groups = {
        global_cluster: sorted(ids)
        for global_cluster, ids in global_to_registry_ids.items()
        if len(ids) > 1
    }
    collision_duplicate_loss = sum(len(ids) - 1 for ids in collision_groups.values())

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(representatives):
        registry_cluster_id = str(item.get("cluster_id") or "")
        expression = str(item.get("representative_expression") or "")
        aggregate_row = clustered_by_registry_id.get(registry_cluster_id, {})
        aggregate_cluster = str(aggregate_row.get("global_signal_cluster_id") or "")
        collision_peers = collision_groups.get(aggregate_cluster, []) if aggregate_cluster else []
        reason = "ok"
        if not expression:
            reason = "missing_representative_expression"
        elif not aggregate_row:
            reason = "missing_aggregate_match"
        elif len(collision_peers) > 1:
            reason = "recluster_collision_group"
        rows.append(
            {
                "registry_cluster_id": registry_cluster_id,
                "row_kind": "representative",
                "representative_index": index,
                "candidate_id": item.get("candidate_id"),
                "has_representative_expression": bool(expression),
                "has_source_candidate": bool(item.get("candidate_id")),
                "has_aggregate_row": bool(aggregate_row),
                "aggregate_global_cluster_id": aggregate_cluster,
                "aggregate_cluster_member_count": len(collision_peers) if collision_peers else (1 if aggregate_cluster else 0),
                "collides_with_registry_cluster_ids": ",".join(collision_peers),
                "match_failure_reason": reason,
                "representative_expression": expression,
            }
        )

    missing_declared_count = max(0, declared_count - len(representatives))
    for index in range(missing_declared_count):
        rows.append(
            {
                "registry_cluster_id": f"declared_missing_{index + 1:03d}",
                "row_kind": "declared_missing_placeholder",
                "representative_index": "",
                "candidate_id": "",
                "has_representative_expression": False,
                "has_source_candidate": False,
                "has_aggregate_row": False,
                "aggregate_global_cluster_id": "",
                "aggregate_cluster_member_count": 0,
                "collides_with_registry_cluster_ids": "",
                "match_failure_reason": "declared_count_exceeds_representative_rows",
                "representative_expression": "",
            }
        )

    aggregate_unique_clusters = len(set(row.get("aggregate_global_cluster_id") for row in rows if row.get("aggregate_global_cluster_id")))
    summary = {
        "created_at": _now(),
        "decision": "HOLD_METADATA_ONLY" if missing_declared_count or collision_duplicate_loss else "PASS_METADATA_QA",
        "baseline_path": str(baseline_path),
        "clustered_rows_path": str(clustered_rows_path) if clustered_rows_path else None,
        "declared_cluster_count": declared_count,
        "representative_count": len(representatives),
        "missing_declared_without_representative_count": missing_declared_count,
        "aggregate_matched_representative_count": len(clustered_by_registry_id),
        "aggregate_unique_cluster_count": aggregate_unique_clusters,
        "recluster_collision_group_count": len(collision_groups),
        "recluster_collision_duplicate_loss": collision_duplicate_loss,
        "declared_vs_aggregate_unique_gap": declared_count - aggregate_unique_clusters,
        "collision_groups": collision_groups,
        "interpretation": (
            "The 134 vs 122 gap is metadata/registry accounting, not a new search result: "
            f"{missing_declared_count} declared clusters lack representative rows and "
            f"{collision_duplicate_loss} representative rows collapse under Phase3G reclustering."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# Phase3G Registry QA",
        "",
        f"- created_at: `{summary['created_at']}`",
        f"- decision: `{summary['decision']}`",
        f"- declared_cluster_count: `{summary['declared_cluster_count']}`",
        f"- representative_count: `{summary['representative_count']}`",
        f"- aggregate_unique_cluster_count: `{summary['aggregate_unique_cluster_count']}`",
        f"- missing_declared_without_representative_count: `{summary['missing_declared_without_representative_count']}`",
        f"- recluster_collision_group_count: `{summary['recluster_collision_group_count']}`",
        f"- recluster_collision_duplicate_loss: `{summary['recluster_collision_duplicate_loss']}`",
        f"- declared_vs_aggregate_unique_gap: `{summary['declared_vs_aggregate_unique_gap']}`",
        "",
        "## Interpretation",
        "",
        summary["interpretation"],
        "",
        "## Collision Groups",
        "",
        "| aggregate_global_cluster_id | registry_cluster_ids |",
        "| --- | --- |",
    ]
    for global_cluster, ids in sorted(summary["collision_groups"].items()):
        lines.append(f"| {global_cluster} | {', '.join(ids)} |")
    if not summary["collision_groups"]:
        lines.append("| none | none |")
    lines.extend(
        [
            "",
            "## Required Follow-Up",
            "",
            "- Do not update the future cumulative baseline until representative coverage and recluster collision accounting are explicitly accepted or repaired.",
            "- If the declared count remains 134, store the five missing representative rows or mark them as non-vector-matchable baseline members.",
            "- If recluster collisions are expected, report both `declared_baseline_count` and `vector_matchable_unique_baseline_count` in Phase3H.",
            "",
            "Detailed row-level diagnostics are in `phase3g_registry_qa_rows.csv`.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--clustered-rows", type=Path, default=DEFAULT_CLUSTERED_ROWS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = audit_registry(args.baseline, args.clustered_rows)
    _write_json(args.output_root / "phase3g_registry_qa_report.json", report)
    _write_csv(args.output_root / "phase3g_registry_qa_rows.csv", report["rows"])
    _write_markdown(args.output_root / "PHASE3G_REGISTRY_QA_2026-05-15.md", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["decision"] == "PASS_METADATA_QA" else 2


if __name__ == "__main__":
    raise SystemExit(main())
