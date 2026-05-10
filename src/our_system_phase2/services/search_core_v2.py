from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso


SEARCH_CORE_V2_VERSION = "phase2-search-core-v2-family-first-2026-04-26"
DEFAULT_TOP_RECENT_IC = 0.025
DEFAULT_KEEP_REVIEW_IC = 0.02
DEFAULT_MAX_EXPOSURE = 0.25


def _read_report(value: Path | str | dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text(encoding="utf-8"))


def _unwrap_call(expression: str, name: str) -> str | None:
    prefix = f"{name}("
    expression = expression.strip()
    if not expression.lower().startswith(prefix.lower()) or not expression.endswith(")"):
        return None
    depth = 0
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(expression) - 1:
                return None
    return expression[len(prefix) : -1].strip()


def scale_twin_key(expression: str) -> str:
    """Collapse direct CSRank/ZScore wrappers while preserving direction.

    Early search treats `CSRank(x)` and `ZScore(x)` as scale twins because they
    usually express the same primitive ordering. Inverted twins remain separate.
    """
    expression = expression.strip()
    neg_payload = _unwrap_call(expression, "Neg")
    direction = "inverted" if neg_payload is not None else "normal"
    payload = neg_payload if neg_payload is not None else expression
    for wrapper in ("CSRank", "Rank", "ZScore"):
        inner = _unwrap_call(payload, wrapper)
        if inner is not None:
            return f"{direction}:{inner}"
    return f"{direction}:{payload}"


def _candidate_metric(candidate: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = candidate.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def candidate_search_score(candidate: dict[str, Any]) -> float:
    recent_ic = _candidate_metric(candidate, "recent_fast_screen_rank_ic")
    if recent_ic == 0.0:
        recent_ic = _candidate_metric(candidate, "recent_mean_rank_ic")
    full_ic = _candidate_metric(candidate, "mean_window_rank_ic")
    sortino = max(-2.0, min(2.0, _candidate_metric(candidate, "mean_window_sortino"))) / 2.0
    positive_ratio = _candidate_metric(candidate, "recent_positive_rank_ic_ratio", default=0.5)
    cost_score = _candidate_metric(candidate, "estimated_validation_cost_score")
    support_bonus = 0.03 if candidate.get("passes_real_market_smoke") else 0.0
    return round(
        (0.38 * recent_ic)
        + (0.38 * full_ic)
        + (0.12 * sortino)
        + (0.09 * positive_ratio)
        + support_bonus
        - (0.002 * cost_score),
        6,
    )


def _rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            candidate_search_score(item),
            _candidate_metric(item, "mean_window_rank_ic"),
            _candidate_metric(item, "recent_mean_rank_ic"),
        ),
        reverse=True,
    )


def dedupe_scale_twins(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    winners: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for candidate in _rank_candidates(candidates):
        key = scale_twin_key(str(candidate.get("expression", "")))
        current = winners.get(key)
        if current is None:
            enriched = dict(candidate)
            enriched["scale_twin_key"] = key
            enriched["search_score"] = candidate_search_score(candidate)
            winners[key] = enriched
            continue
        duplicates.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "expression": candidate.get("expression"),
                "scale_twin_key": key,
                "kept_candidate_id": current.get("candidate_id"),
                "reason": "scale_twin_lower_search_score",
            }
        )
    return _rank_candidates(list(winners.values())), duplicates


