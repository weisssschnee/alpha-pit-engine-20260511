from __future__ import annotations

import json
import math
import re
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v3 import candidate_regime_profile
from our_system_phase2.services.search_core_v4 import activation_pattern_novelty, gate_separability_scores, pareto_front
from our_system_phase2.services.search_core_v5 import OBJECTIVE_KEYS


SEARCH_CORE_V7_VERSION = "phase2-search-core-v7-actual-neighborhood-objectives-2026-04-26"


def _read_report(value: Path | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _metric(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


def _nearest_psd(matrix: np.ndarray, jitter: float = 1e-6) -> np.ndarray:
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    return (eigenvectors @ np.diag(np.clip(eigenvalues, jitter, None)) @ eigenvectors.T).astype(float)


def _extract_last_window(expression: str) -> int | None:
    matches = re.findall(r",\s*(\d+)\)", expression)
    if not matches:
        return None
    return int(matches[-1])


def _window_neighborhood(anchor: int, *, minimum: int = 1, maximum: int = 252) -> list[int]:
    windows = {
        anchor - 2,
        anchor - 1,
        anchor,
        anchor + 1,
        anchor + 2,
        int(round(anchor * 1.5)),
    }
    return sorted(window for window in windows if minimum <= window <= maximum)


def _family_expression(family: str, window: int) -> str | None:
    if family == "a5_volatility":
        return f"CSRank(Std($ret,{window}))"
    if family == "a5_momentum":
        return f"CSRank(Mom($close,{window}))"
    if family == "a5_gap":
        return f"CSRank(Div(Sub($open,Delay($close,{window})),Delay($close,{window})))"
    if family == "a5_dev_ma":
        return f"CSRank(Div(Sub($close,Mean($close,{window})),Mean($close,{window})))"
    if family == "a5_amihud":
        return f"Neg(CSRank(Mean(Div(Abs($ret),$amount),{window})))"
    return None


def build_local_formula_neighborhood_ledger(
    *,
    v6_plan: Path | str | dict[str, Any],
    top_family_count: int = 3,
) -> dict[str, Any]:
    plan = _read_report(v6_plan)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in plan.get("correlated_ehi_ranked_candidates", [])[:top_family_count]:
        family = str(candidate.get("primitive_family"))
        anchor = _extract_last_window(str(candidate.get("expression", "")))
        if anchor is None:
            continue
        for window in _window_neighborhood(anchor):
            expression = _family_expression(family, window)
            if expression is None or expression in seen:
                continue
            seen.add(expression)
            records.append(
                {
                    "candidate_id": f"v7-local-{len(records) + 1:04d}",
                    "expression": expression,
                    "retained": True,
                    "source_mode": "search_core_v7_actual_neighborhood_sample",
                    "frontier_lane": "search_core_v7_local_neighborhood",
                    "archive_cell": f"v7_{family}_local",
                    "primitive_family": family,
                    "anchor_candidate_id": candidate.get("candidate_id"),
                    "anchor_expression": candidate.get("expression"),
                    "anchor_window": anchor,
                    "window": window,
                    "direction": "normal" if family != "a5_amihud" else "inverted",
                }
            )
    return {
        "run_id": "phase2-search-core-v7-local-neighborhood-ledger",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V7_VERSION,
        "scope": "local_formula_neighborhood_samples_for_actual_objective_covariance",
        "source_v6_run_id": plan.get("run_id"),
        "top_family_count": top_family_count,
        "record_count": len(records),
        "records": records,
    }


def _profile_to_objective(profile: dict[str, Any], novelty: float, separability: float) -> dict[str, float]:
    edge_strength = max(_metric(profile.get("broad_score")), _metric(profile.get("specialist_score")))
    low_fragility = 1.0 / (1.0 + max(0.0, _metric(profile.get("fragility_score"))))
    return {
        "edge_strength": round(edge_strength, 6),
        "activation_novelty": round(novelty, 6),
        "gate_separability": round(separability, 6),
        "low_fragility": round(low_fragility, 6),
    }


def _objective_matrix(items: list[dict[str, Any]]) -> np.ndarray:
    if not items:
        return np.zeros((0, len(OBJECTIVE_KEYS)), dtype=float)
    return np.vstack(
        [
            np.array([_metric(item["objective_vector"].get(key)) for key in OBJECTIVE_KEYS], dtype=float)
            for item in items
        ]
    )


def build_actual_neighborhood_objective_plan(
    *,
    validation_report: Path | str | dict[str, Any],
    activation_gate_dataset: Path | str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = _read_report(validation_report)
    dataset = _read_report(activation_gate_dataset) if activation_gate_dataset is not None else None
    profiles = [candidate_regime_profile(item) for item in report.get("evaluations", [])]
    active_windows = {
        str(profile.get("candidate_id")): {str(window.get("window")) for window in profile.get("activation_windows", [])}
        for profile in profiles
    }
    novelty = activation_pattern_novelty(active_windows)
    separability = gate_separability_scores(dataset) if dataset is not None else {}
    actual_profiles: list[dict[str, Any]] = []
    for profile in profiles:
        candidate_id = str(profile.get("candidate_id"))
        objective = _profile_to_objective(
            profile,
            novelty.get(candidate_id, 0.0),
            separability.get(candidate_id, {}).get("gate_separability_score", 0.0),
        )
        math_value = round(
            (0.42 * objective["edge_strength"])
            + (0.22 * objective["activation_novelty"])
            + (0.24 * objective["gate_separability"])
            + (0.12 * objective["low_fragility"]),
            6,
        )
        actual_profiles.append(
            {
                "candidate_id": candidate_id,
                "primitive_family": profile.get("primitive_family"),
                "expression": profile.get("expression"),
                "edge_mode": profile.get("edge_mode"),
                "math_search_value": math_value,
                "objective_vector": objective,
                "activation_windows": sorted(active_windows.get(candidate_id, set())),
                "gate_geometry": separability.get(candidate_id, {}),
                "source_profile": profile,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in actual_profiles:
        grouped.setdefault(str(item.get("primitive_family")), []).append(item)

    family_covariance = []
    for family, items in grouped.items():
        matrix = _objective_matrix(items)
        center = matrix.mean(axis=0) if len(matrix) else np.zeros(len(OBJECTIVE_KEYS))
        if len(matrix) > 1:
            covariance = _nearest_psd(np.cov(matrix, rowvar=False))
        else:
            covariance = np.diag(np.full(len(OBJECTIVE_KEYS), 1e-6))
        distances = np.linalg.norm(matrix - center, axis=1) if len(matrix) else np.array([])
        family_covariance.append(
            {
                "primitive_family": family,
                "sample_count": len(items),
                "actual_objective_mean": {key: round(float(value), 6) for key, value in zip(OBJECTIVE_KEYS, center)},
                "actual_objective_covariance": [
                    [round(float(value), 8) for value in row]
                    for row in covariance.tolist()
                ],
                "actual_mutation_radius": round(float(distances.mean()), 6) if len(distances) else 0.0,
                "best_candidate_id": max(items, key=lambda item: item["math_search_value"]).get("candidate_id"),
                "best_math_search_value": round(max(item["math_search_value"] for item in items), 6),
            }
        )
    family_covariance.sort(key=lambda item: (item["best_math_search_value"], item["actual_mutation_radius"]), reverse=True)
    front = pareto_front(actual_profiles)
    return {
        "run_id": "phase2-search-core-v7-actual-neighborhood-objective-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V7_VERSION,
        "scope": "actual_objective_vectors_from_local_formula_neighborhood_validation",
        "validation_report": report.get("ledger_path") or "provided_dict",
        "candidate_count": len(actual_profiles),
        "family_count": len(grouped),
        "pareto_front_count": len(front),
        "actual_objective_profiles": sorted(actual_profiles, key=lambda item: item["math_search_value"], reverse=True),
        "actual_pareto_front": front,
        "family_actual_covariance": family_covariance,
        "next_math_upgrade_candidates": [
            "feed_actual_family_covariance_back_into_v6_correlated_ehi",
            "weight_neighborhood_samples_by_structural_expression_distance",
            "increase_local_samples_around_top_actual_covariance_families",
        ],
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V7_ACTUAL_OBJECTIVE_COVARIANCE",
    }

