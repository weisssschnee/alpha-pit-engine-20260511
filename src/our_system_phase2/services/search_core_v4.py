from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

from our_system_phase2.domain.models import utc_now_iso


SEARCH_CORE_V4_VERSION = "phase2-search-core-v4-pareto-qd-info-geometry-2026-04-26"


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


def _active_windows_from_plan(plan: dict[str, Any]) -> dict[str, set[str]]:
    active: dict[str, set[str]] = {}
    for item in plan.get("activation_map", []):
        candidate_id = str(item.get("candidate_id"))
        active[candidate_id] = {str(window.get("window")) for window in item.get("activation_windows", [])}
    return active


def activation_pattern_novelty(active_windows: dict[str, set[str]]) -> dict[str, float]:
    novelty: dict[str, float] = {}
    for candidate_id, active in active_windows.items():
        similarities = []
        for other_id, other in active_windows.items():
            if other_id == candidate_id:
                continue
            union = active | other
            similarity = (len(active & other) / len(union)) if union else 0.0
            similarities.append(similarity)
        max_similarity = max(similarities, default=0.0)
        novelty[candidate_id] = round(1.0 - max_similarity, 6)
    return novelty


def _rows_by_candidate(dataset: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in dataset.get("rows", []):
        grouped.setdefault(str(row.get("candidate_id")), []).append(row)
    return grouped


def gate_separability_scores(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    feature_columns = [str(column) for column in dataset.get("feature_columns", [])]
    scores: dict[str, dict[str, Any]] = {}
    for candidate_id, rows in _rows_by_candidate(dataset).items():
        active = [row for row in rows if row.get("activated")]
        inactive = [row for row in rows if not row.get("activated")]
        if not active or not inactive or not feature_columns:
            scores[candidate_id] = {
                "gate_separability_score": 0.0,
                "active_count": len(active),
                "inactive_count": len(inactive),
                "feature_z_deltas": {},
            }
            continue
        z_deltas: dict[str, float] = {}
        squared = []
        for column in feature_columns:
            active_values = np.array([_metric(row.get(column), default=np.nan) for row in active], dtype=float)
            inactive_values = np.array([_metric(row.get(column), default=np.nan) for row in inactive], dtype=float)
            active_values = active_values[np.isfinite(active_values)]
            inactive_values = inactive_values[np.isfinite(inactive_values)]
            if active_values.size == 0 or inactive_values.size == 0:
                z_delta = 0.0
            else:
                pooled = np.concatenate([active_values, inactive_values])
                scale = float(np.std(pooled))
                z_delta = 0.0 if scale <= 1e-12 else float((np.mean(active_values) - np.mean(inactive_values)) / scale)
            z_deltas[column] = round(z_delta, 6)
            squared.append(z_delta * z_delta)
        separability = math.sqrt(sum(squared) / len(squared)) if squared else 0.0
        scores[candidate_id] = {
            "gate_separability_score": round(separability, 6),
            "active_count": len(active),
            "inactive_count": len(inactive),
            "feature_z_deltas": z_deltas,
        }
    return scores


def _dominates(left: dict[str, float], right: dict[str, float]) -> bool:
    keys = sorted(set(left) & set(right))
    if not keys:
        return False
    return all(left[key] >= right[key] for key in keys) and any(left[key] > right[key] for key in keys)


def pareto_front(candidates: list[dict[str, Any]], objective_key: str = "objective_vector") -> list[dict[str, Any]]:
    front = []
    for candidate in candidates:
        objective = candidate.get(objective_key, {})
        dominated = False
        for other in candidates:
            if other is candidate:
                continue
            if _dominates(other.get(objective_key, {}), objective):
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    return sorted(front, key=lambda item: item.get("math_search_value", 0.0), reverse=True)


def _softmax_weights(items: list[dict[str, Any]], key: str, temperature: float = 0.18) -> dict[str, float]:
    if not items:
        return {}
    values = np.array([_metric(item.get(key)) for item in items], dtype=float)
    shifted = values - np.max(values)
    scaled = shifted / max(temperature, 1e-6)
    weights = np.exp(scaled)
    denom = float(weights.sum())
    if denom <= 0:
        return {str(item.get("candidate_id")): round(1.0 / len(items), 6) for item in items}
    return {str(item.get("candidate_id")): round(float(weight / denom), 6) for item, weight in zip(items, weights)}


def build_phase2_search_core_v4_plan(
    *,
    v3_plan: Path | str | dict[str, Any],
    activation_gate_dataset: Path | str | dict[str, Any],
) -> dict[str, Any]:
    plan = _read_report(v3_plan)
    dataset = _read_report(activation_gate_dataset)
    active_windows = _active_windows_from_plan(plan)
    novelty = activation_pattern_novelty(active_windows)
    separability = gate_separability_scores(dataset)
    profiles = list(plan.get("candidate_regime_profiles", []))
    enriched: list[dict[str, Any]] = []
    for profile in profiles:
        candidate_id = str(profile.get("candidate_id"))
        broad = _metric(profile.get("broad_score"))
        specialist = _metric(profile.get("specialist_score"))
        edge_strength = max(broad, specialist)
        fragility = _metric(profile.get("fragility_score"))
        novelty_score = novelty.get(candidate_id, 0.0)
        gate_score = separability.get(candidate_id, {}).get("gate_separability_score", 0.0)
        low_fragility = 1.0 / (1.0 + max(0.0, fragility))
        math_value = round(
            (0.42 * edge_strength)
            + (0.22 * novelty_score)
            + (0.24 * _metric(gate_score))
            + (0.12 * low_fragility),
            6,
        )
        enriched.append(
            {
                "candidate_id": candidate_id,
                "primitive_family": profile.get("primitive_family"),
                "expression": profile.get("expression"),
                "edge_mode": profile.get("edge_mode"),
                "math_search_value": math_value,
                "objective_vector": {
                    "edge_strength": round(edge_strength, 6),
                    "activation_novelty": round(novelty_score, 6),
                    "gate_separability": round(_metric(gate_score), 6),
                    "low_fragility": round(low_fragility, 6),
                },
                "broad_score": broad,
                "specialist_score": specialist,
                "fragility_score": fragility,
                "activation_windows": sorted(active_windows.get(candidate_id, set())),
                "gate_geometry": separability.get(candidate_id, {}),
            }
        )
    front = pareto_front(enriched)
    weights = _softmax_weights(front, "math_search_value")
    family_scores: dict[str, list[float]] = {}
    for item in front:
        family_scores.setdefault(str(item.get("primitive_family")), []).append(_metric(item.get("math_search_value")))
    family_allocation = sorted(
        [
            {
                "primitive_family": family,
                "front_member_count": len(values),
                "mean_front_math_search_value": round(mean(values), 6),
                "max_front_math_search_value": round(max(values), 6),
            }
            for family, values in family_scores.items()
        ],
        key=lambda item: (item["max_front_math_search_value"], item["mean_front_math_search_value"]),
        reverse=True,
    )
    return {
        "run_id": "phase2-search-core-v4-pareto-qd-info-geometry-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V4_VERSION,
        "scope": "mathematical_search_objective_pareto_quality_diversity_information_geometry",
        "not_claiming_tradable_alpha": True,
        "mathematical_objectives": [
            "edge_strength_max_of_broad_and_specialist_score",
            "activation_pattern_novelty",
            "gate_separability_in_market_state_space",
            "low_fragility",
        ],
        "candidate_count": len(enriched),
        "pareto_front_count": len(front),
        "pareto_front": front,
        "candidate_math_profiles": sorted(enriched, key=lambda item: item["math_search_value"], reverse=True),
        "expansion_weights": weights,
        "family_allocation": family_allocation,
        "next_math_upgrade_candidates": [
            "replace_scalar_math_search_value_with_bayesian_posterior_over_objective_vectors",
            "learn_activation_gate_and_estimate_conditional_expected_utility",
            "use_kernelized_activation_distance_for_factor_manifold_novelty",
            "run_quality_diversity_archive_over_family_x_regime_cells",
        ],
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V4_MATHEMATICAL_SEARCH",
    }

