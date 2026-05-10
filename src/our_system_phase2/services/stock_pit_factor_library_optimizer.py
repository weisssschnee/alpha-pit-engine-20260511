from __future__ import annotations

import re
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path
from typing import Any, Iterable

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import read_json_artifact
from our_system_phase2.services.real_market_data import dataset_role_for_path
from our_system_phase2.services.search_memory import expression_memory_key, skeleton_memory_key
from our_system_phase2.services.stock_pit_ledger_policy import stock_pit_terminal_reward_proxy
from our_system_phase2.services.variation import expression_complexity


STOCK_PIT_FACTOR_LIBRARY_OPTIMIZER_VERSION = "phase2-stock-pit-factor-library-optimizer-v1-2026-05-10"
FACTOR_OPERATOR_ALLOWLIST = {
    "Abs",
    "Add",
    "CSRank",
    "CSResidual",
    "Delay",
    "Div",
    "Mean",
    "Mom",
    "Mul",
    "Neg",
    "Sign",
    "Std",
    "Sub",
    "ZScore",
}


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json_artifact(path)
    except (OSError, ValueError):
        return None


def _validation_report_paths_from_root(root: Path) -> list[Path]:
    paths: list[Path] = []
    direct = root / "stage1_validation_report.json"
    summary = root / "stage1_summary.json"
    if direct.exists():
        paths.append(direct)
    elif summary.exists():
        paths.append(summary)

    status = _read_json_if_exists(root / "supervisor_status.json")
    if status:
        completed = status.get("completed", {})
        if isinstance(completed, dict):
            for item in completed.values():
                if not isinstance(item, dict):
                    continue
                output_root = item.get("output_root")
                if not output_root:
                    continue
                worker_root = Path(str(output_root))
                validation_path = worker_root / "stage1_validation_report.json"
                summary_path = worker_root / "stage1_summary.json"
                if validation_path.exists():
                    paths.append(validation_path)
                elif summary_path.exists():
                    paths.append(summary_path)
    return list(dict.fromkeys(paths))


def _dataset_role(payload: dict[str, Any]) -> str | None:
    role = payload.get("dataset_role")
    if role:
        return str(role)
    dataset_path = payload.get("dataset_path")
    if dataset_path:
        return dataset_role_for_path(Path(str(dataset_path)))
    return None


def _evaluation_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("evaluations")
    if isinstance(rows, list):
        return [dict(row) for row in rows if isinstance(row, dict)]
    fallback: list[dict[str, Any]] = []
    for key in ("top_long_only_candidates", "diversified_top_long_only_candidates", "candidates"):
        values = payload.get(key)
        if isinstance(values, list):
            fallback.extend(dict(row) for row in values if isinstance(row, dict))
    return fallback


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _family(row: dict[str, Any]) -> str:
    return str(row.get("research_family") or row.get("primitive_family") or "unknown")


def _expression(row: dict[str, Any]) -> str:
    return str(row.get("expression") or "")


def _fields(expression: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression)}


def _operators(expression: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(", expression)
        if match.group(1) in FACTOR_OPERATOR_ALLOWLIST
    }


def _windows(expression: str) -> set[str]:
    return {
        str(value)
        for value in sorted(
            {
                int(match.group(1))
                for match in re.finditer(r"(?<![A-Za-z0-9_])([1-9][0-9]{0,2})(?![A-Za-z0-9_])", expression)
                if 1 <= int(match.group(1)) <= 252
            }
        )
    }


def _motifs(row: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "primitive_family",
            "research_family",
            "proposal_kind",
            "side_search_role",
            "expression",
            "atom",
            "left_atom",
            "right_atom",
            "interaction_kind",
        )
    ).lower()
    parts = {part for part in re.split(r"[^a-z0-9]+", text) if len(part) >= 3}
    motifs = {
        part
        for part in parts
        if part
        in {
            "amount",
            "close",
            "down",
            "gap",
            "limit",
            "liquidity",
            "momentum",
            "open",
            "position",
            "pressure",
            "rank",
            "residual",
            "slope",
            "stock",
            "surge",
            "trend",
            "turnover",
            "volume",
            "volatility",
            "vwap",
            "zscore",
        }
    }
    if "limit_up" in text:
        motifs.add("limit_up")
    if "limit_down" in text:
        motifs.add("limit_down")
    return motifs


