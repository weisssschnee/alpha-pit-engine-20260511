"""Selector-only placebo audit for Phase3H/G2 signal-vector linkage.

This audit checks whether the G2 queue materially depends on the pre-replay
signal vectors. It does not run replay and does not use replay/deployable
labels. A selector that still produces nearly the same queue under randomized
vectors is not actually being controlled by the signal-vector representation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3e_selectors import (
    Phase3ERegistryContext,
    select_phase3e_queue,
    strip_forbidden_replay_label_rows,
    write_selector_artifacts,
)
from our_system_phase2.services.phase3g_signal_vector_store import (
    DEFAULT_PHASE3G_SIGNAL_CORR_THRESHOLD,
    Phase3GSignalVectorStore,
    _corr,
    expression_vector_id,
)
from our_system_phase2.services.stock_pit_phase3_repair import (
    PHASE3_ABLATION_ARMS,
    _ablation_budgets,
    _selector_baseline_path,
)


PHASE3H_PLACEBO_AUDIT_VERSION = "phase3h-g2-placebo-audit-v1-2026-05-15"
DEFAULT_PHASE3G_VECTOR_NPZ = Path("runtime/phase3g_signal_vectors/phase3g_signal_vectors_20260514.npz")
DEFAULT_PHASE3G_VECTOR_METADATA = Path("runtime/phase3g_signal_vectors/vector_metadata.parquet")
DEFAULT_MODES = ["real", "random_expression", "random_registry", "random_all"]
H1_ARM = "Phase3H_H1_G2_signal_vector_control"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _stable_seed(*parts: Any) -> int:
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return int(digest, 16) % (2**32 - 1)


def _normalize(values: np.ndarray) -> np.ndarray:
    arr = values.astype(np.float32, copy=False)
    denom = float(np.linalg.norm(arr))
    if not np.isfinite(denom) or denom <= 1e-12:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr / denom).astype(np.float32)


def _random_vector(dim: int, *parts: Any) -> np.ndarray:
    rng = np.random.default_rng(_stable_seed(*parts))
    return _normalize(rng.standard_normal(max(1, int(dim))).astype(np.float32))


def _retag_rows(rows: list[dict[str, Any]], arm: str = H1_ARM) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        item = dict(row)
        item["ablation_arm"] = arm
        output.append(item)
    return output


@dataclass
class PlaceboSignalVectorStore:
    """Wrap Phase3GSignalVectorStore with deterministic randomized vector modes."""

    base: Phase3GSignalVectorStore
    mode: str
    seed: str

    def __post_init__(self) -> None:
        self.corr_threshold = float(getattr(self.base, "corr_threshold", DEFAULT_PHASE3G_SIGNAL_CORR_THRESHOLD))
        base_vectors = list(getattr(self.base, "_registry_vectors", []) or [])
        base_clusters = list(getattr(self.base, "_registry_cluster_ids", []) or [])
        dim = int(base_vectors[0].shape[0]) if base_vectors else 1
        self._dim = dim
        if self.mode in {"random_registry", "random_all"}:
            self._registry_vectors = [
                _random_vector(dim, "registry", self.mode, self.seed, index) for index, _ in enumerate(base_vectors)
            ]
        else:
            self._registry_vectors = base_vectors
        self._registry_cluster_ids = base_clusters
        self._candidate_cache: dict[str, np.ndarray] = {}

    def coverage_ready(self) -> bool:
        return bool(self._registry_vectors)

    def vector_for_expression(self, expression: str) -> tuple[np.ndarray | None, dict[str, Any]]:
        vector_id = expression_vector_id(expression)
        if self.mode in {"random_expression", "random_all"}:
            if vector_id not in self._candidate_cache:
                self._candidate_cache[vector_id] = _random_vector(self._dim, "candidate", self.mode, self.seed, vector_id)
            return self._candidate_cache[vector_id], {
                "signal_vector_id": vector_id,
                "signal_vector_source": f"placebo_{self.mode}",
                "signal_vector_error": "",
            }
        vector, meta = self.base.vector_for_expression(expression)
        if vector is None:
            return vector, meta
        return vector, {
            **meta,
            "signal_vector_source": f"placebo_{self.mode}_candidate_real",
        }

    def registry_similarity(self, expression: str) -> dict[str, Any]:
        vector, meta = self.vector_for_expression(expression)
        if vector is None or not self._registry_vectors:
            return {
                **meta,
                "nearest_134_signal_cluster_id": "",
                "max_corr_to_134_signal_vector": 0.0,
                "mean_topk_corr_to_134_signal_vector": 0.0,
                "known_signal_cluster_id": "",
                "signal_vector_ready": False,
            }
        scores = [abs(_corr(vector, registry_vector)) for registry_vector in self._registry_vectors]
        best_index = int(np.argmax(scores)) if scores else -1
        best = float(scores[best_index]) if best_index >= 0 else 0.0
        top = sorted(scores, reverse=True)[: min(5, len(scores))]
        nearest = self._registry_cluster_ids[best_index] if best_index >= 0 and self._registry_cluster_ids else ""
        return {
            **meta,
            "nearest_134_signal_cluster_id": nearest,
            "max_corr_to_134_signal_vector": round(best, 6),
            "mean_topk_corr_to_134_signal_vector": round(float(sum(top) / len(top)), 6) if top else 0.0,
            "known_signal_cluster_id": nearest if best >= self.corr_threshold else "",
            "signal_vector_ready": True,
        }

    def selected_similarity(self, expression: str, selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
        vector, meta = self.vector_for_expression(expression)
        if vector is None or not selected_rows:
            return {
                **meta,
                "max_corr_to_selected_queue_signal": 0.0,
                "mean_corr_to_selected_queue_signal": 0.0,
                "nearest_selected_signal_cluster_id": "",
                "nearest_selected_signal_vector_id": "",
            }
        scores: list[tuple[float, dict[str, Any]]] = []
        for selected in selected_rows:
            selected_vector, selected_meta = self.vector_for_expression(str(selected.get("expression") or ""))
            if selected_vector is None:
                continue
            scores.append((abs(_corr(vector, selected_vector)), {**selected, **selected_meta}))
        if not scores:
            return {
                **meta,
                "max_corr_to_selected_queue_signal": 0.0,
                "mean_corr_to_selected_queue_signal": 0.0,
                "nearest_selected_signal_cluster_id": "",
                "nearest_selected_signal_vector_id": "",
            }
        scores.sort(key=lambda item: item[0], reverse=True)
        top_values = [item[0] for item in scores[: min(5, len(scores))]]
        nearest_row = scores[0][1]
        nearest_cluster = str(
            nearest_row.get("known_signal_cluster_id")
            or nearest_row.get("provisional_signal_cluster_id")
            or nearest_row.get("signal_vector_id")
            or ""
        )
        return {
            **meta,
            "max_corr_to_selected_queue_signal": round(float(scores[0][0]), 6),
            "mean_corr_to_selected_queue_signal": round(float(sum(top_values) / len(top_values)), 6),
            "nearest_selected_signal_cluster_id": nearest_cluster if float(scores[0][0]) >= self.corr_threshold else "",
            "nearest_selected_signal_vector_id": str(nearest_row.get("signal_vector_id") or ""),
        }

    def feature_bundle(self, expression: str, selected_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        selected_rows = selected_rows or []
        registry = self.registry_similarity(expression)
        selected = self.selected_similarity(expression, selected_rows)
        known = str(registry.get("known_signal_cluster_id") or "")
        selected_cluster = str(selected.get("nearest_selected_signal_cluster_id") or "")
        vector_id = str(registry.get("signal_vector_id") or selected.get("signal_vector_id") or expression_vector_id(expression))
        provisional = known or selected_cluster or f"sigprov_{vector_id[:12]}"
        return {
            **registry,
            **selected,
            "known_signal_cluster_id": known,
            "provisional_signal_cluster_id": provisional,
            "signal_vector_cluster_basis": "known_134" if known else ("selected_queue" if selected_cluster else "self_vector"),
        }


def _selected_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys = set()
    for row in rows:
        key = str(row.get("candidate_id") or row.get("expr_hash") or row.get("normalized_expression") or row.get("expression") or "")
        if key:
            keys.add(key)
    return keys


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _mode_metrics(mode: str, selected: list[dict[str, Any]], audit_rows: list[dict[str, Any]], real_keys: set[str] | None) -> dict[str, Any]:
    selected_audit = [row for row in audit_rows if _truthy(row.get("selected_for_audit"))]
    keys = _selected_keys(selected)
    overlap = None
    if real_keys is not None:
        overlap = len(keys & real_keys) / max(1, len(keys | real_keys))
    known_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    signal_sources: dict[str, int] = {}
    selected_corrs: list[float] = []
    registry_corrs: list[float] = []
    turnovers: list[float] = []
    for row in selected_audit:
        known = str(row.get("known_signal_cluster_id") or "")
        source_lane = str(row.get("source_lane") or "")
        vector_source = str(row.get("signal_vector_source") or "")
        if known:
            known_counts[known] = known_counts.get(known, 0) + 1
        if source_lane:
            source_counts[source_lane] = source_counts.get(source_lane, 0) + 1
        if vector_source:
            signal_sources[vector_source] = signal_sources.get(vector_source, 0) + 1
        try:
            selected_corrs.append(float(row.get("max_corr_to_selected_queue_signal") or 0.0))
            registry_corrs.append(float(row.get("max_corr_to_134_signal_vector") or 0.0))
            turnovers.append(float(row.get("turnover_proxy") or 0.0))
        except (TypeError, ValueError):
            continue
    return {
        "mode": mode,
        "selected_count": len(selected),
        "selector_selected_rows": len(selected_audit),
        "overlap_with_real_jaccard": round(float(overlap), 6) if overlap is not None else None,
        "known_signal_cluster_counts_top10": dict(sorted(known_counts.items(), key=lambda item: item[1], reverse=True)[:10]),
        "source_lane_counts": dict(sorted(source_counts.items())),
        "signal_vector_sources": dict(sorted(signal_sources.items())),
        "mean_selected_queue_corr": round(float(np.mean(selected_corrs)), 6) if selected_corrs else 0.0,
        "median_selected_queue_corr": round(float(np.median(selected_corrs)), 6) if selected_corrs else 0.0,
        "mean_registry_corr": round(float(np.mean(registry_corrs)), 6) if registry_corrs else 0.0,
        "median_registry_corr": round(float(np.median(registry_corrs)), 6) if registry_corrs else 0.0,
        "median_turnover_proxy": round(float(np.median(turnovers)), 6) if turnovers else 0.0,
    }


def _run_mode(
    *,
    pool: dict[str, Any],
    seed: int,
    mode: str,
    base_store: Phase3GSignalVectorStore,
    output_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    arm_config = dict(PHASE3_ABLATION_ARMS[H1_ARM])
    selector_profile = str(arm_config.get("selector_profile") or "signal_vector_diversified_proxy")
    strict_audit_budget = int(pool.get("strict_audit_budget") or 64)
    budgets = _ablation_budgets(strict_audit_budget, H1_ARM)
    candidate_pool = _retag_rows(strip_forbidden_replay_label_rows(list(pool.get("candidate_pool") or [])))
    default_selected = _retag_rows(strip_forbidden_replay_label_rows(list(pool.get("default_selected") or [])))
    context = Phase3ERegistryContext.from_path(_selector_baseline_path(H1_ARM, arm_config))
    signal_store: Any = base_store if mode == "real" else PlaceboSignalVectorStore(base_store, mode=mode, seed=str(seed))
    selected, audit_rows, preflight = select_phase3e_queue(
        candidate_pool,
        budgets=budgets,
        selector_profile=selector_profile,
        context=context,
        seed=f"{seed}::{mode}",
        default_selected=default_selected,
        total_budget=strict_audit_budget,
        signal_vector_store=signal_store,
    )
    mode_root = output_root / f"s{seed}" / mode
    write_selector_artifacts(mode_root, audit_rows=audit_rows, preflight=preflight, selector_profile=selector_profile)
    write_json_artifact(
        mode_root / "phase3_strict_selection_inputs.json",
        {
            "selected": selected,
            "ablation_arm": H1_ARM,
            "selector_profile": selector_profile,
            "mode": mode,
            "strict_audit_budget": strict_audit_budget,
        },
    )
    return selected, audit_rows, preflight


def _decision(seed_reports: list[dict[str, Any]]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    for seed_report in seed_reports:
        seed = seed_report["seed"]
        real = seed_report["modes"].get("real", {})
        if real.get("selected_count") != 64:
            blockers.append(f"seed{seed}:real_selected_count_not_64")
        for mode, metrics in seed_report["modes"].items():
            if mode == "real":
                continue
            overlap = float(metrics.get("overlap_with_real_jaccard") or 0.0)
            if overlap >= 0.95:
                blockers.append(f"seed{seed}:{mode}_overlap_ge_0p95")
            elif overlap >= 0.85:
                warnings.append(f"seed{seed}:{mode}_overlap_ge_0p85")
            if metrics.get("selected_count") != 64:
                blockers.append(f"seed{seed}:{mode}_selected_count_not_64")
    if blockers:
        return "FAIL_PLACEBO_SELECTOR_GATE", sorted(set(blockers + warnings))
    if warnings:
        return "HOLD_PLACEBO_SELECTOR_GATE_REPLAY_RECOMMENDED", sorted(set(warnings))
    return "PASS_PLACEBO_SELECTOR_BEHAVIOR_GATE", []


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3H G2 Placebo Selector Audit",
        "",
        f"- created_at: {payload['created_at']}",
        f"- experiment_id: {payload['experiment_id']}",
        f"- run_root: `{payload['run_root']}`",
        f"- decision: **{payload['decision']}**",
        "",
        "## Scope",
        "",
        "- Checked: whether H1/G2 selector queues depend on signal-vector representation.",
        "- Not checked: replay pass degradation under placebo; this is selector-only.",
        "",
        "## Summary",
        "",
        "| seed | mode | selected | overlap_real | median_turnover | mean_sel_corr | median_registry_corr |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for seed_report in payload["seed_reports"]:
        for mode, metrics in seed_report["modes"].items():
            lines.append(
                f"| {seed_report['seed']} | {mode} | {metrics['selected_count']} | "
                f"{metrics.get('overlap_with_real_jaccard')} | {metrics['median_turnover_proxy']} | "
                f"{metrics['mean_selected_queue_corr']} | {metrics['median_registry_corr']} |"
            )
    lines.extend(
        [
            "",
            "## Decision Items",
            "",
        ]
    )
    for item in payload.get("decision_items") or []:
        lines.append(f"- {item}")
    if not payload.get("decision_items"):
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- PASS here means the selector queue is vector-dependent under randomized-vector placebo.",
            "- It does not prove alpha performance degrades under placebo; a replay placebo smoke is the next gate if needed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seeds", nargs="*", type=int, default=[33, 34, 35, 36])
    parser.add_argument("--modes", nargs="*", default=DEFAULT_MODES)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--vector-npz", type=Path, default=DEFAULT_PHASE3G_VECTOR_NPZ)
    parser.add_argument("--vector-metadata", type=Path, default=DEFAULT_PHASE3G_VECTOR_METADATA)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    seed_reports: list[dict[str, Any]] = []
    for seed in args.seeds:
        pool_path = args.run_root / f"s{seed}" / "shared_candidate_pool.json"
        if not pool_path.exists():
            raise FileNotFoundError(f"missing shared candidate pool for seed {seed}: {pool_path}")
        pool = _read_json(pool_path)
        pool["dataset_path"] = str(args.dataset_path)
        base_store = Phase3GSignalVectorStore(
            dataset_path=args.dataset_path,
            vector_npz=args.vector_npz,
            metadata_path=args.vector_metadata,
        )
        mode_outputs: dict[str, dict[str, Any]] = {}
        real_keys: set[str] | None = None
        for mode in args.modes:
            selected, audit_rows, _preflight = _run_mode(
                pool=pool,
                seed=seed,
                mode=mode,
                base_store=base_store,
                output_root=args.output_root,
            )
            metrics = _mode_metrics(mode, selected, audit_rows, real_keys)
            if mode == "real":
                real_keys = _selected_keys(selected)
                metrics = _mode_metrics(mode, selected, audit_rows, None)
            mode_outputs[mode] = metrics
        seed_reports.append({"seed": seed, "pool": str(pool_path), "modes": mode_outputs})

    decision, decision_items = _decision(seed_reports)
    payload = {
        "version": PHASE3H_PLACEBO_AUDIT_VERSION,
        "created_at": utc_now_iso(),
        "experiment_id": "phase3h_g2_placebo_selector_audit_20260515",
        "run_root": str(args.run_root),
        "output_root": str(args.output_root),
        "dataset_path": str(args.dataset_path),
        "vector_npz": str(args.vector_npz),
        "vector_metadata": str(args.vector_metadata),
        "modes": args.modes,
        "seeds": args.seeds,
        "decision": decision,
        "decision_items": decision_items,
        "seed_reports": seed_reports,
        "reproducibility": {
            "mode": "selector_only",
            "replay_run": False,
            "official_results_mutated": False,
            "commands": "python -m our_system_phase2.runtime.phase3h_g2_placebo_audit --run-root ...",
        },
    }
    write_json_artifact(args.output_root / "phase3h_g2_placebo_audit.json", payload)
    _write_markdown(args.output_root / "PHASE3H_G2_PLACEBO_AUDIT_2026-05-15.md", payload)
    print(json.dumps({"decision": decision, "decision_items": decision_items, "output_root": str(args.output_root)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
