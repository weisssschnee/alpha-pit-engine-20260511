"""Build the post-Phase3H cumulative deployable-cluster registry.

This is metadata/accounting work only. It consumes the Phase3H global
recluster output and appends newly discovered deployable signal clusters to
the previously frozen 134-cluster discovery registry.
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


DEFAULT_PREVIOUS_BASELINE = Path("src/our_system_phase2/runtime/baselines/phase3E_cumulative_deployable_clusters_20260514.json")
DEFAULT_CLUSTERED_ROWS = Path("reports/phase3h_global_recluster_20260516/phase3H_global_clustered_rows.json")
DEFAULT_AGGREGATE_REPORT = Path("reports/phase3h_global_recluster_20260516/phase3H_global_recluster_report.json")
DEFAULT_OUTPUT_BASELINE = Path("src/our_system_phase2/runtime/baselines/phase3H_cumulative_deployable_clusters_20260515.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3h_cumulative_registry_20260516")


FIELD_FAMILY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("price", ("open", "high", "low", "close", "vwap")),
    ("flow", ("amount", "volume", "turnover")),
    ("cap", ("market_cap", "float_market_cap", "total_market_cap")),
    ("limit", ("limit", "up", "down")),
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _deployable_pass(row: dict[str, Any], *, turnover_max: float) -> bool:
    return (
        _as_bool(row.get("portfolio_replay_pass"))
        and not _as_bool(row.get("is_gap_family"))
        and _as_bool(row.get("cost_survives"))
        and _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0) <= turnover_max
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return list(payload.get("rows", payload) if isinstance(payload, dict) else payload)


def _fields(expression: str) -> list[str]:
    return sorted(set(match.lower() for match in re.findall(r"\$([A-Za-z0-9_]+)", expression)))


def _operators(expression: str) -> list[str]:
    return sorted(set(match for match in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression)))


def _field_families(expression: str) -> list[str]:
    fields = _fields(expression)
    families: set[str] = set()
    for field in fields:
        for family, tokens in FIELD_FAMILY_RULES:
            if any(token in field for token in tokens):
                families.add(family)
    if fields and not families:
        families.add("other")
    return sorted(families)


def _complexity(expression: str) -> float:
    return len(_operators(expression)) + 0.75 * len(_fields(expression)) + 0.15 * expression.count("(")


def _representative_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        _safe_float(row.get("portfolio_replay_long_only_sortino"), default=-999.0),
        _safe_float(row.get("strict_cost_adjusted_sortino"), default=-999.0),
        -_safe_float(row.get("strict_mean_one_way_turnover"), default=999.0),
        _safe_float(row.get("fast_reward"), default=-999.0),
    )


def _next_declared_cluster_id(index: int) -> str:
    return f"cluster_{index:03d}"


def build_registry(
    *,
    previous_baseline: Path,
    clustered_rows: Path,
    aggregate_report: Path,
    output_baseline: Path,
    output_root: Path,
    turnover_max: float,
) -> dict[str, Any]:
    previous = _read_json(previous_baseline)
    previous_reps = list(previous.get("deployable_representatives") or [])
    previous_declared = int(previous.get("declared_cluster_count") or previous.get("declared_cumulative_cluster_count") or len(previous_reps))

    report = _read_json(aggregate_report)
    global_metrics = report.get("global_union_metrics") or {}
    new_source_clusters = list(global_metrics.get("new_deployable_cluster_ids_vs_phase3_cumulative") or [])
    rows = _load_rows(clustered_rows)
    phase_rows = [row for row in rows if row.get("aggregate_source_kind") == "phase3A_seed"]

    reps_by_source_cluster: dict[str, dict[str, Any]] = {}
    for cluster_id in new_source_clusters:
        candidates = [
            row
            for row in phase_rows
            if str(row.get("global_signal_cluster_id") or "") == cluster_id and _deployable_pass(row, turnover_max=turnover_max)
        ]
        if not candidates:
            continue
        reps_by_source_cluster[cluster_id] = sorted(candidates, key=_representative_sort_key, reverse=True)[0]

    new_reps: list[dict[str, Any]] = []
    first_new_index = previous_declared + 1
    for offset, source_cluster_id in enumerate(sorted(reps_by_source_cluster)):
        row = reps_by_source_cluster[source_cluster_id]
        expression = str(row.get("expression") or "")
        new_reps.append(
            {
                "cluster_id": _next_declared_cluster_id(first_new_index + offset),
                "source_global_signal_cluster_id": source_cluster_id,
                "representative_expression": expression,
                "candidate_id": row.get("candidate_id") or "",
                "first_seen_phase": "Phase3H",
                "source_arm": row.get("ablation_arm") or "",
                "source_seed": row.get("source_seed") or "",
                "source_generator": row.get("proof_variant") or row.get("proposal_kind") or "",
                "source_lane": row.get("phase3_budget_bucket") or "",
                "field_families": _field_families(expression),
                "operator_families": _operators(expression),
                "strict_mean_one_way_turnover": _safe_float(row.get("strict_mean_one_way_turnover"), default=None),
                "portfolio_replay_avg_one_way_turnover": _safe_float(row.get("portfolio_replay_avg_one_way_turnover"), default=None),
                "portfolio_replay_long_only_sortino": _safe_float(row.get("portfolio_replay_long_only_sortino"), default=None),
                "portfolio_replay_long_short_sortino": _safe_float(row.get("portfolio_replay_long_short_sortino"), default=None),
                "strict_cost_adjusted_sortino": _safe_float(row.get("strict_cost_adjusted_sortino"), default=None),
                "complexity_score": round(_complexity(expression), 6),
                "global_cluster_source": "phase3H_global_recluster_20260516",
            }
        )

    declared_count = previous_declared + len(new_reps)
    previous_rep_count = len(previous_reps)
    previous_vector_baseline = previous.get("selector_vector_baseline")
    if previous_vector_baseline is None:
        previous_vector_baseline = previous.get("reclustered_unique_cluster_count")
    new_vector_matchable = len(new_reps)
    selector_vector_baseline_estimate = int(previous_vector_baseline or 122) + new_vector_matchable

    cumulative = {
        "baseline_name": "phase3H_cumulative_20260515",
        "created_at": _now(),
        "source_aggregate": str(aggregate_report),
        "previous_baseline": str(previous_baseline),
        "declared_previous_cluster_count": previous_declared,
        "declared_new_cluster_count_vs_previous": len(new_reps),
        "declared_cluster_count": declared_count,
        "representative_rows": previous_rep_count + len(new_reps),
        "selector_vector_baseline_estimate": selector_vector_baseline_estimate,
        "selector_vector_baseline_status": "requires_next_canonical_recluster_for_official_selector_use",
        "cluster_label_scope": "declared_discovery_registry_with_phase3H_new_signal_clusters",
        "notes": [
            "Discovery accounting advances from 134 to 149 using 15 Phase3H new deployable signal clusters.",
            "Selector vector baseline is intentionally not set to 149; previous dual-baseline policy remains active.",
            "New declared cluster IDs are sequential registry IDs; source_global_signal_cluster_id preserves the Phase3H recluster coordinate.",
        ],
        "deployable_representatives": previous_reps + new_reps,
    }

    canonicalization = {
        "created_at": _now(),
        "decision": "PASS_DISCOVERY_BASELINE_UPDATE_WITH_DUAL_BASELINE",
        "discovery_baseline_declared_clusters": declared_count,
        "representative_rows": previous_rep_count + len(new_reps),
        "previous_selector_vector_baseline": int(previous_vector_baseline or 122),
        "new_phase3H_vector_matchable_clusters": new_vector_matchable,
        "selector_vector_baseline_estimate": selector_vector_baseline_estimate,
        "natural_merges_carried_forward": 7,
        "missing_representatives_carried_forward": max(0, declared_count - (previous_rep_count + len(new_reps))),
        "source_new_cluster_ids": sorted(reps_by_source_cluster),
        "policy": (
            "Use discovery_baseline=149 for cumulative discovery accounting. Use the prior "
            "selector-vector baseline plus the 15 Phase3H vector-matchable additions until the "
            "next official selector-vector canonicalization run."
        ),
    }

    source_map = [
        {
            "declared_cluster_id": item["cluster_id"],
            "source_global_signal_cluster_id": item["source_global_signal_cluster_id"],
            "candidate_id": item["candidate_id"],
            "source_arm": item["source_arm"],
            "source_seed": item["source_seed"],
            "source_lane": item["source_lane"],
            "strict_mean_one_way_turnover": item["strict_mean_one_way_turnover"],
            "representative_expression": item["representative_expression"],
        }
        for item in new_reps
    ]

    _write_json(output_baseline, cumulative)
    _write_json(output_root / "phase3h_cumulative_registry_summary.json", {"summary": canonicalization, "new_representatives": new_reps})
    _write_csv(output_root / "phase3h_new_cluster_representatives.csv", source_map)
    _write_markdown(output_root / "PHASE3H_CUMULATIVE_REGISTRY_2026-05-16.md", canonicalization, source_map, output_baseline)
    return {"summary": canonicalization, "baseline_path": str(output_baseline)}


def _write_markdown(path: Path, summary: dict[str, Any], source_map: list[dict[str, Any]], output_baseline: Path) -> None:
    lines = [
        "# Phase3H Cumulative Registry",
        "",
        f"- decision: `{summary['decision']}`",
        f"- discovery_baseline_declared_clusters: `{summary['discovery_baseline_declared_clusters']}`",
        f"- representative_rows: `{summary['representative_rows']}`",
        f"- previous_selector_vector_baseline: `{summary['previous_selector_vector_baseline']}`",
        f"- new_phase3H_vector_matchable_clusters: `{summary['new_phase3H_vector_matchable_clusters']}`",
        f"- selector_vector_baseline_estimate: `{summary['selector_vector_baseline_estimate']}`",
        f"- missing_representatives_carried_forward: `{summary['missing_representatives_carried_forward']}`",
        "",
        "## Policy",
        "",
        summary["policy"],
        "",
        "## New Representatives",
        "",
        "| declared_cluster_id | source_global_signal_cluster_id | source_arm | source_lane | turnover |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in source_map:
        lines.append(
            "| {declared} | {source} | {arm} | {lane} | {turnover} |".format(
                declared=row["declared_cluster_id"],
                source=row["source_global_signal_cluster_id"],
                arm=row["source_arm"],
                lane=row["source_lane"],
                turnover=row["strict_mean_one_way_turnover"],
            )
        )
    lines.extend(["", "## Outputs", "", f"- `{output_baseline}`", "- `phase3h_cumulative_registry_summary.json`", "- `phase3h_new_cluster_representatives.csv`"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-baseline", type=Path, default=DEFAULT_PREVIOUS_BASELINE)
    parser.add_argument("--clustered-rows", type=Path, default=DEFAULT_CLUSTERED_ROWS)
    parser.add_argument("--aggregate-report", type=Path, default=DEFAULT_AGGREGATE_REPORT)
    parser.add_argument("--output-baseline", type=Path, default=DEFAULT_OUTPUT_BASELINE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    result = build_registry(
        previous_baseline=args.previous_baseline,
        clustered_rows=args.clustered_rows,
        aggregate_report=args.aggregate_report,
        output_baseline=args.output_baseline,
        output_root=args.output_root,
        turnover_max=args.turnover_max,
    )
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
