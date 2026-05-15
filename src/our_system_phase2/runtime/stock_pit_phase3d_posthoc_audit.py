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

from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


FIELD_GROUPS: dict[str, set[str]] = {
    "price": {"open", "high", "low", "close", "vwap", "ret", "returns"},
    "flow": {"amount", "volume", "turnover", "turnover_rate"},
    "cap": {"final_total_market_cap", "final_float_market_cap", "total_market_cap", "float_market_cap"},
    "limit": {"limit_up", "limit_down", "limitup", "limitdown"},
    "state": {"trend", "regime", "sector", "industry"},
}

TEMPORAL_OPS = {"Delay", "Delta", "Mean", "Std", "Mom", "Corr", "Cov", "Decay", "TsRank", "RankTs"}
PATHOLOGY_FLAGS = {
    "operator_pathology",
    "complexity_overfit",
    "turnover_too_high",
    "gap_dependency",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or "cluster_missing")


def _phase3_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]


def _phase3b_baseline_clusters(rows: list[dict[str, Any]], turnover_max: float) -> set[str]:
    out: set[str] = set()
    for row in rows:
        if row.get("aggregate_source_kind") != "phase3b_union_baseline":
            continue
        if _deployable(row, turnover_max=turnover_max):
            out.add(_cluster_id(row))
    return out


def _deployable(row: dict[str, Any], *, turnover_max: float) -> bool:
    if row.get("aggregate_source_kind") == "phase3b_union_baseline":
        return _safe_bool(row.get("portfolio_replay_pass")) and _safe_bool(row.get("cost_survives"))
    return _deployable_pass(row, turnover_max=turnover_max)


def _deployable_rows(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    return [row for row in rows if _deployable(row, turnover_max=turnover_max)]


def _fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or "")))


def _operators(expression: str) -> list[str]:
    return re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression or "")


def _field_families(expression: str) -> list[str]:
    fields = _fields(expression)
    families: set[str] = set()
    for field in fields:
        low = field.lower()
        matched = False
        for family, members in FIELD_GROUPS.items():
            if low in members or any(token in low for token in members):
                families.add(family)
                matched = True
        if not matched:
            families.add("other")
    return sorted(families)


def _max_depth(expression: str) -> int:
    depth = 0
    max_depth = 0
    for char in expression or "":
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    return max_depth


def _max_product_arity(expression: str) -> int:
    # The DSL uses nested binary Mul, so count a simple upper bound from contiguous Mul calls.
    return len(re.findall(r"\bMul\s*\(", expression or ""))


def _anatomy(row: dict[str, Any]) -> dict[str, Any]:
    expression = str(row.get("expression") or "")
    ops = _operators(expression)
    fields = _fields(expression)
    families = _field_families(expression)
    return {
        "field_list": "|".join(fields),
        "field_family_list": "|".join(families),
        "operator_list": "|".join(sorted(set(ops))),
        "tree_depth": _max_depth(expression),
        "temporal_op_count": sum(1 for op in ops if op in TEMPORAL_OPS),
        "corr_op_count": sum(1 for op in ops if op == "Corr"),
        "product_op_count": sum(1 for op in ops if op == "Mul"),
        "product_arity_proxy": _max_product_arity(expression),
        "turnover": _safe_float(row.get("strict_mean_one_way_turnover"), default=float("nan")),
        "mechanism_label": row.get("mechanism_label") or row.get("primitive_family") or row.get("proposal_kind") or "unknown",
    }


def _cluster_sets(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in _phase3_rows(rows):
        if _deployable(row, turnover_max=turnover_max):
            out[str(row.get("ablation_arm") or "unknown")].add(_cluster_id(row))
    return out


def _representative_for_cluster(rows: list[dict[str, Any]], cluster_id: str, *, turnover_max: float) -> dict[str, Any] | None:
    candidates = [
        row
        for row in _phase3_rows(rows)
        if _cluster_id(row) == cluster_id and _deployable(row, turnover_max=turnover_max)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (
            _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0),
            -_safe_float(row.get("portfolio_replay_long_only_sortino"), default=0.0),
            str(row.get("candidate_id") or ""),
        ),
    )[0]


