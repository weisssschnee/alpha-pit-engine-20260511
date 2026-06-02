from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.variation import canonicalize_expression_light


DEFAULT_RECLUSTER_ROWS = Path("reports/cn_underutilized_field_registry_recluster_20260601/recluster_review_rows.csv")
DEFAULT_REGISTRY = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_registry_review_queue_20260601")
DEFAULT_QUEUE_JSON = Path("runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _registry_canonicals(path: Path) -> set[str]:
    data = _read_json(path)
    out: set[str] = set()
    for row in data.get("deployable_representatives") or []:
        if not isinstance(row, dict):
            continue
        expr = row.get("representative_expression") or row.get("canonical_expression") or row.get("expression") or ""
        if expr:
            out.add(canonicalize_expression_light(str(expr)))
    return out


def _queue_entry(row: dict[str, str], sequence: int) -> dict[str, Any]:
    return {
        "review_queue_id": f"cn_uf_new_{sequence:03d}",
        "review_status": "pending_global_cluster_integration",
        "baseline_source": "phase3K_complete_149_representative_registry_20260517",
        "evidence_source": "cn_underutilized_field_replay128_registry_recluster",
        "signal_cluster_id": row.get("signal_cluster_id", ""),
        "candidate_id": row.get("candidate_id", ""),
        "source_lane": row.get("source_lane", ""),
        "source_generator": row.get("source_generator", ""),
        "factor_lane": row.get("factor_lane", ""),
        "primary_field_family": row.get("primary_field_family", ""),
        "representative_expression": row.get("expression", ""),
        "canonical_expression": canonicalize_expression_light(row.get("expression", "")),
        "signal_vector_id": row.get("signal_vector_id", ""),
        "signal_vector_source": row.get("signal_vector_source", ""),
        "nearest_registry_entry_id": row.get("nearest_registry_entry_id", ""),
        "nearest_legacy_cluster_id": row.get("nearest_legacy_cluster_id", ""),
        "max_abs_corr_to_149_signal_vector": float(row.get("max_abs_corr_to_149_signal_vector") or 0.0),
        "mean_top3_abs_corr_to_149_signal_vector": float(row.get("mean_top3_abs_corr_to_149_signal_vector") or 0.0),
        "registry_signal_match_tier": row.get("registry_signal_match_tier", ""),
        "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover", ""),
        "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino", ""),
        "deployable_cluster_member_count": row.get("deployable_cluster_member_count", ""),
        "promotion_rule": "eligible_only_after_full_global_signal_cluster_integration",
    }


def run_review_queue(
    *,
    recluster_rows_path: Path,
    registry_path: Path,
    report_dir: Path,
    queue_json: Path,
) -> dict[str, Any]:
    rows = _read_csv(recluster_rows_path)
    registry_canonicals = _registry_canonicals(registry_path)
    provisional_rows = [row for row in rows if row.get("registry_signal_match_tier") == "provisional_new_signal_space"]
    duplicate_rows = [row for row in rows if row.get("registry_signal_match_tier") == "known_or_duplicate_signal_cluster"]
    review_rows = [row for row in rows if row.get("registry_signal_match_tier") == "registry_similarity_review"]

    queue = [_queue_entry(row, idx + 1) for idx, row in enumerate(provisional_rows)]
    duplicate_canonical_hits = sum(1 for item in queue if item["canonical_expression"] in registry_canonicals)
    queue_canonical_counts = Counter(item["canonical_expression"] for item in queue)
    queue_internal_duplicate_count = sum(count - 1 for count in queue_canonical_counts.values() if count > 1)

    payload: dict[str, Any] = {
        "queue_id": "cn_underutilized_field_provisional_new_queue_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "PASS_REGISTRY_REVIEW_QUEUE_READY",
        "scope": "candidate registry-review queue for replay128 underutilized-field provisional-new signal-space representatives; does not mutate official baseline",
        "baseline": {
            "registry_path": str(registry_path),
            "declared_discovery_baseline": 149,
        },
        "inputs": {
            "recluster_rows_path": str(recluster_rows_path),
        },
        "counts": {
            "recluster_rows": len(rows),
            "queued_provisional_new": len(queue),
            "known_duplicate_holdout": len(duplicate_rows),
            "review_band_holdout": len(review_rows),
            "queue_canonical_hits_in_registry": duplicate_canonical_hits,
            "queue_internal_duplicate_canonical_count": queue_internal_duplicate_count,
            "candidate_discovery_baseline_if_all_queue_survives": 149 + len(queue),
        },
        "source_lane_counts": dict(Counter(item["source_lane"] for item in queue)),
        "factor_lane_counts": dict(Counter(item["factor_lane"] for item in queue)),
        "holdouts": [
            {
                "signal_cluster_id": row.get("signal_cluster_id", ""),
                "candidate_id": row.get("candidate_id", ""),
                "factor_lane": row.get("factor_lane", ""),
                "match_tier": row.get("registry_signal_match_tier", ""),
                "nearest_registry_entry_id": row.get("nearest_registry_entry_id", ""),
                "max_abs_corr_to_149_signal_vector": float(row.get("max_abs_corr_to_149_signal_vector") or 0.0),
                "expression": row.get("expression", ""),
            }
            for row in duplicate_rows + review_rows
        ],
        "queue": queue,
        "next_gate": [
            "run full global signal-cluster integration with the frozen 149 registry plus queued representatives",
            "promote only representatives that remain distinct after duplicate-family and book-readiness review",
            "do not update official discovery baseline from this queue alone",
        ],
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    queue_json.parent.mkdir(parents=True, exist_ok=True)
    queue_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (report_dir / "cn_underutilized_field_registry_review_queue.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(report_dir / "registry_review_queue.csv", queue)
    _write_csv(report_dir / "registry_review_holdouts.csv", payload["holdouts"])
    _write_markdown(report_dir / "CN_UNDERUTILIZED_FIELD_REGISTRY_REVIEW_QUEUE_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Registry Review Queue - 2026-06-01",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Scope",
        "",
        payload["scope"],
        "",
        "## Counts",
        "",
    ]
    for key, value in payload["counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Queue By Source Lane", ""])
    for key, value in sorted(payload["source_lane_counts"].items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Queue By Factor Lane", ""])
    for key, value in sorted(payload["factor_lane_counts"].items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Holdouts", ""])
    if payload["holdouts"]:
        for item in payload["holdouts"]:
            lines.append(
                "- `{cluster}` `{tier}` corr=`{corr:.6f}` nearest=`{nearest}` factor=`{factor}`".format(
                    cluster=item["signal_cluster_id"],
                    tier=item["match_tier"],
                    corr=float(item["max_abs_corr_to_149_signal_vector"]),
                    nearest=item["nearest_registry_entry_id"],
                    factor=item["factor_lane"],
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary", ""])
    lines.append("This queue is not an official baseline update. It is an input to the next global-cluster integration gate.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recluster-rows-path", type=Path, default=DEFAULT_RECLUSTER_ROWS)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--queue-json", type=Path, default=DEFAULT_QUEUE_JSON)
    args = parser.parse_args()
    payload = run_review_queue(
        recluster_rows_path=args.recluster_rows_path,
        registry_path=args.registry_path,
        report_dir=args.report_dir,
        queue_json=args.queue_json,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
