from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.runtime.stock_pit_phase3_aggregate import _expression_complexity, _safe_float
from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass
from our_system_phase2.services.stock_pit_true_limit_search_bakeoff_v2 import write_json_artifact


B1 = "Phase3B_B1_phase3A_full"
B2 = "Phase3B_B2_direct_R0_quota_only"
B3 = "Phase3B_B3_repair_aware_soft_quota"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or "cluster_missing")


def _is_phase3(row: dict[str, Any]) -> bool:
    return row.get("aggregate_source_kind") == "phase3A_seed"


def _is_deployable(row: dict[str, Any], turnover_max: float) -> bool:
    if row.get("aggregate_source_kind") == "phase2_r0_baseline":
        return bool(row.get("portfolio_replay_pass")) and bool(row.get("cost_survives")) and _safe_float(row.get("strict_mean_one_way_turnover"), 999.0) <= turnover_max
    return _deployable_pass(row, turnover_max=turnover_max)


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2, 6)


def _representative_expression(rows: list[dict[str, Any]]) -> str:
    expressions = [str(row.get("expression") or "") for row in rows if row.get("expression")]
    if not expressions:
        return ""
    return Counter(expressions).most_common(1)[0][0]


def _arm_rows(rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    return [row for row in rows if _is_phase3(row) and row.get("ablation_arm") == arm]


def _cluster_rows(rows: list[dict[str, Any]], *, turnover_max: float) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _non_gap_replay_pass(row) or _is_deployable(row, turnover_max):
            grouped[_cluster_id(row)].append(row)
    return grouped


def build_b1_b2_overlap(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    b1_rows = _arm_rows(rows, B1)
    b2_rows = _arm_rows(rows, B2)
    b1_by_cluster = _cluster_rows(b1_rows, turnover_max=turnover_max)
    b2_by_cluster = _cluster_rows(b2_rows, turnover_max=turnover_max)
    clusters = sorted(set(b1_by_cluster) | set(b2_by_cluster))
    output: list[dict[str, Any]] = []
    for cluster in clusters:
        left = b1_by_cluster.get(cluster, [])
        right = b2_by_cluster.get(cluster, [])
        b1_deployable = [row for row in left if _is_deployable(row, turnover_max)]
        b2_deployable = [row for row in right if _is_deployable(row, turnover_max)]
        output.append(
            {
                "cluster_id": cluster,
                "status": "shared" if b1_deployable and b2_deployable else "b1_only" if b1_deployable else "b2_only" if b2_deployable else "non_deployable_overlap",
                "b1_raw_non_gap_count": sum(1 for row in left if _non_gap_replay_pass(row)),
                "b2_raw_non_gap_count": sum(1 for row in right if _non_gap_replay_pass(row)),
                "b1_deployable_count": len(b1_deployable),
                "b2_deployable_count": len(b2_deployable),
                "b1_has_deployable": bool(b1_deployable),
                "b2_has_deployable": bool(b2_deployable),
                "example_expression": _representative_expression(b1_deployable or b2_deployable or left or right),
            }
        )
    return output


def build_top_cluster_audit(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    scopes: dict[str, list[dict[str, Any]]] = {"GLOBAL": [row for row in rows if _is_phase3(row)]}
    for row in rows:
        if _is_phase3(row):
            scopes.setdefault(str(row.get("ablation_arm")), []).append(row)

    for scope, group in sorted(scopes.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        counts = Counter(_cluster_id(row) for row in non_gap)
        for cluster, count in counts.most_common(10):
            cluster_group = [row for row in group if _cluster_id(row) == cluster]
            deployable = [row for row in cluster_group if _is_deployable(row, turnover_max)]
            output.append(
                {
                    "scope": scope,
                    "cluster_id": cluster,
                    "raw_non_gap_count": count,
                    "raw_non_gap_share": round(count / max(1, len(non_gap)), 6),
                    "deployable_row_count": len(deployable),
                    "unique_expression_count": len({str(row.get("expression") or "") for row in cluster_group}),
                    "arms": "|".join(sorted({str(row.get("ablation_arm")) for row in cluster_group if row.get("ablation_arm")})),
                    "lanes": "|".join(sorted({str(row.get("phase3_budget_bucket")) for row in cluster_group if row.get("phase3_budget_bucket")})),
                    "median_turnover_deployable": _median([_safe_float(row.get("strict_mean_one_way_turnover"), float("nan")) for row in deployable]),
                    "median_complexity_deployable": _median([float(_expression_complexity(str(row.get("expression") or "")) or 0) for row in deployable]),
                    "example_expression": _representative_expression(deployable or cluster_group),
                }
            )
    return output


def _load_run_report(row: dict[str, Any]) -> dict[str, Any]:
    root = row.get("seed_root")
    if not root:
        return {}
    path = Path(str(root)) / "phase3_repair_report.json"
    if not path.exists():
        return {}
    try:
        return _read_json(path)
    except Exception:
        return {}


def build_b3_quota_failure_audit(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    b3_rows = _arm_rows(rows, B3)
    quota_keys = [
        "quota_applied",
        "quota_type",
        "quota_stage",
        "quota_basis",
        "rejected_by_quota",
        "quota_reject_reason",
        "parent_cluster",
        "provisional_child_cluster",
        "final_child_cluster",
        "escaped_parent_cluster",
    ]
    for row in b3_rows:
        if any(row.get(key) not in (None, "", False) for key in quota_keys):
            output.append(
                {
                    "source": "audited_row",
                    "seed": row.get("source_seed"),
                    "candidate_id": row.get("candidate_id"),
                    "cluster_id": _cluster_id(row),
                    "phase3_budget_bucket": row.get("phase3_budget_bucket"),
                    "selection_policy": row.get("selection_policy"),
                    "non_gap_pass": _non_gap_replay_pass(row),
                    "deployable": _is_deployable(row, turnover_max),
                    **{key: row.get(key) for key in quota_keys},
                }
            )

    seen_reports: set[str] = set()
    for row in b3_rows:
        root = str(row.get("seed_root") or "")
        if not root or root in seen_reports:
            continue
        seen_reports.add(root)
        report = _load_run_report(row)
        summary = report.get("quota_event_summary") if isinstance(report, dict) else None
        if isinstance(summary, list):
            for item in summary:
                if isinstance(item, dict):
                    output.append({"source": "run_report_quota_event_summary", "seed_root": root, **item})
        elif isinstance(summary, dict):
            output.append({"source": "run_report_quota_event_summary", "seed_root": root, **summary})
        count = report.get("quota_event_count") if isinstance(report, dict) else None
        if count is not None and not summary:
            output.append({"source": "run_report_quota_event_count", "seed_root": root, "quota_event_count": count})

    if not output:
        output.append(
            {
                "source": "audit_note",
                "note": "No row-level quota rejection metadata found in audited B3 rows; inspect run reports if future quota code writes pre-audit rejection ledgers.",
                "b3_audited_rows": len(b3_rows),
            }
        )
    return output


def build_ast_repair_by_arm(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _is_phase3(row) and row.get("phase3_budget_bucket") == "ast_failure_aware_repair":
            grouped[str(row.get("ablation_arm"))].append(row)
    for arm, group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _is_deployable(row, turnover_max)]
        counts = Counter(_cluster_id(row) for row in non_gap)
        top_cluster, top_count = counts.most_common(1)[0] if counts else ("none", 0)
        output.append(
            {
                "ablation_arm": arm,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "unique_return_corr_clusters": len({_cluster_id(row) for row in non_gap}),
                "deployable_clusters": len({_cluster_id(row) for row in deployable}),
                "top_cluster_id": top_cluster,
                "top_cluster_share": round(top_count / max(1, len(non_gap)), 6),
                "repair_policies": "|".join(sorted({str(row.get("repair_policy")) for row in group if row.get("repair_policy")})),
                "deployable_cluster_ids": "|".join(sorted({_cluster_id(row) for row in deployable})),
            }
        )
    return output


def build_cluster_credit_simulation(rows: list[dict[str, Any]], *, turnover_max: float) -> list[dict[str, Any]]:
    output = []
    scopes: dict[str, list[dict[str, Any]]] = {"GLOBAL": [row for row in rows if _is_phase3(row)]}
    for row in rows:
        if _is_phase3(row):
            scopes.setdefault(str(row.get("ablation_arm")), []).append(row)
    for scope, group in sorted(scopes.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _is_deployable(row, turnover_max)]
        counts = Counter(_cluster_id(row) for row in non_gap)
        top_cluster, top_count = counts.most_common(1)[0] if counts else ("none", 0)
        output.append(
            {
                "scope": scope,
                "audited": len(group),
                "raw_non_gap_pass": len(non_gap),
                "raw_non_gap_per_audited": round(len(non_gap) / max(1, len(group)), 6),
                "unique_non_gap_clusters": len(counts),
                "deployable_clusters": len({_cluster_id(row) for row in deployable}),
                "top_cluster_id": top_cluster,
                "top_cluster_share": round(top_count / max(1, len(non_gap)), 6),
                "cluster_cap_credit_1_per_cluster": len(counts),
                "inverse_sqrt_raw_credit": round(sum(count / math.sqrt(count) for count in counts.values()), 6),
                "raw_to_cap_inflation": round(len(non_gap) / max(1, len(counts)), 6),
            }
        )
    return output


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_empty_\n"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def write_decision_record(path: Path, report: dict[str, Any], cluster_credit: list[dict[str, Any]], ast_by_arm: list[dict[str, Any]]) -> None:
    per_arm = report.get("per_arm_metrics", [])
    arm_by_name = {row.get("ablation_arm"): row for row in per_arm if isinstance(row, dict)}
    b1 = arm_by_name.get(B1, {})
    b2 = arm_by_name.get(B2, {})
    b3 = arm_by_name.get(B3, {})
    lines = [
        "# Phase3B Decision Record - 2026-05-12",
        "",
        "## Decision",
        "",
        "- B3 repair-aware soft quota failed to confirm: raw non-gap was high, but deployable clusters did not beat B2/B1 and top-cluster concentration worsened.",
        "- B1 Phase3A full is selected as the stable incumbent (`C0S`) because it has comparable deployable output with lower concentration.",
        "- B2 direct R0 quota only is selected as the productive incumbent (`C0P`) with cluster-credit caution because it produced the most deployable clusters but concentrated too strongly.",
        "- AST repair is retained. It remains a real contributor and should not be removed.",
        "- Phase3C is blocked until this record and the posthoc audit CSVs are reviewed; Phase3C must measure new deployable clusters versus the Phase3B union, not versus Phase2 R0.",
        "",
        "## Arm Metrics",
        "",
        _markdown_table(
            per_arm,
            [
                "ablation_arm",
                "audited",
                "raw_non_gap_pass",
                "unique_return_corr_clusters",
                "deployable_clusters",
                "top_cluster_share",
                "median_turnover",
                "median_complexity",
            ],
        ),
        "## Incumbents",
        "",
        f"- C0S = `{B1}`: deployable `{b1.get('deployable_clusters')}`, top cluster share `{b1.get('top_cluster_share')}`.",
        f"- C0P = `{B2}`: deployable `{b2.get('deployable_clusters')}`, top cluster share `{b2.get('top_cluster_share')}`; apply cluster-credit cap before using as a source.",
        f"- Rejected as current default = `{B3}`: deployable `{b3.get('deployable_clusters')}`, top cluster share `{b3.get('top_cluster_share')}`.",
        "",
        "## AST Repair",
        "",
        _markdown_table(ast_by_arm, ["ablation_arm", "audited", "raw_non_gap_pass", "unique_return_corr_clusters", "deployable_clusters", "top_cluster_share"]),
        "## Cluster-Credit Simulation",
        "",
        _markdown_table(cluster_credit, ["scope", "audited", "raw_non_gap_pass", "unique_non_gap_clusters", "deployable_clusters", "top_cluster_share", "cluster_cap_credit_1_per_cluster", "inverse_sqrt_raw_credit", "raw_to_cap_inflation"]),
        "## Phase3C Baseline Contract",
        "",
        "- C0S: B1 stable control.",
        "- C0P: B2 productive control plus cluster-credit cap.",
        "- C1/C2/C3 FormulaGenV2 or open-ended generator variants must report new deployable clusters vs the Phase3B union cluster set.",
        "- Raw pass is diagnostic only.",
        "",
        "## Reproducibility",
        "",
        f"- aggregate_experiment_id: `{report.get('experiment_id')}`",
        f"- aggregate_decision: `{report.get('decision')}`",
        f"- metadata_gate_decision: `{report.get('phase3A_pass_criteria', {}).get('metadata_gate_decision')}`",
        f"- created_at: `{datetime.now(timezone.utc).astimezone().isoformat()}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate-json", required=True, type=Path)
    parser.add_argument("--clustered-rows-json", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    report = _read_json(args.aggregate_json)
    rows = _read_json(args.clustered_rows_json).get("rows", [])

    b1_b2_overlap = build_b1_b2_overlap(rows, turnover_max=args.turnover_max)
    top_cluster_audit = build_top_cluster_audit(rows, turnover_max=args.turnover_max)
    b3_quota_failure = build_b3_quota_failure_audit(rows, turnover_max=args.turnover_max)
    ast_by_arm = build_ast_repair_by_arm(rows, turnover_max=args.turnover_max)
    cluster_credit = build_cluster_credit_simulation(rows, turnover_max=args.turnover_max)

    _write_csv(args.output_root / "phase3B_b1_b2_overlap.csv", b1_b2_overlap)
    _write_csv(args.output_root / "phase3B_top_cluster_audit.csv", top_cluster_audit)
    _write_csv(args.output_root / "phase3B_b3_quota_failure_audit.csv", b3_quota_failure)
    _write_csv(args.output_root / "phase3B_ast_repair_by_arm.csv", ast_by_arm)
    _write_csv(args.output_root / "phase3B_cluster_credit_simulation.csv", cluster_credit)

    write_decision_record(args.output_root / "PHASE3B_DECISION_RECORD_2026-05-12.md", report, cluster_credit, ast_by_arm)
    write_json_artifact(
        args.output_root / "phase3B_posthoc_manifest.json",
        {
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "aggregate_json": str(args.aggregate_json),
            "clustered_rows_json": str(args.clustered_rows_json),
            "outputs": [
                "PHASE3B_DECISION_RECORD_2026-05-12.md",
                "phase3B_b1_b2_overlap.csv",
                "phase3B_top_cluster_audit.csv",
                "phase3B_b3_quota_failure_audit.csv",
                "phase3B_ast_repair_by_arm.csv",
                "phase3B_cluster_credit_simulation.csv",
            ],
        },
    )
    print(json.dumps({"output_root": str(args.output_root), "files": 7}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