def _cluster_key(row: dict[str, Any]) -> str:
    expression = _expression(row)
    family = _family(row)
    motifs = "_".join(sorted(_motifs(row))[:4]) or "nomotif"
    if expression:
        skeleton = skeleton_memory_key(expression)[:12]
        return f"{family}::{motifs}::{skeleton}"
    return f"{family}::{motifs}"


def _quality_score(row: dict[str, Any]) -> dict[str, Any]:
    reward_report = stock_pit_terminal_reward_proxy(row)
    reward = _float_value(reward_report.get("reward"))
    long_return = _float_value(row.get("mean_window_long_return"))
    long_sortino = _float_value(row.get("mean_window_long_sortino"))
    rank_ic = _float_value(row.get("mean_window_rank_ic"))
    hit_ratio = _float_value(row.get("recent_positive_rank_ic_ratio"), default=0.0)
    tradability_available = bool(row.get("tradability_filter_available", False))
    complexity = expression_complexity(_expression(row)) if _expression(row) else {"operator_count": 0, "char_count": 0}
    quality = (
        reward
        + (0.08 * max(0.0, min(long_sortino, 6.0)))
        + (18.0 * max(0.0, min(long_return, 0.01)))
        + (1.8 * max(0.0, min(rank_ic, 0.12)))
        + (0.08 * max(0.0, hit_ratio - 0.50))
        + (0.04 if tradability_available else -0.10)
        - min(0.20, _float_value(complexity.get("operator_count")) * 0.012)
    )
    return {
        "quality_score": round(float(quality), 6),
        "terminal_reward_proxy": reward_report,
        "quality_components": {
            "long_return": round(long_return, 6),
            "long_sortino": round(long_sortino, 6),
            "rank_ic": round(rank_ic, 6),
            "hit_ratio": round(hit_ratio, 6),
            "tradability_available": tradability_available,
            "operator_count": complexity.get("operator_count"),
        },
    }


def _candidate_brief(row: dict[str, Any], *, quality: dict[str, Any], source_path: str) -> dict[str, Any]:
    expression = _expression(row)
    return {
        "candidate_id": row.get("candidate_id"),
        "expression": expression,
        "expression_key": expression_memory_key(expression) if expression else None,
        "skeleton_key": skeleton_memory_key(expression) if expression else None,
        "primitive_family": row.get("primitive_family"),
        "research_family": row.get("research_family") or row.get("primitive_family"),
        "proposal_kind": row.get("proposal_kind"),
        "cluster_key": _cluster_key(row),
        "fields": sorted(_fields(expression)),
        "operators": sorted(_operators(expression)),
        "windows": sorted(_windows(expression), key=lambda value: int(value)),
        "motifs": sorted(_motifs(row)),
        "mean_window_long_sortino": row.get("mean_window_long_sortino"),
        "mean_window_long_return": row.get("mean_window_long_return"),
        "mean_window_rank_ic": row.get("mean_window_rank_ic"),
        "recent_positive_rank_ic_ratio": row.get("recent_positive_rank_ic_ratio"),
        "tradability_filter_available": row.get("tradability_filter_available"),
        "tradability_ic_excluded_row_count": row.get("tradability_ic_excluded_row_count"),
        "quality_score": quality["quality_score"],
        "quality_components": quality["quality_components"],
        "source_path": source_path,
    }


