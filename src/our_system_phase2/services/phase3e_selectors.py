from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore
from our_system_phase2.services.phase3g_vector_selector import (
    PHASE3G_VECTOR_SELECTOR_VERSION,
    is_signal_vector_selector,
    score_signal_vector_selector,
    signal_vector_book_marginal_mode,
)
from our_system_phase2.services.search_core_v8 import rank_validation_canonical_expression
from our_system_phase2.services.variation import extract_structural_skeleton


PHASE3E_SELECTOR_VERSION = "phase3e-phase3g-selectors-v3-2026-05-14"

FORBIDDEN_REPLAY_LABEL_FIELDS = {
    "portfolio_replay_pass",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_avg_one_way_turnover",
    "cost_survives",
    "signal_cluster_id",
    "global_signal_cluster_id",
    "deployable",
    "strict_cost_adjusted_sortino",
    "strict_mean_rank_ic",
    "strict_mean_one_way_turnover",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _stable_noise(*parts: Any) -> float:
    text = "|".join(str(part) for part in parts)
    # deterministic [0, 1) without importing hashlib in hot selector code
    value = 0
    for char in text[:256]:
        value = (value * 131 + ord(char)) % 1_000_003
    return value / 1_000_003.0


def _fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or "")))


def _operators(expression: str) -> list[str]:
    return re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression or "")


def _windows(expression: str) -> list[int]:
    values = set()
    for token in re.findall(r",\s*(\d+)\s*\)", expression or ""):
        values.add(int(token))
    return sorted(value for value in values if value > 0)


def complexity_score(expression: str) -> float:
    return round(len(_operators(expression)) + 0.75 * len(_fields(expression)) + 0.25 * len(_windows(expression)) + 0.15 * expression.count("("), 6)


def turnover_structure_risk(expression: str) -> float:
    """Pre-replay formula-level turnover risk heuristic.

    Cheap turnover columns understate realized replay turnover for some Phase3G
    candidates. This feature only uses expression structure, so it is safe for
    selector-time use.
    """

    expr = expression or ""
    risk = 0.0
    risk += 1.20 * len(re.findall(r"Mom\([^,]+,\s*(?:1|2)\s*\)", expr))
    risk += 0.65 * len(re.findall(r"Delta\([^,]+,\s*1\s*\)", expr))
    risk += 0.45 * len(re.findall(r"Sign\([^)]*Delta\([^,]+,\s*1\s*\)", expr))
    risk += 0.55 * len(re.findall(r"Sub\(\s*Delta\([^,]+,\s*1\s*\)\s*,\s*Delay\(\s*Delta\([^,]+,\s*1\s*\)", expr))
    risk += 0.40 * len(re.findall(r"Mean\(Abs\(\$ret\),\s*(?:1|2|3|4|5)\s*\)", expr))
    risk += 0.35 * len(re.findall(r"Mean\(Abs\(Delta\([^,]+,\s*1\s*\)\),\s*(?:1|2|3|4|5|6|7|8)\s*\)", expr))
    risk += 0.30 * len(re.findall(r"Corr\([^)]*,\s*(?:2|3|4|5|6|7|8)\s*\)", expr))
    if re.search(r"Delta\(\$(?:final_)?(?:float_)?(?:total_)?market_cap,\s*1\s*\)", expr):
        risk += 0.60
    if re.search(r"Delta\(\$(?:amount|volume|turnover),\s*1\s*\)", expr):
        risk += 0.35
    if re.search(r"Delta\(\$(?:open|high|low),\s*1\s*\)", expr):
        risk += 0.30
    if re.search(r"CSResidual\(.*Mean\(Abs\(\$ret\),\s*(?:1|2|3)\s*\)", expr):
        risk += 0.45
    return round(min(4.0, risk), 6)


def _field_group(field: str) -> str:
    low = field.lower()
    if any(token in low for token in ("open", "high", "low", "close", "vwap", "ret", "return")):
        return "price"
    if any(token in low for token in ("amount", "volume", "turnover", "money", "amt")):
        return "flow"
    if "cap" in low or "market" in low:
        return "cap"
    if "limit" in low:
        return "limit"
    if "trend" in low or "regime" in low or "sector" in low or "industry" in low:
        return "state"
    return "other"


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _canonical(expression: str) -> str:
    return rank_validation_canonical_expression(expression or "")


def _stable_id(text: str, length: int = 12) -> str:
    value = 0
    for char in text[:512]:
        value = (value * 131 + ord(char)) % 4_294_967_291
    return f"{value:08x}"[:length]


def _row_key(row: dict[str, Any]) -> str:
    expression = str(row.get("expression") or "")
    candidate_id = str(row.get("candidate_id") or "")
    return _canonical(expression) or candidate_id


def _window_bucket(expression: str) -> str:
    windows = _windows(expression)
    if not windows:
        return "w_none"
    largest = max(windows)
    if largest <= 5:
        return "w_micro"
    if largest <= 20:
        return "w_short"
    if largest <= 60:
        return "w_medium"
    return "w_long"


def _provisional_cluster_id(expression: str) -> str:
    fields = "|".join(sorted({_field_group(field) for field in _fields(expression)}))
    operators = "|".join(sorted(set(_operators(expression))))
    skeleton = extract_structural_skeleton(expression)
    payload = f"{fields}::{operators}::{_window_bucket(expression)}::{skeleton}"
    return f"prov_{_stable_id(payload)}"


