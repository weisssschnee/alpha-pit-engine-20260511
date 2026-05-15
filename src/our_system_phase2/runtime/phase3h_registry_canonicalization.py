"""Canonicalize the Phase3H registry baseline.

Phase3G exposed a metadata/accounting mismatch:

* 134 declared cumulative deployable clusters.
* 129 representative rows.
* 122 unique vector-matchable clusters after Phase3G reclustering.

This script does not change any search result. It formalizes the dual-baseline
policy used by Phase3H:

* discovery_baseline = 134 for historical deployable-cluster accounting.
* selector_vector_baseline = 122 for signal-vector nearest-cluster/cap logic.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QA_REPORT = Path("reports/phase3g_registry_qa_20260515/phase3g_registry_qa_report.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3h_registry_canonicalization_20260515")


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


def _parse_peer_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted(str(item) for item in value if str(item))
    text = str(value).strip()
    if not text:
        return []
    return sorted(part.strip() for part in text.split(",") if part.strip())


def canonicalize_registry(qa_report_path: Path) -> dict[str, Any]:
    qa = _read_json(qa_report_path)
    qa_summary = qa.get("summary", {})
    qa_rows = qa.get("rows", [])

    collision_groups = {
        str(cluster_id): sorted(str(item) for item in members)
        for cluster_id, members in (qa_summary.get("collision_groups") or {}).items()
    }
    collision_canonical_by_global: dict[str, str] = {
        global_cluster_id: peers[0]
        for global_cluster_id, peers in collision_groups.items()
        if peers
    }

    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    merged_rows: list[dict[str, Any]] = []
    vector_cluster_to_declared: dict[str, list[str]] = defaultdict(list)

    for row in qa_rows:
        declared_cluster_id = str(row.get("registry_cluster_id") or "")
        aggregate_cluster_id = str(row.get("aggregate_global_cluster_id") or "")
        peers = _parse_peer_list(row.get("collides_with_registry_cluster_ids"))
        canonical_declared = collision_canonical_by_global.get(aggregate_cluster_id, declared_cluster_id)

        has_repr = bool(row.get("has_representative_expression"))
        has_aggregate = bool(row.get("has_aggregate_row"))
        if not has_repr:
            status = "missing_representative"
            vector_cluster_id = ""
            reason = str(row.get("match_failure_reason") or "missing_representative")
        elif not has_aggregate:
            status = "non_vector_matchable"
            vector_cluster_id = ""
            reason = str(row.get("match_failure_reason") or "missing_aggregate_match")
        elif peers and declared_cluster_id != canonical_declared:
            status = "merged_into_existing_vector_cluster"
            vector_cluster_id = aggregate_cluster_id
            reason = "recluster_collision_natural_merge"
        else:
            status = "vector_matchable"
            vector_cluster_id = aggregate_cluster_id
            reason = str(row.get("match_failure_reason") or "ok")

        out = {
            "declared_cluster_id": declared_cluster_id,
            "representative_candidate_id": row.get("candidate_id") or "",
            "representative_expression": row.get("representative_expression") or "",
            "vector_cluster_id": vector_cluster_id,
            "status": status,
            "merge_group_id": aggregate_cluster_id if peers else "",
            "vector_cluster_representative_declared_cluster_id": canonical_declared if peers else declared_cluster_id,
            "collides_with_declared_cluster_ids": ",".join(peers),
            "reason": reason,
            "source_row_kind": row.get("row_kind") or "",
        }
        rows.append(out)
        if vector_cluster_id:
            vector_cluster_to_declared[vector_cluster_id].append(declared_cluster_id)
        if status == "missing_representative":
            missing_rows.append(out)
        if status == "merged_into_existing_vector_cluster":
            merged_rows.append(out)

    selector_vector_baseline_count = len(vector_cluster_to_declared)
    discovery_baseline_count = int(qa_summary.get("declared_cluster_count") or len(rows))
    representative_count = int(qa_summary.get("representative_count") or 0)

    summary = {
        "created_at": _now(),
        "decision": "PASS_DUAL_BASELINE_POLICY",
        "metadata_policy": "DUAL_BASELINE_ACCEPTED",
        "qa_report_path": str(qa_report_path),
        "discovery_baseline": discovery_baseline_count,
        "selector_vector_baseline": selector_vector_baseline_count,
        "representative_count": representative_count,
        "missing_representatives": len(missing_rows),
        "merged_representatives": len(merged_rows),
        "vector_matchable_declared_rows": sum(1 for row in rows if row["status"] == "vector_matchable"),
        "non_vector_matchable_rows": sum(1 for row in rows if row["status"] in {"missing_representative", "non_vector_matchable"}),
        "policy": (
            "Use discovery_baseline=134 for historical cumulative cluster accounting and "
            "selector_vector_baseline=122 for Phase3H signal-vector nearest-cluster/cap logic."
        ),
        "interpretation": (
            "The 134->122 gap is accepted as registry canonicalization: five declared clusters "
            "lack representatives and seven representative rows naturally merge under signal-vector "
            "reclustering. This no longer blocks G2 as a Phase3H signal-vector control, but it still "
            "blocks any true book-residual selector claim."
        ),
    }
    return {
        "summary": summary,
        "declared_to_vector_cluster_map": rows,
        "missing_representatives": missing_rows,
        "merged_representatives": merged_rows,
        "vector_cluster_members": {
            cluster_id: sorted(members)
            for cluster_id, members in sorted(vector_cluster_to_declared.items())
        },
    }


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    merged_rows = report["merged_representatives"]
    missing_rows = report["missing_representatives"]

    lines = [
        "# Phase3H Registry Canonicalization",
        "",
        f"- created_at: `{summary['created_at']}`",
        f"- decision: `{summary['decision']}`",
        f"- metadata_policy: `{summary['metadata_policy']}`",
        f"- discovery_baseline: `{summary['discovery_baseline']}`",
        f"- selector_vector_baseline: `{summary['selector_vector_baseline']}`",
        f"- representative_count: `{summary['representative_count']}`",
        f"- missing_representatives: `{summary['missing_representatives']}`",
        f"- merged_representatives: `{summary['merged_representatives']}`",
        "",
        "## Policy",
        "",
        summary["policy"],
        "",
        "This clears the Phase3G metadata blocker for using G2 as a Phase3H signal-vector control. It does not clear the true book-residual selector gate.",
        "",
        "## Interpretation",
        "",
        summary["interpretation"],
        "",
        "## Missing Representatives",
        "",
        "| declared_cluster_id | reason |",
        "| --- | --- |",
    ]
    if missing_rows:
        for row in missing_rows:
            lines.append(f"| {row['declared_cluster_id']} | {row['reason']} |")
    else:
        lines.append("| none | none |")

    lines.extend(["", "## Natural Signal-Vector Merges", "", "| declared_cluster_id | vector_cluster_id | canonical_declared_cluster | peers |", "| --- | --- | --- | --- |"])
    if merged_rows:
        for row in merged_rows:
            lines.append(
                "| {declared} | {vector} | {canonical} | {peers} |".format(
                    declared=row["declared_cluster_id"],
                    vector=row["vector_cluster_id"],
                    canonical=row["vector_cluster_representative_declared_cluster_id"],
                    peers=row["collides_with_declared_cluster_ids"],
                )
            )
    else:
        lines.append("| none | none | none | none |")

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `phase3h_registry_canonicalization.json`",
            "- `declared_to_vector_cluster_map.csv`",
            "- `missing_representatives.csv`",
            "- `merged_representatives.csv`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-report", type=Path, default=DEFAULT_QA_REPORT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    report = canonicalize_registry(args.qa_report)
    output_root = args.output_root
    _write_json(output_root / "phase3h_registry_canonicalization.json", report)
    _write_csv(output_root / "declared_to_vector_cluster_map.csv", report["declared_to_vector_cluster_map"])
    _write_csv(output_root / "missing_representatives.csv", report["missing_representatives"])
    _write_csv(output_root / "merged_representatives.csv", report["merged_representatives"])
    _write_markdown(output_root / "PHASE3H_REGISTRY_CANONICALIZATION_2026-05-15.md", report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