def load_stock_pit_factor_candidates(
    roots: Iterable[Path | str],
    *,
    expected_dataset_role: str | None = "stock_pit_panel",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    skipped_sources: list[dict[str, Any]] = []
    for root in [Path(item) for item in roots]:
        report_paths = _validation_report_paths_from_root(root)
        if not report_paths:
            skipped_sources.append({"root": str(root), "reason": "no_validation_report_found"})
            continue
        for report_path in report_paths:
            payload = _read_json_if_exists(report_path)
            if payload is None:
                skipped_sources.append({"path": str(report_path), "reason": "validation_report_unreadable"})
                continue
            source_role = _dataset_role(payload)
            if expected_dataset_role is not None and source_role != expected_dataset_role:
                skipped_sources.append(
                    {
                        "path": str(report_path),
                        "reason": "dataset_role_mismatch_or_unscoped",
                        "expected_dataset_role": expected_dataset_role,
                        "source_dataset_role": source_role,
                    }
                )
                continue
            rows = _evaluation_rows(payload)
            for row in rows:
                expression = _expression(row)
                if not expression:
                    continue
                quality = _quality_score(row)
                candidates.append(_candidate_brief(row, quality=quality, source_path=str(report_path)))
            source_reports.append(
                {
                    "path": str(report_path),
                    "dataset_role": source_role,
                    "evaluation_row_count": len(rows),
                }
            )
    return candidates, {
        "source_reports": source_reports,
        "skipped_sources": skipped_sources,
        "candidate_count_before_dedupe": len(candidates),
    }


def _dedupe_by_expression(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for candidate in candidates:
        key = str(candidate.get("expression_key") or candidate.get("expression") or "")
        existing = best.get(key)
        if existing is None or _float_value(candidate.get("quality_score")) > _float_value(existing.get("quality_score")):
            if existing is not None:
                duplicate_count += 1
            best[key] = candidate
        else:
            duplicate_count += 1
    deduped = sorted(best.values(), key=lambda item: _float_value(item.get("quality_score")), reverse=True)
    return deduped, {
        "candidate_count_after_expression_dedupe": len(deduped),
        "duplicate_expression_count": duplicate_count,
    }


def _structural_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_tokens = (
        set(left.get("fields") or [])
        | set(left.get("operators") or [])
        | set(left.get("motifs") or [])
        | {str(left.get("primitive_family") or "")}
    )
    right_tokens = (
        set(right.get("fields") or [])
        | set(right.get("operators") or [])
        | set(right.get("motifs") or [])
        | {str(right.get("primitive_family") or "")}
    )
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    skeleton_bonus = 0.20 if left.get("skeleton_key") == right.get("skeleton_key") else 0.0
    family_bonus = 0.15 if left.get("primitive_family") == right.get("primitive_family") else 0.0
    return min(1.0, (overlap / union) + skeleton_bonus + family_bonus)


def _select_representatives(
    candidates: list[dict[str, Any]],
    *,
    max_factors: int,
    max_per_family: int,
    max_per_cluster: int,
    similarity_threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    cluster_counts: Counter[str] = Counter()
    skipped_family_cap = 0
    skipped_cluster_cap = 0
    skipped_similarity = 0
    for candidate in candidates:
        family = str(candidate.get("primitive_family") or "unknown")
        cluster = str(candidate.get("cluster_key") or "unknown")
        if family_counts[family] >= max(1, int(max_per_family)):
            skipped_family_cap += 1
            continue
        if cluster_counts[cluster] >= max(1, int(max_per_cluster)):
            skipped_cluster_cap += 1
            continue
        if any(_structural_similarity(candidate, kept) >= similarity_threshold for kept in selected):
            skipped_similarity += 1
            continue
        selected.append(candidate)
        family_counts[family] += 1
        cluster_counts[cluster] += 1
        if len(selected) >= max(1, int(max_factors)):
            break
    return selected, {
        "selected_count": len(selected),
        "skipped_family_cap": skipped_family_cap,
        "skipped_cluster_cap": skipped_cluster_cap,
        "skipped_structural_similarity": skipped_similarity,
        "family_counts": dict(family_counts),
        "cluster_counts": dict(cluster_counts),
    }


def _apply_group_cap(weights: dict[str, float], factors: list[dict[str, Any]], *, key: str, cap: float) -> dict[str, float]:
    if not weights or cap <= 0:
        return weights
    grouped: dict[str, list[str]] = defaultdict(list)
    id_by_expr = {str(item["expression_key"]): item for item in factors}
    for expression_key in weights:
        item = id_by_expr[expression_key]
        grouped[str(item.get(key) or "unknown")].append(expression_key)
    capped = dict(weights)
    for _ in range(4):
        changed = False
        for group_keys in grouped.values():
            total = sum(capped.get(item, 0.0) for item in group_keys)
            if total <= cap or total <= 0:
                continue
            scale = cap / total
            for item in group_keys:
                capped[item] *= scale
            changed = True
        total_weight = sum(capped.values())
        if total_weight > 0:
            capped = {item: value / total_weight for item, value in capped.items()}
        if not changed:
            break
    return capped


def _factor_weights(
    selected: list[dict[str, Any]],
    *,
    shrinkage: float,
    max_family_weight: float,
    max_cluster_weight: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not selected:
        return [], {"method": "nonnegative_quality_shrinkage", "selected_count": 0}
    floor = min(_float_value(item.get("quality_score")) for item in selected)
    shifted = {
        str(item["expression_key"]): max(0.0, _float_value(item.get("quality_score")) - floor + 0.05)
        for item in selected
    }
    if sum(shifted.values()) <= 0:
        shifted = {str(item["expression_key"]): 1.0 for item in selected}
    total = sum(shifted.values())
    raw = {item: value / total for item, value in shifted.items()}
    raw = _apply_group_cap(raw, selected, key="primitive_family", cap=max_family_weight)
    raw = _apply_group_cap(raw, selected, key="cluster_key", cap=max_cluster_weight)
    equal = 1.0 / len(selected)
    blend = max(0.0, min(1.0, float(shrinkage)))
    weights = {
        key: ((1.0 - blend) * value) + (blend * equal)
        for key, value in raw.items()
    }
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {key: value / total_weight for key, value in weights.items()}
    weighted: list[dict[str, Any]] = []
    for item in selected:
        row = dict(item)
        row["optimizer_weight"] = round(float(weights[str(item["expression_key"])]), 8)
        weighted.append(row)
    family_weights: Counter[str] = Counter()
    cluster_weights: Counter[str] = Counter()
    for row in weighted:
        family_weights[str(row.get("primitive_family") or "unknown")] += float(row["optimizer_weight"])
        cluster_weights[str(row.get("cluster_key") or "unknown")] += float(row["optimizer_weight"])
    return weighted, {
        "method": "nonnegative_quality_shrinkage_with_family_and_cluster_caps",
        "shrinkage_to_equal_weight": round(blend, 6),
        "max_family_weight": round(float(max_family_weight), 6),
        "max_cluster_weight": round(float(max_cluster_weight), 6),
        "weight_sum": round(sum(float(row["optimizer_weight"]) for row in weighted), 8),
        "effective_factor_count": round(
            1.0 / max(1e-12, sum(float(row["optimizer_weight"]) ** 2 for row in weighted)),
            6,
        ),
        "family_weights": [
            {"family": family, "weight": round(weight, 8)}
            for family, weight in family_weights.most_common()
        ],
        "cluster_weights": [
            {"cluster_key": cluster, "weight": round(weight, 8)}
            for cluster, weight in cluster_weights.most_common(20)
        ],
    }


def _conflict_report(selected: list[dict[str, Any]], *, threshold: float = 0.55) -> dict[str, Any]:
    conflicts: list[dict[str, Any]] = []
    for left_index, left in enumerate(selected):
        for right in selected[left_index + 1 :]:
            similarity = _structural_similarity(left, right)
            if similarity >= threshold:
                conflicts.append(
                    {
                        "left_candidate_id": left.get("candidate_id"),
                        "right_candidate_id": right.get("candidate_id"),
                        "similarity": round(similarity, 6),
                        "left_family": left.get("primitive_family"),
                        "right_family": right.get("primitive_family"),
                    }
                )
    conflicts.sort(key=lambda item: item["similarity"], reverse=True)
    return {
        "similarity_metric": "structural_jaccard_plus_skeleton_family_bonus_not_signal_return_correlation",
        "threshold": threshold,
        "conflict_count": len(conflicts),
        "top_conflicts": conflicts[:20],
        "average_pair_similarity": round(
            sum(
                _structural_similarity(left, right)
                for left_index, left in enumerate(selected)
                for right in selected[left_index + 1 :]
            )
            / max(1, (len(selected) * (len(selected) - 1)) // 2),
            6,
        ),
    }


def build_stock_pit_factor_library_optimizer_report(
    roots: Iterable[Path | str],
    *,
    expected_dataset_role: str | None = "stock_pit_panel",
    max_factors: int = 32,
    max_per_family: int = 3,
    max_per_cluster: int = 1,
    similarity_threshold: float = 0.78,
    shrinkage: float = 0.35,
    max_family_weight: float = 0.25,
    max_cluster_weight: float = 0.18,
    min_quality_score: float | None = None,
) -> dict[str, Any]:
    candidates, load_report = load_stock_pit_factor_candidates(
        roots,
        expected_dataset_role=expected_dataset_role,
    )
    deduped, dedupe_report = _dedupe_by_expression(candidates)
    if min_quality_score is not None:
        deduped = [item for item in deduped if _float_value(item.get("quality_score")) >= float(min_quality_score)]
    selected, selection_report = _select_representatives(
        deduped,
        max_factors=max_factors,
        max_per_family=max_per_family,
        max_per_cluster=max_per_cluster,
        similarity_threshold=similarity_threshold,
    )
    weighted, weight_report = _factor_weights(
        selected,
        shrinkage=shrinkage,
        max_family_weight=max_family_weight,
        max_cluster_weight=max_cluster_weight,
    )
    score_values = [_float_value(item.get("quality_score")) for item in weighted]
    return {
        "created_at": utc_now_iso(),
        "optimizer_version": STOCK_PIT_FACTOR_LIBRARY_OPTIMIZER_VERSION,
        "scope": "stock_pit_factor_library_selection_and_nonnegative_rank_ensemble_weighting",
        "expected_dataset_role": expected_dataset_role,
        "roots": [str(root) for root in roots],
        "commercial_ready": False,
        "commercial_readiness_decision": "RESEARCH_LIBRARY_ONLY",
        "does_not_claim_live_edge": True,
        "method_contract": {
            "uses_markowitz": False,
            "uses_expected_return_mvo": False,
            "reason": "factor_return_means_are_too_noisy_for_first_pass; use shrinkage and caps before full walk-forward optimizer",
            "uses_signal_return_correlation": False,
            "correlation_proxy": "structural_similarity_until_factor_return_panel_is_materialized",
            "long_only_factor_weights": True,
            "nonnegative_weights": True,
        },
        "load_report": load_report,
        "dedupe_report": dedupe_report,
        "filter_report": {
            "min_quality_score": min_quality_score,
            "candidate_count_after_quality_filter": len(deduped),
        },
        "selection_report": selection_report,
        "weight_report": weight_report,
        "conflict_report": _conflict_report(weighted),
        "library_quality_summary": {
            "selected_count": len(weighted),
            "mean_quality_score": round(sum(score_values) / len(score_values), 6) if score_values else None,
            "top_quality_score": round(max(score_values), 6) if score_values else None,
            "quality_score_std": round(
                sqrt(sum((value - (sum(score_values) / len(score_values))) ** 2 for value in score_values) / len(score_values)),
                6,
            )
            if score_values
            else None,
        },
        "selected_factors": weighted,
    }
