"""Phase3L-A champion cluster selection.

This is a no-search, no-replay scoring pass. It consumes the completed
149-entry representative registry plus locked J2/J4 and K-B fresh G2 book
artifacts, then produces a daily-evidence champion shortlist for deeper audit.

The output is intentionally not a production proof. Grade A here means
"eligible for Alpha Proof Pack deep audit", not "trade-ready".
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_149 = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_LOCKED_FILTERS = Path("runtime/baselines/phase3j_locked_book_filters.json")
DEFAULT_KB_CLUSTER_METRICS = Path("reports/phase3k_b_locked_filter_generalization_20260516/phase3k_b_cluster_metrics.csv")
DEFAULT_KB_NEW_VS_149 = Path("reports/phase3k_c_complete_149_registry_20260517/phase3k_c_kb_new_vs_149.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_champion_selection_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _round(value: Any, digits: int = 6) -> float | None:
    out = _safe_float(value)
    return round(out, digits) if out is not None else None


def _canonical_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression or "")


def _operators(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression or "")))


def _fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")))


def _parse_jsonish_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [part for part in re.split(r"[|,]", text) if part]
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return [str(payload)]


def _field_families(expression: str, existing: Any = None) -> list[str]:
    parsed = _parse_jsonish_list(existing)
    if parsed:
        return sorted(set(parsed))
    families: set[str] = set()
    for field in _fields(expression):
        name = field.lower()
        if any(token in name for token in ["open", "high", "low", "close", "vwap"]):
            families.add("price")
        if any(token in name for token in ["amount", "volume", "turnover"]):
            families.add("flow")
        if "cap" in name or "market" in name:
            families.add("cap")
        if "limit" in name:
            families.add("limit")
    return sorted(families or ["unknown"])


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(hi, max(lo, value))


def _cost_component(cost: float | None) -> float:
    if cost is None:
        return 0.35
    if cost <= 0:
        return 0.0
    return _clip(cost / 5.0)


def _turnover_component(p90_turnover: float | None) -> float:
    if p90_turnover is None:
        return 0.30
    if p90_turnover <= 0.15:
        return 1.0
    if p90_turnover <= 0.30:
        return 0.75 - (p90_turnover - 0.15) / 0.15 * 0.20
    if p90_turnover <= 0.50:
        return 0.45 - (p90_turnover - 0.30) / 0.20 * 0.30
    return 0.05


def _capacity_component(capacity: float | None) -> float:
    if capacity is None or capacity <= 0:
        return 0.30
    # 5M is weak, 100M+ is strong for this daily proxy.
    return _clip((math.log10(capacity) - math.log10(5_000_000.0)) / (math.log10(100_000_000.0) - math.log10(5_000_000.0)))


def _corr_component(max_corr: float | None) -> float:
    if max_corr is None:
        return 0.55
    if max_corr <= 0.50:
        return 1.0
    if max_corr <= 0.80:
        return 0.70 - (max_corr - 0.50) / 0.30 * 0.30
    if max_corr <= 0.90:
        return 0.30
    return 0.10


def _feasibility_component(limit_hit: float | None, suspension: float | None) -> float:
    loss = (limit_hit or 0.0) + (suspension or 0.0)
    return 1.0 - _clip(loss / 0.12)


def _book_component(retained_j2: bool, retained_j4: bool, source_scope: str) -> float:
    if retained_j4:
        return 1.0
    if retained_j2:
        return 0.78
    if source_scope == "kb_fresh_g2":
        return 0.45
    return 0.28


def _known_simple_family(expression: str, cluster_id: str) -> bool:
    expr = _canonical_expression(expression).lower()
    if cluster_id in {"cluster_001", "registry_001"}:
        return True
    simple_patterns = [
        r"^csrank\(mean\(\$close,\d+\)\)$",
        r"^csrank\(mean\(\$open,\d+\)\)$",
        r"^csrank\(std\(\$close,\d+\)\)$",
    ]
    return any(re.match(pattern, expr) for pattern in simple_patterns)


def _candidate_from_locked(row: dict[str, Any], *, retained_j2: bool, retained_j4: bool) -> dict[str, Any]:
    expression = str(row.get("representative_expression") or "")
    cluster_id = str(row.get("cluster_id") or "")
    return {
        "candidate_uid": f"phase3j_locked:{cluster_id}",
        "cluster_id": cluster_id,
        "source_scope": "phase3j_locked_book",
        "source_phase": "Phase3J",
        "representative_expression": expression,
        "canonical_expression": _canonical_expression(expression),
        "representative_candidate_id": row.get("representative_candidate_id") or "",
        "source_lane": row.get("source_lane") or "",
        "field_families": "|".join(_field_families(expression)),
        "operator_families": "|".join(_parse_jsonish_list(row.get("operator_families")) or _operators(expression)),
        "retained_by_j2": retained_j2,
        "retained_by_j4_relaxed": retained_j4,
        "new_vs_149_proxy": False,
        "known_vs_149_reason": "existing_locked_phase3j_book",
        "max_corr_to_149_registry_proxy": None,
        "p90_turnover": _safe_float(row.get("p90_replay_turnover")),
        "median_turnover": _safe_float(row.get("median_replay_turnover")),
        "cost_adjusted_score": _safe_float(row.get("cost_adjusted_score")),
        "capacity_proxy": _safe_float(row.get("capacity_proxy")),
        "median_amount_20d": _safe_float(row.get("median_amount_20d")),
        "limit_hit_rate": _safe_float(row.get("limit_hit_rate")),
        "suspension_rate": _safe_float(row.get("suspension_rate")),
        "raw_pass_count": _safe_int(row.get("raw_pass_count"), 1),
        "deployable_count": _safe_int(row.get("deployable_count"), 1),
    }


def _candidate_from_kb(row: dict[str, str], novelty: dict[str, dict[str, str]], memberships: dict[str, set[str]]) -> dict[str, Any]:
    cluster_id = str(row.get("cluster_id") or "")
    expression = str(row.get("representative_expression") or "")
    novelty_row = novelty.get(cluster_id, {})
    return {
        "candidate_uid": f"phase3k_b_fresh:{cluster_id}",
        "cluster_id": cluster_id,
        "source_scope": "kb_fresh_g2",
        "source_phase": "Phase3K-B",
        "representative_expression": expression,
        "canonical_expression": _canonical_expression(expression),
        "representative_candidate_id": row.get("representative_candidate_id") or "",
        "source_lane": row.get("source_lane") or "",
        "field_families": "|".join(_field_families(expression, row.get("field_families"))),
        "operator_families": "|".join(_parse_jsonish_list(row.get("operator_families")) or _operators(expression)),
        "retained_by_j2": cluster_id in memberships.get("J2_fresh", set()),
        "retained_by_j4_relaxed": cluster_id in memberships.get("J4_relaxed_fresh", set()),
        "new_vs_149_proxy": _as_bool(novelty_row.get("new_vs_149_proxy")),
        "known_vs_149_reason": novelty_row.get("known_vs_149_reason") or "",
        "max_corr_to_149_registry_proxy": _safe_float(novelty_row.get("max_corr_to_149_registry_proxy") or row.get("max_corr_to_registry")),
        "p90_turnover": _safe_float(row.get("p90_replay_turnover")),
        "median_turnover": _safe_float(row.get("median_replay_turnover")),
        "cost_adjusted_score": _safe_float(row.get("cost_adjusted_score")),
        "capacity_proxy": _safe_float(row.get("capacity_proxy")),
        "median_amount_20d": _safe_float(row.get("median_amount_20d")),
        "limit_hit_rate": _safe_float(row.get("limit_hit_rate")),
        "suspension_rate": _safe_float(row.get("suspension_rate")),
        "raw_pass_count": _safe_int(row.get("raw_pass_count"), 1),
        "deployable_count": _safe_int(row.get("deployable_count"), 1),
    }


def _candidate_from_registry(row: dict[str, Any]) -> dict[str, Any]:
    expression = str(row.get("representative_expression") or "")
    registry_id = str(row.get("registry_entry_id") or row.get("cluster_id") or "")
    return {
        "candidate_uid": f"registry149:{registry_id}",
        "cluster_id": registry_id,
        "legacy_cluster_id": row.get("legacy_cluster_id") or "",
        "source_scope": "registry_149",
        "source_phase": row.get("first_seen_phase") or row.get("registry_source") or "registry_149",
        "representative_expression": expression,
        "canonical_expression": _canonical_expression(expression),
        "representative_candidate_id": row.get("candidate_id") or "",
        "source_lane": row.get("source_lane") or "",
        "field_families": "|".join(_field_families(expression, row.get("field_list"))),
        "operator_families": "|".join(_parse_jsonish_list(row.get("operator_families")) or _operators(expression)),
        "retained_by_j2": False,
        "retained_by_j4_relaxed": False,
        "new_vs_149_proxy": False,
        "known_vs_149_reason": "registry_member",
        "max_corr_to_149_registry_proxy": None,
        "p90_turnover": _safe_float(row.get("strict_mean_one_way_turnover") or row.get("portfolio_replay_avg_one_way_turnover")),
        "median_turnover": _safe_float(row.get("portfolio_replay_avg_one_way_turnover") or row.get("strict_mean_one_way_turnover")),
        "cost_adjusted_score": _safe_float(row.get("strict_cost_adjusted_sortino") or row.get("portfolio_replay_long_only_sortino")),
        "capacity_proxy": None,
        "median_amount_20d": None,
        "limit_hit_rate": None,
        "suspension_rate": None,
        "raw_pass_count": 1,
        "deployable_count": 1,
    }


def _score_candidate(row: dict[str, Any]) -> dict[str, Any]:
    p90 = _safe_float(row.get("p90_turnover"))
    cost = _safe_float(row.get("cost_adjusted_score"))
    capacity = _safe_float(row.get("capacity_proxy"))
    max_corr = _safe_float(row.get("max_corr_to_149_registry_proxy"))
    limit_hit = _safe_float(row.get("limit_hit_rate"))
    suspension = _safe_float(row.get("suspension_rate"))
    retained_j2 = _as_bool(row.get("retained_by_j2"))
    retained_j4 = _as_bool(row.get("retained_by_j4_relaxed"))
    source_scope = str(row.get("source_scope") or "")
    raw_pass_count = _safe_int(row.get("raw_pass_count"), 1)
    deployable_count = _safe_int(row.get("deployable_count"), 1)

    discovery_component = _clip(0.55 * _cost_component(cost) + 0.25 * _clip(deployable_count / 3.0) + 0.20 * _clip(raw_pass_count / 4.0))
    book_component = _book_component(retained_j2, retained_j4, source_scope)
    cost_component = _cost_component(cost)
    turnover_component = _turnover_component(p90)
    capacity_component = _capacity_component(capacity)
    corr_component = _corr_component(max_corr)
    feasibility_component = _feasibility_component(limit_hit, suspension)

    score = 100.0 * (
        0.22 * discovery_component
        + 0.18 * book_component
        + 0.18 * cost_component
        + 0.14 * turnover_component
        + 0.12 * capacity_component
        + 0.08 * corr_component
        + 0.08 * feasibility_component
    )

    penalties: list[str] = []
    if cost is not None and cost <= 0:
        score -= 22.0
        penalties.append("non_positive_cost_proxy")
    if p90 is not None and p90 > 0.45:
        score -= 12.0
        penalties.append("high_p90_turnover")
    if capacity is not None and capacity < 5_000_000:
        score -= 12.0
        penalties.append("very_low_capacity_proxy")
    if max_corr is not None and max_corr >= 0.90:
        score -= 8.0
        penalties.append("near_registry_duplicate")
    if _known_simple_family(str(row.get("representative_expression") or ""), str(row.get("cluster_id") or "")):
        score -= 8.0
        penalties.append("known_simple_or_overcrowded_family")

    evidence_complete = all(value is not None for value in [p90, cost, capacity])
    proof_gaps = [
        "subperiod_stability_not_yet_audited",
        "sign_flip_placebo_not_yet_audited",
        "low_order_ablation_not_yet_audited",
    ]
    if not evidence_complete:
        proof_gaps.append("daily_book_readiness_metrics_incomplete")

    grade = "C"
    if (
        score >= 70.0
        and evidence_complete
        and (retained_j4 or retained_j2)
        and (p90 is None or p90 <= 0.32)
        and (cost is not None and cost > 0.0)
        and (capacity is not None and capacity >= 5_000_000)
        and ((limit_hit or 0.0) + (suspension or 0.0) <= 0.08)
        and "known_simple_or_overcrowded_family" not in penalties
    ):
        grade = "A"
    elif score >= 52.0 and (retained_j4 or retained_j2 or (cost is not None and cost > 0.0)):
        grade = "B"

    row.update(
        {
            "champion_score": round(max(0.0, score), 6),
            "grade": grade,
            "discovery_strength_component": round(discovery_component, 6),
            "book_readiness_component": round(book_component, 6),
            "cost_proxy_component": round(cost_component, 6),
            "turnover_component": round(turnover_component, 6),
            "capacity_component": round(capacity_component, 6),
            "novelty_corr_component": round(corr_component, 6),
            "feasibility_component": round(feasibility_component, 6),
            "penalties": "|".join(penalties),
            "proof_gaps": "|".join(proof_gaps),
            "champion_decision": "ENTER_PHASE3L_C_DEEP_AUDIT" if grade == "A" else ("KEEP_AS_GRADE_B_RESERVE" if grade == "B" else "REGISTRY_ONLY_OR_REJECT_FOR_CHAMPION"),
        }
    )
    return row


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_expr: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[str]] = defaultdict(list)
    for row in candidates:
        key = str(row.get("canonical_expression") or row.get("candidate_uid"))
        sources[key].append(str(row.get("candidate_uid")))
        current = by_expr.get(key)
        if current is None or _safe_float(row.get("champion_score"), -1.0) > _safe_float(current.get("champion_score"), -1.0):
            by_expr[key] = row
    output = []
    for key, row in by_expr.items():
        item = dict(row)
        item["merged_duplicate_candidate_uids"] = "|".join(sorted(set(sources[key])))
        item["duplicate_candidate_count"] = len(set(sources[key]))
        output.append(item)
    return output


def _family_key(row: dict[str, Any]) -> str:
    fields = str(row.get("field_families") or "unknown")
    ops = str(row.get("operator_families") or "unknown")
    # Keep enough detail to avoid one primitive dominating the champion card list.
    return f"{fields}::{ops[:80]}"


def _select_champions(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    for row in sorted(rows, key=lambda item: _safe_float(item.get("champion_score"), 0.0), reverse=True):
        if row.get("grade") not in {"A", "B"}:
            continue
        source = str(row.get("source_lane") or row.get("source_scope") or "unknown")
        family = _family_key(row)
        if row.get("grade") == "A":
            if source_counts[source] >= 8:
                continue
            if family_counts[family] >= 4:
                continue
        else:
            if len([item for item in selected if item.get("grade") == "A"]) < 8:
                continue
            if source_counts[source] >= 10:
                continue
            if family_counts[family] >= 5:
                continue
        item = dict(row)
        item["champion_rank"] = len(selected) + 1
        selected.append(item)
        source_counts[source] += 1
        family_counts[family] += 1
        if len(selected) >= limit:
            break
    return selected


def _load_candidates(
    *,
    registry_path: Path,
    locked_filters_path: Path,
    kb_cluster_metrics_path: Path,
    kb_new_vs_149_path: Path,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    registry = _read_json(registry_path)
    for row in registry.get("deployable_representatives", []):
        candidates.append(_candidate_from_registry(row))

    locked = _read_json(locked_filters_path)
    j2_clusters = {str(item.get("cluster_id")) for item in locked.get("baseline_book_candidate", {}).get("clusters", [])}
    j4_clusters = {str(item.get("cluster_id")) for item in locked.get("liquidity_aware_overlay_candidate", {}).get("clusters", [])}
    locked_by_cluster: dict[str, dict[str, Any]] = {}
    for row in locked.get("baseline_book_candidate", {}).get("clusters", []):
        locked_by_cluster[str(row.get("cluster_id"))] = row
    for row in locked.get("liquidity_aware_overlay_candidate", {}).get("clusters", []):
        locked_by_cluster[str(row.get("cluster_id"))] = row
    for cluster_id, row in sorted(locked_by_cluster.items()):
        candidates.append(_candidate_from_locked(row, retained_j2=cluster_id in j2_clusters, retained_j4=cluster_id in j4_clusters))

    novelty_rows = _read_csv(kb_new_vs_149_path)
    novelty_by_cluster: dict[str, dict[str, str]] = {}
    memberships: dict[str, set[str]] = defaultdict(set)
    for row in novelty_rows:
        cluster_id = str(row.get("cluster_id") or "")
        book = str(row.get("book") or "")
        memberships[book].add(cluster_id)
        if book == "J0_fresh":
            novelty_by_cluster[cluster_id] = row
    for row in _read_csv(kb_cluster_metrics_path):
        candidates.append(_candidate_from_kb(row, novelty_by_cluster, memberships))

    return [_score_candidate(row) for row in candidates]


def _summarize(rows: list[dict[str, Any]], champions: list[dict[str, Any]]) -> dict[str, Any]:
    grade_counts = Counter(str(row.get("grade")) for row in rows)
    champ_grade_counts = Counter(str(row.get("grade")) for row in champions)
    source_counts = Counter(str(row.get("source_lane") or row.get("source_scope") or "unknown") for row in champions)
    grade_a = [row for row in champions if row.get("grade") == "A"]
    return {
        "candidate_count": len(rows),
        "grade_counts_all_scored": dict(sorted(grade_counts.items())),
        "champion_count": len(champions),
        "champion_grade_counts": dict(sorted(champ_grade_counts.items())),
        "grade_a_count": len(grade_a),
        "grade_b_count": len([row for row in champions if row.get("grade") == "B"]),
        "champion_source_lane_counts": dict(source_counts.most_common()),
        "grade_a_min_score": min((_safe_float(row.get("champion_score"), 0.0) for row in grade_a), default=None),
        "grade_a_max_score": max((_safe_float(row.get("champion_score"), 0.0) for row in grade_a), default=None),
        "scope": "daily-evidence champion shortlist only; not production-ready alpha proof",
    }


def _markdown(summary: dict[str, Any], champions: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3L-A Champion Cluster Selection",
        "",
        f"- created_at: `{summary['created_at']}`",
        f"- decision: `{summary['decision']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- champion_count: `{summary['champion_count']}`",
        f"- grade_a_count: `{summary['grade_a_count']}`",
        f"- grade_b_count: `{summary['grade_b_count']}`",
        "",
        "## Interpretation",
        "",
        "Grade A means eligible for Phase3L-C deep audit. It is not a production-ready alpha label.",
        "The current selection uses daily replay/book-readiness proxies, J2/J4 retention, cost/capacity proxies, and new-vs-149 proxy evidence.",
        "",
        "## Top Champions",
        "",
        "| rank | grade | score | cluster | source | lane | p90_turnover | cost | capacity | new_vs_149 | decision |",
        "| ---: | --- | ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in champions[:30]:
        lines.append(
            "| {rank} | {grade} | {score} | {cluster} | {scope} | {lane} | {turnover} | {cost} | {capacity} | {new} | {decision} |".format(
                rank=row.get("champion_rank", ""),
                grade=row.get("grade", ""),
                score=row.get("champion_score", ""),
                cluster=row.get("cluster_id", ""),
                scope=row.get("source_scope", ""),
                lane=row.get("source_lane", ""),
                turnover=_round(row.get("p90_turnover")),
                cost=_round(row.get("cost_adjusted_score")),
                capacity=_round(row.get("capacity_proxy")),
                new=row.get("new_vs_149_proxy", ""),
                decision=row.get("champion_decision", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Required Next Proof",
            "",
            "- subperiod stability",
            "- regime bucket performance",
            "- sign-flip placebo",
            "- low-order ablation",
            "- champion-book correlation and family caps",
            "",
            "## Scope",
            "",
            "- No new search was run.",
            "- No G2/J2/J4 parameter was changed.",
            "- No minute execution, live capacity, or production deployment is confirmed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry-149", type=Path, default=DEFAULT_REGISTRY_149)
    parser.add_argument("--locked-filters", type=Path, default=DEFAULT_LOCKED_FILTERS)
    parser.add_argument("--kb-cluster-metrics", type=Path, default=DEFAULT_KB_CLUSTER_METRICS)
    parser.add_argument("--kb-new-vs-149", type=Path, default=DEFAULT_KB_NEW_VS_149)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--champion-limit", type=int, default=30)
    args = parser.parse_args()

    scored = _dedupe_candidates(
        _load_candidates(
            registry_path=args.registry_149,
            locked_filters_path=args.locked_filters,
            kb_cluster_metrics_path=args.kb_cluster_metrics,
            kb_new_vs_149_path=args.kb_new_vs_149,
        )
    )
    scored = sorted(scored, key=lambda item: _safe_float(item.get("champion_score"), 0.0), reverse=True)
    champions = _select_champions(scored, args.champion_limit)
    summary = _summarize(scored, champions)
    summary.update(
        {
            "created_at": _now(),
            "experiment_id": "20260517_phase3l_a_champion_selection",
            "decision": "PASS_PHASE3L_A_CHAMPION_SELECTION" if summary["grade_a_count"] >= 8 else "HOLD_PHASE3L_A_INSUFFICIENT_GRADE_A",
            "inputs": {
                "registry_149": str(args.registry_149),
                "locked_filters": str(args.locked_filters),
                "kb_cluster_metrics": str(args.kb_cluster_metrics),
                "kb_new_vs_149": str(args.kb_new_vs_149),
            },
            "grading_policy": {
                "grade_a": "daily-evidence deep-audit candidate; requires complete daily book-readiness metrics, J2/J4 retention, positive cost proxy, acceptable p90 turnover/capacity, and no known simple-family penalty",
                "grade_b": "reserve candidate with useful daily evidence but weaker retention, capacity, turnover, or novelty profile",
                "grade_c": "registry-only or insufficient evidence for proof pack",
            },
        }
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_root / "phase3l_champion_clusters.csv", champions)
    _write_csv(args.output_root / "phase3l_all_cluster_scores.csv", scored)
    _write_json(args.output_root / "phase3l_champion_selection.json", {"summary": summary, "champions": champions})
    (args.output_root / "PHASE3L_CHAMPION_SELECTION_2026-05-17.md").write_text(_markdown(summary, champions), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