def _group_by_family(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        family = str(candidate.get("primitive_family") or candidate.get("frontier_lane") or "unknown")
        grouped.setdefault(family, []).append(candidate)
    return grouped


def _family_budget(fast_candidates: list[dict[str, Any]], full_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_fast = _group_by_family(fast_candidates)
    grouped_full = _group_by_family(full_candidates)
    families = sorted(set(grouped_fast) | set(grouped_full))
    rows: list[dict[str, Any]] = []
    for family in families:
        fast_ranked = _rank_candidates(grouped_fast.get(family, []))
        full_ranked = _rank_candidates(grouped_full.get(family, []))
        best = (full_ranked or fast_ranked or [{}])[0]
        full_best_ic = _candidate_metric(best, "mean_window_rank_ic") if full_ranked else None
        recent_best_ic = _candidate_metric((fast_ranked or [best])[0], "recent_mean_rank_ic")
        promoted_fast_count = sum(1 for item in grouped_fast.get(family, []) if item.get("promoted_to_full_history_review"))
        if full_ranked and full_best_ic is not None and full_best_ic >= DEFAULT_KEEP_REVIEW_IC:
            budget_tier = "audit_expand"
        elif recent_best_ic >= DEFAULT_TOP_RECENT_IC:
            budget_tier = "regime_probe"
        else:
            budget_tier = "watch"
        rows.append(
            {
                "primitive_family": family,
                "budget_tier": budget_tier,
                "fast_candidate_count": len(grouped_fast.get(family, [])),
                "fast_promoted_count": promoted_fast_count,
                "full_history_candidate_count": len(grouped_full.get(family, [])),
                "best_candidate_id": best.get("candidate_id"),
                "best_expression": best.get("expression"),
                "best_search_score": candidate_search_score(best) if best else None,
                "best_recent_ic": recent_best_ic,
                "best_full_history_ic": full_best_ic,
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            {"audit_expand": 3, "regime_probe": 2, "watch": 1}.get(str(item["budget_tier"]), 0),
            item["best_search_score"] or -999.0,
        ),
        reverse=True,
    )


def _full_by_candidate_id(full_candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("candidate_id")): item for item in full_candidates}


def _promoted_representatives(
    fast_candidates: list[dict[str, Any]],
    full_candidates: list[dict[str, Any]],
    *,
    per_family_limit: int,
    total_limit: int,
) -> list[dict[str, Any]]:
    grouped = _group_by_family(full_candidates or fast_candidates)
    representatives: list[dict[str, Any]] = []
    fast_by_id = {str(item.get("candidate_id")): item for item in fast_candidates}
    for family, candidates in grouped.items():
        for candidate in _rank_candidates(candidates)[:per_family_limit]:
            fast_candidate = fast_by_id.get(str(candidate.get("candidate_id")), {})
            representatives.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "primitive_family": family,
                    "expression": candidate.get("expression"),
                    "search_score": candidate_search_score(candidate),
                    "recent_fast_screen_rank_ic": candidate.get("recent_fast_screen_rank_ic")
                    or fast_candidate.get("recent_mean_rank_ic"),
                    "full_history_rank_ic": candidate.get("mean_window_rank_ic"),
                    "full_history_sortino": candidate.get("mean_window_sortino"),
                    "passes_real_market_smoke": candidate.get("passes_real_market_smoke"),
                    "recommended_action": "strict_audit_or_neutralization"
                    if candidate.get("passes_real_market_smoke")
                    else "full_history_review",
                }
            )
    return sorted(
        representatives,
        key=lambda item: (
            item["search_score"],
            item["full_history_rank_ic"] or -999.0,
            item["recent_fast_screen_rank_ic"] or -999.0,
        ),
        reverse=True,
    )[:total_limit]


def _shadow_queues(
    fast_candidates: list[dict[str, Any]],
    full_candidates: list[dict[str, Any]],
    strict_audit: dict[str, Any] | None,
) -> dict[str, list[dict[str, Any]]]:
    full_ids = {str(item.get("candidate_id")) for item in full_candidates}
    full_by_id = _full_by_candidate_id(full_candidates)
    regime_local = []
    for candidate in fast_candidates:
        candidate_id = str(candidate.get("candidate_id"))
        recent_ic = _candidate_metric(candidate, "recent_mean_rank_ic")
        full_candidate = full_by_id.get(candidate_id)
        full_ic = _candidate_metric(full_candidate or {}, "mean_window_rank_ic")
        if recent_ic >= DEFAULT_TOP_RECENT_IC and (candidate_id not in full_ids or full_ic < DEFAULT_KEEP_REVIEW_IC):
            regime_local.append(
                {
                    "candidate_id": candidate_id,
                    "primitive_family": candidate.get("primitive_family"),
                    "expression": candidate.get("expression"),
                    "recent_mean_rank_ic": recent_ic,
                    "full_history_rank_ic": full_ic if candidate_id in full_ids else None,
                    "reason": "strong_recent_signal_needs_regime_local_tracking",
                }
            )

    tail_economics = []
    for candidate in full_candidates:
        sortino = _candidate_metric(candidate, "mean_window_sortino")
        full_ic = _candidate_metric(candidate, "mean_window_rank_ic")
        if sortino > 0.5 and full_ic < DEFAULT_KEEP_REVIEW_IC:
            tail_economics.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "primitive_family": candidate.get("primitive_family"),
                    "expression": candidate.get("expression"),
                    "mean_window_rank_ic": full_ic,
                    "mean_window_sortino": sortino,
                    "reason": "tail_economics_stronger_than_rank_ic",
                }
            )

    residualization = []
    if strict_audit:
        exposure_summary = strict_audit.get("exposure_summary") or {}
        high_exposures = []
        for exposure_name, exposure in exposure_summary.items():
            value = _candidate_metric(exposure, "abs_mean_daily_rank_corr")
            if value >= DEFAULT_MAX_EXPOSURE:
                high_exposures.append({"exposure": exposure_name, "abs_mean_daily_rank_corr": value})
        blocker_flags = [str(item) for item in strict_audit.get("blocker_flags", [])]
        if high_exposures or any("neutralization" in item for item in blocker_flags):
            residualization.append(
                {
                    "candidate_id": strict_audit.get("candidate_id"),
                    "expression": strict_audit.get("expression"),
                    "gatekeeper_decision": strict_audit.get("gatekeeper_decision"),
                    "high_exposures": high_exposures,
                    "blocker_flags": blocker_flags,
                    "reason": "needs_neutralization_or_exposure_residualization_before_keep_review",
                }
            )

    return {
        "regime_local_shadow": _rank_candidates(regime_local),
        "tail_economics_shadow": _rank_candidates(tail_economics),
        "residualization_queue": residualization,
    }


