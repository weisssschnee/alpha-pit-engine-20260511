from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso


SEARCH_CORE_V5_VERSION = "phase2-search-core-v5-expected-hypervolume-2026-04-26"
OBJECTIVE_KEYS = ("edge_strength", "activation_novelty", "gate_separability", "low_fragility")


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


def _vector(objective: dict[str, Any]) -> np.ndarray:
    return np.array([_metric(objective.get(key)) for key in OBJECTIVE_KEYS], dtype=float)


def _objective_matrix(candidates: list[dict[str, Any]]) -> np.ndarray:
    if not candidates:
        return np.zeros((0, len(OBJECTIVE_KEYS)), dtype=float)
    return np.vstack([_vector(candidate.get("objective_vector", {})) for candidate in candidates])


def _upper_bounds(points: np.ndarray) -> np.ndarray:
    if points.size == 0:
        return np.ones(len(OBJECTIVE_KEYS), dtype=float)
    max_values = np.maximum(points.max(axis=0), 1e-6)
    floors = np.array([0.35, 1.0, 1.0, 1.0], dtype=float)
    return np.maximum(max_values * 1.25, floors)


def _dominated_mask(query_points: np.ndarray, frontier: np.ndarray) -> np.ndarray:
    if frontier.size == 0 or query_points.size == 0:
        return np.zeros(len(query_points), dtype=bool)
    dominates = np.all(frontier[:, None, :] >= query_points[None, :, :], axis=2)
    return np.any(dominates, axis=0)


def monte_carlo_hypervolume(
    frontier_vectors: np.ndarray,
    *,
    reference: np.ndarray | None = None,
    upper: np.ndarray | None = None,
    mc_points: int = 8192,
    seed: int = 1729,
) -> float:
    if reference is None:
        reference = np.zeros(len(OBJECTIVE_KEYS), dtype=float)
    if upper is None:
        upper = _upper_bounds(frontier_vectors)
    rng = np.random.default_rng(seed)
    samples = rng.uniform(reference, upper, size=(mc_points, len(OBJECTIVE_KEYS)))
    dominated = _dominated_mask(samples, frontier_vectors)
    box_volume = float(np.prod(upper - reference))
    return round(box_volume * float(np.mean(dominated)), 8)


def hypervolume_improvement(
    current_frontier: np.ndarray,
    candidate_vector: np.ndarray,
    *,
    upper: np.ndarray | None = None,
    mc_points: int = 8192,
    seed: int = 1729,
) -> float:
    if upper is None:
        upper = _upper_bounds(np.vstack([current_frontier, candidate_vector.reshape(1, -1)]))
    current_hv = monte_carlo_hypervolume(current_frontier, upper=upper, mc_points=mc_points, seed=seed)
    expanded = np.vstack([current_frontier, candidate_vector.reshape(1, -1)])
    expanded_hv = monte_carlo_hypervolume(expanded, upper=upper, mc_points=mc_points, seed=seed)
    return round(max(0.0, expanded_hv - current_hv), 8)


def _posterior_sigma(candidate: dict[str, Any]) -> np.ndarray:
    geometry = candidate.get("gate_geometry") or {}
    active_count = max(1.0, _metric(geometry.get("active_count"), default=1.0))
    fragility = max(0.0, _metric(candidate.get("fragility_score")))
    uncertainty = 1.0 / math.sqrt(active_count + 1.0)
    return np.array(
        [
            0.025 + (0.035 * uncertainty) + (0.020 * fragility),
            0.030 + (0.020 * uncertainty),
            0.090 + (0.260 * uncertainty),
            0.025 + (0.025 * fragility),
        ],
        dtype=float,
    )