def build_sm_pm_overlap(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    by_arm = _cluster_sets(rows, turnover_max=turnover_max)
    sm = by_arm.get("Phase3C_SM_mixed", set())
    pm = by_arm.get("Phase3C_PM_mixed", set())
    overlap = sm & pm
    return [
        {
            "left_arm": "Phase3C_SM_mixed",
            "right_arm": "Phase3C_PM_mixed",
            "sm_deployable_clusters": len(sm),
            "pm_deployable_clusters": len(pm),
            "overlap": len(overlap),
            "sm_only": len(sm - pm),
            "pm_only": len(pm - sm),
            "union": len(sm | pm),
            "jaccard": round(len(overlap) / max(1, len(sm | pm)), 6),
            "sm_only_cluster_ids": "|".join(sorted(sm - pm)),
            "pm_only_cluster_ids": "|".join(sorted(pm - sm)),
            "overlap_cluster_ids": "|".join(sorted(overlap)),
        }
    ]


def build_open_ended_anatomy(rows: list[dict[str, Any]], *, turnover_max: float, baseline_clusters: set[str]) -> list[dict[str, Any]]:
    deployable = [
        row
        for row in _phase3_rows(rows)
        if row.get("phase3_budget_bucket") == "agnostic_freeform_ast" and _deployable(row, turnover_max=turnover_max)
    ]
    best_by_cluster: dict[str, dict[str, Any]] = {}
    for row in deployable:
        cluster = _cluster_id(row)
        previous = best_by_cluster.get(cluster)
        if previous is None or _safe_float(row.get("strict_mean_one_way_turnover"), 999.0) < _safe_float(previous.get("strict_mean_one_way_turnover"), 999.0):
            best_by_cluster[cluster] = row
    output = []
    for cluster, row in sorted(best_by_cluster.items()):
        item = {
            "cluster_id": cluster,
            "new_vs_phase3B_union": cluster not in baseline_clusters,
            "ablation_arm": row.get("ablation_arm"),
            "source_seed": row.get("source_seed"),
            "candidate_id": row.get("candidate_id"),
            "expression": row.get("expression"),
            "raw_member_count": sum(1 for member in deployable if _cluster_id(member) == cluster),
            "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
            "portfolio_replay_long_only_sortino": row.get("portfolio_replay_long_only_sortino"),
            "portfolio_replay_long_only_net_mean": row.get("portfolio_replay_long_only_net_mean"),
        }
        item.update(_anatomy(row))
        output.append(item)
    return output


def build_repair_expansion_audit(rows: list[dict[str, Any]], *, turnover_max: float, baseline_clusters: set[str]) -> list[dict[str, Any]]:
    lane_rows = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "formula_gen_v2_repair_expansion"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        grouped[str(row.get("proposal_kind") or row.get("primitive_family") or "unknown")].append(row)
    output = []
    for action, group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _deployable(row, turnover_max=turnover_max)]
        clusters = {_cluster_id(row) for row in deployable}
        escaped = [
            row
            for row in deployable
            if row.get("parent_signal_cluster_id") and str(row.get("parent_signal_cluster_id")) != _cluster_id(row)
        ]
        output.append(
            {
                "repair_action": action,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "deployable_rows": len(deployable),
                "deployable_clusters": len(clusters),
                "new_vs_phase3B_union_clusters": len(clusters - baseline_clusters),
                "cluster_ids": "|".join(sorted(clusters)),
                "new_cluster_ids": "|".join(sorted(clusters - baseline_clusters)),
                "escaped_parent_cluster_rows": len(escaped),
                "escaped_but_not_new_rows": sum(1 for row in escaped if _cluster_id(row) in baseline_clusters),
                "median_turnover": _median([_safe_float(row.get("strict_mean_one_way_turnover"), default=float("nan")) for row in deployable]),
            }
        )
    return output


def build_defined_direct_failure_audit(rows: list[dict[str, Any]], *, turnover_max: float, baseline_clusters: set[str]) -> list[dict[str, Any]]:
    lane_rows = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "formula_gen_v2_defined"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        grouped[str(row.get("primitive_family") or row.get("proposal_kind") or "unknown")].append(row)
    output = []
    for family, group in sorted(grouped.items()):
        deployable = [row for row in group if _deployable(row, turnover_max=turnover_max)]
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        clusters = {_cluster_id(row) for row in deployable}
        blockers = Counter()
        for row in group:
            flags = row.get("strict_blocker_flags")
            if isinstance(flags, list):
                blockers.update(str(flag) for flag in flags)
            if not _safe_bool(row.get("cost_survives")):
                blockers["cost_or_tradability_fail"] += 1
            if _safe_float(row.get("strict_mean_one_way_turnover"), 999.0) > turnover_max:
                blockers["turnover_too_high"] += 1
            if not _safe_bool(row.get("portfolio_replay_pass")):
                blockers["replay_fail"] += 1
        output.append(
            {
                "family": family,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "deployable_rows": len(deployable),
                "deployable_clusters": len(clusters),
                "new_vs_phase3B_union_clusters": len(clusters - baseline_clusters),
                "known_duplicate_clusters": len(clusters & baseline_clusters),
                "top_failure_reasons": "|".join(f"{k}:{v}" for k, v in blockers.most_common(6)),
                "median_turnover": _median([_safe_float(row.get("strict_mean_one_way_turnover"), default=float("nan")) for row in group]),
            }
        )
    return output