def _extract_precompute_targets(candidates: list[dict[str, Any]], strict_audit: dict[str, Any] | None) -> dict[str, Any]:
    expressions = [str(item.get("expression", "")) for item in candidates]
    rolling_patterns = set()
    for expression in expressions:
        for match in re.finditer(r"\b(?:Mean|Delay|Std|Mom|WMA|Med|Kurt|Skew)\([^()]+?,\s*\d+\)", expression):
            rolling_patterns.add(match.group(0))
    horizon_days = strict_audit.get("horizon_days") if strict_audit else None
    return {
        "base_expression_count": len(expressions),
        "rolling_subexpressions": sorted(rolling_patterns),
        "scale_twin_keys": sorted({scale_twin_key(expression) for expression in expressions}),
        "horizon_label_cache_days": horizon_days or [2, 5, 10, 20, 60],
    }


def build_phase2_search_core_v2_plan(
    *,
    fast_screen_report: Path | str | dict[str, Any],
    full_history_report: Path | str | dict[str, Any] | None = None,
    strict_audit_report: Path | str | dict[str, Any] | None = None,
    per_family_limit: int = 1,
    total_promotion_limit: int = 12,
) -> dict[str, Any]:
    fast = _read_report(fast_screen_report) or {}
    full = _read_report(full_history_report) or {}
    strict = _read_report(strict_audit_report)
    fast_candidates, scale_duplicates = dedupe_scale_twins(list(fast.get("evaluations", [])))
    full_candidates, full_scale_duplicates = dedupe_scale_twins(list(full.get("evaluations", [])))
    scale_duplicates.extend(full_scale_duplicates)
    representatives = _promoted_representatives(
        fast_candidates,
        full_candidates,
        per_family_limit=per_family_limit,
        total_limit=total_promotion_limit,
    )
    family_budget = _family_budget(fast_candidates, full_candidates)
    shadow_queues = _shadow_queues(fast_candidates, full_candidates, strict)
    next_audits = []
    if strict:
        blockers = [str(item) for item in strict.get("blocker_flags", [])]
        if "sector_neutralization_not_run" in blockers:
            next_audits.append("sector_neutralized_strict_audit")
        if strict.get("exposure_summary", {}).get("turnover_rate", {}).get("abs_mean_daily_rank_corr", 0) >= DEFAULT_MAX_EXPOSURE:
            next_audits.append("turnover_rate_residualized_strict_audit")
        if "capacity_model_not_run" in blockers:
            next_audits.append("capacity_liquidity_sensitivity")
        if "survivorship_and_universe_policy_not_promotion_grade" in blockers:
            next_audits.append("survivorship_universe_policy_review")
    elif representatives:
        next_audits.append("strict_audit_top_family_representatives")

    return {
        "run_id": "phase2-search-core-v2-plan",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V2_VERSION,
        "scope": "family_first_real_parameter_search_planning",
        "not_claiming_tradable_alpha": True,
        "promotion_policy": {
            "recent_screen_role": "budget_allocation_not_keep_evidence",
            "full_history_role": "family_representative_selection",
            "strict_audit_role": "blocker_discovery_before_keep_review",
            "scale_twin_policy": "dedupe_direct_CSRank_ZScore_twins_in_early_search",
            "shadow_policy": "preserve_recent_tail_and_exposure_heavy_candidates_without_deleting",
        },
        "input_reports": {
            "fast_screen": fast.get("ledger_path") or fast.get("source_report") or "provided_dict",
            "full_history": full.get("ledger_path") or full.get("source_report") if full else None,
            "strict_audit_candidate_id": strict.get("candidate_id") if strict else None,
        },
        "candidate_counts": {
            "fast_after_scale_dedupe": len(fast_candidates),
            "full_history_after_scale_dedupe": len(full_candidates),
            "scale_twin_duplicate_count": len(scale_duplicates),
        },
        "family_budget": family_budget,
        "promoted_representatives": representatives,
        "shadow_queues": shadow_queues,
        "scale_twin_duplicates": scale_duplicates[:64],
        "feature_store_precompute_plan": _extract_precompute_targets(representatives, strict),
        "next_audits": next_audits,
        "decision": "CONTINUE_PHASE2_SEARCH_CORE_V2",
    }