def _selected_queue_similarity(expression: str, selected_rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not selected_rows:
        return 0.0, 0.0
    canonical = _canonical(expression)
    skeleton = extract_structural_skeleton(expression)
    field_groups = {_field_group(field) for field in _fields(expression)}
    operators = set(_operators(expression))
    scores = []
    for selected in selected_rows:
        selected_expression = str(selected.get("expression") or "")
        if not selected_expression:
            continue
        exact = 1.0 if canonical == _canonical(selected_expression) else 0.0
        ast = 1.0 if skeleton == extract_structural_skeleton(selected_expression) else 0.0
        field_overlap = _jaccard(field_groups, {_field_group(field) for field in _fields(selected_expression)})
        operator_overlap = _jaccard(operators, set(_operators(selected_expression)))
        scores.append(max(exact, 0.55 * ast + 0.20 * field_overlap + 0.25 * operator_overlap))
    if not scores:
        return 0.0, 0.0
    top = sorted(scores, reverse=True)[: min(5, len(scores))]
    return round(max(scores), 6), round(sum(top) / len(top), 6)


def _first_number(row: dict[str, Any], keys: list[str]) -> tuple[float | None, str | None]:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        number = _safe_float(value, default=float("nan"))
        if math.isfinite(number):
            return number, key
    return None, None


def _percentile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    position = (len(clean) - 1) * q
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return clean[low]
    weight = position - low
    return clean[low] * (1.0 - weight) + clean[high] * weight


def operator_pathology_flag(row: dict[str, Any]) -> bool:
    expression = str(row.get("expression") or "")
    reasons = str(row.get("source_failure_reasons") or row.get("all_reasons") or "")
    if "operator_pathology" in reasons:
        return True
    if bool(row.get("operator_pathology")):
        return True
    if "Div(" in expression and "Add(Abs(" not in expression:
        return True
    if expression.count("Corr(") > 1:
        return True
    if re.search(r"Mul\(\s*\$[A-Za-z_][A-Za-z0-9_]*\s*,\s*Mul\(\s*\$[A-Za-z_]", expression):
        return True
    return False


@dataclass(frozen=True)
class RegistryThresholds:
    turnover_p90: float | None
    complexity_p90: float | None
    cost_adjusted_p10: float | None
    factor_exposure_p90: float | None
    sector_concentration_p90: float | None


class Phase3ERegistryContext:
    def __init__(self, registry_rows: list[dict[str, Any]], *, baseline_name: str = "phase3D_cumulative_103") -> None:
        self.registry_rows = registry_rows
        self.baseline_name = baseline_name
        self.proxy_rows = []
        turnovers = []
        complexities = []
        cost_scores = []
        for row in registry_rows:
            expression = str(row.get("representative_expression") or "")
            if not expression:
                continue
            turnover = _safe_float(row.get("median_turnover"), default=float("nan"))
            if math.isfinite(turnover):
                turnovers.append(turnover)
            complexity = complexity_score(expression)
            complexities.append(complexity)
            cost_score = _safe_float(row.get("cost_adjusted_score"), default=float("nan"))
            if math.isfinite(cost_score):
                cost_scores.append(cost_score)
            self.proxy_rows.append(
                {
                    "cluster_id": row.get("cluster_id"),
                    "expression": expression,
                    "canonical": _canonical(expression),
                    "skeleton": extract_structural_skeleton(expression),
                    "field_groups": {_field_group(field) for field in _fields(expression)},
                    "operators": set(_operators(expression)),
                }
            )
        self.thresholds = RegistryThresholds(
            turnover_p90=_percentile(turnovers, 0.90),
            complexity_p90=_percentile(complexities, 0.90),
            cost_adjusted_p10=_percentile(cost_scores, 0.10),
            factor_exposure_p90=None,
            sector_concentration_p90=None,
        )

    @classmethod
    def from_path(cls, path: Path | str) -> "Phase3ERegistryContext":
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        rows = data.get("cluster_registry") or data.get("deployable_representatives") or []
        if not isinstance(rows, list):
            raise TypeError("Phase3E registry baseline must contain a list")
        return cls(rows, baseline_name=str(data.get("baseline_name") or "phase3D_cumulative_103"))

    def similarity_proxy(self, expression: str) -> dict[str, Any]:
        canonical = _canonical(expression)
        skeleton = extract_structural_skeleton(expression)
        field_groups = {_field_group(field) for field in _fields(expression)}
        operators = set(_operators(expression))
        best = {
            "max_corr_to_103_registry": 0.0,
            "mean_corr_to_103_registry": 0.0,
            "max_ast_similarity_to_103": 0.0,
            "field_family_overlap_to_103": 0.0,
            "operator_family_overlap_to_103": 0.0,
            "nearest_103_cluster": None,
        }
        scores = []
        for baseline in self.proxy_rows:
            exact = 1.0 if canonical == baseline["canonical"] else 0.0
            ast = 1.0 if skeleton == baseline["skeleton"] else 0.0
            field_overlap = _jaccard(field_groups, baseline["field_groups"])
            operator_overlap = _jaccard(operators, baseline["operators"])
            proxy = max(exact, 0.55 * ast + 0.20 * field_overlap + 0.25 * operator_overlap)
            scores.append(float(proxy))
            if proxy > float(best["max_corr_to_103_registry"]):
                best = {
                    "max_corr_to_103_registry": round(float(proxy), 6),
                    "mean_corr_to_103_registry": 0.0,
                    "max_ast_similarity_to_103": round(float(ast), 6),
                    "field_family_overlap_to_103": round(float(field_overlap), 6),
                    "operator_family_overlap_to_103": round(float(operator_overlap), 6),
                    "nearest_103_cluster": baseline["cluster_id"],
                }
        if scores:
            top = sorted(scores, reverse=True)[: min(5, len(scores))]
            best["mean_corr_to_103_registry"] = round(sum(top) / len(top), 6)
        return best


def _source_lane(row: dict[str, Any]) -> str:
    return str(row.get("phase3_budget_bucket") or row.get("proof_variant") or "unknown")


def feature_row(
    row: dict[str, Any],
    context: Phase3ERegistryContext,
    *,
    selected_rows: list[dict[str, Any]] | None = None,
    signal_vector_store: Phase3GSignalVectorStore | None = None,
) -> dict[str, Any]:
    expression = str(row.get("expression") or "")
    similarity = context.similarity_proxy(expression)
    selected_rows = selected_rows or []
    selected_similarity, selected_mean_similarity = _selected_queue_similarity(expression, selected_rows)
    turnover, turnover_source = _first_number(
        row,
        [
            "mean_window_one_way_turnover",
            "cheap_backtest_turnover",
            "mean_one_way_turnover",
            "mean_window_long_selected_turnover_rate",
        ],
    )
    cost_adjusted, cost_source = _first_number(
        row,
        [
            "cost_adjusted_proxy",
            "cheap_backtest_fitness",
            "fast_reward",
            "mean_window_long_sortino",
            "mean_window_sortino",
            "mean_window_rank_ic",
        ],
    )
    factor_exposure, factor_source = _first_number(row, ["factor_exposure_proxy", "factor_exposure", "beta_exposure"])
    sector_concentration, sector_source = _first_number(row, ["sector_concentration_proxy", "sector_exposure"])
    complexity = complexity_score(expression)
    structure_turnover_risk = turnover_structure_risk(expression)
    base_quality = cost_adjusted if cost_adjusted is not None else _safe_float(row.get("fast_reward"), default=0.0)
    pathology = operator_pathology_flag(row)
    max_registry_corr = float(similarity["max_corr_to_103_registry"])
    nearest_registry_cluster = str(similarity["nearest_103_cluster"] or "")
    known_cluster_id = nearest_registry_cluster if max_registry_corr >= 0.90 else ""
    provisional_cluster_id = _provisional_cluster_id(expression)
    source_lane = _source_lane(row)
    source_lane_cluster_id = f"{source_lane}|{known_cluster_id or provisional_cluster_id}"
    missing = []
    if turnover is None:
        missing.append("turnover_proxy")
    if cost_adjusted is None:
        missing.append("cost_adjusted_proxy")
    if factor_exposure is None:
        missing.append("factor_exposure_proxy")
    if sector_concentration is None:
        missing.append("sector_concentration_proxy")
    signal_features: dict[str, Any] = {
        "signal_vector_id": "",
        "signal_vector_source": "",
        "signal_vector_error": "",
        "signal_vector_ready": False,
        "nearest_134_signal_cluster_id": "",
        "max_corr_to_134_signal_vector": 0.0,
        "mean_topk_corr_to_134_signal_vector": 0.0,
        "novelty_vs_134_signal_vector": 0.0,
        "known_signal_cluster_id": "",
        "provisional_signal_cluster_id": "",
        "source_lane_signal_cluster_id": f"{source_lane}|",
        "signal_vector_cluster_basis": "",
        "max_corr_to_selected_queue_signal": 0.0,
        "mean_corr_to_selected_queue_signal": 0.0,
        "nearest_selected_signal_cluster_id": "",
        "nearest_selected_signal_vector_id": "",
    }
    if signal_vector_store is not None:
        bundle = signal_vector_store.feature_bundle(expression, selected_rows)
        max_signal_corr = _safe_float(bundle.get("max_corr_to_134_signal_vector"), default=0.0)
        known_signal = str(bundle.get("known_signal_cluster_id") or "")
        provisional_signal = str(bundle.get("provisional_signal_cluster_id") or "")
        signal_features.update(
            {
                "signal_vector_id": bundle.get("signal_vector_id") or "",
                "signal_vector_source": bundle.get("signal_vector_source") or "",
                "signal_vector_error": bundle.get("signal_vector_error") or "",
                "signal_vector_ready": bool(bundle.get("signal_vector_ready")),
                "nearest_134_signal_cluster_id": bundle.get("nearest_134_signal_cluster_id") or "",
                "max_corr_to_134_signal_vector": round(float(max_signal_corr), 6),
                "mean_topk_corr_to_134_signal_vector": bundle.get("mean_topk_corr_to_134_signal_vector") or 0.0,
                "novelty_vs_134_signal_vector": round(max(0.0, 1.0 - float(max_signal_corr)), 6),
                "known_signal_cluster_id": known_signal,
                "provisional_signal_cluster_id": provisional_signal,
                "source_lane_signal_cluster_id": f"{source_lane}|{provisional_signal}",
                "signal_vector_cluster_basis": bundle.get("signal_vector_cluster_basis") or "",
                "max_corr_to_selected_queue_signal": bundle.get("max_corr_to_selected_queue_signal") or 0.0,
                "mean_corr_to_selected_queue_signal": bundle.get("mean_corr_to_selected_queue_signal") or 0.0,
                "nearest_selected_signal_cluster_id": bundle.get("nearest_selected_signal_cluster_id") or "",
                "nearest_selected_signal_vector_id": bundle.get("nearest_selected_signal_vector_id") or "",
            }
        )

    return {
        "candidate_id": row.get("candidate_id"),
        "expr_hash": row.get("expr_hash"),
        "expression": expression,
        "source_lane": source_lane,
        "source_profile": row.get("source_profile"),
        "base_quality": round(float(base_quality), 8),
        "turnover_proxy": turnover,
        "turnover_proxy_source": turnover_source,
        "cost_adjusted_proxy": cost_adjusted,
        "cost_adjusted_proxy_source": cost_source,
        "factor_exposure_proxy": factor_exposure,
        "factor_exposure_proxy_source": factor_source,
        "sector_concentration_proxy": sector_concentration,
        "sector_concentration_proxy_source": sector_source,
        "complexity_score": complexity,
        "turnover_structure_risk": structure_turnover_risk,
        "operator_pathology_flag": pathology,
        "max_corr_to_103_registry": similarity["max_corr_to_103_registry"],
        "mean_corr_to_103_registry": similarity["mean_corr_to_103_registry"],
        "nearest_103_cluster": similarity["nearest_103_cluster"],
        "max_corr_to_134_registry": similarity["max_corr_to_103_registry"],
        "mean_corr_to_134_registry": similarity["mean_corr_to_103_registry"],
        "nearest_134_cluster_id": similarity["nearest_103_cluster"],
        "novelty_vs_134": round(max(0.0, 1.0 - max_registry_corr), 6),
        "known_cluster_id": known_cluster_id,
        "provisional_cluster_id": provisional_cluster_id,
        "source_lane_cluster_id": source_lane_cluster_id,
        "max_corr_to_selected_queue": round(float(selected_similarity), 6),
        "mean_corr_to_selected_queue": round(float(selected_mean_similarity), 6),
        "feature_missing": "|".join(missing),
        "uses_forbidden_replay_labels": any(field in row and row.get(field) is not None for field in FORBIDDEN_REPLAY_LABEL_FIELDS),
        **signal_features,
    }


def _threshold_penalty(value: float | None, threshold: float | None) -> float:
    if value is None or threshold is None or threshold <= 0:
        return 0.0
    return max(0.0, float(value) / float(threshold) - 1.0)


def _score_deployability(features: dict[str, Any], thresholds: RegistryThresholds) -> tuple[float, bool, str, str]:
    reasons = []
    not_applied = []
    if bool(features["operator_pathology_flag"]):
        reasons.append("operator_pathology")
    turnover = features.get("turnover_proxy")
    if turnover is None or thresholds.turnover_p90 is None:
        not_applied.append("turnover_cap")
    elif float(turnover) > float(thresholds.turnover_p90):
        reasons.append("turnover_gt_registry_p90")
    if thresholds.complexity_p90 is None:
        not_applied.append("complexity_cap")
    elif float(features["complexity_score"]) > float(thresholds.complexity_p90):
        reasons.append("complexity_gt_registry_p90")
    cost = features.get("cost_adjusted_proxy")
    if cost is None:
        not_applied.append("cost_adjusted_required")
    elif float(cost) <= 0.0:
        reasons.append("cost_adjusted_nonpositive")
    if features.get("factor_exposure_proxy") is None or thresholds.factor_exposure_p90 is None:
        not_applied.append("factor_exposure_cap")
    if features.get("sector_concentration_proxy") is None or thresholds.sector_concentration_p90 is None:
        not_applied.append("sector_concentration_cap")

    novelty = 1.0 - float(features["max_corr_to_103_registry"])
    turnover_penalty = _threshold_penalty(features.get("turnover_proxy"), thresholds.turnover_p90)
    complexity_penalty = _threshold_penalty(float(features["complexity_score"]), thresholds.complexity_p90)
    factor_penalty = _threshold_penalty(features.get("factor_exposure_proxy"), thresholds.factor_exposure_p90)
    sector_penalty = _threshold_penalty(features.get("sector_concentration_proxy"), thresholds.sector_concentration_p90)
    cost_score = float(features["cost_adjusted_proxy"]) if features.get("cost_adjusted_proxy") is not None else 0.0
    score = (
        float(features["base_quality"])
        + 0.30 * cost_score
        + 0.20 * max(0.0, 1.0 - (float(features.get("turnover_proxy") or 0.0) / max(1e-9, float(thresholds.turnover_p90 or 1.0))))
        + 0.15 * novelty
        - 0.30 * turnover_penalty
        - 0.25 * factor_penalty
        - 0.20 * sector_penalty
        - 0.20 * complexity_penalty
    )
    return round(score, 8), not reasons, "|".join(reasons), "|".join(not_applied)


def _score_book_proxy(features: dict[str, Any], thresholds: RegistryThresholds) -> float:
    novelty = 1.0 - float(features["max_corr_to_103_registry"])
    turnover_penalty = _threshold_penalty(features.get("turnover_proxy"), thresholds.turnover_p90)
    factor_penalty = _threshold_penalty(features.get("factor_exposure_proxy"), thresholds.factor_exposure_p90)
    complexity_penalty = _threshold_penalty(float(features["complexity_score"]), thresholds.complexity_p90)
    score = (
        float(features["base_quality"])
        + 0.50 * novelty
        - 0.40 * float(features["max_corr_to_103_registry"])
        - 0.30 * float(features["max_corr_to_selected_queue"])
        - 0.30 * turnover_penalty
        - 0.20 * factor_penalty
        - 0.15 * complexity_penalty
    )
    return round(score, 8)


def _selected_count(selected_rows: list[dict[str, Any]], field: str, value: Any) -> int:
    if value is None or value == "":
        return 0
    return sum(1 for row in selected_rows if str(row.get(field) or "") == str(value))


def _score_book_proxy_diversified(
    features: dict[str, Any],
    thresholds: RegistryThresholds,
    *,
    selected_rows: list[dict[str, Any]],
    strengthened: bool,
) -> tuple[float, bool, str, dict[str, Any]]:
    base_e3_score = _score_book_proxy(features, thresholds)
    known_cluster = str(features.get("known_cluster_id") or "")
    provisional_cluster = str(features.get("provisional_cluster_id") or "")
    source_lane_cluster = str(features.get("source_lane_cluster_id") or "")
    known_count = _selected_count(selected_rows, "known_cluster_id", known_cluster)
    provisional_count = _selected_count(selected_rows, "provisional_cluster_id", provisional_cluster)
    source_lane_cluster_count = _selected_count(selected_rows, "source_lane_cluster_id", source_lane_cluster)
    cap_reasons = []
    if known_cluster:
        if known_cluster == "cluster_001" and known_count >= 2:
            cap_reasons.append("cluster_001_known_cap")
        elif known_count >= 3:
            cap_reasons.append("known_cluster_cap")
    if provisional_count >= 4:
        cap_reasons.append("provisional_cluster_cap")
    if source_lane_cluster_count >= 2:
        cap_reasons.append("source_lane_cluster_cap")

    novelty = float(features.get("novelty_vs_134") or 0.0)
    selected_corr = float(features.get("max_corr_to_selected_queue") or 0.0)
    turnover_penalty = _threshold_penalty(features.get("turnover_proxy"), thresholds.turnover_p90)
    complexity_penalty = _threshold_penalty(float(features["complexity_score"]), thresholds.complexity_p90)
    known_penalty = math.sqrt(float(known_count)) if known_cluster else 0.0
    provisional_penalty = math.sqrt(float(provisional_count)) if provisional_cluster else 0.0
    source_lane_penalty = math.sqrt(float(source_lane_cluster_count)) if source_lane_cluster else 0.0
    cluster_001_penalty = 2.0 * math.sqrt(float(known_count + 1)) if known_cluster == "cluster_001" else 0.0

    if strengthened:
        score = (
            base_e3_score
            + 0.70 * novelty
            - 0.95 * selected_corr
            - 0.50 * float(features.get("max_corr_to_134_registry") or 0.0)
            - 0.70 * known_penalty
            - 0.65 * provisional_penalty
            - 0.50 * source_lane_penalty
            - 0.35 * turnover_penalty
            - 0.20 * complexity_penalty
            - 0.35 * cluster_001_penalty
        )
    else:
        score = (
            base_e3_score
            + 0.40 * novelty
            - 0.70 * selected_corr
            - 0.60 * known_penalty
            - 0.50 * provisional_penalty
            - 0.40 * source_lane_penalty
            - 0.30 * turnover_penalty
            - 0.20 * complexity_penalty
            - 0.30 * cluster_001_penalty
        )
    details = {
        "base_e3_score": round(float(base_e3_score), 8),
        "known_cluster_count_before_pick": known_count,
        "provisional_cluster_count_before_pick": provisional_count,
        "source_lane_cluster_count_before_pick": source_lane_cluster_count,
        "known_cluster_count_penalty": round(float(known_penalty), 6),
        "provisional_cluster_count_penalty": round(float(provisional_penalty), 6),
        "source_lane_cluster_count_penalty": round(float(source_lane_penalty), 6),
        "anti_concentration_penalty": round(float(0.60 * known_penalty + 0.50 * provisional_penalty + 0.40 * source_lane_penalty), 6),
        "cluster_001_penalty": round(float(cluster_001_penalty), 6),
        "turnover_penalty": round(float(turnover_penalty), 6),
        "complexity_penalty": round(float(complexity_penalty), 6),
        "cap_reject_reason": "|".join(cap_reasons),
    }
    hard_pass = not cap_reasons and not bool(features["operator_pathology_flag"])
    reject_reason = "|".join(cap_reasons or (["operator_pathology"] if bool(features["operator_pathology_flag"]) else []))
    return round(score, 8), hard_pass, reject_reason, details


def _copy_selected(row: dict[str, Any], *, policy: str, role: str, bucket: str, source_profile: str) -> dict[str, Any]:
    item = dict(row)
    item["selection_policy"] = policy
    item["strict_selection_role"] = role
    item["selection_pool_type"] = "phase3e_selector_pool"
    item["phase3_budget_bucket"] = bucket
    item["source_profile"] = source_profile
    item["quota_applied"] = False
    item["quota_type"] = "phase3e_selector"
    item["quota_stage"] = "selector_pre_audit"
    item["quota_basis"] = policy
    item["rejected_by_quota"] = False
    item["quota_reject_reason"] = None
    return item


def _attach_selector_feature_metadata(item: dict[str, Any], features: dict[str, Any], *, selector_profile: str, selection_score: float) -> None:
    item["phase3e_selector_profile"] = selector_profile
    item["phase3e_selection_score"] = round(float(selection_score), 8)
    for key in (
        "max_corr_to_103_registry",
        "mean_corr_to_103_registry",
        "nearest_103_cluster",
        "max_corr_to_134_registry",
        "mean_corr_to_134_registry",
        "nearest_134_cluster_id",
        "novelty_vs_134",
        "known_cluster_id",
        "provisional_cluster_id",
        "source_lane_cluster_id",
        "max_corr_to_selected_queue",
        "mean_corr_to_selected_queue",
        "base_e3_score",
        "known_cluster_count_before_pick",
        "provisional_cluster_count_before_pick",
        "source_lane_cluster_count_before_pick",
        "anti_concentration_penalty",
        "cluster_001_penalty",
        "turnover_structure_risk",
        "turnover_penalty",
        "turnover_structure_penalty",
        "complexity_penalty",
        "cap_reject_reason",
        "signal_vector_id",
        "signal_vector_source",
        "signal_vector_error",
        "signal_vector_ready",
        "nearest_134_signal_cluster_id",
        "max_corr_to_134_signal_vector",
        "mean_topk_corr_to_134_signal_vector",
        "novelty_vs_134_signal_vector",
        "known_signal_cluster_id",
        "provisional_signal_cluster_id",
        "source_lane_signal_cluster_id",
        "signal_vector_cluster_basis",
        "max_corr_to_selected_queue_signal",
        "mean_corr_to_selected_queue_signal",
        "nearest_selected_signal_cluster_id",
        "nearest_selected_signal_vector_id",
        "known_signal_cluster_count_before_pick",
        "provisional_signal_cluster_count_before_pick",
        "source_lane_signal_cluster_count_before_pick",
        "vector_diversity_penalty",
        "known_signal_cluster_penalty",
        "provisional_signal_cluster_penalty",
        "source_lane_signal_cluster_penalty",
        "cluster_001_signal_penalty",
        "cluster_003_signal_penalty",
        "selector_mode",
        "cap_relaxed_for_backfill",
    ):
        if key in features:
            item[key] = features[key]


def _book_marginal_mode(selector_profile: str) -> str:
    signal_mode = signal_vector_book_marginal_mode(selector_profile)
    if signal_mode:
        return signal_mode
    return "proxy" if selector_profile.startswith("book_marginal_proxy") else ""


def _score_for_selector_profile(
    selector_profile: str,
    features: dict[str, Any],
    thresholds: RegistryThresholds,
    *,
    selected_rows: list[dict[str, Any]],
) -> tuple[float, bool, str, str, dict[str, Any]]:
    if is_signal_vector_selector(selector_profile):
        base_e3_score = _score_book_proxy(features, thresholds)
        score, hard_pass, reject_reason, details = score_signal_vector_selector(
            selector_profile,
            features,
            thresholds,
            selected_rows=selected_rows,
            base_e3_score=base_e3_score,
        )
        return score, hard_pass, reject_reason, "candidate_return_vector|registry_return_vectors|true_book_marginal", details
    if selector_profile == "deployability_hardened":
        score, hard_pass, reject_reason, not_applied = _score_deployability(features, thresholds)
        return score, hard_pass, reject_reason, not_applied, {}
    if selector_profile == "book_marginal_proxy":
        score = _score_book_proxy(features, thresholds)
        hard_pass = not bool(features["operator_pathology_flag"])
        reject_reason = "operator_pathology" if not hard_pass else ""
        return score, hard_pass, reject_reason, "candidate_return_vector|registry_return_vectors", {"base_e3_score": score}
    if selector_profile in {"book_marginal_proxy_diversified", "book_marginal_proxy_strengthened"}:
        score, hard_pass, reject_reason, details = _score_book_proxy_diversified(
            features,
            thresholds,
            selected_rows=selected_rows,
            strengthened=selector_profile == "book_marginal_proxy_strengthened",
        )
        return score, hard_pass, reject_reason, "candidate_return_vector|registry_return_vectors", details
    score = float(features["base_quality"]) + 0.05 * (1.0 - float(features["max_corr_to_103_registry"]))
    hard_pass = not bool(features["operator_pathology_flag"])
    reject_reason = "operator_pathology" if not hard_pass else ""
    return score, hard_pass, reject_reason, "", {}


def _selector_missing_true_book_features(selector_profile: str) -> str:
    if is_signal_vector_selector(selector_profile):
        return "candidate_return_vector|registry_return_vectors|true_book_marginal"
    return "candidate_return_vector|registry_return_vectors" if _book_marginal_mode(selector_profile) else ""


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    seen = set()
    for row in rows:
        key = _row_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _bucket(row: dict[str, Any]) -> str:
    return str(row.get("phase3_budget_bucket") or row.get("proof_variant") or "unknown")


def select_phase3e_queue(
    candidate_pool: list[dict[str, Any]],
    *,
    budgets: dict[str, int],
    selector_profile: str,
    context: Phase3ERegistryContext,
    seed: str,
    default_selected: list[dict[str, Any]] | None = None,
    total_budget: int | None = None,
    signal_vector_store: Phase3GSignalVectorStore | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    total_budget = int(total_budget if total_budget is not None else sum(max(0, int(value)) for value in budgets.values()))
    default_selected = default_selected or []
    if signal_vector_store is None and is_signal_vector_selector(selector_profile):
        signal_vector_store = Phase3GSignalVectorStore.default()
    if selector_profile in {"standard_D3", "standard"}:
        selected = [_copy_selected(row, policy="phase3e_standard_D3", role=str(row.get("strict_selection_role") or "phase3e_standard"), bucket=_bucket(row), source_profile="D3_primary") for row in default_selected]
        audit = _audit_rows(candidate_pool, selected, selector_profile=selector_profile, context=context, seed=seed, signal_vector_store=signal_vector_store)
        return selected[:total_budget], audit, feature_preflight(candidate_pool, context=context, selector_profile=selector_profile, signal_vector_store=signal_vector_store)
    if selector_profile == "mixed_profile_cluster_capped":
        primary_budget = int(round(total_budget * 0.80))
        sidecar_budget = total_budget - primary_budget
        primary_selected, primary_audit, _ = _select_scored(
            candidate_pool,
            budgets=_scale_budgets(budgets, primary_budget),
            selector_profile="standard_D3",
            context=context,
            seed=f"{seed}::primary",
            source_profile="D3_primary",
            policy="phase3e_D3_primary_component",
            signal_vector_store=signal_vector_store,
        )
        remaining_pool = [row for row in candidate_pool if _row_key(row) not in {_row_key(item) for item in primary_selected}]
        sidecar_selected, sidecar_audit, _ = _select_scored(
            remaining_pool,
            budgets=_sidecar_budgets(sidecar_budget),
            selector_profile="book_marginal_proxy",
            context=context,
            seed=f"{seed}::D2_sidecar",
            source_profile="D2_sidecar",
            policy="phase3e_D2_sidecar_cluster_capped",
            signal_vector_store=signal_vector_store,
        )
        selected = primary_selected + sidecar_selected
        audit = primary_audit + sidecar_audit
        for row in audit:
            row["selector_name"] = "mixed_profile_cluster_capped"
        return selected[:total_budget], audit, feature_preflight(candidate_pool, context=context, selector_profile=selector_profile, signal_vector_store=signal_vector_store)
    return _select_scored(
        candidate_pool,
        budgets=budgets,
        selector_profile=selector_profile,
        context=context,
        seed=seed,
        source_profile="D3_primary",
        policy=f"phase3e_{selector_profile}",
        signal_vector_store=signal_vector_store,
    )


def _sidecar_budgets(total: int) -> dict[str, int]:
    total = max(0, int(total))
    r0 = int(round(total * 0.65))
    agnostic = int(round(total * 0.20))
    repair_expansion = int(round(total * 0.13))
    defined = int(round(total * 0.02))
    repair = max(0, total - r0 - agnostic - repair_expansion - defined)
    return {
        "r0_cem_led": r0,
        "ast_failure_aware_repair": repair,
        "replay_aware_residual": 0,
        "novelty_diagnostic": 0,
        "formula_gen_v2_defined": defined,
        "agnostic_freeform_ast": agnostic,
        "formula_gen_v2_repair_expansion": repair_expansion,
    }


def _scale_budgets(budgets: dict[str, int], target_total: int) -> dict[str, int]:
    target_total = max(0, int(target_total))
    current = sum(max(0, int(value)) for value in budgets.values())
    if current <= 0:
        return {key: 0 for key in budgets}
    out = {key: int(math.floor(max(0, int(value)) * target_total / current)) for key, value in budgets.items()}
    diff = target_total - sum(out.values())
    for key in sorted(budgets, key=lambda item: budgets[item], reverse=True):
        if diff <= 0:
            break
        out[key] += 1
        diff -= 1
    return out


def _select_scored(
    candidate_pool: list[dict[str, Any]],
    *,
    budgets: dict[str, int],
    selector_profile: str,
    context: Phase3ERegistryContext,
    seed: str,
    source_profile: str,
    policy: str,
    signal_vector_store: Phase3GSignalVectorStore | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if signal_vector_store is None and is_signal_vector_selector(selector_profile):
        signal_vector_store = Phase3GSignalVectorStore.default()
    pool = _dedupe_rows(candidate_pool)
    selector_version = PHASE3G_VECTOR_SELECTOR_VERSION if is_signal_vector_selector(selector_profile) else PHASE3E_SELECTOR_VERSION
    selected: list[dict[str, Any]] = []
    audit_by_key: dict[str, dict[str, Any]] = {}
    remaining = list(pool)
    bucket_remaining = {key: max(0, int(value)) for key, value in budgets.items()}
    total_budget = sum(bucket_remaining.values())
    rank = 0
    while remaining and len(selected) < total_budget and any(value > 0 for value in bucket_remaining.values()):
        scored = []
        for row in remaining:
            bucket = _bucket(row)
            if bucket_remaining.get(bucket, 0) <= 0:
                continue
            features = feature_row(row, context, selected_rows=selected, signal_vector_store=signal_vector_store)
            score, hard_pass, reject_reason, not_applied, details = _score_for_selector_profile(
                selector_profile,
                features,
                context.thresholds,
                selected_rows=selected,
            )
            features.update(details)
            audit_item = _audit_item(
                row,
                features,
                selector_profile=selector_profile,
                selector_version=selector_version,
                hard_pass=hard_pass,
                reject_reason=reject_reason,
                gate_not_applied=not_applied,
                selection_score=score,
                selected=False,
                selection_reason="candidate",
                rank_before_selection=None,
            )
            audit_by_key[_row_key(row)] = audit_item
            if hard_pass:
                scored.append((score, _stable_noise(seed, row.get("candidate_id"), row.get("expression")), row, features))
        if not scored:
            break
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, picked, features = scored[0]
        bucket = _bucket(picked)
        bucket_remaining[bucket] -= 1
        rank += 1
        selected_item = _copy_selected(
            picked,
            policy=policy,
            role=f"{policy}_rank_{rank}",
            bucket=bucket,
            source_profile=source_profile,
        )
        selected_item["phase3e_selector_profile"] = selector_profile
        _attach_selector_feature_metadata(selected_item, features, selector_profile=selector_profile, selection_score=float(scored[0][0]))
        selected.append(selected_item)
        audit_by_key[_row_key(picked)] = _audit_item(
            picked,
            features,
            selector_profile=selector_profile,
            selector_version=selector_version,
            hard_pass=True,
            reject_reason="",
            gate_not_applied=_selector_missing_true_book_features(selector_profile),
            selection_score=float(scored[0][0]),
            selected=True,
            selection_reason=f"selected_{source_profile}",
            rank_before_selection=rank,
        )
        remaining = [row for row in remaining if _row_key(row) != _row_key(picked)]
    if remaining and len(selected) < total_budget:
        # Backfill only after exact bucket quotas are exhausted by missing/pathological pools.
        # This keeps audit budgets executable while preserving selector diagnostics.
        while remaining and len(selected) < total_budget:
            scored = []
            relaxed_cap_scored = []
            for row in remaining:
                features = feature_row(row, context, selected_rows=selected, signal_vector_store=signal_vector_store)
                score, hard_pass, reject_reason, not_applied, details = _score_for_selector_profile(
                    selector_profile,
                    features,
                    context.thresholds,
                    selected_rows=selected,
                )
                features.update(details)
                audit_by_key[_row_key(row)] = _audit_item(
                    row,
                    features,
                    selector_profile=selector_profile,
                    selector_version=selector_version,
                    hard_pass=hard_pass,
                    reject_reason=reject_reason,
                    gate_not_applied=not_applied,
                    selection_score=score,
                    selected=False,
                    selection_reason="backfill_candidate",
                    rank_before_selection=None,
                )
                if hard_pass:
                    scored.append((score, _stable_noise(seed, "backfill", row.get("candidate_id"), row.get("expression")), row, features))
                elif is_signal_vector_selector(selector_profile) and not bool(features["operator_pathology_flag"]) and str(features.get("cap_reject_reason") or ""):
                    relaxed_features = dict(features)
                    relaxed_features["cap_relaxed_for_backfill"] = True
                    relaxed_cap_scored.append((score - 1.0, _stable_noise(seed, "relaxed_backfill", row.get("candidate_id"), row.get("expression")), row, relaxed_features))
            if not scored:
                scored = relaxed_cap_scored
            if not scored:
                break
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            _, _, picked, features = scored[0]
            rank += 1
            selected_item = _copy_selected(
                picked,
                policy=policy,
                role=f"{policy}_backfill_rank_{rank}",
                bucket=_bucket(picked),
                source_profile=source_profile,
            )
            selected_item["phase3e_selector_profile"] = selector_profile
            _attach_selector_feature_metadata(selected_item, features, selector_profile=selector_profile, selection_score=float(scored[0][0]))
            selected.append(selected_item)
            audit_by_key[_row_key(picked)] = _audit_item(
                picked,
                features,
                selector_profile=selector_profile,
                selector_version=selector_version,
                hard_pass=True,
                reject_reason="",
                gate_not_applied=_selector_missing_true_book_features(selector_profile),
                selection_score=float(scored[0][0]),
                selected=True,
                selection_reason=f"selected_{source_profile}_backfill",
                rank_before_selection=rank,
            )
            remaining = [row for row in remaining if _row_key(row) != _row_key(picked)]
    audit = list(audit_by_key.values())
    return selected, audit, feature_preflight(candidate_pool, context=context, selector_profile=selector_profile, signal_vector_store=signal_vector_store)


def _audit_rows(
    candidate_pool: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    *,
    selector_profile: str,
    context: Phase3ERegistryContext,
    seed: str,
    signal_vector_store: Phase3GSignalVectorStore | None = None,
) -> list[dict[str, Any]]:
    selector_version = PHASE3G_VECTOR_SELECTOR_VERSION if is_signal_vector_selector(selector_profile) else PHASE3E_SELECTOR_VERSION
    selected_keys = {_row_key(row): index + 1 for index, row in enumerate(selected)}
    audit = []
    for row in _dedupe_rows(candidate_pool):
        features = feature_row(row, context, signal_vector_store=signal_vector_store)
        key = _row_key(row)
        audit.append(
            _audit_item(
                row,
                features,
                selector_profile=selector_profile,
                selector_version=selector_version,
                hard_pass=not bool(features["operator_pathology_flag"]),
                reject_reason="operator_pathology" if bool(features["operator_pathology_flag"]) else "",
                gate_not_applied="",
                selection_score=float(features["base_quality"]),
                selected=key in selected_keys,
                selection_reason="standard_D3_selection" if key in selected_keys else "candidate",
                rank_before_selection=selected_keys.get(key),
            )
        )
    return audit


def _audit_item(
    row: dict[str, Any],
    features: dict[str, Any],
    *,
    selector_profile: str,
    selector_version: str,
    hard_pass: bool,
    reject_reason: str,
    gate_not_applied: str,
    selection_score: float,
    selected: bool,
    selection_reason: str,
    rank_before_selection: int | None,
) -> dict[str, Any]:
    item = {
        "arm": row.get("ablation_arm"),
        "candidate_id": row.get("candidate_id"),
        "expr_hash": row.get("expr_hash"),
        "source_lane": features["source_lane"],
        "source_generator": row.get("source_generator") or row.get("generator") or row.get("proof_variant"),
        "source_profile": row.get("source_profile"),
        "selector_name": selector_profile,
        "selector_version": selector_version,
        "base_e3_score": features.get("base_e3_score", ""),
        "base_quality": features["base_quality"],
        "turnover_proxy": features["turnover_proxy"],
        "turnover_structure_risk": features.get("turnover_structure_risk", ""),
        "cost_adjusted_proxy": features["cost_adjusted_proxy"],
        "factor_exposure_proxy": features["factor_exposure_proxy"],
        "sector_concentration_proxy": features["sector_concentration_proxy"],
        "complexity_score": features["complexity_score"],
        "operator_pathology_flag": features["operator_pathology_flag"],
        "max_corr_to_103_registry": features["max_corr_to_103_registry"],
        "mean_corr_to_103_registry": features["mean_corr_to_103_registry"],
        "nearest_103_cluster": features.get("nearest_103_cluster"),
        "max_corr_to_134_registry": features.get("max_corr_to_134_registry"),
        "mean_corr_to_134_registry": features.get("mean_corr_to_134_registry"),
        "nearest_134_cluster_id": features.get("nearest_134_cluster_id"),
        "novelty_vs_134": features.get("novelty_vs_134"),
        "max_corr_to_selected_queue": features["max_corr_to_selected_queue"],
        "max_corr_to_selected_queue_before_pick": features["max_corr_to_selected_queue"],
        "mean_corr_to_selected_queue": features.get("mean_corr_to_selected_queue"),
        "mean_corr_to_selected_queue_before_pick": features.get("mean_corr_to_selected_queue"),
        "provisional_cluster_id": features.get("provisional_cluster_id"),
        "known_cluster_id": features.get("known_cluster_id"),
        "known_cluster_count_before_pick": features.get("known_cluster_count_before_pick", ""),
        "provisional_cluster_count_before_pick": features.get("provisional_cluster_count_before_pick", ""),
        "source_lane_cluster_count_before_pick": features.get("source_lane_cluster_count_before_pick", ""),
        "known_cluster_count_penalty": features.get("known_cluster_count_penalty", ""),
        "provisional_cluster_count_penalty": features.get("provisional_cluster_count_penalty", ""),
        "source_lane_cluster_count_penalty": features.get("source_lane_cluster_count_penalty", ""),
        "anti_concentration_penalty": features.get("anti_concentration_penalty", ""),
        "cluster_001_penalty": features.get("cluster_001_penalty", ""),
        "signal_vector_id": features.get("signal_vector_id", ""),
        "signal_vector_source": features.get("signal_vector_source", ""),
        "signal_vector_error": features.get("signal_vector_error", ""),
        "signal_vector_ready": features.get("signal_vector_ready", ""),
        "nearest_134_signal_cluster_id": features.get("nearest_134_signal_cluster_id", ""),
        "max_corr_to_134_signal_vector": features.get("max_corr_to_134_signal_vector", ""),
        "mean_topk_corr_to_134_signal_vector": features.get("mean_topk_corr_to_134_signal_vector", ""),
        "novelty_vs_134_signal_vector": features.get("novelty_vs_134_signal_vector", ""),
        "known_signal_cluster_id": features.get("known_signal_cluster_id", ""),
        "provisional_signal_cluster_id": features.get("provisional_signal_cluster_id", ""),
        "source_lane_signal_cluster_id": features.get("source_lane_signal_cluster_id", ""),
        "signal_vector_cluster_basis": features.get("signal_vector_cluster_basis", ""),
        "max_corr_to_selected_queue_signal": features.get("max_corr_to_selected_queue_signal", ""),
        "max_corr_to_selected_queue_signal_before_pick": features.get("max_corr_to_selected_queue_signal", ""),
        "mean_corr_to_selected_queue_signal": features.get("mean_corr_to_selected_queue_signal", ""),
        "mean_corr_to_selected_queue_signal_before_pick": features.get("mean_corr_to_selected_queue_signal", ""),
        "nearest_selected_signal_cluster_id": features.get("nearest_selected_signal_cluster_id", ""),
        "nearest_selected_signal_vector_id": features.get("nearest_selected_signal_vector_id", ""),
        "known_signal_cluster_count_before_pick": features.get("known_signal_cluster_count_before_pick", ""),
        "provisional_signal_cluster_count_before_pick": features.get("provisional_signal_cluster_count_before_pick", ""),
        "source_lane_signal_cluster_count_before_pick": features.get("source_lane_signal_cluster_count_before_pick", ""),
        "vector_diversity_penalty": features.get("vector_diversity_penalty", ""),
        "known_signal_cluster_penalty": features.get("known_signal_cluster_penalty", ""),
        "provisional_signal_cluster_penalty": features.get("provisional_signal_cluster_penalty", ""),
        "source_lane_signal_cluster_penalty": features.get("source_lane_signal_cluster_penalty", ""),
        "cluster_001_signal_penalty": features.get("cluster_001_signal_penalty", ""),
        "cluster_003_signal_penalty": features.get("cluster_003_signal_penalty", ""),
        "cap_relaxed_for_backfill": features.get("cap_relaxed_for_backfill", ""),
        "selector_mode": features.get("selector_mode", ""),
        "turnover_penalty": features.get("turnover_penalty", ""),
        "turnover_structure_penalty": features.get("turnover_structure_penalty", ""),
        "complexity_penalty": features.get("complexity_penalty", ""),
        "hard_gate_pass": hard_pass,
        "hard_reject_reason": reject_reason,
        "cap_reject_reason": features.get("cap_reject_reason", ""),
        "feature_missing": features["feature_missing"],
        "gate_not_applied": gate_not_applied,
        "selection_score": round(float(selection_score), 8),
        "selection_score_final": round(float(selection_score), 8),
        "rank_before_selection": rank_before_selection,
        "selection_rank": rank_before_selection,
        "selected_for_audit": selected,
        "selection_reason": selection_reason,
        "uses_forbidden_replay_labels": features["uses_forbidden_replay_labels"],
        "book_marginal_mode": _book_marginal_mode(selector_profile),
        "residual_ir_proxy": "",
        "book_marginal_score": round(float(selection_score), 8) if _book_marginal_mode(selector_profile) else "",
        "projection_topk_clusters": "",
        "expression": row.get("expression"),
    }
    return item


def feature_preflight(
    candidate_pool: list[dict[str, Any]],
    *,
    context: Phase3ERegistryContext,
    selector_profile: str = "standard_D3",
    signal_vector_store: Phase3GSignalVectorStore | None = None,
) -> dict[str, Any]:
    if signal_vector_store is None and is_signal_vector_selector(selector_profile):
        signal_vector_store = Phase3GSignalVectorStore.default()
    rows = _dedupe_rows(candidate_pool)
    features = [feature_row(row, context, signal_vector_store=signal_vector_store) for row in rows]

    def coverage(key: str) -> float:
        return round(sum(1 for item in features if item.get(key) is not None and item.get(key) != "") / max(1, len(features)), 6)

    true_e3 = False
    proxy_e3 = coverage("max_corr_to_103_registry") > 0 and coverage("complexity_score") > 0
    signal_proxy = is_signal_vector_selector(selector_profile)
    signal_proxy_pass = (not signal_proxy) or (
        bool(signal_vector_store and signal_vector_store.coverage_ready())
        and coverage("signal_vector_ready") > 0
        and coverage("max_corr_to_134_signal_vector") > 0
    )
    selector_version = PHASE3G_VECTOR_SELECTOR_VERSION if signal_proxy else PHASE3E_SELECTOR_VERSION
    return {
        "selector_version": selector_version,
        "candidate_count": len(rows),
        "registry_baseline_name": context.baseline_name,
        "thresholds": {
            "turnover_p90": context.thresholds.turnover_p90,
            "complexity_p90": context.thresholds.complexity_p90,
            "cost_adjusted_p10": context.thresholds.cost_adjusted_p10,
            "factor_exposure_p90": context.thresholds.factor_exposure_p90,
            "sector_concentration_p90": context.thresholds.sector_concentration_p90,
        },
        "coverage": {
            "turnover_proxy": coverage("turnover_proxy"),
            "turnover_structure_risk": coverage("turnover_structure_risk"),
            "cost_adjusted_proxy": coverage("cost_adjusted_proxy"),
            "factor_exposure_proxy": coverage("factor_exposure_proxy"),
            "sector_concentration_proxy": coverage("sector_concentration_proxy"),
            "candidate_return_vector": 0.0,
            "registry_return_vectors": 0.0,
            "max_corr_to_103_proxy": coverage("max_corr_to_103_registry"),
            "signal_vector_ready": coverage("signal_vector_ready"),
            "max_corr_to_134_signal_vector": coverage("max_corr_to_134_signal_vector"),
            "mean_topk_corr_to_134_signal_vector": coverage("mean_topk_corr_to_134_signal_vector"),
            "selected_queue_signal_corr": coverage("max_corr_to_selected_queue_signal"),
            "operator_pathology_flag": coverage("operator_pathology_flag"),
            "complexity_score": coverage("complexity_score"),
        },
        "e2_minimum_requirement_pass": coverage("turnover_proxy") > 0 and coverage("complexity_score") > 0 and coverage("max_corr_to_103_registry") > 0,
        "e3_true_requirement_pass": true_e3,
        "e3_proxy_requirement_pass": proxy_e3,
        "signal_vector_proxy_requirement_pass": signal_proxy_pass,
        "signal_vector_store_ready": bool(signal_vector_store and signal_vector_store.coverage_ready()),
        "book_marginal_mode": _book_marginal_mode(selector_profile) or ("true" if true_e3 else "proxy"),
        "replay_label_leakage_guard": {
            "forbidden_fields": sorted(FORBIDDEN_REPLAY_LABEL_FIELDS),
            "selector_uses_forbidden_fields": False,
        },
    }


def write_selector_artifacts(root: Path, *, audit_rows: list[dict[str, Any]], preflight: dict[str, Any], selector_profile: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "phase3e_selector_feature_preflight.json", preflight)
    _write_csv(root / "phase3e_selector_audit.csv", audit_rows)
    lines = [
        "# Phase3E Selector Feature Preflight",
        "",
        f"- selector_profile: {selector_profile}",
        f"- selector_version: {preflight.get('selector_version')}",
        f"- candidate_count: {preflight.get('candidate_count')}",
        f"- book_marginal_mode: {preflight.get('book_marginal_mode')}",
        f"- e2_minimum_requirement_pass: {preflight.get('e2_minimum_requirement_pass')}",
        f"- e3_true_requirement_pass: {preflight.get('e3_true_requirement_pass')}",
        f"- e3_proxy_requirement_pass: {preflight.get('e3_proxy_requirement_pass')}",
        "",
        "## Coverage",
        "",
        "```json",
        json.dumps(preflight.get("coverage") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Thresholds",
        "",
        "```json",
        json.dumps(preflight.get("thresholds") or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Leakage Guard",
        "",
        "```json",
        json.dumps(preflight.get("replay_label_leakage_guard") or {}, ensure_ascii=False, indent=2),
        "```",
    ]
    (root / "PHASE3E_SELECTOR_FEATURE_PREFLIGHT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
