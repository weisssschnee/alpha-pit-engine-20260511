"""Freeze Phase3J locked book filters for Phase3K validation.

This script creates the machine-readable artifact that fixes J2 and
J4_relaxed. It does not search, evaluate, or tune thresholds.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _cluster_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "cluster_id": row.get("cluster_id"),
                "representative_candidate_id": row.get("representative_candidate_id"),
                "representative_expression": row.get("representative_expression"),
                "source_lane": row.get("source_lane"),
                "raw_pass_count": int(float(row.get("raw_pass_count") or 0)),
                "deployable_count": int(float(row.get("deployable_count") or 0)),
                "p90_replay_turnover": float(row.get("p90_replay_turnover") or 0.0),
                "median_replay_turnover": float(row.get("median_replay_turnover") or 0.0),
                "capacity_proxy": float(row.get("capacity_proxy") or 0.0),
                "median_amount_20d": float(row.get("median_amount_20d") or 0.0),
                "limit_hit_rate": float(row.get("limit_hit_rate") or 0.0),
                "suspension_rate": float(row.get("suspension_rate") or 0.0),
                "cost_adjusted_score": float(row.get("cost_adjusted_score") or 0.0),
            }
        )
    return sorted(out, key=lambda item: str(item["cluster_id"]))


def _stable_hash(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--j2", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j2_clusters.csv"))
    parser.add_argument("--j4", type=Path, default=Path("reports/phase3j_j4_filter_sensitivity_20260516/phase3j_book_j4_relaxed_candidate_clusters.csv"))
    parser.add_argument("--removed", type=Path, default=Path("reports/phase3j_j2_j4_relaxed_comparison_20260516/phase3j_j2_only_removed_clusters.csv"))
    parser.add_argument("--comparison", type=Path, default=Path("reports/phase3j_j2_j4_relaxed_comparison_20260516/phase3j_j2_j4_relaxed_comparison.json"))
    parser.add_argument("--output", type=Path, default=Path("runtime/baselines/phase3j_locked_book_filters.json"))
    args = parser.parse_args()

    j2_rows = _cluster_summary(_read_csv(args.j2))
    j4_rows = _cluster_summary(_read_csv(args.j4))
    removed_rows = _cluster_summary(_read_csv(args.removed))
    comparison = _read_json(args.comparison)
    stable_payload = {
        "filter_family": "phase3j_locked_book_filters",
        "filter_version": "phase3j_locked_book_filters_v1_20260516",
        "decision": "PASS_PHASE3J_BOOK_FILTER_DISCOVERY",
        "next_phase": "Phase3K_locked_book_validation",
        "locked": True,
        "do_not_tune_before_phase3k": True,
        "baseline_book_candidate": {
            "name": "J2_balanced",
            "cluster_count": len(j2_rows),
            "cluster_ids": [row["cluster_id"] for row in j2_rows],
            "clusters": j2_rows,
        },
        "liquidity_aware_overlay_candidate": {
            "name": "J4_relaxed",
            "cluster_count": len(j4_rows),
            "relation_to_j2": "J2_minus_cluster_087",
            "cluster_ids": [row["cluster_id"] for row in j4_rows],
            "clusters": j4_rows,
            "thresholds": {
                "amount_bottom_quantile": 0.05,
                "capacity_bottom_quantile": 0.05,
                "gate_mode": "reject_only_if_both_amount_and_capacity_below_threshold",
                "max_limit_hit_rate": 0.20,
                "max_suspension_rate": 0.01,
            },
        },
        "removed_from_j2_by_j4_relaxed": {
            "count": len(removed_rows),
            "cluster_ids": [row["cluster_id"] for row in removed_rows],
            "clusters": removed_rows,
            "removal_logic": "remove cluster if both amount and capacity are below 5th percentile or feasibility rates breach thresholds",
        },
        "original_j4": {
            "status": "demoted",
            "reason": "too conservative / over-filtered",
        },
        "not_confirmed": [
            "mature_capacity_model",
            "production_book",
            "execution_fill_model",
            "live_slippage_model",
        ],
        "evidence": {
            "comparison_report": str(args.comparison),
            "overlap": comparison.get("overlap"),
            "plateau": {key: value for key, value in (comparison.get("plateau") or {}).items() if key != "top_variants"},
            "book_proxy": comparison.get("book_proxy"),
        },
    }
    payload = dict(stable_payload)
    payload["created_at"] = utc_now_iso()
    payload["filter_version_hash"] = _stable_hash(stable_payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