def build_ast_repair_collapse_audit(rows: list[dict[str, Any]], *, turnover_max: float, baseline_clusters: set[str]) -> list[dict[str, Any]]:
    lane_rows = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "ast_failure_aware_repair"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane_rows:
        if _non_gap_replay_pass(row):
            grouped[_cluster_id(row)].append(row)
    output = []
    for cluster, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        deployable = [row for row in group if _deployable(row, turnover_max=turnover_max)]
        policies = Counter(str(row.get("repair_policy") or row.get("proposal_kind") or "unknown") for row in group)
        fields = Counter()
        operators = Counter()
        parents = Counter()
        for row in group:
            fields.update(_field_families(str(row.get("expression") or "")))
            operators.update(_operators(str(row.get("expression") or "")))
            if row.get("parent_signal_cluster_id"):
                parents[str(row.get("parent_signal_cluster_id"))] += 1
            elif row.get("parent_cluster"):
                parents[str(row.get("parent_cluster"))] += 1
        output.append(
            {
                "cluster_id": cluster,
                "raw_non_gap_pass": len(group),
                "deployable_rows": len(deployable),
                "is_new_vs_phase3B_union": cluster not in baseline_clusters,
                "cluster_capped_credit": 1 if deployable else 0,
                "top_repair_policies": "|".join(f"{k}:{v}" for k, v in policies.most_common(5)),
                "top_field_families": "|".join(f"{k}:{v}" for k, v in fields.most_common(5)),
                "top_operators": "|".join(f"{k}:{v}" for k, v in operators.most_common(8)),
                "top_parent_clusters": "|".join(f"{k}:{v}" for k, v in parents.most_common(5)),
                "representative_expression": group[0].get("expression"),
            }
        )
    return output


def build_cumulative_baseline(
    *,
    phase3b_baseline_path: Path,
    rows: list[dict[str, Any]],
    aggregate: dict[str, Any],
    output_path: Path,
    turnover_max: float,
) -> dict[str, Any]:
    phase3b = _read_json(phase3b_baseline_path)
    phase3b_reps = list(phase3b.get("deployable_representatives") or [])
    new_cluster_ids = set((aggregate.get("global_union_metrics") or {}).get("new_deployable_cluster_ids_vs_phase3B_union") or [])
    phase3c_reps = []
    for cluster_id in sorted(new_cluster_ids):
        row = _representative_for_cluster(rows, cluster_id, turnover_max=turnover_max)
        if row is None:
            continue
        phase3c_reps.append(
            {
                "cluster_id": f"phase3c_{cluster_id}",
                "representative_expression": row.get("expression"),
                "candidate_id": row.get("candidate_id"),
                "ablation_arm": row.get("ablation_arm"),
                "source_seed": row.get("source_seed"),
                "phase3_budget_bucket": row.get("phase3_budget_bucket"),
                "selection_policy": row.get("selection_policy"),
                "source_phase3c_global_cluster_id": cluster_id,
                "source_commit": "7f4ff5e",
                "cluster_member_count": sum(
                    1
                    for member in _phase3_rows(rows)
                    if _cluster_id(member) == cluster_id and _deployable(member, turnover_max=turnover_max)
                ),
            }
        )
    payload = {
        "baseline_name": "phase3B_plus_phase3C_large_union_20260514",
        "source_phase3b_baseline": str(phase3b_baseline_path),
        "source_phase3c_report": "reports/phase3c_large_full_20260513/phase3C_large_global_aggregate.json",
        "source_phase3c_commit": "7f4ff5e",
        "phase3b_source_declared_deployable_cluster_count": phase3b.get("global_deployable_cluster_count"),
        "phase3b_representative_count": len(phase3b_reps),
        "phase3c_new_deployable_cluster_count": len(new_cluster_ids),
        "phase3c_new_representative_count": len(phase3c_reps),
        "declared_cumulative_cluster_count": int(phase3b.get("global_deployable_cluster_count") or len(phase3b_reps)) + len(new_cluster_ids),
        "notes": (
            "Representative list intentionally preserves Phase3B source count plus Phase3C new cluster representatives. "
            "Future aggregates should recluster these representatives with fresh candidates, so reclustered baseline count may be lower."
        ),
        "cluster_ids": [str(item.get("cluster_id")) for item in phase3b_reps]
        + [str(item.get("cluster_id")) for item in phase3c_reps],
        "deployable_representatives": phase3b_reps + phase3c_reps,
    }
    _write_json(output_path, payload)
    return payload


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    middle = len(clean) // 2
    if len(clean) % 2:
        return round(clean[middle], 6)
    return round((clean[middle - 1] + clean[middle]) / 2.0, 6)


