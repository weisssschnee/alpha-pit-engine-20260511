from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.search_core_v4 import pareto_front
from our_system_phase2.services.search_core_v5 import (
    OBJECTIVE_KEYS,
    _objective_matrix,
    _posterior_sigma,
    _softmax_weights,
    _upper_bounds,
    hypervolume_improvement,
    monte_carlo_hypervolume,
)


SEARCH_CORE_V6_VERSION = "phase2-search-core-v6-correlated-neighborhood-posterior-2026-04-26"


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


def _clip(value: float, lower: float = 0.0, upper: float = 2.0) -> float:
    return max(lower, min(upper, value))


def fast_screen_proxy_objective(record: dict[str, Any]) -> np.ndarray:
    recent_ic = max(0.0, _metric(record.get("recent_mean_rank_ic")))
    mean_ic = max(0.0, _metric(record.get("mean_window_rank_ic")))
    positive_ratio = _clip(_metric(record.get("recent_positive_rank_ic_ratio"), default=0.5), 0.0, 1.0)
    sortino = _clip(_metric(record.get("recent_mean_sortino")), -2.0, 2.0)
    cost = max(0.0, _metric(record.get("estimated_validation_cost_score")))
    validation_cost_penalty = 1.0 / (1.0 + (cost / 20.0))
    return np.array(
        [
            max(recent_ic, mean_ic),
            positive_ratio,
            max(0.0, sortino + 1.0) / 2.0,
            positive_ratio * validation_cost_penalty,
        ],
        dtype=float,
    )


def _nearest_psd(matrix: np.ndarray, jitter: float = 1e-5) -> np.ndarray:
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, jitter, None)
    return (eigenvectors @ np.diag(clipped) @ eigenvectors.T).astype(float)


def family_neighborhood_statistics(fast_screen_report: Path | str | dict[str, Any]) -> dict[str, dict[str, Any]]:
    report = _read_report(fast_screen_report)
    grouped: dict[str, list[np.ndarray]] = {}
    for record in report.get("evaluations", []):
        family = str(record.get("primitive_family") or "unknown")
        grouped.setdefault(family, []).append(fast_screen_proxy_objective(record))

    stats: dict[str, dict[str, Any]] = {}
    for family, vectors in grouped.items():
        matrix = np.vstack(vectors)
        center = matrix.mean(axis=0)
        if len(vectors) > 1:
            covariance = np.cov(matrix, rowvar=False)
        else:
            covariance = np.diag(np.full(len(OBJECTIVE_KEYS), 0.0025))
        covariance = _nearest_psd(covariance)
        distances = np.linalg.norm(matrix - center, axis=1)
        mutation_radius = float(distances.mean()) if len(distances) else 0.0
        stats[family] = {
            "family": family,
            "sample_count": len(vectors),
            "proxy_mean": {key: round(float(value), 6) for key, value in zip(OBJECTIVE_KEYS, center)},
            "proxy_covariance": covariance.tolist(),
            "proxy_correlation": np.corrcoef(matrix, rowvar=False).tolist() if len(vectors) > 1 else np.eye(len(OBJECTIVE_KEYS)).tolist(),
            "mutation_radius": round(mutation_radius, 6),
            "mean_pairwise_radius": round(float(np.mean(distances)), 6) if len(distances) else 0.0,
        }
    return stats


def _blend_covariance(candidate: dict[str, Any], neighborhood: dict[str, Any] | None) -> np.ndarray:
    diagonal = np.diag(np.square(_posterior_sigma(candidate)))
    if not neighborhood:
        return diagonal
    proxy_covariance = np.array(neighborhood.get("proxy_covariance", diagonal), dtype=float)
    if proxy_covariance.shape != diagonal.shape:
        return diagonal
    scale = np.trace(diagonal) / max(float(np.trace(proxy_covariance)), 1e-8)
    scaled_proxy = proxy_covariance * scale
    return _nearest_psd((0.45 * diagonal) + (0.55 * scaled_proxy))


def correlated_posterior_samples(
    candidate: dict[str, Any],
    neighborhood: dict[str, Any] | None,
    *,
    sample_count: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    mean_vector = np.array([_metric(candidate.get("objective_vector", {}).get(key)) for key in OBJECTIVE_KEYS], dtype=float)
    covariance = _blend_covariance(candidate, neighborhood)
    samples = rng.multivariate_normal(mean_vector, covariance, size=sample_count)
    return np.clip(samples, 0.0, None)


def _expected_correlated_ehi(
    *,
    current_frontier: np.ndarray,
    candidate: dict[str, Any],
    neighborhood: dict[str, Any] | None,
    upper: np.ndarray,
    posterior_sample_count: int,
    hv_mc_points: int,
    seed: int,
) -> dict[str, Any]:
    samples = correlated_posterior_samples(candidate, neighborhood, sample_count=posterior_sample_count, seed=seed)
    improvements = [
        hypervolume_improvement(current_frontier, sample, upper=upper, mc_points=hv_mc_points, seed=seed)
        for sample in samples
    ]
    positive = [value for value in improvements if value > 0]
    covariance = _blend_covariance(candidate, neighborhood)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "correlated_expected_hypervolume_improvement": round(float(mean(improvements)), 8) if improvements else 0.0,
        "positive_improvement_probability": round(len(positive) / len(improvements), 6) if improvements else 0.0,
        "max_sample_hypervolume_improvement": round(max(improvements), 8) if improvements else 0.0,
        "posterior_covariance": [
            [round(float(value), 8) for value in row]
            for row in covariance.tolist()
        ],
    }


