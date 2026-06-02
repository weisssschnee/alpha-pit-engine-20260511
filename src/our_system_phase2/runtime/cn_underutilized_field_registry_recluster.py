from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.phase3g_signal_vector_store import (
    DEFAULT_PHASE3G_RUNTIME_CACHE_DIR,
    Phase3GSignalVectorStore,
)
from our_system_phase2.services.variation import canonicalize_expression_light


DEFAULT_SURVIVOR_REPS = Path(
    "reports/cn_underutilized_field_survivor_attribution_20260601/deployable_cluster_representatives.csv"
)
DEFAULT_REGISTRY = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_DATASET = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_REPORT_DIR = Path("reports/cn_underutilized_field_registry_recluster_20260601")
DEFAULT_RUNTIME_CACHE = DEFAULT_PHASE3G_RUNTIME_CACHE_DIR / "underutilized_recluster_20260601"


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


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def _registry_rows(path: Path) -> list[dict[str, Any]]:
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(data.get("deployable_representatives") or []):
        if not isinstance(row, dict):
            continue
        expr = _safe_str(row.get("representative_expression") or row.get("canonical_expression") or row.get("expression"))
        if not expr:
            continue
        rows.append(
            {
                "registry_row_index": index,
                "registry_entry_id": _safe_str(row.get("registry_entry_id") or row.get("cluster_id") or f"registry_{index+1:03d}"),
                "legacy_cluster_id": _safe_str(row.get("legacy_cluster_id") or row.get("cluster_id")),
                "registry_source": _safe_str(row.get("registry_source")),
                "registry_source_lane": _safe_str(row.get("source_lane")),
                "registry_expression": expr,
                "registry_canonical": canonicalize_expression_light(expr),
            }
        )
    return rows