def posterior_samples_for_candidate(
    candidate: dict[str, Any],
    *,
    sample_count: int = 256,
    seed: int = 1729,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mean_vector = _vector(candidate.get("objective_vector", {}))
    sigma = _posterior_sigma(candidate)
    samples = rng.normal(mean_vector, sigma, size=(sample_count, len(OBJECTIVE_KEYS)))
    return np.clip(samples, 0.0, None)


def expected_hypervolume_improvement(
    *,
    current_frontier: np.ndarray,
    candidate: dict[str, Any],
    upper: np.ndarray,
    posterior_sample_count: int = 256,
    hv_mc_points: int = 4096,
    seed: int = 1729,
) -> dict[str, Any]:
    samples = posterior_samples_for_candidate(candidate, sample_count=posterior_sample_count, seed=seed)
    improvements = [
        hypervolume_improvement(
            current_frontier,
            sample,
            upper=upper,
            mc_points=hv_mc_points,
            seed=seed,
        )
        for sample in samples
    ]
    positive = [value for value in improvements if value > 0]
    return {
        "candidate_id": candidate.get("candidate_id"),
        "expected_hypervolume_improvement": round(float(mean(improvements)), 8) if improvements else 0.0,
        "positive_improvement_probability": round(len(positive) / len(improvements), 6) if improvements else 0.0,
        "max_sample_hypervolume_improvement": round(max(improvements), 8) if improvements else 0.0,
        "posterior_sigma": {key: round(float(value), 6) for key, value in zip(OBJECTIVE_KEYS, _posterior_sigma(candidate))},
    }


def _softmax_weights(rows: list[dict[str, Any]], key: str, temperature: float = 0.015) -> dict[str, float]:
    if not rows:
        return {}
    values = np.array([_metric(row.get(key)) for row in rows], dtype=float)
    if float(values.max()) <= 0.0:
        return {str(row.get("candidate_id")): round(1.0 / len(rows), 6) for row in rows}
    shifted = values - values.max()
    weights = np.exp(shifted / max(temperature, 1e-9))
    denom = float(weights.sum())
    return {str(row.get("candidate_id")): round(float(weight / denom), 6) for row, weight in zip(rows, weights)}


def build_phase2_search_core_v5_plan(
    *,
    v4_plan: Path | str | dict[str, Any],
    posterior_sample_count: int = 160,
    hv_mc_points: int = 3072,
    seed: int = 1729,
) -> dict[str, Any]:
    plan = _read_report(v4_plan)
    candidates = list(plan.get("candidate_math_profiles", []))
    current_front = _objective_matrix(list(plan.get("pareto_front", [])))
    all_points = _objective_matrix(candidates)
    upper = _upper_bounds(all_points)
    current_hv = monte_carlo_hypervolume(current_front, upper=upper, mc_points=hv_mc_points, seed=seed)
    rows = []
    for index, candidate in enumerate(candidates):
        ehi = expected_hypervolume_improvement(
            current_frontier=current_front,
            candidate=candidate,
            upper=upper,
            posterior_sample_count=posterior_sample_count,
            hv_mc_points=hv_mc_points,
            seed=seed + index,
        )
        objective = candidate.get("objective_vector", {})
        rows.append(
            {
                **ehi,
                "primitive_family": candidate.get("primitive_family"),
                "edge_mode": candidate.get("edge_mode"),
                "expression": candidate.get("expression"),
                "objective_vector": objective,
                "math_search_value": candidate.get("math_search_value"),
            }
        )
    rows.sort(
        key=lambda item: (
            item["expected_hypervolume_improvement"],
            item["positive_improvement_probability"],
            _metric(item.get("math_search_value")),
        ),
        reverse=True,
    )
    weights = _softmax_weights(rows, "expected_hypervolume_improvement")
    family_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family_rows.setdefault(str(row.get("primitive_family")), []).append(row)
    family_allocation = sorted(
        [
            {
                "primitive_family": family,
                "candidate_count": len(items),
                "mean_expected_hypervolume_improvement": round(
                    mean(item["expected_hypervolume_improvement"] for item in items), 8
                ),
                "max_expected_hypervolume_improvement": round(
                    max(item["expected_hypervolume_improvement"] for item in items), 8
                ),
                "expansion_weight": round(sum(weights.get(str(item.get("candidate_id")), 0.0) for item in items), 6),
            }
            for family, items in family_rows.items()
        ],
        key=lambda item: (item["expansion_weight"], item["max_expected_hypervolume_improvement"]),
        reverse=True,
    )
    return {
        "run_id": "phase2-search-core-v5-expected-hypervolume-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V5_VERSION,
        "scope": "bayesian_active_search_expected_hypervolume_improvement",
        "not_claiming_tradable_alpha": True,
        "objective_keys": list(OBJECTIVE_KEYS),
        "posterior_policy": {
            "mean": "current_v4_objective_vector",
            "sigma": "active_window_count_and_fragility_scaled_diagonal_gaussian",
            "posterior_sample_count": posterior_sample_count,
            "hv_mc_points": hv_mc_points,
            "seed": seed,
        },
        "current_frontier_hypervolume": current_hv,
        "upper_bounds": {key: round(float(value), 6) for key, value in zip(OBJECTIVE_KEYS, upper)},
        "candidate_count": len(candidates),
        "ehi_ranked_candidates": rows,
        "expansion_weights": weights,
        "family_allocation": family_allocation,
        "next_math_upgrade_candidates": [
            "replace_diagonal_gaussian_with_correlated_objective_posterior",
            "estimate_objective_uncertainty_from_repeated_formula_neighborhood_samples",
            "use_exact_hypervolume_for_small_fronts_and_mc_only_for_large_fronts",
            "combine_ehi_with_formula_grammar_mutation_radius",
        ],
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V5_EXPECTED_HYPERVOLUME_SEARCH",
    }

