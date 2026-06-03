"""Signal-vector novelty audit for integrated factor candidates.

This is a no-search, no-replay audit. It compares candidate pre-replay signal
vectors against a frozen representative registry. It does not read replay
labels for selection and does not claim final replay-cluster novelty.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore


VERSION = "cn-integrated-factor-pack-signal-novelty-audit-v1-2026-06-03"
DEFAULT_REGISTRY_149 = Path("reports/phase3k_c_complete_149_registry_20260517/phase3k_c_149_representatives.csv")
DEFAULT_ROWS = Path(
    "runtime/cn_integrated_factor_pack_v2_coverage_aware_fresh_pool_replay_s36_20260603/"
    "attribution/stratified_replay_rows.csv"
)
DEFAULT_OUTPUT_ROOT = Path("reports/cn_integrated_factor_pack_v2_signal_novelty_audit_20260603")


def _canonical(expression: str) -> str:
    return re.sub(r"\s+", "", expression or "")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "1.0", "true", "yes", "y", "pass"}


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _corr(left: np.ndarray | None, right: np.ndarray | None) -> float:
    if left is None or right is None or left.shape != right.shape or left.size == 0:
        return 0.0
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not math.isfinite(denom) or denom <= 1e-12:
        return 0.0
    value = float(np.dot(left, right) / denom)
    return value if math.isfinite(value) else 0.0


def _deployable_proxy(row: dict[str, Any], *, turnover_max: float) -> bool:
    raw = _as_bool(row.get("portfolio_replay_pass"))
    cost = _as_bool(row.get("cost_survives"))
    turnover = _safe_float(row.get("portfolio_replay_avg_one_way_turnover"), None)
    if turnover is None:
        turnover = _safe_float(row.get("strict_mean_one_way_turnover"), 999.0) or 999.0
    return raw and cost and turnover <= turnover_max


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows-csv", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--registry-csv", type=Path, default=DEFAULT_REGISTRY_149)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--runtime-cache-dir", type=Path, default=Path("runtime/phase3g_signal_vectors/runtime_eval_cache_integrated_v2_novelty_149"))
    parser.add_argument("--sample-size", type=int, default=3000)
    parser.add_argument("--recent-quarter-window-count", type=int, default=1)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--corr-threshold", type=float, default=0.80)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    registry_rows = _read_csv(args.registry_csv)
    candidate_rows = _read_csv(args.rows_csv)
    registry_by_exact = {
        _canonical(row.get("representative_expression", "")): row
        for row in registry_rows
        if _canonical(row.get("representative_expression", ""))
    }

    store = Phase3GSignalVectorStore(
        dataset_path=args.dataset_path,
        sample_size=max(1, int(args.sample_size)),
        recent_quarter_window_count=max(1, int(args.recent_quarter_window_count)),
        recent_warmup_days=max(1, int(args.recent_warmup_days)),
        corr_threshold=float(args.corr_threshold),
        runtime_cache_dir=args.runtime_cache_dir,
    )

    registry_vectors: list[dict[str, Any]] = []
    registry_errors: list[dict[str, Any]] = []
    for row in registry_rows:
        expression = str(row.get("representative_expression") or "")
        vector, meta = store.vector_for_expression(expression)
        item = {
            "registry_entry_id": row.get("registry_entry_id"),
            "legacy_cluster_id": row.get("legacy_cluster_id"),
            "registry_source": row.get("registry_source"),
            "expression": expression,
            **meta,
        }
        if vector is None:
            registry_errors.append(item)
            continue
        registry_vectors.append({**item, "vector": vector})

    audit_rows: list[dict[str, Any]] = []
    deployable_signal_new = 0
    deployable_signal_duplicate = 0
    deployable_exact_duplicate = 0
    deployable_proxy_count = 0
    for row in candidate_rows:
        expression = str(row.get("expression") or "")
        canonical = _canonical(expression)
        deployable = _deployable_proxy(row, turnover_max=float(args.turnover_max))
        if deployable:
            deployable_proxy_count += 1
        vector, meta = store.vector_for_expression(expression)
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        if vector is not None and registry_vectors:
            for registry in registry_vectors:
                score = abs(_corr(vector, registry["vector"]))
                if score > best[0]:
                    best = (score, registry)
        exact_hit = registry_by_exact.get(canonical)
        signal_duplicate = bool(best[0] >= float(args.corr_threshold))
        if deployable:
            if exact_hit:
                deployable_exact_duplicate += 1
            if signal_duplicate:
                deployable_signal_duplicate += 1
            else:
                deployable_signal_new += 1
        nearest = best[1] or {}
        audit_rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "factor_lane": row.get("factor_lane"),
                "expression": expression,
                "portfolio_replay_pass": row.get("portfolio_replay_pass"),
                "cost_survives": row.get("cost_survives"),
                "portfolio_replay_avg_one_way_turnover": row.get("portfolio_replay_avg_one_way_turnover"),
                "deployable_proxy": deployable,
                "exact_seen_in_149_registry": bool(exact_hit),
                "nearest_exact_registry_entry_id": exact_hit.get("registry_entry_id") if exact_hit else "",
                "signal_vector_ready": vector is not None,
                **meta,
                "nearest_149_registry_entry_id": nearest.get("registry_entry_id", ""),
                "nearest_149_legacy_cluster_id": nearest.get("legacy_cluster_id", ""),
                "nearest_149_registry_source": nearest.get("registry_source", ""),
                "max_corr_to_149_signal_vector": round(float(best[0]), 6),
                "signal_duplicate_vs_149_proxy": signal_duplicate,
                "signal_new_vs_149_proxy": not signal_duplicate,
            }
        )

    summary = {
        "created_at": utc_now_iso(),
        "version": VERSION,
        "decision": "PASS_SIGNAL_VECTOR_NOVELTY_PROXY" if deployable_signal_new > 0 else "HOLD_NO_SIGNAL_VECTOR_NOVELTY_PROXY",
        "scope": "sampled pre-replay signal vector nearest-149 proxy; not final replay global recluster",
        "rows_csv": str(args.rows_csv),
        "registry_csv": str(args.registry_csv),
        "dataset_path": str(args.dataset_path),
        "sample_size": int(args.sample_size),
        "recent_quarter_window_count": int(args.recent_quarter_window_count),
        "recent_warmup_days": int(args.recent_warmup_days),
        "corr_threshold": float(args.corr_threshold),
        "registry_rows": len(registry_rows),
        "registry_vector_ready": len(registry_vectors),
        "registry_vector_errors": len(registry_errors),
        "candidate_rows": len(candidate_rows),
        "candidate_vector_ready": sum(1 for row in audit_rows if row["signal_vector_ready"]),
        "deployable_proxy_count": deployable_proxy_count,
        "deployable_exact_duplicate_vs_149": deployable_exact_duplicate,
        "deployable_signal_duplicate_vs_149_proxy": deployable_signal_duplicate,
        "deployable_signal_new_vs_149_proxy": deployable_signal_new,
    }
    write_json_artifact(output_root / "signal_novelty_summary.json", summary)
    _write_csv(output_root / "signal_novelty_rows.csv", audit_rows)
    _write_csv(output_root / "registry_vector_errors.csv", registry_errors)
    markdown = [
        "# CN Integrated Factor Pack V2 Signal Novelty Audit",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "| metric | value |",
        "| --- | ---: |",
        f"| registry rows | {summary['registry_rows']} |",
        f"| registry vector ready | {summary['registry_vector_ready']} |",
        f"| candidate rows | {summary['candidate_rows']} |",
        f"| candidate vector ready | {summary['candidate_vector_ready']} |",
        f"| deployable proxy count | {summary['deployable_proxy_count']} |",
        f"| deployable signal-new vs 149 proxy | {summary['deployable_signal_new_vs_149_proxy']} |",
        f"| deployable signal-duplicate vs 149 proxy | {summary['deployable_signal_duplicate_vs_149_proxy']} |",
        "",
        "This is a sampled pre-replay signal-vector proxy, not final replay-cluster novelty.",
    ]
    (output_root / "CN_INTEGRATED_FACTOR_PACK_V2_SIGNAL_NOVELTY_AUDIT.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
