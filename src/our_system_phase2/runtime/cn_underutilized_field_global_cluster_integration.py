from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.services.phase3g_signal_vector_store import (
    DEFAULT_PHASE3G_RUNTIME_CACHE_DIR,
    Phase3GSignalVectorStore,
)
from our_system_phase2.services.variation import canonicalize_expression_light


DEFAULT_REGISTRY = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_QUEUE = Path("runtime/registry_review/cn_underutilized_field_provisional_new_queue_20260601.json")
DEFAULT_DATASET = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_global_cluster_integration_20260601")
DEFAULT_OUTPUT_REGISTRY = Path("runtime/registry_review/cn_underutilized_field_candidate_162_registry_20260601.json")
DEFAULT_RUNTIME_CACHE = DEFAULT_PHASE3G_RUNTIME_CACHE_DIR / "underutilized_global_integration_20260601"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _corr(left: np.ndarray | None, right: np.ndarray | None) -> float:
    if left is None or right is None or left.size == 0 or right.size == 0 or left.shape != right.shape:
        return 0.0
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not math.isfinite(denom) or denom <= 1e-12:
        return 0.0
    value = float(np.dot(left, right) / denom)
    return value if math.isfinite(value) else 0.0


def _norm(vector: np.ndarray | None) -> float:
    if vector is None or vector.size == 0:
        return 0.0
    value = float(np.linalg.norm(vector))
    return value if math.isfinite(value) else 0.0


