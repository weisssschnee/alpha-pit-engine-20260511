from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.runtime.stock_pit_phase3d_posthoc_audit import (
    _anatomy,
    _cluster_id,
    _deployable,
    _field_families,
    _fields,
    _median,
    _operators,
    _phase3_rows,
    _read_json,
    _representative_for_cluster,
    _safe_bool,
    _safe_float,
    _write_csv,
    _write_json,
)
from our_system_phase2.services.stock_pit_phase3_repair import _non_gap_replay_pass


PRIMARY_ARM = "Phase3D_D3_SM_no_defined_direct"
SECONDARY_ARM = "Phase3D_D2_PM_open_repair"


def _global_metrics(aggregate: dict[str, Any]) -> dict[str, Any]:
    metrics = aggregate.get("global_union_metrics") or {}
    if not isinstance(metrics, dict):
        raise TypeError("aggregate global_union_metrics must be a dict")
    return metrics


def _cluster_sets_by_arm(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in _phase3_rows(rows):
        if _deployable(row, turnover_max=turnover_max):
            out[str(row.get("ablation_arm") or "unknown")].add(_cluster_id(row))
    return out


def build_d3_d2_overlap(rows: list[dict[str, Any]], *, turnover_max: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_arm = _cluster_sets_by_arm(rows, turnover_max=turnover_max)
    d3 = by_arm.get(PRIMARY_ARM, set())
    d2 = by_arm.get(SECONDARY_ARM, set())
    overlap = d3 & d2
    summary = [
        {
            "primary_arm": PRIMARY_ARM,
            "secondary_arm": SECONDARY_ARM,
            "d3_deployable_clusters": len(d3),
            "d2_deployable_clusters": len(d2),
            "overlap": len(overlap),
            "d3_only": len(d3 - d2),
            "d2_only": len(d2 - d3),
            "union": len(d3 | d2),
            "jaccard": round(len(overlap) / max(1, len(d3 | d2)), 6),
            "d3_only_cluster_ids": "|".join(sorted(d3 - d2)),
            "d2_only_cluster_ids": "|".join(sorted(d2 - d3)),
            "overlap_cluster_ids": "|".join(sorted(overlap)),
        }
    ]
    membership = []
    for cluster in sorted(d3 | d2):
        in_d3 = cluster in d3
        in_d2 = cluster in d2
        if in_d3 and in_d2:
            status = "overlap"
        elif in_d3:
            status = "d3_only"
        else:
            status = "d2_only"
        membership.append(
            {
                "cluster_id": cluster,
                "in_d3_primary": in_d3,
                "in_d2_secondary": in_d2,
                "status": status,
            }
        )
    return summary, membership


def _best_by_cluster(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not _deployable(row, turnover_max=turnover_max):
            continue
        cluster = _cluster_id(row)
        previous = best.get(cluster)
        key = (
            _safe_float(row.get("strict_mean_one_way_turnover"), 999.0),
            -_safe_float(row.get("portfolio_replay_long_only_sortino"), 0.0),
            -_safe_float(row.get("strict_cost_adjusted_sortino"), 0.0),
            str(row.get("candidate_id") or ""),
        )
        if previous is None:
            best[cluster] = row
            continue
        previous_key = (
            _safe_float(previous.get("strict_mean_one_way_turnover"), 999.0),
            -_safe_float(previous.get("portfolio_replay_long_only_sortino"), 0.0),
            -_safe_float(previous.get("strict_cost_adjusted_sortino"), 0.0),
            str(previous.get("candidate_id") or ""),
        )
        if key < previous_key:
            best[cluster] = row
    return best


def build_agnostic_anatomy(
    rows: list[dict[str, Any]],
    *,
    turnover_max: float,
    new_vs_previous_ids: set[str],
    top_cluster_id: str,
) -> list[dict[str, Any]]:
    lane = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "agnostic_freeform_ast"]
    best = _best_by_cluster(lane, turnover_max=turnover_max)
    output = []
    for cluster, row in sorted(best.items()):
        deployable_members = [member for member in lane if _cluster_id(member) == cluster and _deployable(member, turnover_max=turnover_max)]
        item = {
            "cluster_id": cluster,
            "new_vs_phase3c_cumulative_81": cluster in new_vs_previous_ids,
            "would_be_new_vs_phase3d_cumulative_103": False,
            "top_cluster_flag": cluster == top_cluster_id,
            "ablation_arm": row.get("ablation_arm"),
            "source_seed": row.get("source_seed"),
            "candidate_id": row.get("candidate_id"),
            "expression": row.get("expression"),
            "deployable_member_count": len(deployable_members),
            "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
            "portfolio_replay_long_only_sortino": row.get("portfolio_replay_long_only_sortino"),
            "portfolio_replay_long_only_net_mean": row.get("portfolio_replay_long_only_net_mean"),
        }
        item.update(_anatomy(row))
        output.append(item)
    return output


def build_repair_expansion_audit(
    rows: list[dict[str, Any]],
    *,
    turnover_max: float,
    new_vs_previous_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lane = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "formula_gen_v2_repair_expansion"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane:
        action = str(row.get("repair_policy") or row.get("proposal_kind") or row.get("primitive_family") or "unknown")
        grouped[action].append(row)

    summary = []
    row_level = []
    for action, group in sorted(grouped.items()):
        deployable = [row for row in group if _deployable(row, turnover_max=turnover_max)]
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        clusters = {_cluster_id(row) for row in deployable}
        escaped = [
            row
            for row in deployable
            if row.get("parent_signal_cluster_id") and str(row.get("parent_signal_cluster_id")) != _cluster_id(row)
        ]
        summary.append(
            {
                "repair_action": action,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "deployable_rows": len(deployable),
                "deployable_clusters": len(clusters),
                "new_vs_phase3c_cumulative_81_clusters": len(clusters & new_vs_previous_ids),
                "new_cluster_ids": "|".join(sorted(clusters & new_vs_previous_ids)),
                "escaped_parent_cluster_rows": len(escaped),
                "escaped_but_not_new_rows": sum(1 for row in escaped if _cluster_id(row) not in new_vs_previous_ids),
                "median_turnover": _median([_safe_float(row.get("strict_mean_one_way_turnover"), float("nan")) for row in deployable]),
            }
        )
        for row in deployable:
            row_level.append(
                {
                    "repair_action": action,
                    "cluster_id": _cluster_id(row),
                    "new_vs_phase3c_cumulative_81": _cluster_id(row) in new_vs_previous_ids,
                    "ablation_arm": row.get("ablation_arm"),
                    "source_seed": row.get("source_seed"),
                    "candidate_id": row.get("candidate_id"),
                    "parent_candidate_id": row.get("parent_candidate_id"),
                    "parent_signal_cluster_id": row.get("parent_signal_cluster_id") or row.get("parent_cluster"),
                    "escaped_parent_cluster": bool(row.get("parent_signal_cluster_id")) and str(row.get("parent_signal_cluster_id")) != _cluster_id(row),
                    "turnover": row.get("strict_mean_one_way_turnover"),
                    "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
                    "expression": row.get("expression"),
                }
            )
    return summary, row_level


def build_ast_raw_collapse_audit(
    rows: list[dict[str, Any]],
    *,
    turnover_max: float,
    new_vs_previous_ids: set[str],
) -> list[dict[str, Any]]:
    lane = [row for row in _phase3_rows(rows) if row.get("phase3_budget_bucket") == "ast_failure_aware_repair"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lane:
        if _non_gap_replay_pass(row):
            grouped[_cluster_id(row)].append(row)
    output = []
    for cluster, group in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        deployable = [row for row in group if _deployable(row, turnover_max=turnover_max)]
        policies = Counter(str(row.get("repair_policy") or row.get("proposal_kind") or "unknown") for row in group)
        fields = Counter()
        operators = Counter()
        parents = Counter()
        arms = Counter()
        for row in group:
            fields.update(_field_families(str(row.get("expression") or "")))
            operators.update(_operators(str(row.get("expression") or "")))
            arms[str(row.get("ablation_arm") or "unknown")] += 1
            parent = row.get("parent_signal_cluster_id") or row.get("parent_cluster")
            if parent:
                parents[str(parent)] += 1
        output.append(
            {
                "cluster_id": cluster,
                "raw_non_gap_pass": len(group),
                "deployable_rows": len(deployable),
                "deployable_cluster_credit": 1 if deployable else 0,
                "new_vs_phase3c_cumulative_81": cluster in new_vs_previous_ids,
                "cluster_capped_credit": 1 if deployable else 0,
                "raw_pass_credit_allowed": False,
                "top_repair_policies": "|".join(f"{key}:{value}" for key, value in policies.most_common(5)),
                "top_field_families": "|".join(f"{key}:{value}" for key, value in fields.most_common(5)),
                "top_operators": "|".join(f"{key}:{value}" for key, value in operators.most_common(8)),
                "top_parent_clusters": "|".join(f"{key}:{value}" for key, value in parents.most_common(5)),
                "arm_sources": "|".join(f"{key}:{value}" for key, value in arms.most_common(5)),
                "representative_expression": group[0].get("expression"),
            }
        )
    return output


def _registry_entry_from_previous(item: dict[str, Any]) -> dict[str, Any]:
    expression = str(item.get("representative_expression") or "")
    cluster_id = str(item.get("cluster_id") or "")
    first_seen = "Phase3C" if cluster_id.startswith("phase3c_") else "Phase3B"
    source_member = item.get("source_phase3c_global_cluster_id") or item.get("source_phase3b_global_cluster_id") or cluster_id
    return {
        "cluster_id": cluster_id,
        "first_seen_phase": first_seen,
        "source_arm": item.get("ablation_arm"),
        "source_generator": item.get("phase3_budget_bucket"),
        "representative_expression": expression,
        "candidate_id": item.get("candidate_id"),
        "source_seed": item.get("source_seed"),
        "source_report": "phase3C_cumulative_baseline",
        "return_corr_members": [str(source_member)],
        "deployable": True,
        "median_turnover": item.get("median_turnover"),
        "cost_adjusted_score": item.get("strict_cost_adjusted_sortino"),
        "top_cluster_flag": False,
        "field_families": _field_families(expression),
        "operator_families": sorted(set(_operators(expression))),
        "lineage": {
            "parent_cluster": item.get("parent_signal_cluster_id") or item.get("parent_cluster"),
            "repair_action": item.get("repair_policy") or item.get("proposal_kind"),
        },
        "source_previous_cluster_id": item.get("source_phase3c_global_cluster_id") or item.get("source_phase3b_global_cluster_id"),
        "source_commit": item.get("source_commit"),
    }


def _registry_entry_from_phase3d(row: dict[str, Any], *, cluster_id: str, top_cluster_id: str) -> dict[str, Any]:
    expression = str(row.get("expression") or "")
    return {
        "cluster_id": cluster_id,
        "first_seen_phase": "Phase3D",
        "source_arm": row.get("ablation_arm"),
        "source_generator": row.get("phase3_budget_bucket"),
        "representative_expression": expression,
        "candidate_id": row.get("candidate_id"),
        "source_seed": row.get("source_seed"),
        "source_report": "reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_aggregate.json",
        "source_phase3d_global_cluster_id": _cluster_id(row),
        "return_corr_members": [_cluster_id(row)],
        "deployable": True,
        "median_turnover": row.get("strict_mean_one_way_turnover"),
        "cost_adjusted_score": row.get("strict_cost_adjusted_sortino"),
        "top_cluster_flag": _cluster_id(row) == top_cluster_id,
        "field_families": _field_families(expression),
        "operator_families": sorted(set(_operators(expression))),
        "lineage": {
            "parent_cluster": row.get("parent_signal_cluster_id") or row.get("parent_cluster"),
            "repair_action": row.get("repair_policy") or row.get("proposal_kind"),
        },
        "portfolio_replay_long_only_sortino": row.get("portfolio_replay_long_only_sortino"),
        "portfolio_replay_long_only_net_mean": row.get("portfolio_replay_long_only_net_mean"),
    }


def build_cumulative_103_registry(
    *,
    previous_baseline: dict[str, Any],
    rows: list[dict[str, Any]],
    aggregate: dict[str, Any],
    turnover_max: float,
    output_path: Path,
) -> dict[str, Any]:
    g = _global_metrics(aggregate)
    previous_reps = list(previous_baseline.get("deployable_representatives") or [])
    previous_registry = [_registry_entry_from_previous(item) for item in previous_reps]
    new_ids = set(g.get("new_deployable_cluster_ids_vs_phase3_cumulative") or [])
    new_reps = []
    for source_cluster_id in sorted(new_ids):
        row = _representative_for_cluster(rows, source_cluster_id, turnover_max=turnover_max)
        if row is None:
            continue
        new_cluster_id = f"phase3d_{source_cluster_id}"
        new_reps.append(_registry_entry_from_phase3d(row, cluster_id=new_cluster_id, top_cluster_id=str(g.get("global_top_cluster_id") or "")))

    declared_previous = int(previous_baseline.get("declared_cumulative_cluster_count") or len(previous_reps))
    declared_total = declared_previous + len(new_ids)
    payload = {
        "baseline_name": "phase3B_plus_phase3C_plus_phase3D_union_20260514",
        "source_previous_cumulative_baseline": previous_baseline.get("baseline_name"),
        "source_phase3d_report": "reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_aggregate.json",
        "source_phase3d_commit": "abe790c",
        "previous_declared_cumulative_cluster_count": declared_previous,
        "phase3d_new_deployable_cluster_count": len(new_ids),
        "phase3d_new_representative_count": len(new_reps),
        "declared_cumulative_cluster_count": declared_total,
        "notes": (
            "Declared count preserves historical representative counts: Phase3B 42 + Phase3C 39 + Phase3D 22 = 103. "
            "Future aggregate runs should recluster these representatives with fresh candidates and report both declared and reclustered counts."
        ),
        "cluster_ids": [str(item.get("cluster_id")) for item in previous_reps] + [str(item.get("cluster_id")) for item in new_reps],
        "deployable_representatives": previous_reps + new_reps,
        "cluster_registry": previous_registry + new_reps,
    }
    if declared_total != 103:
        payload["warning"] = f"declared_total_expected_103_but_got_{declared_total}"
    _write_json(output_path, payload)
    return payload


def _registry_csv_rows(registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for item in registry:
        lineage = item.get("lineage") if isinstance(item.get("lineage"), dict) else {}
        out.append(
            {
                "cluster_id": item.get("cluster_id"),
                "first_seen_phase": item.get("first_seen_phase"),
                "source_arm": item.get("source_arm"),
                "source_generator": item.get("source_generator"),
                "median_turnover": item.get("median_turnover"),
                "cost_adjusted_score": item.get("cost_adjusted_score"),
                "top_cluster_flag": item.get("top_cluster_flag"),
                "field_families": "|".join(item.get("field_families") or []),
                "operator_families": "|".join(item.get("operator_families") or []),
                "parent_cluster": lineage.get("parent_cluster"),
                "repair_action": lineage.get("repair_action"),
                "representative_expression": item.get("representative_expression"),
            }
        )
    return out


def _arm_metrics(aggregate: dict[str, Any], arm: str) -> dict[str, Any]:
    for row in aggregate.get("per_arm_metrics") or []:
        if row.get("ablation_arm") == arm:
            return row
    return {}


def write_decision_record(
    *,
    path: Path,
    aggregate: dict[str, Any],
    cumulative: dict[str, Any],
    overlap_summary: list[dict[str, Any]],
    agnostic_rows: list[dict[str, Any]],
    repair_rows: list[dict[str, Any]],
    ast_rows: list[dict[str, Any]],
    output_root: Path,
) -> None:
    g = _global_metrics(aggregate)
    d3 = _arm_metrics(aggregate, PRIMARY_ARM)
    d2 = _arm_metrics(aggregate, SECONDARY_ARM)
    d0 = _arm_metrics(aggregate, "Phase3D_D0_SM_current_control")
    d1 = _arm_metrics(aggregate, "Phase3D_D1_SM_open_repair")
    overlap = overlap_summary[0] if overlap_summary else {}

    lines = [
        "# Phase3D Decision Record",
        "",
        f"- created_at: {datetime.now(timezone.utc).isoformat()}",
        "- decision: PASS_CONFIRM_PHASE3D_REALLOCATION_FULL",
        "- scope: search-structure and budget-reallocation decision; not commercial alpha deployment proof",
        "- source_commit: abe790c phase3d record reallocation full aggregate",
        "",
        "## Arm Results",
        "",
        "| arm | deployable_clusters | audited | top_cluster_share | median_turnover | judgment |",
        "|---|---:|---:|---:|---:|---|",
        f"| D0 SM current | {d0.get('deployable_clusters')} | {d0.get('audited')} | {d0.get('top_cluster_share')} | {d0.get('median_turnover')} | strong control |",
        f"| D1 SM open/repair | {d1.get('deployable_clusters')} | {d1.get('audited')} | {d1.get('top_cluster_share')} | {d1.get('median_turnover')} | too much reallocation weakens SM |",
        f"| D2 PM open/repair | {d2.get('deployable_clusters')} | {d2.get('audited')} | {d2.get('top_cluster_share')} | {d2.get('median_turnover')} | productive secondary, concentration risk |",
        f"| D3 SM no-defined-direct | {d3.get('deployable_clusters')} | {d3.get('audited')} | {d3.get('top_cluster_share')} | {d3.get('median_turnover')} | primary incumbent |",
        "",
        "## Confirmed",
        "",
        "- D3_SM_no_defined_direct is the primary incumbent.",
        "- D2_PM_open_repair is retained as productive secondary, but only with cluster-credit cap.",
        "- agnostic_freeform_ast is a protected official lane.",
        "- formula_gen_v2_repair_expansion is an official repair extension.",
        "- formula_gen_v2_defined_direct is removed from official budget and retained only as repair source/template library.",
        "- novelty_diagnostic is removed from official budget.",
        "- generic AST repair is retained only with cluster-capped credit; raw pass credit is not allowed.",
        "",
        "## New Main Profiles",
        "",
        "```yaml",
        "phase3D_primary_profile:",
        "  name: D3_SM_no_defined_direct",
        "  budget:",
        "    stable_incumbent_SM_base: 0.70",
        "    agnostic_freeform_ast: 0.18",
        "    formula_gen_v2_repair_expansion: 0.12",
        "    formula_gen_v2_defined_direct: 0.00",
        "    novelty_diagnostic: 0.00",
        "  constraints:",
        "    generic_ast_repair_credit: cluster_capped",
        "    formula_gen_v2_repair_credit: cluster_capped",
        "    raw_pass_credit_allowed: false",
        "    new_cluster_baseline: phase3D_cumulative_103",
        "",
        "phase3D_productive_secondary:",
        "  name: D2_PM_open_repair",
        "  role: secondary_productive_source",
        "  budget:",
        "    productive_PM_base: 0.65",
        "    agnostic_freeform_ast: 0.20",
        "    formula_gen_v2_repair_expansion: 0.13",
        "    formula_gen_v2_defined_direct: 0.02",
        "  required_constraints:",
        "    cluster_credit_cap: true",
        "    raw_pass_credit_allowed: false",
        "    dominant_cluster_soft_penalty: true",
        "```",
        "",
        "## Not Confirmed",
        "",
        "- commercial alpha deployment",
        "- live survival",
        "- capacity at scale",
        "- TokenAlphaLM official generation",
        "",
        "## Primary Incumbent",
        "",
        f"- arm: {PRIMARY_ARM}",
        f"- deployable_clusters: {d3.get('deployable_clusters')}",
        f"- audited: {d3.get('audited')}",
        f"- top_cluster_share: {d3.get('top_cluster_share')}",
        "",
        "## Secondary Productive Incumbent",
        "",
        f"- arm: {SECONDARY_ARM}",
        f"- deployable_clusters: {d2.get('deployable_clusters')}",
        f"- audited: {d2.get('audited')}",
        f"- top_cluster_share: {d2.get('top_cluster_share')}",
        "- required_constraint: cluster_credit_cap",
        "",
        "## Module Status",
        "",
        "| module | audited | raw_non_gap_pass | deployable_clusters | status |",
        "|---|---:|---:|---:|---|",
        "| agnostic_freeform_ast | 176 | 67 | 17 | protected official lane |",
        "| formula_gen_v2_repair_expansion | 112 | 53 | 11 | official repair extension |",
        "| formula_gen_v2_defined_direct | 28 | 4 | 1 | official budget 0; repair/template source only |",
        "| novelty_diagnostic | 20 | 0 | 0 | removed from official budget |",
        "| generic_ast_repair | 176 | 169 | 9 | cluster-capped credit only |",
        "",
        "## Future Baseline",
        "",
        f"- phase3C_cumulative_declared_clusters: {cumulative.get('previous_declared_cumulative_cluster_count')}",
        f"- phase3D_new_clusters_vs_phase3C_cumulative: {cumulative.get('phase3d_new_deployable_cluster_count')}",
        f"- phase3D_cumulative_known_deployable_clusters: {cumulative.get('declared_cumulative_cluster_count')}",
        "- future Phase3E/Phase4 new-cluster metrics must be measured against this 103-cluster representative baseline.",
        "- aggregate code should still recluster the 103 representatives with fresh candidates and report declared vs reclustered counts separately.",
        "",
        "## No-Run Audits",
        "",
        f"- D3/D2 overlap: D3 only {overlap.get('d3_only')}, D2 only {overlap.get('d2_only')}, overlap {overlap.get('overlap')}, union {overlap.get('union')}.",
        f"- agnostic_freeform deployable clusters audited in anatomy table: {len(agnostic_rows)}.",
        f"- FormulaGenV2 repair action buckets: {len(repair_rows)}.",
        f"- generic AST repair raw-collapse clusters: {len(ast_rows)}.",
        "",
        "## Phase3E Design",
        "",
        "Phase3E should move from pure discovery count to deployability hardening and book-level marginal value.",
        "",
        "| arm | profile | purpose |",
        "|---|---|---|",
        "| E0 | D3 primary control | confirm D3 on fresh seeds |",
        "| E1 | D3 + D2 productive sidecar | test whether D2 adds clusters not covered by D3 |",
        "| E2 | D3 + stricter deployability selector | improve cost/turnover/exposure quality even if count drops |",
        "| E3 | D3 + book-level marginal selector | select clusters by marginal book value, not just new-cluster status |",
        "",
        "Suggested scale: seeds 21,22,23,24; 64 audited per arm per seed; total 1024 audited.",
        "",
        "Primary Phase3E metrics:",
        "",
        "- new deployable clusters vs cumulative 103",
        "- cost-adjusted deployable clusters",
        "- median turnover",
        "- factor/sector exposure",
        "- cluster-capped credit",
        "- top cluster share",
        "- marginal book IR proxy",
        "- mean/max corr to existing book",
        "",
        "## Experiment Record",
        "",
        "- date: 2026-05-14",
        "- experiment_id: 20260514_phase3D_decision_consolidation",
        "- objective: freeze Phase3D reallocation decision and create the 103-cluster cumulative baseline",
        "- status: completed",
        "- mode: light/no-run posthoc",
        "",
        "### Inputs",
        "",
        "- aggregate: reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_aggregate.json",
        "- clustered rows: reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_clustered_rows.json",
        "- previous cumulative baseline: src/our_system_phase2/runtime/baselines/phase3C_cumulative_deployable_clusters_20260514.json",
        "",
        "### Parameters",
        "",
        "- turnover_max: 0.75",
        "- costs: inherited strict runs, 10bps",
        "- seeds: Phase3D seeds 17,18,19,20 from completed aggregate",
        "",
        "### Commands",
        "",
        "```text",
        "G:\\PythonProject\\.venv\\Scripts\\python.exe -m our_system_phase2.runtime.stock_pit_phase3d_decision_consolidation",
        "```",
        "",
        "### Outputs",
        "",
        f"- decision record: {path}",
        f"- output root: {output_root}",
        "- cumulative baseline: src/our_system_phase2/runtime/baselines/phase3D_cumulative_deployable_clusters_20260514.json",
        "",
        "### Metrics",
        "",
        f"- global audited: {g.get('audited')}",
        f"- global deployable clusters: {g.get('global_deployable_clusters')}",
        f"- Phase3D new clusters vs Phase3C cumulative: {g.get('new_deployable_clusters_vs_phase3_cumulative')}",
        f"- raw non-gap pass: {g.get('raw_non_gap_pass')}",
        f"- global top cluster share: {g.get('global_top_cluster_share')}",
        "",
        "### Decision",
        "",
        "PROMOTE_CANDIDATE for D3 primary profile; HOLD_RESEARCH for commercial deployment.",
        "",
        "### Next Action",
        "",
        "- Do not start another blind search immediately.",
        "- Use the 103-cluster registry for Phase3E design and book-level selection.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate Phase3D final decision and build the cumulative 103 registry.")
    parser.add_argument("--aggregate-json", type=Path, default=Path("reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_aggregate.json"))
    parser.add_argument("--clustered-rows-json", type=Path, default=Path("reports/phase3d_reallocation_full_20260514/phase3D_reallocation_full_global_clustered_rows.json"))
    parser.add_argument("--previous-cumulative-baseline-json", type=Path, default=Path("src/our_system_phase2/runtime/baselines/phase3C_cumulative_deployable_clusters_20260514.json"))
    parser.add_argument("--new-cumulative-baseline-json", type=Path, default=Path("src/our_system_phase2/runtime/baselines/phase3D_cumulative_deployable_clusters_20260514.json"))
    parser.add_argument("--output-root", type=Path, default=Path("reports/phase3d_decision_20260514"))
    parser.add_argument("--decision-record", type=Path, default=Path("reports/PHASE3D_DECISION_RECORD_2026-05-14.md"))
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    aggregate = _read_json(args.aggregate_json)
    clustered_payload = _read_json(args.clustered_rows_json)
    rows = clustered_payload.get("rows") if isinstance(clustered_payload, dict) else clustered_payload
    if not isinstance(rows, list):
        raise TypeError("clustered rows payload must contain a list under 'rows'")
    previous = _read_json(args.previous_cumulative_baseline_json)
    g = _global_metrics(aggregate)
    new_vs_previous_ids = set(g.get("new_deployable_cluster_ids_vs_phase3_cumulative") or [])
    top_cluster_id = str(g.get("global_top_cluster_id") or "")

    args.output_root.mkdir(parents=True, exist_ok=True)
    overlap_summary, overlap_membership = build_d3_d2_overlap(rows, turnover_max=args.turnover_max)
    agnostic_rows = build_agnostic_anatomy(
        rows,
        turnover_max=args.turnover_max,
        new_vs_previous_ids=new_vs_previous_ids,
        top_cluster_id=top_cluster_id,
    )
    repair_summary, repair_row_level = build_repair_expansion_audit(
        rows,
        turnover_max=args.turnover_max,
        new_vs_previous_ids=new_vs_previous_ids,
    )
    ast_rows = build_ast_raw_collapse_audit(
        rows,
        turnover_max=args.turnover_max,
        new_vs_previous_ids=new_vs_previous_ids,
    )
    cumulative = build_cumulative_103_registry(
        previous_baseline=previous,
        rows=rows,
        aggregate=aggregate,
        turnover_max=args.turnover_max,
        output_path=args.new_cumulative_baseline_json,
    )

    _write_csv(args.output_root / "phase3d_d3_d2_overlap.csv", overlap_summary)
    _write_csv(args.output_root / "phase3d_d3_d2_cluster_membership.csv", overlap_membership)
    _write_csv(args.output_root / "phase3d_agnostic_freeform_anatomy.csv", agnostic_rows)
    _write_csv(args.output_root / "phase3d_formula_gen_v2_repair_expansion_audit.csv", repair_summary)
    _write_csv(args.output_root / "phase3d_formula_gen_v2_repair_expansion_rows.csv", repair_row_level)
    _write_csv(args.output_root / "phase3d_generic_ast_repair_raw_collapse_audit.csv", ast_rows)
    _write_csv(args.output_root / "phase3d_cumulative_103_registry.csv", _registry_csv_rows(cumulative.get("cluster_registry") or []))

    write_decision_record(
        path=args.decision_record,
        aggregate=aggregate,
        cumulative=cumulative,
        overlap_summary=overlap_summary,
        agnostic_rows=agnostic_rows,
        repair_rows=repair_summary,
        ast_rows=ast_rows,
        output_root=args.output_root,
    )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "20260514_phase3D_decision_consolidation",
        "status": "completed",
        "decision": "PASS_CONFIRM_PHASE3D_REALLOCATION_FULL",
        "aggregate_json": str(args.aggregate_json),
        "clustered_rows_json": str(args.clustered_rows_json),
        "previous_cumulative_baseline_json": str(args.previous_cumulative_baseline_json),
        "new_cumulative_baseline_json": str(args.new_cumulative_baseline_json),
        "decision_record": str(args.decision_record),
        "output_root": str(args.output_root),
        "overlap_summary": overlap_summary,
        "module_counts": {
            "agnostic_freeform_deployable_clusters": len(agnostic_rows),
            "formula_gen_v2_repair_action_buckets": len(repair_summary),
            "generic_ast_raw_non_gap_clusters": len(ast_rows),
            "cumulative_declared_cluster_count": cumulative.get("declared_cumulative_cluster_count"),
        },
    }
    _write_json(args.output_root / "phase3d_decision_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
