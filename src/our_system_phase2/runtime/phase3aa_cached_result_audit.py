"""Audit Phase3AA cached mature-pool replay outputs.

The selector can include event-derived candidates in a 64-row frozen queue while
smaller replay smoke runs audit only a prefix of that queue. This report makes
that visible by joining replay rows back to frozen-selection metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


EVENT_SOURCE = "event_derived_feature_layer"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _source_for(row: dict[str, Any], selected_by_id: dict[str, dict[str, Any]]) -> str:
    meta = selected_by_id.get(str(row.get("candidate_id"))) or {}
    return str(meta.get("source_lane") or meta.get("source_generator") or row.get("source_lane") or "unknown")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _summarize(root: Path) -> dict[str, Any]:
    selector_root = root / "selector" / "aa"
    replay_roots = []
    for name in ("replay", "replay64"):
        candidate = root / name / "aa"
        if (candidate / "phase3_strict_rows.json").exists():
            replay_roots.append(candidate)
    if not replay_roots and (root / "aa" / "phase3_strict_rows.json").exists():
        replay_roots.append(root / "aa")
    if not selector_root.exists():
        selector_root = root.parent / "selector" / "aa"

    selected_payload = _read_json(selector_root / "phase3_strict_selection_inputs.json")
    selected = list(selected_payload.get("selected") or [])
    selected_by_id = {str(row.get("candidate_id")): row for row in selected}
    selected_sources = Counter(str(row.get("source_lane") or row.get("source_generator") or "unknown") for row in selected)

    replay_summaries: list[dict[str, Any]] = []
    row_records: list[dict[str, Any]] = []
    for replay_root in replay_roots:
        strict_rows = _read_json(replay_root / "phase3_strict_rows.json").get("strict_rows") or []
        report_path = replay_root / "phase3_repair_report.json"
        report = _read_json(report_path) if report_path.exists() else {}
        source_counts: Counter[str] = Counter()
        raw_counts: Counter[str] = Counter()
        cost_counts: Counter[str] = Counter()
        clusters_by_source: dict[str, set[str]] = defaultdict(set)
        for row in strict_rows:
            source = _source_for(row, selected_by_id)
            source_counts[source] += 1
            cluster_id = row.get("signal_cluster_id")
            if cluster_id:
                clusters_by_source[source].add(str(cluster_id))
            if row.get("portfolio_replay_pass"):
                raw_counts[source] += 1
            if row.get("cost_survives"):
                cost_counts[source] += 1
            row_records.append(
                {
                    "replay_root": str(replay_root),
                    "candidate_id": row.get("candidate_id"),
                    "source": source,
                    "signal_cluster_id": cluster_id,
                    "portfolio_replay_pass": bool(row.get("portfolio_replay_pass")),
                    "cost_survives": bool(row.get("cost_survives")),
                    "portfolio_replay_long_short_sortino": _safe_float(row.get("portfolio_replay_long_short_sortino")),
                    "portfolio_replay_avg_one_way_turnover": _safe_float(row.get("portfolio_replay_avg_one_way_turnover")),
                    "expression": row.get("expression"),
                }
            )
        replay_summaries.append(
            {
                "replay_root": str(replay_root),
                "audited_count": len(strict_rows),
                "source_counts": dict(source_counts),
                "raw_pass_counts": dict(raw_counts),
                "cost_survives_counts": dict(cost_counts),
                "unique_signal_clusters_by_source": {key: len(value) for key, value in clusters_by_source.items()},
                "event_audited_count": int(source_counts.get(EVENT_SOURCE, 0)),
                "event_raw_pass_count": int(raw_counts.get(EVENT_SOURCE, 0)),
                "event_cost_survives_count": int(cost_counts.get(EVENT_SOURCE, 0)),
                "main_kpi": report.get("main_kpi") or {},
            }
        )

    return {
        "root": str(root),
        "selector_total_count": len(selected),
        "selector_source_counts": dict(selected_sources),
        "event_selected_count": int(selected_sources.get(EVENT_SOURCE, 0)),
        "replay_summaries": replay_summaries,
        "rows": row_records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    summaries = [_summarize(root) for root in args.root]
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        rows.extend(summary.pop("rows"))

    write_json_artifact(
        args.output_root / "phase3aa_cached_result_audit.json",
        {
            "created_at": utc_now_iso(),
            "schema_version": "phase3aa-cached-result-audit-v1",
            "summaries": summaries,
        },
    )
    if rows:
        with (args.output_root / "phase3aa_cached_result_rows.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"output_root": str(args.output_root), "root_count": len(summaries), "row_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