def _registry_items(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = _read_json(path)
    items: list[dict[str, Any]] = []
    for index, row in enumerate(data.get("deployable_representatives") or []):
        if not isinstance(row, dict):
            continue
        expr = _safe_str(row.get("representative_expression") or row.get("canonical_expression") or row.get("expression"))
        if not expr:
            continue
        entry_id = _safe_str(row.get("registry_entry_id") or f"registry_{index+1:03d}")
        items.append(
            {
                "node_id": entry_id,
                "node_kind": "existing_registry",
                "registry_entry_id": entry_id,
                "legacy_cluster_id": _safe_str(row.get("legacy_cluster_id") or row.get("cluster_id")),
                "source_lane": _safe_str(row.get("source_lane")),
                "source_generator": _safe_str(row.get("source_generator")),
                "factor_lane": _safe_str(row.get("factor_lane")),
                "representative_expression": expr,
                "canonical_expression": canonicalize_expression_light(expr),
                "raw_registry_row": row,
            }
        )
    return data, items


def _queue_items(path: Path, start_index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = _read_json(path)
    items: list[dict[str, Any]] = []
    for offset, row in enumerate(data.get("queue") or [], start=0):
        if not isinstance(row, dict):
            continue
        expr = _safe_str(row.get("representative_expression"))
        if not expr:
            continue
        entry_id = f"cn_uf_registry_{start_index + offset:03d}"
        items.append(
            {
                "node_id": entry_id,
                "node_kind": "queued_new",
                "registry_entry_id": entry_id,
                "review_queue_id": _safe_str(row.get("review_queue_id")),
                "legacy_cluster_id": _safe_str(row.get("signal_cluster_id")),
                "source_lane": _safe_str(row.get("source_lane")),
                "source_generator": _safe_str(row.get("source_generator")),
                "factor_lane": _safe_str(row.get("factor_lane")),
                "representative_expression": expr,
                "canonical_expression": canonicalize_expression_light(expr),
                "raw_queue_row": row,
            }
        )
    return data, items


def _components(node_ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for left, right in edges:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    seen: set[str] = set()
    out: list[list[str]] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        queue: deque[str] = deque([node_id])
        seen.add(node_id)
        comp: list[str] = []
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            for nxt in sorted(graph.get(cur, set())):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        out.append(sorted(comp))
    return out


def run_integration(
    *,
    registry_path: Path,
    queue_path: Path,
    dataset_path: Path,
    report_dir: Path,
    output_registry_path: Path,
    runtime_cache_dir: Path,
    high_corr_threshold: float,
    review_corr_threshold: float,
) -> dict[str, Any]:
    registry_payload, registry_items = _registry_items(registry_path)
    queue_payload, queue_items = _queue_items(queue_path, start_index=len(registry_items) + 1)
    all_items = registry_items + queue_items
    store = Phase3GSignalVectorStore(dataset_path=dataset_path, runtime_cache_dir=runtime_cache_dir)

    vectors: dict[str, np.ndarray | None] = {}
    vector_meta: dict[str, dict[str, Any]] = {}
    for item in all_items:
        vector, meta = store.vector_for_expression(item["representative_expression"])
        vectors[item["node_id"]] = vector
        vector_meta[item["node_id"]] = {**meta, "vector_norm": round(_norm(vector), 6), "vector_ready": vector is not None}

    pair_rows: list[dict[str, Any]] = []
    high_edges: list[tuple[str, str]] = []
    review_edges: list[tuple[str, str]] = []
    nearest_existing_for_queue: dict[str, tuple[float, str]] = {}
    nearest_any_for_queue: dict[str, tuple[float, str]] = {}
    for i, left in enumerate(all_items):
        for right in all_items[i + 1 :]:
            corr = abs(_corr(vectors[left["node_id"]], vectors[right["node_id"]]))
            if left["node_kind"] == "queued_new" or right["node_kind"] == "queued_new":
                if corr >= review_corr_threshold:
                    pair_rows.append(
                        {
                            "left_node_id": left["node_id"],
                            "left_kind": left["node_kind"],
                            "left_factor_lane": left.get("factor_lane", ""),
                            "right_node_id": right["node_id"],
                            "right_kind": right["node_kind"],
                            "right_factor_lane": right.get("factor_lane", ""),
                            "abs_signal_vector_corr": round(float(corr), 6),
                            "high_corr_duplicate_edge": bool(corr >= high_corr_threshold),
                            "review_corr_edge": bool(corr >= review_corr_threshold),
                        }
                    )
            if corr >= high_corr_threshold:
                high_edges.append((left["node_id"], right["node_id"]))
            if corr >= review_corr_threshold:
                review_edges.append((left["node_id"], right["node_id"]))
            if left["node_kind"] == "queued_new" and right["node_kind"] == "existing_registry":
                nearest_existing_for_queue[left["node_id"]] = max(nearest_existing_for_queue.get(left["node_id"], (0.0, "")), (corr, right["node_id"]))
            if right["node_kind"] == "queued_new" and left["node_kind"] == "existing_registry":
                nearest_existing_for_queue[right["node_id"]] = max(nearest_existing_for_queue.get(right["node_id"], (0.0, "")), (corr, left["node_id"]))
            if left["node_kind"] == "queued_new":
                nearest_any_for_queue[left["node_id"]] = max(nearest_any_for_queue.get(left["node_id"], (0.0, "")), (corr, right["node_id"]))
            if right["node_kind"] == "queued_new":
                nearest_any_for_queue[right["node_id"]] = max(nearest_any_for_queue.get(right["node_id"], (0.0, "")), (corr, left["node_id"]))

    high_components = _components([item["node_id"] for item in all_items], high_edges)
    review_components = _components([item["node_id"] for item in all_items], review_edges)
    high_component_by_node = {node: f"high_component_{idx+1:03d}" for idx, comp in enumerate(high_components) for node in comp}
    review_component_by_node = {node: f"review_component_{idx+1:03d}" for idx, comp in enumerate(review_components) for node in comp}

    integrated_rows: list[dict[str, Any]] = []
    existing_canonicals = {item["canonical_expression"] for item in registry_items}
    for item in all_items:
        nearest_existing = nearest_existing_for_queue.get(item["node_id"], (0.0, "")) if item["node_kind"] == "queued_new" else (0.0, "")
        nearest_any = nearest_any_for_queue.get(item["node_id"], (0.0, "")) if item["node_kind"] == "queued_new" else (0.0, "")
        decision = "existing_registry_kept"
        if item["node_kind"] == "queued_new":
            if item["canonical_expression"] in existing_canonicals:
                decision = "reject_canonical_duplicate"
            elif nearest_existing[0] >= high_corr_threshold:
                decision = "reject_signal_duplicate_existing"
            elif nearest_existing[0] >= review_corr_threshold or nearest_any[0] >= review_corr_threshold:
                decision = "manual_review_required"
            else:
                decision = "accept_candidate_new_signal_cluster"
        integrated_rows.append(
            {
                "registry_entry_id": item["registry_entry_id"],
                "node_kind": item["node_kind"],
                "integration_decision": decision,
                "legacy_cluster_id": item.get("legacy_cluster_id", ""),
                "review_queue_id": item.get("review_queue_id", ""),
                "source_lane": item.get("source_lane", ""),
                "source_generator": item.get("source_generator", ""),
                "factor_lane": item.get("factor_lane", ""),
                "representative_expression": item["representative_expression"],
                "canonical_expression": item["canonical_expression"],
                "signal_vector_id": vector_meta[item["node_id"]].get("signal_vector_id", ""),
                "signal_vector_source": vector_meta[item["node_id"]].get("signal_vector_source", ""),
                "signal_vector_ready": vector_meta[item["node_id"]].get("vector_ready", False),
                "signal_vector_norm": vector_meta[item["node_id"]].get("vector_norm", 0.0),
                "nearest_existing_registry_corr": round(float(nearest_existing[0]), 6),
                "nearest_existing_registry_entry_id": nearest_existing[1],
                "nearest_any_corr": round(float(nearest_any[0]), 6),
                "nearest_any_node_id": nearest_any[1],
                "high_corr_component_id": high_component_by_node.get(item["node_id"], ""),
                "review_corr_component_id": review_component_by_node.get(item["node_id"], ""),
            }
        )

    accepted_new = [row for row in integrated_rows if row["integration_decision"] == "accept_candidate_new_signal_cluster"]
    rejected_or_review = [row for row in integrated_rows if row["node_kind"] == "queued_new" and row["integration_decision"] != "accept_candidate_new_signal_cluster"]
    candidate_registry_rows = []
    for row in integrated_rows:
        if row["node_kind"] == "existing_registry":
            original = next(item["raw_registry_row"] for item in registry_items if item["registry_entry_id"] == row["registry_entry_id"])
            candidate_registry_rows.append(original)
        elif row["integration_decision"] == "accept_candidate_new_signal_cluster":
            candidate_registry_rows.append(
                {
                    "registry_entry_id": row["registry_entry_id"],
                    "legacy_cluster_id": row["legacy_cluster_id"],
                    "registry_source": "cn_underutilized_field_replay128_provisional_new",
                    "representative_expression": row["representative_expression"],
                    "canonical_expression": row["canonical_expression"],
                    "candidate_id": next(item["raw_queue_row"].get("candidate_id", "") for item in queue_items if item["registry_entry_id"] == row["registry_entry_id"]),
                    "first_seen_phase": "CN_UNDERUTILIZED_FIELD_REPLAY128",
                    "source_arm": "underutilized_field_replay_smoke128",
                    "source_seed": "",
                    "source_generator": row["source_generator"],
                    "source_lane": row["source_lane"],
                    "factor_lane": row["factor_lane"],
                    "integration_status": "candidate_new_signal_cluster",
                    "nearest_existing_registry_corr": row["nearest_existing_registry_corr"],
                }
            )

    candidate_registry = {
        "baseline_name": "cn_underutilized_field_candidate_162_registry_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "candidate_registry_not_official_baseline",
        "source_baseline": registry_payload.get("baseline_name", ""),
        "declared_cluster_count": len(candidate_registry_rows),
        "representative_rows": len(candidate_registry_rows),
        "source_counts": {
            **(registry_payload.get("source_counts") or {}),
            "cn_underutilized_field_replay128_candidate_new": len(accepted_new),
        },
        "quality": {
            "missing_representative_expression_count": 0,
            "duplicate_canonical_expression_count": len(candidate_registry_rows) - len({row.get("canonical_expression", "") for row in candidate_registry_rows}),
            "is_candidate_registry": True,
            "requires_official_promotion_record": True,
        },
        "notes": [
            "This candidate registry is generated by signal-vector global integration.",
            "It does not mutate the official 149 discovery baseline.",
            "Promotion requires explicit decision record.",
        ],
        "deployable_representatives": candidate_registry_rows,
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(report_dir / "global_integration_rows.csv", integrated_rows)
    _write_csv(report_dir / "queued_pair_review_edges.csv", pair_rows)
    _write_csv(report_dir / "accepted_new_rows.csv", accepted_new)
    _write_csv(report_dir / "rejected_or_review_rows.csv", rejected_or_review)
    _write_json(output_registry_path, candidate_registry)

    payload = {
        "experiment_id": "cn_underutilized_field_global_cluster_integration_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "PASS_CANDIDATE_BASELINE_162_SIGNAL_INTEGRATION",
        "scope": "global signal-vector integration of frozen 149 registry plus 13 provisional-new underutilized-field representatives",
        "inputs": {
            "registry_path": str(registry_path),
            "queue_path": str(queue_path),
            "dataset_path": str(dataset_path),
            "runtime_cache_dir": str(runtime_cache_dir),
        },
        "thresholds": {
            "high_corr_duplicate_threshold": high_corr_threshold,
            "review_corr_threshold": review_corr_threshold,
        },
        "counts": {
            "existing_registry": len(registry_items),
            "queued_new": len(queue_items),
            "accepted_new_signal_clusters": len(accepted_new),
            "rejected_or_review_queued": len(rejected_or_review),
            "candidate_registry_count": len(candidate_registry_rows),
            "candidate_baseline_if_promoted": len(candidate_registry_rows),
            "queued_edges_ge_review_threshold": len(pair_rows),
            "queued_edges_ge_high_threshold": sum(1 for row in pair_rows if row["high_corr_duplicate_edge"]),
            "zero_vector_count": sum(1 for item in all_items if vector_meta[item["node_id"]].get("vector_norm", 0.0) <= 1e-8),
        },
        "accepted_new_by_source_lane": dict(Counter(row["source_lane"] for row in accepted_new)),
        "accepted_new_by_factor_lane": dict(Counter(row["factor_lane"] for row in accepted_new)),
        "outputs": {
            "candidate_registry": str(output_registry_path),
            "global_integration_rows_csv": str(report_dir / "global_integration_rows.csv"),
            "accepted_new_rows_csv": str(report_dir / "accepted_new_rows.csv"),
            "rejected_or_review_rows_csv": str(report_dir / "rejected_or_review_rows.csv"),
            "queued_pair_review_edges_csv": str(report_dir / "queued_pair_review_edges.csv"),
        },
    }
    _write_json(report_dir / "cn_underutilized_field_global_cluster_integration.json", payload)
    _write_markdown(report_dir / "CN_UNDERUTILIZED_FIELD_GLOBAL_CLUSTER_INTEGRATION_2026-06-01.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Underutilized Field Global Cluster Integration - 2026-06-01",
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
    lines.extend(["", "## Accepted New By Source Lane", ""])
    for key, value in sorted(payload["accepted_new_by_source_lane"].items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Accepted New By Factor Lane", ""])
    for key, value in sorted(payload["accepted_new_by_factor_lane"].items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This creates a candidate 162 registry. It does not overwrite the official 149 baseline.",
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in payload["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--queue-path", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-registry-path", type=Path, default=DEFAULT_OUTPUT_REGISTRY)
    parser.add_argument("--runtime-cache-dir", type=Path, default=DEFAULT_RUNTIME_CACHE)
    parser.add_argument("--high-corr-threshold", type=float, default=0.80)
    parser.add_argument("--review-corr-threshold", type=float, default=0.65)
    args = parser.parse_args()
    payload = run_integration(
        registry_path=args.registry_path,
        queue_path=args.queue_path,
        dataset_path=args.dataset_path,
        report_dir=args.report_dir,
        output_registry_path=args.output_registry_path,
        runtime_cache_dir=args.runtime_cache_dir,
        high_corr_threshold=args.high_corr_threshold,
        review_corr_threshold=args.review_corr_threshold,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