def _survivor_rows(path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(path)
    rows: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        expr = _safe_str(row.get("expression"))
        if not expr:
            continue
        rows.append(
            {
                "survivor_row_index": int(index),
                "signal_cluster_id": _safe_str(row.get("signal_cluster_id")),
                "candidate_id": _safe_str(row.get("candidate_id")),
                "source_lane": _safe_str(row.get("source_lane")),
                "source_generator": _safe_str(row.get("source_generator")),
                "factor_lane": _safe_str(row.get("factor_lane")),
                "primary_field_family": _safe_str(row.get("primary_field_family")),
                "expression": expr,
                "survivor_canonical": canonicalize_expression_light(expr),
                "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
                "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
                "deployable_cluster_member_count": row.get("deployable_cluster_member_count"),
            }
        )
    return rows


def _match_tier(max_corr: float, *, high_threshold: float, review_threshold: float) -> str:
    if max_corr >= high_threshold:
        return "known_or_duplicate_signal_cluster"
    if max_corr >= review_threshold:
        return "registry_similarity_review"
    return "provisional_new_signal_space"


def _connected_components(ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {item: set() for item in ids}
    for left, right in edges:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    seen: set[str] = set()
    comps: list[list[str]] = []
    for item in ids:
        if item in seen:
            continue
        queue: deque[str] = deque([item])
        seen.add(item)
        comp: list[str] = []
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            for nxt in sorted(graph.get(cur, set())):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        comps.append(sorted(comp))
    return comps


def run_recluster(
    *,
    survivor_reps_path: Path,
    registry_path: Path,
    dataset_path: Path,
    output_dir: Path,
    runtime_cache_dir: Path,
    high_corr_threshold: float,
    review_corr_threshold: float,
) -> dict[str, Any]:
    survivor_rows = _survivor_rows(survivor_reps_path)
    registry_rows = _registry_rows(registry_path)
    store = Phase3GSignalVectorStore(dataset_path=dataset_path, runtime_cache_dir=runtime_cache_dir)

    registry_vectors: list[dict[str, Any]] = []
    for row in registry_rows:
        vector, meta = store.vector_for_expression(row["registry_expression"])
        registry_vectors.append(
            {
                **row,
                **meta,
                "vector_ready": vector is not None,
                "vector_norm": _norm(vector),
                "vector": vector,
            }
        )

    survivor_vectors: list[dict[str, Any]] = []
    for row in survivor_rows:
        vector, meta = store.vector_for_expression(row["expression"])
        survivor_vectors.append(
            {
                **row,
                **meta,
                "vector_ready": vector is not None,
                "vector_norm": _norm(vector),
                "vector": vector,
            }
        )

    review_rows: list[dict[str, Any]] = []
    top3_rows: list[dict[str, Any]] = []
    for survivor in survivor_vectors:
        vector = survivor.get("vector")
        scored: list[tuple[float, dict[str, Any]]] = []
        if vector is not None:
            for registry in registry_vectors:
                if registry.get("vector") is None:
                    continue
                scored.append((abs(_corr(vector, registry["vector"])), registry))
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:3]
        best_corr = float(top[0][0]) if top else 0.0
        best = top[0][1] if top else {}
        exact = survivor["survivor_canonical"] == _safe_str(best.get("registry_canonical"))
        tier = _match_tier(best_corr, high_threshold=high_corr_threshold, review_threshold=review_corr_threshold)
        review_rows.append(
            {
                "signal_cluster_id": survivor["signal_cluster_id"],
                "candidate_id": survivor["candidate_id"],
                "source_lane": survivor["source_lane"],
                "source_generator": survivor["source_generator"],
                "factor_lane": survivor["factor_lane"],
                "primary_field_family": survivor["primary_field_family"],
                "expression": survivor["expression"],
                "signal_vector_id": survivor.get("signal_vector_id", ""),
                "signal_vector_source": survivor.get("signal_vector_source", ""),
                "signal_vector_ready": bool(survivor.get("vector_ready")),
                "signal_vector_norm": round(float(survivor.get("vector_norm") or 0.0), 6),
                "nearest_registry_entry_id": best.get("registry_entry_id", ""),
                "nearest_legacy_cluster_id": best.get("legacy_cluster_id", ""),
                "nearest_registry_source": best.get("registry_source", ""),
                "nearest_registry_source_lane": best.get("registry_source_lane", ""),
                "nearest_registry_expression": best.get("registry_expression", ""),
                "nearest_registry_vector_norm": round(float(best.get("vector_norm") or 0.0), 6),
                "max_abs_corr_to_149_signal_vector": round(best_corr, 6),
                "mean_top3_abs_corr_to_149_signal_vector": round(float(sum(score for score, _ in top) / len(top)), 6) if top else 0.0,
                "registry_exact_canonical_match": bool(exact),
                "registry_signal_match_tier": tier,
                "strict_mean_one_way_turnover": survivor.get("strict_mean_one_way_turnover"),
                "strict_cost_adjusted_sortino": survivor.get("strict_cost_adjusted_sortino"),
                "deployable_cluster_member_count": survivor.get("deployable_cluster_member_count"),
            }
        )
        for rank, (score, registry) in enumerate(top, start=1):
            top3_rows.append(
                {
                    "signal_cluster_id": survivor["signal_cluster_id"],
                    "candidate_id": survivor["candidate_id"],
                    "rank": rank,
                    "abs_corr": round(float(score), 6),
                    "registry_entry_id": registry.get("registry_entry_id", ""),
                    "legacy_cluster_id": registry.get("legacy_cluster_id", ""),
                    "registry_source": registry.get("registry_source", ""),
                    "registry_source_lane": registry.get("registry_source_lane", ""),
                    "registry_expression": registry.get("registry_expression", ""),
                }
            )

    survivor_pair_rows: list[dict[str, Any]] = []
    survivor_edges: list[tuple[str, str]] = []
    for i, left in enumerate(survivor_vectors):
        for right in survivor_vectors[i + 1 :]:
            corr = abs(_corr(left.get("vector"), right.get("vector")))
            if corr >= review_corr_threshold:
                survivor_pair_rows.append(
                    {
                        "left_signal_cluster_id": left["signal_cluster_id"],
                        "right_signal_cluster_id": right["signal_cluster_id"],
                        "left_factor_lane": left["factor_lane"],
                        "right_factor_lane": right["factor_lane"],
                        "abs_signal_vector_corr": round(float(corr), 6),
                        "collision_threshold_pass": bool(corr >= high_corr_threshold),
                    }
                )
            if corr >= high_corr_threshold:
                survivor_edges.append((left["signal_cluster_id"], right["signal_cluster_id"]))

    components = _connected_components([row["signal_cluster_id"] for row in survivor_rows], survivor_edges)
    component_rows = [
        {
            "component_id": f"component_{idx+1:03d}",
            "member_count": len(component),
            "members": "|".join(component),
            "is_multi_cluster_collision_component": len(component) > 1,
        }
        for idx, component in enumerate(components)
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "recluster_review_rows.csv", review_rows)
    _write_csv(output_dir / "recluster_top3_registry_matches.csv", top3_rows)
    _write_csv(output_dir / "survivor_internal_signal_corr_pairs.csv", survivor_pair_rows)
    _write_csv(output_dir / "survivor_internal_components.csv", component_rows)

    tier_counts = defaultdict(int)
    for row in review_rows:
        tier_counts[str(row["registry_signal_match_tier"])] += 1
    source_tier_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    factor_tier_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in review_rows:
        source_tier_counts[str(row["source_lane"])][str(row["registry_signal_match_tier"])] += 1
        factor_tier_counts[str(row["factor_lane"])][str(row["registry_signal_match_tier"])] += 1

    payload: dict[str, Any] = {
        "experiment_id": "cn_underutilized_field_registry_recluster_20260601",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": "PASS_SIGNAL_VECTOR_REGISTRY_RECLUSTER_AUDIT",
        "scope": "posthoc signal-vector comparison of replay128 deployable survivor representatives vs frozen 149 registry; no selection or replay rerun",
        "inputs": {
            "survivor_reps_path": str(survivor_reps_path),
            "registry_path": str(registry_path),
            "dataset_path": str(dataset_path),
            "runtime_cache_dir": str(runtime_cache_dir),
        },
        "thresholds": {
            "high_corr_duplicate_threshold": high_corr_threshold,
            "review_corr_threshold": review_corr_threshold,
        },
        "counts": {
            "survivor_representatives": len(survivor_rows),
            "survivor_vector_ready": sum(1 for row in survivor_vectors if row.get("vector_ready")),
            "survivor_zero_vector_count": sum(1 for row in survivor_vectors if row.get("vector_ready") and float(row.get("vector_norm") or 0.0) <= 1e-8),
            "registry_rows": len(registry_rows),
            "registry_vector_ready": sum(1 for row in registry_vectors if row.get("vector_ready")),
            "registry_zero_vector_count": sum(1 for row in registry_vectors if row.get("vector_ready") and float(row.get("vector_norm") or 0.0) <= 1e-8),
            "known_or_duplicate_signal_cluster": tier_counts.get("known_or_duplicate_signal_cluster", 0),
            "registry_similarity_review": tier_counts.get("registry_similarity_review", 0),
            "provisional_new_signal_space": tier_counts.get("provisional_new_signal_space", 0),
            "internal_corr_pairs_ge_review_threshold": len(survivor_pair_rows),
            "internal_corr_pairs_ge_high_threshold": len(survivor_edges),
            "internal_multi_cluster_components": sum(1 for row in component_rows if row["is_multi_cluster_collision_component"]),
        },
        "tier_counts_by_source_lane": {key: dict(value) for key, value in sorted(source_tier_counts.items())},
        "tier_counts_by_factor_lane": {key: dict(value) for key, value in sorted(factor_tier_counts.items())},
        "outputs": {
            "review_rows_csv": str(output_dir / "recluster_review_rows.csv"),
            "top3_csv": str(output_dir / "recluster_top3_registry_matches.csv"),
            "internal_pairs_csv": str(output_dir / "survivor_internal_signal_corr_pairs.csv"),
            "internal_components_csv": str(output_dir / "survivor_internal_components.csv"),
        },
    }
    (output_dir / "cn_underutilized_field_registry_recluster.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(output_dir / "CN_UNDERUTILIZED_FIELD_REGISTRY_RECLUSTER_2026-06-01.md", payload, review_rows)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any], review_rows: list[dict[str, Any]]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Underutilized Field Registry Recluster - 2026-06-01",
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
    for key, value in counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `known_or_duplicate_signal_cluster`: survivor is high-correlation to a frozen 149 registry representative.",
            "- `registry_similarity_review`: survivor is not a high-confidence duplicate but is close enough to require review.",
            "- `provisional_new_signal_space`: survivor is not close to the 149 registry under this sampled signal-vector proxy.",
            "",
            "This is still a pre-replay signal-vector proxy audit. It is stronger than symbolic matching, but it is not a new official baseline update by itself.",
            "",
            "## Survivor Review Rows",
            "",
            "| tier | cluster | source_lane | factor_lane | max_corr_to_149 | nearest_registry | expression |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    for row in sorted(review_rows, key=lambda item: (item["registry_signal_match_tier"], -float(item["max_abs_corr_to_149_signal_vector"]))):
        expr = str(row["expression"]).replace("|", "\\|")
        if len(expr) > 90:
            expr = expr[:87] + "..."
        lines.append(
            "| {tier} | {cluster} | {source} | {factor} | {corr:.6f} | {nearest} | `{expr}` |".format(
                tier=row["registry_signal_match_tier"],
                cluster=row["signal_cluster_id"],
                source=row["source_lane"],
                factor=row["factor_lane"],
                corr=float(row["max_abs_corr_to_149_signal_vector"]),
                nearest=row["nearest_registry_entry_id"],
                expr=expr,
            )
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in payload["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--survivor-reps-path", type=Path, default=DEFAULT_SURVIVOR_REPS)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--runtime-cache-dir", type=Path, default=DEFAULT_RUNTIME_CACHE)
    parser.add_argument("--high-corr-threshold", type=float, default=0.80)
    parser.add_argument("--review-corr-threshold", type=float, default=0.65)
    args = parser.parse_args()
    payload = run_recluster(
        survivor_reps_path=args.survivor_reps_path,
        registry_path=args.registry_path,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        runtime_cache_dir=args.runtime_cache_dir,
        high_corr_threshold=args.high_corr_threshold,
        review_corr_threshold=args.review_corr_threshold,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