def build_phase2_search_core_v6_plan(
    *,
    v5_plan: Path | str | dict[str, Any],
    fast_screen_report: Path | str | dict[str, Any],
    posterior_sample_count: int = 160,
    hv_mc_points: int = 3072,
    seed: int = 1729,
) -> dict[str, Any]:
    plan = _read_report(v5_plan)
    candidates = list(plan.get("ehi_ranked_candidates", []))
    current_front = _objective_matrix(pareto_front(candidates))
    all_points = _objective_matrix(candidates)
    upper = _upper_bounds(all_points)
    current_hv = monte_carlo_hypervolume(current_front, upper=upper, mc_points=hv_mc_points, seed=seed)
    neighborhood_stats = family_neighborhood_statistics(fast_screen_report)
    max_radius = max((item["mutation_radius"] for item in neighborhood_stats.values()), default=1.0) or 1.0

    rows = []
    for index, candidate in enumerate(candidates):
        family = str(candidate.get("primitive_family") or "unknown")
        neighborhood = neighborhood_stats.get(family)
        ehi = _expected_correlated_ehi(
            current_frontier=current_front,
            candidate=candidate,
            neighborhood=neighborhood,
            upper=upper,
            posterior_sample_count=posterior_sample_count,
            hv_mc_points=hv_mc_points,
            seed=seed + index,
        )
        radius = float(neighborhood.get("mutation_radius", 0.0)) if neighborhood else 0.0
        normalized_radius = radius / max_radius
        radius_adjusted = ehi["correlated_expected_hypervolume_improvement"] * (1.0 + (0.35 * normalized_radius))
        rows.append(
            {
                **ehi,
                "primitive_family": family,
                "edge_mode": candidate.get("edge_mode"),
                "expression": candidate.get("expression"),
                "objective_vector": candidate.get("objective_vector"),
                "math_search_value": candidate.get("math_search_value"),
                "mutation_radius": round(radius, 6),
                "normalized_mutation_radius": round(normalized_radius, 6),
                "radius_adjusted_expected_hypervolume_improvement": round(radius_adjusted, 8),
                "neighborhood_sample_count": neighborhood.get("sample_count", 0) if neighborhood else 0,
            }
        )
    rows.sort(
        key=lambda item: (
            item["radius_adjusted_expected_hypervolume_improvement"],
            item["correlated_expected_hypervolume_improvement"],
            item["positive_improvement_probability"],
        ),
        reverse=True,
    )
    weights = _softmax_weights(rows, "radius_adjusted_expected_hypervolume_improvement")
    family_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        family_rows.setdefault(str(row.get("primitive_family")), []).append(row)
    family_allocation = sorted(
        [
            {
                "primitive_family": family,
                "candidate_count": len(items),
                "max_radius_adjusted_ehi": round(max(item["radius_adjusted_expected_hypervolume_improvement"] for item in items), 8),
                "mean_correlated_ehi": round(mean(item["correlated_expected_hypervolume_improvement"] for item in items), 8),
                "expansion_weight": round(sum(weights.get(str(item.get("candidate_id")), 0.0) for item in items), 6),
                "neighborhood_sample_count": max(item["neighborhood_sample_count"] for item in items),
                "mutation_radius": max(item["mutation_radius"] for item in items),
            }
            for family, items in family_rows.items()
        ],
        key=lambda item: (item["expansion_weight"], item["max_radius_adjusted_ehi"]),
        reverse=True,
    )
    return {
        "run_id": "phase2-search-core-v6-correlated-neighborhood-posterior-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V6_VERSION,
        "scope": "correlated_objective_posterior_from_formula_neighborhood_samples",
        "not_claiming_tradable_alpha": True,
        "objective_keys": list(OBJECTIVE_KEYS),
        "posterior_policy": {
            "mean": "v5_candidate_objective_vector",
            "covariance": "blend_of_v5_diagonal_uncertainty_and_fast_screen_family_neighborhood_proxy_covariance",
            "radius_adjustment": "mutation_radius_from_family_proxy_objective_dispersion",
            "posterior_sample_count": posterior_sample_count,
            "hv_mc_points": hv_mc_points,
            "seed": seed,
        },
        "current_frontier_hypervolume": current_hv,
        "candidate_count": len(candidates),
        "neighborhood_family_count": len(neighborhood_stats),
        "correlated_ehi_ranked_candidates": rows,
        "expansion_weights": weights,
        "family_allocation": family_allocation,
        "neighborhood_statistics": neighborhood_stats,
        "next_math_upgrade_candidates": [
            "learn_neighborhood_covariance_from_full_history_samples_not_only_fast_screen_proxy",
            "use_structural_expression_distance_to_weight_neighborhood_samples",
            "model_objective_posterior_as_mixture_by_edge_mode",
            "connect_radius_adjusted_ehi_to_actual_mutation_operator_selection",
        ],
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V6_CORRELATED_POSTERIOR_SEARCH",
    }

