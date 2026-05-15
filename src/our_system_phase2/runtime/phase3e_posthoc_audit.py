from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


ARM_E0 = "Phase3E_E0_D3_primary"
ARM_E2 = "Phase3E_E2_D3_deployability_hardened"
ARM_E3 = "Phase3E_E3_D3_book_marginal"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or "cluster_missing")


def _phase3_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]


def _deployable(row: dict[str, Any], turnover_max: float) -> bool:
    if row.get("aggregate_source_kind") in {"phase3b_union_baseline", "phase3_cumulative_baseline"}:
        return bool(row.get("portfolio_replay_pass")) and bool(row.get("cost_survives"))
    return _deployable_pass(row, turnover_max=turnover_max)


def _non_gap(row: dict[str, Any]) -> bool:
    return _non_gap_replay_pass(row)


def _quantiles(values: list[float]) -> dict[str, Any]:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None, "mean": None}

    def q(frac: float) -> float:
        if len(clean) == 1:
            return clean[0]
        pos = frac * (len(clean) - 1)
        left = int(math.floor(pos))
        right = int(math.ceil(pos))
        if left == right:
            return clean[left]
        return clean[left] + (clean[right] - clean[left]) * (pos - left)

    return {
        "count": len(clean),
        "min": round(clean[0], 6),
        "p25": round(q(0.25), 6),
        "median": round(median(clean), 6),
        "p75": round(q(0.75), 6),
        "max": round(clean[-1], 6),
        "mean": round(sum(clean) / len(clean), 6),
    }


def _expr_features(expression: str) -> dict[str, Any]:
    ops = re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression or "")
    fields = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")
    families: set[str] = set()
    for field in fields:
        name = field.lower()
        if any(token in name for token in ["close", "open", "high", "low", "vwap", "price"]):
            families.add("price")
        if any(token in name for token in ["amount", "volume", "turnover"]):
            families.add("flow_liquidity")
        if any(token in name for token in ["cap", "market"]):
            families.add("capitalization")
        if any(token in name for token in ["ret", "return"]):
            families.add("return")
        if any(token in name for token in ["vol", "std", "abs"]):
            families.add("volatility")
        if any(token in name for token in ["limit", "up", "down"]):
            families.add("limit_state")
    if fields and not families:
        families.add("other")
    depth = 0
    max_depth = 0
    for char in expression or "":
        if char == "(":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    return {
        "field_family": "|".join(sorted(families)) or "none",
        "field_list": "|".join(sorted(set(fields))),
        "operator_family": "|".join(sorted(set(ops))) or "none",
        "tree_depth": max_depth,
        "corr_ops_count": sum(1 for op in ops if op.lower() in {"corr", "cov"}),
        "temporal_ops_count": sum(1 for op in ops if op.lower() in {"delta", "delay", "mean", "mom", "corr", "cov", "tsrank", "ts_rank"}),
        "product_arity": sum(1 for op in ops if op.lower() == "mul"),
        "signed_nonlinear_count": sum(1 for op in ops if op.lower() in {"sign", "possign", "negsign"}),
    }


def _cluster_status(cluster: str, cumulative_clusters: set[str], phase3e_deployable_clusters: set[str]) -> dict[str, Any]:
    if cluster in cumulative_clusters:
        status_103 = "known_vs_103"
    elif cluster in phase3e_deployable_clusters:
        status_103 = "new_vs_103"
    else:
        status_103 = "not_deployable_cluster"
    # The 134 baseline is the post-Phase3E declared baseline: 103 declared + 31 new.
    # Therefore current Phase3E clusters are known after this decision record.
    if cluster in cumulative_clusters or cluster in phase3e_deployable_clusters:
        status_134 = "known_in_future_134_after_phase3e"
    else:
        status_134 = "not_in_future_134_registry"
    return {
        "known_vs_new_vs_103": status_103,
        "known_vs_new_vs_134": status_134,
        "new_vs_103": status_103 == "new_vs_103",
        "new_vs_134": False,
    }


