"""Complete the 149-entry representative registry and audit Phase3K-B novelty.

This is metadata/accounting work only. It does not rerun search, strict
evaluation, replay, or filtering. The goal is to avoid treating the existing
149 declared baseline as a full representative registry when it only contains
144 representative rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PHASE3D_BASELINE = Path("src/our_system_phase2/runtime/baselines/phase3D_cumulative_deployable_clusters_20260514.json")
DEFAULT_PHASE3E_AGGREGATE = Path("reports/phase3e_official_s21_s24_company_20260514/phase3E_official_s21_s24_global_aggregate.json")
DEFAULT_PHASE3E_CLUSTERED_ROWS = Path("reports/phase3e_official_s21_s24_company_20260514/phase3E_official_s21_s24_global_clustered_rows.json")
DEFAULT_PHASE3H_BASELINE = Path("src/our_system_phase2/runtime/baselines/phase3H_cumulative_deployable_clusters_20260515.json")
DEFAULT_KB_CLUSTER_METRICS = Path("reports/phase3k_b_locked_filter_generalization_20260516/phase3k_b_cluster_metrics.csv")
DEFAULT_KB_BOOK_MEMBERS = Path("reports/phase3k_b_locked_filter_generalization_20260516/phase3k_b_book_members.csv")
DEFAULT_KB_REMOVED = Path("reports/phase3k_b_locked_filter_generalization_20260516/phase3k_b_j4_removed_clusters.csv")
DEFAULT_OUTPUT_BASELINE = Path("runtime/baselines/phase3K_complete_149_representative_registry_20260517.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3k_c_complete_149_registry_20260517")

SIGNAL_COLLISION_THRESHOLD = 0.80


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _safe_float(value: Any, default: float | None = None) -> float | None:
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
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass"}


def _canonical_expression(expression: str) -> str:
    return re.sub(r"\s+", "", expression or "")


def _fields(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")))


def _operators(expression: str) -> list[str]:
    return sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", expression or "")))


def _deployable_pass(row: dict[str, Any], turnover_max: float) -> bool:
    return (
        _as_bool(row.get("portfolio_replay_pass"))
        and not _as_bool(row.get("is_gap_family"))
        and _as_bool(row.get("cost_survives"))
        and (_safe_float(row.get("strict_mean_one_way_turnover"), 999.0) or 999.0) <= turnover_max
    )


def _representative_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        _safe_float(row.get("portfolio_replay_long_only_sortino"), -999.0) or -999.0,
        _safe_float(row.get("strict_cost_adjusted_sortino"), -999.0) or -999.0,
        -(_safe_float(row.get("strict_mean_one_way_turnover"), 999.0) or 999.0),
        _safe_float(row.get("fast_reward"), -999.0) or -999.0,
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("rows", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise TypeError(f"expected rows list in {path}")
    return rows


def _base_entry(
    *,
    index: int,
    source: str,
    representative: dict[str, Any],
    source_global_signal_cluster_id: str | None = None,
) -> dict[str, Any]:
    expression = str(representative.get("representative_expression") or representative.get("expression") or "")
    return {
        "registry_entry_id": f"registry_{index:03d}",
        "legacy_cluster_id": representative.get("cluster_id") or "",
        "source_global_signal_cluster_id": source_global_signal_cluster_id or representative.get("source_global_signal_cluster_id") or "",
        "registry_source": source,
        "representative_expression": expression,
        "canonical_expression": _canonical_expression(expression),
        "candidate_id": representative.get("candidate_id") or "",
        "first_seen_phase": representative.get("first_seen_phase") or "",
        "source_arm": representative.get("source_arm") or "",
        "source_seed": representative.get("source_seed") or "",
        "source_generator": representative.get("source_generator") or representative.get("proof_variant") or representative.get("proposal_kind") or "",
        "source_lane": representative.get("source_lane") or representative.get("phase3_budget_bucket") or "",
        "field_list": _fields(expression),
        "operator_families": representative.get("operator_families") or _operators(expression),
        "strict_mean_one_way_turnover": _safe_float(representative.get("strict_mean_one_way_turnover")),
        "portfolio_replay_avg_one_way_turnover": _safe_float(representative.get("portfolio_replay_avg_one_way_turnover")),
        "portfolio_replay_long_only_sortino": _safe_float(representative.get("portfolio_replay_long_only_sortino")),
        "strict_cost_adjusted_sortino": _safe_float(representative.get("strict_cost_adjusted_sortino")),
    }


def _phase3e_new_representatives(aggregate_path: Path, rows_path: Path, turnover_max: float) -> list[dict[str, Any]]:
    aggregate = _read_json(aggregate_path)
    metrics = aggregate.get("global_union_metrics") or {}
    new_cluster_ids = list(metrics.get("new_deployable_cluster_ids_vs_phase3_cumulative") or [])
    rows = _load_rows(rows_path)
    out: list[dict[str, Any]] = []
    for cluster_id in sorted(new_cluster_ids):
        candidates = [
            row
            for row in rows
            if row.get("aggregate_source_kind") == "phase3A_seed"
            and str(row.get("global_signal_cluster_id") or "") == cluster_id
            and _deployable_pass(row, turnover_max)
        ]
        if not candidates:
            continue
        row = sorted(candidates, key=_representative_sort_key, reverse=True)[0]
        expression = str(row.get("expression") or "")
        out.append(
            {
                "cluster_id": cluster_id,
                "source_global_signal_cluster_id": cluster_id,
                "representative_expression": expression,
                "candidate_id": row.get("candidate_id") or "",
                "first_seen_phase": "Phase3E",
                "source_arm": row.get("ablation_arm") or "",
                "source_seed": row.get("source_seed") or "",
                "source_generator": row.get("proof_variant") or row.get("proposal_kind") or "",
                "source_lane": row.get("phase3_budget_bucket") or "",
                "strict_mean_one_way_turnover": row.get("strict_mean_one_way_turnover"),
                "portfolio_replay_avg_one_way_turnover": row.get("portfolio_replay_avg_one_way_turnover"),
                "portfolio_replay_long_only_sortino": row.get("portfolio_replay_long_only_sortino"),
                "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
            }
        )
    return out


def _phase3h_new_representatives(phase3h_baseline: Path) -> list[dict[str, Any]]:
    baseline = _read_json(phase3h_baseline)
    reps = list(baseline.get("deployable_representatives") or [])
    return [row for row in reps if str(row.get("first_seen_phase") or "") == "Phase3H"]


def _build_complete_registry(
    *,
    phase3d_baseline: Path,
    phase3e_aggregate: Path,
    phase3e_clustered_rows: Path,
    phase3h_baseline: Path,
    turnover_max: float,
) -> dict[str, Any]:
    phase3d = _read_json(phase3d_baseline)
    phase3d_reps = list(phase3d.get("deployable_representatives") or [])
    phase3e_new = _phase3e_new_representatives(phase3e_aggregate, phase3e_clustered_rows, turnover_max)
    phase3h_new = _phase3h_new_representatives(phase3h_baseline)

    entries: list[dict[str, Any]] = []
    index = 1
    for row in phase3d_reps:
        entries.append(_base_entry(index=index, source="phase3D_cumulative_previous_103", representative=row))
        index += 1
    for row in phase3e_new:
        entries.append(
            _base_entry(
                index=index,
                source="phase3E_new_vs_phase3D_31",
                representative=row,
                source_global_signal_cluster_id=str(row.get("source_global_signal_cluster_id") or row.get("cluster_id") or ""),
            )
        )
        index += 1
    for row in phase3h_new:
        entries.append(
            _base_entry(
                index=index,
                source="phase3H_new_vs_phase3E_15",
                representative=row,
                source_global_signal_cluster_id=str(row.get("source_global_signal_cluster_id") or ""),
            )
        )
        index += 1

    missing_expression = [row for row in entries if not row.get("canonical_expression")]
    duplicate_exprs: dict[str, int] = {}
    for row in entries:
        expr = row.get("canonical_expression")
        if expr:
            duplicate_exprs[expr] = duplicate_exprs.get(expr, 0) + 1

    return {
        "baseline_name": "phase3K_complete_149_representative_registry_20260517",
        "created_at": _now(),
        "declared_cluster_count": 149,
        "representative_rows": len(entries),
        "source_inputs": {
            "phase3d_baseline": str(phase3d_baseline),
            "phase3e_aggregate": str(phase3e_aggregate),
            "phase3e_clustered_rows": str(phase3e_clustered_rows),
            "phase3h_baseline": str(phase3h_baseline),
        },
        "source_counts": {
            "phase3D_previous": len(phase3d_reps),
            "phase3E_new": len(phase3e_new),
            "phase3H_new": len(phase3h_new),
        },
        "quality": {
            "missing_representative_expression_count": len(missing_expression),
            "duplicate_canonical_expression_count": sum(count - 1 for count in duplicate_exprs.values() if count > 1),
            "is_complete_149_representative_registry": len(entries) == 149 and not missing_expression,
        },
        "notes": [
            "This registry repairs the earlier 149 declared / 144 representative gap by using Phase3D's 103 representative rows directly, then appending Phase3E's 31 new representatives and Phase3H's 15 new representatives.",
            "No representative rows are fabricated. Missing expressions would make the registry fail the completeness gate.",
        ],
        "deployable_representatives": entries,
    }


def _kb_novelty_rows(
    *,
    registry: dict[str, Any],
    cluster_metrics_path: Path,
    book_members_path: Path,
    removed_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    registry_exprs = {str(row.get("canonical_expression")) for row in registry.get("deployable_representatives", []) if row.get("canonical_expression")}
    cluster_rows = _read_csv(cluster_metrics_path)
    by_cluster: dict[str, dict[str, str]] = {row.get("cluster_id", ""): row for row in cluster_rows}
    book_rows = _read_csv(book_members_path)
    removed_rows = _read_csv(removed_path)

    output: list[dict[str, Any]] = []
    for row in book_rows:
        cluster = row.get("cluster_id", "")
        expr = row.get("representative_expression", "")
        exact_match = _canonical_expression(expr) in registry_exprs
        max_corr = _safe_float(row.get("max_corr_to_registry"), 0.0) or 0.0
        known_collision = max_corr >= SIGNAL_COLLISION_THRESHOLD
        new_proxy = not exact_match and not known_collision
        output.append(
            {
                "book": row.get("book"),
                "cluster_id": cluster,
                "new_vs_149_proxy": new_proxy,
                "known_vs_149_reason": "exact_expression_match" if exact_match else ("signal_collision_ge_0p80" if known_collision else ""),
                "max_corr_to_149_registry_proxy": round(max_corr, 6),
                "exact_expression_match_149": exact_match,
                "field_families": row.get("field_families"),
                "operator_families": row.get("operator_families"),
                "source_lane": row.get("source_lane"),
                "capacity_proxy": row.get("capacity_proxy"),
                "cost_adjusted_score": row.get("cost_adjusted_score"),
                "p90_replay_turnover": row.get("p90_replay_turnover"),
                "representative_candidate_id": row.get("representative_candidate_id"),
                "representative_expression": expr,
            }
        )

    removed_output: list[dict[str, Any]] = []
    for row in removed_rows:
        cluster = row.get("cluster_id", "")
        source = by_cluster.get(cluster, {})
        expr = row.get("representative_expression") or source.get("representative_expression") or ""
        max_corr = _safe_float(source.get("max_corr_to_registry"), 0.0) or 0.0
        exact_match = _canonical_expression(expr) in registry_exprs
        known_collision = max_corr >= SIGNAL_COLLISION_THRESHOLD
        removed_output.append(
            {
                **row,
                "new_vs_149_proxy": not exact_match and not known_collision,
                "known_vs_149_reason": "exact_expression_match" if exact_match else ("signal_collision_ge_0p80" if known_collision else ""),
                "max_corr_to_149_registry_proxy": round(max_corr, 6),
                "exact_expression_match_149": exact_match,
            }
        )

    summary_by_book: dict[str, dict[str, Any]] = {}
    for book in sorted({str(row.get("book")) for row in output}):
        subset = [row for row in output if str(row.get("book")) == book]
        new_subset = [row for row in subset if row.get("new_vs_149_proxy")]
        summary_by_book[book] = {
            "cluster_count": len(subset),
            "new_vs_149_proxy_count": len(new_subset),
            "known_vs_149_proxy_count": len(subset) - len(new_subset),
            "new_vs_149_proxy_share": round(len(new_subset) / max(1, len(subset)), 6),
        }

    family_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], int] = {}
    for row in output:
        status = "new_vs_149_proxy" if row.get("new_vs_149_proxy") else "known_vs_149_proxy"
        key = (str(row.get("book")), status, str(row.get("field_families")), str(row.get("operator_families")))
        grouped[key] = grouped.get(key, 0) + 1
    for (book, status, fields, operators), count in sorted(grouped.items()):
        family_rows.append(
            {
                "book": book,
                "novelty_status": status,
                "field_families": fields,
                "operator_families": operators,
                "cluster_count": count,
            }
        )

    summary = {
        "signal_collision_threshold": SIGNAL_COLLISION_THRESHOLD,
        "book_summary": summary_by_book,
        "removed_new_vs_149_proxy_count": sum(1 for row in removed_output if row.get("new_vs_149_proxy")),
        "removed_known_vs_149_proxy_count": sum(1 for row in removed_output if not row.get("new_vs_149_proxy")),
        "classification_mode": "proxy_exact_expression_or_signal_collision_threshold",
    }
    return output, removed_output, {"summary": summary, "family_rows": family_rows}


def _write_markdown(path: Path, registry: dict[str, Any], novelty: dict[str, Any]) -> None:
    summary = novelty["summary"]
    lines = [
        "# Phase3K-C Complete 149 Representative Registry",
        "",
        f"- created_at: `{registry['created_at']}`",
        f"- decision: `{'PASS_COMPLETE_149_REPRESENTATIVE_REGISTRY' if registry['quality']['is_complete_149_representative_registry'] else 'HOLD_REGISTRY_INCOMPLETE'}`",
        f"- declared_cluster_count: `{registry['declared_cluster_count']}`",
        f"- representative_rows: `{registry['representative_rows']}`",
        f"- missing_representative_expression_count: `{registry['quality']['missing_representative_expression_count']}`",
        "",
        "## Source Counts",
        "",
        f"- Phase3D previous representatives: `{registry['source_counts']['phase3D_previous']}`",
        f"- Phase3E new representatives: `{registry['source_counts']['phase3E_new']}`",
        f"- Phase3H new representatives: `{registry['source_counts']['phase3H_new']}`",
        "",
        "## K-B New-vs-149 Proxy",
        "",
        "| book | clusters | new proxy | known proxy | new share |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for book, item in sorted(summary["book_summary"].items()):
        lines.append(
            f"| {book} | {item['cluster_count']} | {item['new_vs_149_proxy_count']} | {item['known_vs_149_proxy_count']} | {item['new_vs_149_proxy_share']} |"
        )
    lines.extend(
        [
            "",
            "## Removed Clusters",
            "",
            f"- removed new-vs-149 proxy count: `{summary['removed_new_vs_149_proxy_count']}`",
            f"- removed known-vs-149 proxy count: `{summary['removed_known_vs_149_proxy_count']}`",
            "",
            "## Scope",
            "",
            "- This is a representative-registry and novelty-proxy audit.",
            "- `new_vs_149_proxy` uses exact expression match plus signal-collision threshold >= 0.80.",
            "- It is not a minute execution, capacity, or production deployment proof.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase3d-baseline", type=Path, default=DEFAULT_PHASE3D_BASELINE)
    parser.add_argument("--phase3e-aggregate", type=Path, default=DEFAULT_PHASE3E_AGGREGATE)
    parser.add_argument("--phase3e-clustered-rows", type=Path, default=DEFAULT_PHASE3E_CLUSTERED_ROWS)
    parser.add_argument("--phase3h-baseline", type=Path, default=DEFAULT_PHASE3H_BASELINE)
    parser.add_argument("--kb-cluster-metrics", type=Path, default=DEFAULT_KB_CLUSTER_METRICS)
    parser.add_argument("--kb-book-members", type=Path, default=DEFAULT_KB_BOOK_MEMBERS)
    parser.add_argument("--kb-removed", type=Path, default=DEFAULT_KB_REMOVED)
    parser.add_argument("--output-baseline", type=Path, default=DEFAULT_OUTPUT_BASELINE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    registry = _build_complete_registry(
        phase3d_baseline=args.phase3d_baseline,
        phase3e_aggregate=args.phase3e_aggregate,
        phase3e_clustered_rows=args.phase3e_clustered_rows,
        phase3h_baseline=args.phase3h_baseline,
        turnover_max=args.turnover_max,
    )
    novelty_rows, removed_rows, novelty = _kb_novelty_rows(
        registry=registry,
        cluster_metrics_path=args.kb_cluster_metrics,
        book_members_path=args.kb_book_members,
        removed_path=args.kb_removed,
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_baseline, registry)
    _write_json(args.output_root / "phase3k_c_complete_149_registry_report.json", {"registry_quality": registry["quality"], **novelty})
    _write_csv(args.output_root / "phase3k_c_149_representatives.csv", list(registry["deployable_representatives"]))
    _write_csv(args.output_root / "phase3k_c_kb_new_vs_149.csv", novelty_rows)
    _write_csv(args.output_root / "phase3k_c_kb_removed_new_vs_149.csv", removed_rows)
    _write_csv(args.output_root / "phase3k_c_overlap_cluster_families.csv", novelty["family_rows"])
    _write_markdown(args.output_root / "PHASE3K_C_COMPLETE_149_REPRESENTATIVE_REGISTRY_2026-05-17.md", registry, novelty)
    print(json.dumps({"registry_quality": registry["quality"], **novelty["summary"]}, indent=2, ensure_ascii=False))
    return 0 if registry["quality"]["is_complete_149_representative_registry"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
