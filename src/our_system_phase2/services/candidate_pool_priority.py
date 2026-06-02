from __future__ import annotations

from typing import Any


CANDIDATE_POOL_PRIORITY_VERSION = "candidate-pool-source-priority-v1-2026-05-28"

DEFAULT_SOURCE_WEIGHTS = {
    "incumbent": 1.0,
    "r0_cem_led": 1.0,
    "ast_repair": 0.9,
    "agnostic_freeform_ast": 1.0,
    "formula_gen_v2_repair_expansion": 1.05,
    "event_derived_feature_layer": 0.8,
    "cn_research_feature_layer_v2": 0.95,
    "fundamental_pit_feature_layer": 0.95,
    "cn_flow_liquidity_feature_layer": 0.95,
    "cn_underutilized_field_feature_layer": 0.95,
    "research_factor_feature_layer": 0.95,
    "legacy_or_non_event": 0.75,
}


def candidate_source(row: dict[str, Any]) -> str:
    return str(
        row.get("source_lane")
        or row.get("source_generator")
        or row.get("generator")
        or row.get("feature_adapter")
        or row.get("source_mode")
        or "unknown"
    )


def pool_priority_score(row: dict[str, Any]) -> float:
    source = candidate_source(row)
    score = float(DEFAULT_SOURCE_WEIGHTS.get(source, 0.75))
    if bool(row.get("contains_new_event_adapter_field")):
        score += 0.10
    if bool(row.get("contains_fundamental_field")):
        score += 0.05
    if bool(row.get("contains_flow_liquidity_field")):
        score += 0.06
    if bool(row.get("contains_capacity_field")):
        score += 0.03
    if row.get("diagnostic_role") == "interaction_factor":
        score += 0.05
    if row.get("diagnostic_role") == "r3_secondary_gate":
        score -= 0.20
    if row.get("leakage_flag") and "unsafe_same_day" in str(row.get("leakage_flag")):
        score -= 0.05
    return round(max(0.05, min(1.50, score)), 6)


def source_quota_group(row: dict[str, Any]) -> str:
    source = candidate_source(row)
    event_family = str(row.get("event_family") or "none")
    diagnostic_role = str(row.get("diagnostic_role") or "unknown")
    return f"{source}:{diagnostic_role}:{event_family}"


def source_credit_cap_basis(row: dict[str, Any]) -> str:
    return str(row.get("search_memory_key") or row.get("expr_hash") or row.get("candidate_id") or "missing_credit_cap_basis")


def enrich_candidate_pool_priority(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["pool_priority_version"] = CANDIDATE_POOL_PRIORITY_VERSION
    out["pool_priority_score"] = pool_priority_score(out)
    out["source_quota_group"] = source_quota_group(out)
    out["source_credit_cap_basis"] = source_credit_cap_basis(out)
    out["source_credit_policy"] = "metadata_only_opt_in_no_locked_selector_behavior_change"
    return out


def enrich_candidate_pool_priorities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [enrich_candidate_pool_priority(row) for row in rows]