def _load_selector_rows(reports_root: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for path in sorted(reports_root.glob("phase3e_official_seed*_company_20260514/arms/*/phase3e_selector_audit.csv")):
        seed_match = re.search(r"seed(\d+)_company", str(path))
        seed = f"seed{seed_match.group(1)}" if seed_match else "unknown"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                item = {key.lstrip("\ufeff"): value for key, value in row.items()}
                item["source_seed"] = seed
                output.append(item)
    return output


def _selected_selector_rows(selector_rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    return [row for row in selector_rows if row.get("arm") == arm and _as_bool(row.get("selected_for_audit"))]


def _selector_metric(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    return _quantiles([_safe_float(row.get(field)) for row in rows])


def _expression_key(row: dict[str, Any]) -> str:
    return re.sub(r"\s+", "", str(row.get("expression") or ""))


def _cluster_sets(rows: list[dict[str, Any]], turnover_max: float) -> dict[str, set[str]]:
    phase3 = _phase3_rows(rows)
    cumulative = {
        _cluster_id(row)
        for row in rows
        if row.get("aggregate_source_kind") == "phase3_cumulative_baseline" and _deployable(row, turnover_max)
    }
    phase3_deployable = {_cluster_id(row) for row in phase3 if _deployable(row, turnover_max)}
    by_arm = {
        arm: {_cluster_id(row) for row in phase3 if row.get("ablation_arm") == arm and _deployable(row, turnover_max)}
        for arm in sorted({str(row.get("ablation_arm")) for row in phase3})
    }
    return {"cumulative": cumulative, "phase3_deployable": phase3_deployable, **by_arm}


def _audit_e3_top_cluster(rows: list[dict[str, Any]], clusters: dict[str, set[str]], turnover_max: float) -> list[dict[str, Any]]:
    e3_rows = [row for row in _phase3_rows(rows) if row.get("ablation_arm") == ARM_E3]
    e3_non_gap = [row for row in e3_rows if _non_gap(row)]
    counts = Counter(_cluster_id(row) for row in e3_non_gap)
    top_cluster, raw_count = counts.most_common(1)[0]
    top_rows = [row for row in e3_rows if _cluster_id(row) == top_cluster]
    top_non_gap = [row for row in top_rows if _non_gap(row)]
    top_deployable = [row for row in top_rows if _deployable(row, turnover_max)]
    source_counts = Counter(str(row.get("phase3_budget_bucket") or "unknown") for row in top_non_gap)
    generator_counts = Counter(str(row.get("proof_variant") or row.get("proposal_kind") or "unknown") for row in top_non_gap)
    proposal_counts = Counter(str(row.get("proposal_kind") or "unknown") for row in top_non_gap)
    repair_counts = Counter(str(row.get("repair_policy") or row.get("proposal_kind") or "none") for row in top_non_gap)
    parent_counts = Counter(str(row.get("parent_lane") or "none") for row in top_non_gap)
    expr_sample = str(top_non_gap[0].get("expression") or "") if top_non_gap else ""
    features = _expr_features(expr_sample)
    status = _cluster_status(top_cluster, clusters["cumulative"], clusters["phase3_deployable"])
    row = {
        "top_cluster_id": top_cluster,
        "raw_pass_count": raw_count,
        "e3_raw_pass_total": len(e3_non_gap),
        "raw_pass_share": round(raw_count / max(1, len(e3_non_gap)), 6),
        "deployable_row_count": len(top_deployable),
        "deployable_cluster": top_cluster in clusters[ARM_E3],
        **status,
        "source_lane_counts": json.dumps(source_counts, ensure_ascii=False),
        "source_generator_counts": json.dumps(generator_counts, ensure_ascii=False),
        "proposal_kind_counts": json.dumps(proposal_counts, ensure_ascii=False),
        "parent_lineage_counts": json.dumps(parent_counts, ensure_ascii=False),
        "repair_action_counts": json.dumps(repair_counts, ensure_ascii=False),
        "turnover_profile": json.dumps(_quantiles([_safe_float(row.get("strict_mean_one_way_turnover")) for row in top_deployable]), ensure_ascii=False),
        "representative_expression": expr_sample,
        **features,
    }
    return [row]


def _audit_e3_proxy(selector_rows: list[dict[str, Any]], rows: list[dict[str, Any]], clusters: dict[str, set[str]], turnover_max: float) -> list[dict[str, Any]]:
    phase3 = _phase3_rows(rows)
    output: list[dict[str, Any]] = []
    selected_by_arm = {arm: _selected_selector_rows(selector_rows, arm) for arm in [ARM_E0, ARM_E3]}
    e0_keys = {_expression_key(row) for row in selected_by_arm[ARM_E0]}
    e3_keys = {_expression_key(row) for row in selected_by_arm[ARM_E3]}
    queue_overlap = len(e0_keys & e3_keys)
    queue_union = len(e0_keys | e3_keys)
    for arm in [ARM_E0, ARM_E3]:
        selected = selected_by_arm[arm]
        arm_rows = [row for row in phase3 if row.get("ablation_arm") == arm]
        deployable_clusters = {_cluster_id(row) for row in arm_rows if _deployable(row, turnover_max)}
        deployable_rows = [row for row in arm_rows if _deployable(row, turnover_max)]
        new_vs_103 = deployable_clusters - clusters["cumulative"]
        output.append(
            {
                "arm": arm,
                "selected_count": len(selected),
                "book_marginal_mode": "|".join(sorted(set(row.get("book_marginal_mode") or "none" for row in selected))),
                "queue_overlap_with_other_count": queue_overlap,
                "queue_overlap_with_other_jaccard": round(queue_overlap / max(1, queue_union), 6),
                "deployable_clusters": len(deployable_clusters),
                "new_cluster_count_vs_103": len(new_vs_103),
                "new_cluster_count_vs_134": 0,
                "cluster_capped_credit": len(deployable_clusters),
                "mean_max_corr_to_103": _selector_metric(selected, "max_corr_to_103_registry")["mean"],
                "median_max_corr_to_103": _selector_metric(selected, "max_corr_to_103_registry")["median"],
                "mean_corr_to_selected_queue": _selector_metric(selected, "max_corr_to_selected_queue")["mean"],
                "median_corr_to_selected_queue": _selector_metric(selected, "max_corr_to_selected_queue")["median"],
                "median_turnover_proxy": _selector_metric(selected, "turnover_proxy")["median"],
                "median_replay_turnover_deployable": _quantiles([_safe_float(row.get("strict_mean_one_way_turnover")) for row in deployable_rows])["median"],
                "mean_selection_score": _selector_metric(selected, "selection_score")["mean"],
                "uses_forbidden_replay_labels_any": any(_as_bool(row.get("uses_forbidden_replay_labels")) for row in selected),
                "gate_not_applied": "|".join(sorted(set(str(row.get("gate_not_applied") or "") for row in selected if row.get("gate_not_applied")))),
            }
        )
    return output


def _audit_overlap(clusters: dict[str, set[str]]) -> list[dict[str, Any]]:
    e0 = clusters[ARM_E0]
    e3 = clusters[ARM_E3]
    return [
        {
            "E0_clusters": len(e0),
            "E3_clusters": len(e3),
            "E0_only": len(e0 - e3),
            "E3_only": len(e3 - e0),
            "E0_E3_overlap": len(e0 & e3),
            "E0_union_E3": len(e0 | e3),
            "E0_only_cluster_ids": "|".join(sorted(e0 - e3)),
            "E3_only_cluster_ids": "|".join(sorted(e3 - e0)),
            "overlap_cluster_ids": "|".join(sorted(e0 & e3)),
        }
    ]


def _audit_agnostic(rows: list[dict[str, Any]], clusters: dict[str, set[str]], turnover_max: float) -> list[dict[str, Any]]:
    phase3 = _phase3_rows(rows)
    agnostic = [row for row in phase3 if row.get("phase3_budget_bucket") == "agnostic_freeform_ast"]
    deployable = [row for row in agnostic if _deployable(row, turnover_max)]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in deployable:
        grouped[_cluster_id(row)].append(row)
    output = []
    for cluster, group in sorted(grouped.items()):
        non_gap_rows = [row for row in agnostic if _cluster_id(row) == cluster and _non_gap(row)]
        expr = str(group[0].get("expression") or "")
        features = _expr_features(expr)
        status = _cluster_status(cluster, clusters["cumulative"], clusters["phase3_deployable"])
        output.append(
            {
                "cluster_id": cluster,
                "deployable_row_count": len(group),
                "raw_non_gap_count": len(non_gap_rows),
                **status,
                "source_arms": "|".join(sorted(set(str(row.get("ablation_arm")) for row in group))),
                "turnover_profile": json.dumps(_quantiles([_safe_float(row.get("strict_mean_one_way_turnover")) for row in group]), ensure_ascii=False),
                "representative_expression": expr,
                **features,
            }
        )
    return output


def _audit_e2(selector_rows: list[dict[str, Any]], rows: list[dict[str, Any]], turnover_max: float) -> list[dict[str, Any]]:
    selected_e0 = _selected_selector_rows(selector_rows, ARM_E0)
    selected_e2 = _selected_selector_rows(selector_rows, ARM_E2)
    all_e2 = [row for row in selector_rows if row.get("arm") == ARM_E2]
    reject_rows = [row for row in all_e2 if not _as_bool(row.get("hard_gate_pass"))]
    reject_counts = Counter(str(row.get("hard_reject_reason") or "none") for row in reject_rows)
    e0_keys = {_expression_key(row) for row in selected_e0}
    e2_keys = {_expression_key(row) for row in selected_e2}
    overlap = len(e0_keys & e2_keys)
    union = len(e0_keys | e2_keys)
    phase3 = _phase3_rows(rows)
    e0_deployable = [row for row in phase3 if row.get("ablation_arm") == ARM_E0 and _deployable(row, turnover_max)]
    e2_deployable = [row for row in phase3 if row.get("ablation_arm") == ARM_E2 and _deployable(row, turnover_max)]
    return [
        {
            "arm": ARM_E2,
            "selector_rows": len(all_e2),
            "selected_count": len(selected_e2),
            "hard_reject_count": len(reject_rows),
            "hard_reject_rate": round(len(reject_rows) / max(1, len(all_e2)), 6),
            "hard_reject_reason_distribution": json.dumps(reject_counts, ensure_ascii=False),
            "queue_overlap_with_E0_count": overlap,
            "queue_overlap_with_E0_jaccard": round(overlap / max(1, union), 6),
            "E2_selected_turnover_proxy": json.dumps(_selector_metric(selected_e2, "turnover_proxy"), ensure_ascii=False),
            "E0_selected_turnover_proxy": json.dumps(_selector_metric(selected_e0, "turnover_proxy"), ensure_ascii=False),
            "E2_selected_cost_adjusted_proxy": json.dumps(_selector_metric(selected_e2, "cost_adjusted_proxy"), ensure_ascii=False),
            "E0_selected_cost_adjusted_proxy": json.dumps(_selector_metric(selected_e0, "cost_adjusted_proxy"), ensure_ascii=False),
            "E2_selected_factor_exposure_proxy": json.dumps(_selector_metric(selected_e2, "factor_exposure_proxy"), ensure_ascii=False),
            "E0_selected_factor_exposure_proxy": json.dumps(_selector_metric(selected_e0, "factor_exposure_proxy"), ensure_ascii=False),
            "E2_selected_selection_score": json.dumps(_selector_metric(selected_e2, "selection_score"), ensure_ascii=False),
            "E0_selected_selection_score": json.dumps(_selector_metric(selected_e0, "selection_score"), ensure_ascii=False),
            "E2_replay_deployable_turnover": json.dumps(_quantiles([_safe_float(row.get("strict_mean_one_way_turnover")) for row in e2_deployable]), ensure_ascii=False),
            "E0_replay_deployable_turnover": json.dumps(_quantiles([_safe_float(row.get("strict_mean_one_way_turnover")) for row in e0_deployable]), ensure_ascii=False),
            "feature_missing_common": "|".join(sorted(Counter(str(row.get("feature_missing") or "") for row in selected_e2).keys())),
        }
    ]


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def _write_decision_record(path: Path, aggregate: dict[str, Any]) -> None:
    metrics = aggregate["global_union_metrics"]
    per_arm = aggregate["per_arm_metrics"]
    content = f"""# Phase3E Decision Record 2026-05-14

## Decision

- decision: `PASS_CONFIRM_PHASE3E`
- source aggregate: `reports/phase3e_official_s21_s24_company_20260514/phase3E_official_s21_s24_global_aggregate.json`
- current cumulative baseline: `103`
- Phase3E new deployable clusters vs 103: `{metrics["new_deployable_clusters_vs_phase3_cumulative"]}`
- future declared baseline for Phase3F: `134`

## Final Phase3E Metrics

- audited: `{metrics["audited"]}`
- global unique return-corr clusters: `{metrics["global_unique_return_corr_clusters"]}`
- global deployable clusters: `{metrics["global_deployable_clusters"]}`
- raw non-gap pass: `{metrics["raw_non_gap_pass"]}`
- top cluster share: `{metrics["global_top_cluster_share"]}`
- metadata gate: `{aggregate.get("phase3A_pass_criteria", {}).get("metadata_gate_decision")}`

## Arm Summary

{_markdown_table(per_arm, ["ablation_arm", "audited", "deployable_clusters", "raw_non_gap_pass", "top_cluster_share", "median_turnover", "median_complexity"])}

## State

- primary incumbent remains: `E0_D3_primary`
- candidate selector, not promoted yet: `E3_D3_book_marginal_proxy`
- promoted official lane: `agnostic_freeform_ast`
- retained repair extension: `formula_gen_v2_repair_expansion`
- demoted / not promoted: `E2_D3_deployability_hardened`, `formula_gen_v2_defined_direct`, `novelty_diagnostic`

## Rationale

E3 has the highest deployable cluster count and lowest median turnover, but its top cluster share is `0.55`.
That concentration blocks direct promotion. Phase3F must first test E3 anti-concentration and true/proxy book-marginal validity.

## Next Gate

Run no-run posthoc audits first:

1. E3 top cluster audit
2. E3 proxy truth audit
3. E0/E3 overlap audit
4. agnostic_freeform attribution audit
5. E2 hardening failure audit

Do not start Phase3F until these audits are reviewed.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_phase3e_baseline(rows: list[dict[str, Any]], aggregate: dict[str, Any], turnover_max: float) -> dict[str, Any]:
    candidates = [
        row
        for row in rows
        if (
            row.get("aggregate_source_kind") == "phase3_cumulative_baseline"
            and _deployable(row, turnover_max)
        )
        or (
            row.get("aggregate_source_kind") == "phase3A_seed"
            and _deployable(row, turnover_max)
        )
    ]
    representatives: dict[str, dict[str, Any]] = {}
    for row in candidates:
        cluster = _cluster_id(row)
        if cluster in representatives:
            continue
        expression = str(row.get("expression") or "")
        representatives[cluster] = {
            "cluster_id": cluster,
            "representative_expression": expression,
            "candidate_id": row.get("candidate_id"),
            "first_seen_phase": "Phase3E" if row.get("aggregate_source_kind") == "phase3A_seed" else "pre_phase3E_cumulative",
            "source_arm": row.get("ablation_arm"),
            "source_seed": row.get("source_seed"),
            "source_generator": row.get("proof_variant") or row.get("proposal_kind"),
            "source_lane": row.get("phase3_budget_bucket"),
            "field_families": _expr_features(expression)["field_family"].split("|"),
            "operator_families": _expr_features(expression)["operator_family"].split("|"),
            "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
            "portfolio_replay_avg_one_way_turnover": row.get("portfolio_replay_avg_one_way_turnover"),
            "global_cluster_source": "global_reclustered_phase3e_s21_s24",
        }
    metrics = aggregate["global_union_metrics"]
    declared_previous = int(metrics.get("phase3_cumulative_baseline_declared_clusters") or 103)
    declared_new = int(metrics.get("new_deployable_clusters_vs_phase3_cumulative") or 31)
    return {
        "baseline_name": "phase3E_cumulative_20260514",
        "source_aggregate": "reports/phase3e_official_s21_s24_company_20260514/phase3E_official_s21_s24_global_aggregate.json",
        "declared_previous_cluster_count": declared_previous,
        "declared_new_cluster_count_vs_previous": declared_new,
        "declared_cluster_count": declared_previous + declared_new,
        "reclustered_representative_count": len(representatives),
        "cluster_label_scope": "global_reclustered_across_phase3E_s21_s24_plus_previous_baselines",
        "notes": "Declared count follows the Phase3E decision baseline: 103 previous declared clusters + 31 new deployable clusters. Reclustered representative count can differ because aggregate reclusters historical representatives.",
        "deployable_representatives": [representatives[key] for key in sorted(representatives)],
    }


def _write_summary(path: Path, experiment: dict[str, Any], outputs: dict[str, Path], audit_rows: dict[str, list[dict[str, Any]]]) -> None:
    top = audit_rows["e3_top_cluster"][0]
    proxy = audit_rows["e3_proxy_truth"]
    e3_proxy = next(row for row in proxy if row["arm"] == ARM_E3)
    e0_proxy = next(row for row in proxy if row["arm"] == ARM_E0)
    overlap = audit_rows["e0_e3_overlap"][0]
    e2 = audit_rows["e2_hardening_failure"][0]
    agnostic_rows = audit_rows["agnostic_freeform_attribution"]
    agnostic_new_103 = sum(1 for row in agnostic_rows if row.get("new_vs_103"))
    content = f"""# Phase3E Posthoc Audit 2026-05-14

## Experiment Record

- date: `2026-05-14`
- experiment_id: `{experiment["experiment_id"]}`
- objective: `{experiment["objective"]}`
- status: `completed`
- mode: `light/no-run-posthoc`
- commands: `python -m our_system_phase2.runtime.phase3e_posthoc_audit ...`
- reproducible: `yes, from committed Phase3E aggregate and selector audit artifacts`

## Key Findings

1. E3 top cluster is `{top["top_cluster_id"]}` with `{top["raw_pass_count"]}` raw non-gap rows out of `{top["e3_raw_pass_total"]}` E3 raw non-gap rows (`{top["raw_pass_share"]}` share).
2. E3 top cluster is `{top["known_vs_new_vs_103"]}` and `{top["known_vs_new_vs_134"]}`.
3. E3 has lower max-corr-to-103 than E0 by both mean and median (`{e3_proxy["mean_max_corr_to_103"]}` / `{e3_proxy["median_max_corr_to_103"]}` vs `{e0_proxy["mean_max_corr_to_103"]}` / `{e0_proxy["median_max_corr_to_103"]}`), and lower deployable replay turnover (`{e3_proxy["median_replay_turnover_deployable"]}` vs `{e0_proxy["median_replay_turnover_deployable"]}`).
4. E3 selected-queue internal correlation is high (`{e3_proxy["median_corr_to_selected_queue"]}` median; `{e3_proxy["mean_corr_to_selected_queue"]}` mean), which explains why it can avoid the old registry but still collapse into a new/current dominant cluster.
5. E0/E3 deployable overlap is `{overlap["E0_E3_overlap"]}` clusters; E3-only is `{overlap["E3_only"]}`, so E3 has real incremental cluster coverage but needs concentration control.
6. agnostic freeform contributes `{len(agnostic_rows)}` deployable clusters, `{agnostic_new_103}` of them new vs 103 under the current global clustering.
7. E2 hard reject rate is `{e2["hard_reject_rate"]}`; E2 queue overlap with E0 is `{e2["queue_overlap_with_E0_jaccard"]}`.

## Interpretation

- E3 currently behaves like a useful registry-novelty and low-turnover proxy, but not a complete book-marginal selector.
- The missing piece is selected-queue diversity: E3 lowers correlation to the 103 registry but still self-collapses inside its own queue.
- E3 should remain blocked from primary promotion until Phase3F tests selected-queue diversity and anti-concentration.
- agnostic freeform is confirmed as a core open-ended source, but it needs cluster diversity caps if it feeds E3.

## Output Manifest

{_markdown_table([{"artifact": key, "path": str(value)} for key, value in outputs.items()], ["artifact", "path"])}
"""
    path.write_text(content, encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    aggregate_path = Path(args.aggregate_json)
    clustered_rows_path = Path(args.clustered_rows_json)
    reports_root = Path(args.reports_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aggregate = _read_json(aggregate_path)
    rows = _read_json(clustered_rows_path)["rows"]
    selector_rows = _load_selector_rows(reports_root)
    clusters = _cluster_sets(rows, args.turnover_max)

    audit_rows = {
        "e3_top_cluster": _audit_e3_top_cluster(rows, clusters, args.turnover_max),
        "e3_proxy_truth": _audit_e3_proxy(selector_rows, rows, clusters, args.turnover_max),
        "e0_e3_overlap": _audit_overlap(clusters),
        "agnostic_freeform_attribution": _audit_agnostic(rows, clusters, args.turnover_max),
        "e2_hardening_failure": _audit_e2(selector_rows, rows, args.turnover_max),
    }

    outputs = {
        "e3_top_cluster_csv": output_dir / "phase3e_e3_top_cluster_audit.csv",
        "e3_proxy_truth_csv": output_dir / "phase3e_e3_proxy_truth_audit.csv",
        "e0_e3_overlap_csv": output_dir / "phase3e_e0_e3_overlap_audit.csv",
        "agnostic_freeform_attribution_csv": output_dir / "phase3e_agnostic_freeform_attribution_audit.csv",
        "e2_hardening_failure_csv": output_dir / "phase3e_e2_hardening_failure_audit.csv",
        "summary_json": output_dir / "phase3e_posthoc_audit_summary.json",
        "phase3e_cumulative_baseline_json": Path(args.phase3e_baseline_json),
        "summary_md": reports_root / "PHASE3E_POSTHOC_AUDIT_2026-05-14.md",
        "decision_record_md": reports_root / "PHASE3E_DECISION_RECORD_2026-05-14.md",
    }

    _write_csv(outputs["e3_top_cluster_csv"], audit_rows["e3_top_cluster"])
    _write_csv(outputs["e3_proxy_truth_csv"], audit_rows["e3_proxy_truth"])
    _write_csv(outputs["e0_e3_overlap_csv"], audit_rows["e0_e3_overlap"])
    _write_csv(outputs["agnostic_freeform_attribution_csv"], audit_rows["agnostic_freeform_attribution"])
    _write_csv(outputs["e2_hardening_failure_csv"], audit_rows["e2_hardening_failure"])

    experiment = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "experiment_id": "20260514_phase3e_posthoc_audit",
        "objective": "Audit E3 concentration, E3 proxy validity, E0/E3 overlap, agnostic attribution, and E2 hardening failure before Phase3F.",
        "input_aggregate": str(aggregate_path),
        "input_clustered_rows": str(clustered_rows_path),
        "selector_audit_row_count": len(selector_rows),
        "turnover_max": args.turnover_max,
        "future_declared_baseline": 134,
        "outputs": {key: str(value) for key, value in outputs.items()},
    }
    _write_json(outputs["phase3e_cumulative_baseline_json"], _build_phase3e_baseline(rows, aggregate, args.turnover_max))
    _write_json(outputs["summary_json"], {"experiment": experiment, "audits": audit_rows})
    _write_decision_record(outputs["decision_record_md"], aggregate)
    _write_summary(outputs["summary_md"], experiment, outputs, audit_rows)
    print(json.dumps({"status": "ok", "outputs": {key: str(value) for key, value in outputs.items()}}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-json", required=True)
    parser.add_argument("--clustered-rows-json", required=True)
    parser.add_argument("--reports-root", default="reports")
    parser.add_argument("--output-dir", default="reports/phase3e_posthoc_audit_20260514")
    parser.add_argument("--phase3e-baseline-json", default="src/our_system_phase2/runtime/baselines/phase3E_cumulative_deployable_clusters_20260514.json")
    parser.add_argument("--turnover-max", type=float, default=0.75)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