def write_markdown(
    *,
    path: Path,
    aggregate: dict[str, Any],
    sm_pm: list[dict[str, Any]],
    open_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    defined_rows: list[dict[str, Any]],
    ast_rows: list[dict[str, Any]],
    cumulative: dict[str, Any],
) -> None:
    g = aggregate.get("global_union_metrics") or {}
    smpm = sm_pm[0] if sm_pm else {}
    lines = [
        "# Phase3D Preflight Posthoc Audit",
        "",
        f"- created_at: {datetime.now(timezone.utc).isoformat()}",
        "- status: completed",
        "- decision: PREPARE_PHASE3D_REALLOCATION",
        "",
        "## Phase3C Large Baseline",
        "",
        f"- audited: {g.get('audited')}",
        f"- global_deployable_clusters: {g.get('global_deployable_clusters')}",
        f"- new_deployable_clusters_vs_phase3B_union: {g.get('new_deployable_clusters_vs_phase3B_union')}",
        f"- raw_non_gap_pass: {g.get('raw_non_gap_pass')}",
        f"- global_top_cluster_share: {g.get('global_top_cluster_share')}",
        "",
        "## Cumulative Baseline",
        "",
        f"- declared_cumulative_cluster_count: {cumulative.get('declared_cumulative_cluster_count')}",
        f"- phase3b_representative_count: {cumulative.get('phase3b_representative_count')}",
        f"- phase3c_new_representative_count: {cumulative.get('phase3c_new_representative_count')}",
        "- note: future Phase3D new-cluster metrics should be measured against this cumulative representative baseline, then reclustered.",
        "",
        "## SM/PM Overlap",
        "",
        f"- SM deployable clusters: {smpm.get('sm_deployable_clusters')}",
        f"- PM deployable clusters: {smpm.get('pm_deployable_clusters')}",
        f"- overlap: {smpm.get('overlap')}",
        f"- union: {smpm.get('union')}",
        f"- jaccard: {smpm.get('jaccard')}",
        "",
        "## Module Findings",
        "",
        f"- agnostic_freeform_ast deployable clusters: {len(open_rows)}",
        f"- formula_gen_v2_repair_expansion action buckets: {len(repair_rows)}",
        f"- formula_gen_v2_defined direct family buckets: {len(defined_rows)}",
        f"- AST repair non-gap clusters: {len(ast_rows)}",
        "",
        "## Operational Conclusions",
        "",
        "- Keep SM mixed as primary control.",
        "- Keep PM mixed as productive secondary, but only with cluster-credit cap.",
        "- Promote agnostic_freeform_ast and formula_gen_v2_repair_expansion into Phase3D budget.",
        "- Demote formula_gen_v2_defined direct to 0%-2% unless used as repair source.",
        "- Remove novelty_diagnostic from official budget.",
        "- AST repair raw pass must be cluster-capped before any credit update.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Posthoc audit for Phase3C large results before Phase3D reallocation.")
    parser.add_argument("--aggregate-json", type=Path, default=Path("reports/phase3c_large_full_20260513/phase3C_large_global_aggregate.json"))
    parser.add_argument("--clustered-rows-json", type=Path, default=Path("reports/phase3c_large_full_20260513/phase3C_large_global_clustered_rows.json"))
    parser.add_argument("--phase3b-baseline-json", type=Path, default=Path("src/our_system_phase2/runtime/baselines/phase3B_union_deployable_clusters_20260512.json"))
    parser.add_argument("--output-root", type=Path, default=Path("reports/phase3d_reallocation_preflight_20260514"))
    parser.add_argument("--cumulative-baseline-json", type=Path, default=Path("src/our_system_phase2/runtime/baselines/phase3C_cumulative_deployable_clusters_20260514.json"))
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    aggregate = _read_json(args.aggregate_json)
    clustered_payload = _read_json(args.clustered_rows_json)
    rows = clustered_payload.get("rows") if isinstance(clustered_payload, dict) else clustered_payload
    if not isinstance(rows, list):
        raise TypeError("clustered rows payload must contain a list under 'rows'")

    baseline_clusters = _phase3b_baseline_clusters(rows, args.turnover_max)
    sm_pm = build_sm_pm_overlap(rows, turnover_max=args.turnover_max)
    open_rows = build_open_ended_anatomy(rows, turnover_max=args.turnover_max, baseline_clusters=baseline_clusters)
    repair_rows = build_repair_expansion_audit(rows, turnover_max=args.turnover_max, baseline_clusters=baseline_clusters)
    defined_rows = build_defined_direct_failure_audit(rows, turnover_max=args.turnover_max, baseline_clusters=baseline_clusters)
    ast_rows = build_ast_repair_collapse_audit(rows, turnover_max=args.turnover_max, baseline_clusters=baseline_clusters)
    cumulative = build_cumulative_baseline(
        phase3b_baseline_path=args.phase3b_baseline_json,
        rows=rows,
        aggregate=aggregate,
        output_path=args.cumulative_baseline_json,
        turnover_max=args.turnover_max,
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_root / "phase3d_sm_pm_overlap.csv", sm_pm)
    _write_csv(args.output_root / "phase3d_open_ended_cluster_anatomy.csv", open_rows)
    _write_csv(args.output_root / "phase3d_repair_expansion_audit.csv", repair_rows)
    _write_csv(args.output_root / "phase3d_defined_direct_failure_audit.csv", defined_rows)
    _write_csv(args.output_root / "phase3d_ast_repair_raw_collapse_audit.csv", ast_rows)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "decision": "PREPARE_PHASE3D_REALLOCATION",
        "aggregate_json": str(args.aggregate_json),
        "clustered_rows_json": str(args.clustered_rows_json),
        "phase3b_baseline_json": str(args.phase3b_baseline_json),
        "cumulative_baseline_json": str(args.cumulative_baseline_json),
        "phase3c_global_union_metrics": aggregate.get("global_union_metrics"),
        "sm_pm_overlap": sm_pm[0] if sm_pm else {},
        "open_ended_deployable_cluster_count": len(open_rows),
        "repair_expansion_action_bucket_count": len(repair_rows),
        "defined_direct_family_bucket_count": len(defined_rows),
        "ast_repair_non_gap_cluster_count": len(ast_rows),
        "cumulative_baseline": {
            key: cumulative.get(key)
            for key in [
                "baseline_name",
                "phase3b_source_declared_deployable_cluster_count",
                "phase3b_representative_count",
                "phase3c_new_deployable_cluster_count",
                "phase3c_new_representative_count",
                "declared_cumulative_cluster_count",
            ]
        },
        "outputs": {
            "sm_pm_overlap": str(args.output_root / "phase3d_sm_pm_overlap.csv"),
            "open_ended_cluster_anatomy": str(args.output_root / "phase3d_open_ended_cluster_anatomy.csv"),
            "repair_expansion_audit": str(args.output_root / "phase3d_repair_expansion_audit.csv"),
            "defined_direct_failure_audit": str(args.output_root / "phase3d_defined_direct_failure_audit.csv"),
            "ast_repair_raw_collapse_audit": str(args.output_root / "phase3d_ast_repair_raw_collapse_audit.csv"),
            "markdown": str(args.output_root / "PHASE3D_REALLOCATION_PREFLIGHT_2026-05-14.md"),
        },
    }
    _write_json(args.output_root / "phase3d_reallocation_preflight_summary.json", summary)
    write_markdown(
        path=args.output_root / "PHASE3D_REALLOCATION_PREFLIGHT_2026-05-14.md",
        aggregate=aggregate,
        sm_pm=sm_pm,
        open_rows=open_rows,
        repair_rows=repair_rows,
        defined_rows=defined_rows,
        ast_rows=ast_rows,
        cumulative=cumulative,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
