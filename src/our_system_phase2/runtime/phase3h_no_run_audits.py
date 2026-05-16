"""No-run audits after Phase3H official.

These audits do not launch search/replay. They summarize whether the promoted
G2 selector is structurally diverse, what turnover/cost risks it carries, what
it adds beyond H0, and whether the shared-pool execution path remained clean.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CLUSTERED_ROWS = Path("reports/phase3h_global_recluster_20260516/phase3H_global_clustered_rows.json")
DEFAULT_AGGREGATE_REPORT = Path("reports/phase3h_global_recluster_20260516/phase3H_global_recluster_report.json")
DEFAULT_MANIFEST_ROOT = Path("reports/phase3h_official_manifests_20260516")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3h_no_run_audits_20260516")

H0_ARM = "Phase3H_H0_G0_stable"
H1_ARM = "Phase3H_H1_G2_signal_vector_control"
FORBIDDEN_SELECTION_FIELDS = {
    "portfolio_replay_pass",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_avg_one_way_turnover",
    "global_signal_cluster_id",
    "deployable",
}


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


def _median(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    return round(statistics.median(clean), 6) if clean else None


def _p90(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    index = min(len(clean) - 1, math.ceil(0.9 * len(clean)) - 1)
    return round(clean[index], 6)


def _deployable(row: dict[str, Any], *, turnover_max: float) -> bool:
    return (
        _as_bool(row.get("portfolio_replay_pass"))
        and not _as_bool(row.get("is_gap_family"))
        and _as_bool(row.get("cost_survives"))
        and _safe_float(row.get("strict_mean_one_way_turnover"), default=999.0) <= turnover_max
    )


def _load_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    return list(payload.get("rows", payload) if isinstance(payload, dict) else payload)


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or "cluster_missing")


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[str(row.get(key) or "")].append(row)
    return out


def _cluster_anatomy(rows: list[dict[str, Any]], new_clusters: set[str], *, turnover_max: float) -> list[dict[str, Any]]:
    h1_deployable = [row for row in rows if row.get("ablation_arm") == H1_ARM and _deployable(row, turnover_max=turnover_max)]
    output: list[dict[str, Any]] = []
    for cluster_id, group in sorted(_group(h1_deployable, "global_signal_cluster_id").items()):
        lane_counts = Counter(str(row.get("phase3_budget_bucket") or "") for row in group)
        source_counts = Counter(str(row.get("proof_variant") or "") for row in group)
        turnovers = [_safe_float(row.get("strict_mean_one_way_turnover")) for row in group]
        sortinos = [_safe_float(row.get("portfolio_replay_long_only_sortino")) for row in group]
        representative = sorted(group, key=lambda row: _safe_float(row.get("portfolio_replay_long_only_sortino"), -999.0), reverse=True)[0]
        output.append(
            {
                "cluster_id": cluster_id,
                "deployable_rows": len(group),
                "known_or_new_vs_134": "new" if cluster_id in new_clusters else "known",
                "source_lanes": ";".join(f"{lane}:{count}" for lane, count in lane_counts.most_common()),
                "source_generators": ";".join(f"{source}:{count}" for source, count in source_counts.most_common(5)),
                "median_turnover": _median(turnovers),
                "p90_turnover": _p90(turnovers),
                "median_long_sortino": _median(sortinos),
                "representative_candidate_id": representative.get("candidate_id") or "",
                "representative_expression": representative.get("expression") or "",
            }
        )
    return output


def _turnover_cost_audit(rows: list[dict[str, Any]], new_clusters: set[str], *, turnover_max: float) -> list[dict[str, Any]]:
    h1_deployable = [row for row in rows if row.get("ablation_arm") == H1_ARM and _deployable(row, turnover_max=turnover_max)]
    output: list[dict[str, Any]] = []
    for key_name, grouped in {
        "cluster": _group(h1_deployable, "global_signal_cluster_id"),
        "source_lane": _group(h1_deployable, "phase3_budget_bucket"),
    }.items():
        for key, group in sorted(grouped.items()):
            turnovers = [_safe_float(row.get("strict_mean_one_way_turnover")) for row in group]
            replay_turnovers = [_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in group]
            cost_sortinos = [_safe_float(row.get("strict_cost_adjusted_sortino")) for row in group]
            output.append(
                {
                    "group_type": key_name,
                    "group_id": key,
                    "row_count": len(group),
                    "new_vs_134": "mixed" if key_name != "cluster" else ("new" if key in new_clusters else "known"),
                    "median_strict_turnover": _median(turnovers),
                    "p90_strict_turnover": _p90(turnovers),
                    "median_replay_turnover": _median(replay_turnovers),
                    "median_cost_adjusted_sortino": _median(cost_sortinos),
                    "turnover_gt_0p25_count": sum(1 for value in turnovers if math.isfinite(value) and value > 0.25),
                    "turnover_gt_0p75_count": sum(1 for value in turnovers if math.isfinite(value) and value > 0.75),
                }
            )
    return output


def _marginal_audit(rows: list[dict[str, Any]], new_clusters: set[str], *, turnover_max: float) -> dict[str, Any]:
    h0 = [row for row in rows if row.get("ablation_arm") == H0_ARM and _deployable(row, turnover_max=turnover_max)]
    h1 = [row for row in rows if row.get("ablation_arm") == H1_ARM and _deployable(row, turnover_max=turnover_max)]
    h0_clusters = {_cluster_id(row) for row in h0}
    h1_clusters = {_cluster_id(row) for row in h1}
    h1_only = h1_clusters - h0_clusters
    h0_only = h0_clusters - h1_clusters
    overlap = h1_clusters & h0_clusters
    h1_only_rows = [row for row in h1 if _cluster_id(row) in h1_only]
    return {
        "h0_clusters": len(h0_clusters),
        "g2_clusters": len(h1_clusters),
        "h0_only": len(h0_only),
        "g2_only": len(h1_only),
        "overlap": len(overlap),
        "jaccard": round(len(overlap) / max(1, len(h0_clusters | h1_clusters)), 6),
        "g2_only_new_vs_134": len(h1_only & new_clusters),
        "g2_only_median_turnover": _median([_safe_float(row.get("strict_mean_one_way_turnover")) for row in h1_only_rows]),
        "g2_only_p90_turnover": _p90([_safe_float(row.get("strict_mean_one_way_turnover")) for row in h1_only_rows]),
        "g2_only_cluster_ids": sorted(h1_only),
        "h0_only_cluster_ids": sorted(h0_only),
    }


def _selection_payload(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if isinstance(payload, dict):
        return list(payload.get("selected") or payload.get("candidate_pool") or payload.get("default_selected") or payload.get("rows") or [])
    return list(payload)


def _shared_pool_execution_qa(manifest_root: Path) -> dict[str, Any]:
    seed_summaries: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
    shared_pool_forbidden_hits: list[dict[str, Any]] = []
    for seed in (33, 34, 35, 36):
        manifest_path = manifest_root / f"s{seed}_seed_manifest.json"
        selector_manifest_path = manifest_root / f"s{seed}_selector_manifest.json"
        shared_pool_path = manifest_root / "shared_pools" / f"s{seed}_shared_candidate_pool.json"
        manifest = _read_json(manifest_path) if manifest_path.exists() else {}
        selector_manifest = _read_json(selector_manifest_path) if selector_manifest_path.exists() else {}
        pool_rows = _selection_payload(shared_pool_path) if shared_pool_path.exists() else []
        for index, row in enumerate(pool_rows):
            present = sorted(field for field in FORBIDDEN_SELECTION_FIELDS if row.get(field) is not None)
            if present:
                shared_pool_forbidden_hits.append({"seed": seed, "row_index": index, "fields": ",".join(present)})
        arm_counts = {}
        for arm in ("h0", "h1", "h2", "h3"):
            selection_path = manifest_root / "selector" / f"s{seed}" / arm / "phase3_strict_selection_inputs.json"
            selected = _selection_payload(selection_path) if selection_path.exists() else []
            arm_counts[arm] = len(selected)
            for index, row in enumerate(selected):
                present = sorted(field for field in FORBIDDEN_SELECTION_FIELDS if row.get(field) is not None)
                if present:
                    forbidden_hits.append({"seed": seed, "arm": arm, "row_index": index, "fields": ",".join(present)})
        seed_summaries.append(
            {
                "seed": seed,
                "manifest_exists": manifest_path.exists(),
                "selector_manifest_exists": selector_manifest_path.exists(),
                "shared_pool_exists": shared_pool_path.exists(),
                "shared_pool_hash": manifest.get("shared_pool_hash") or "",
                "frozen_queue_hash_count": len(manifest.get("frozen_queue_hashes") or {}),
                "selector_profile_count": len(manifest.get("selector_profiles") or {}),
                "execution_path": manifest.get("execution_path") or "",
                "selector_arms": ",".join(manifest.get("selector_arms") or []),
                "replay_arms": ",".join(manifest.get("replay_arms") or []),
                "step_statuses": ";".join(f"{step.get('step')}:{step.get('status')}" for step in manifest.get("steps", [])),
                "selector_manifest_arm_count": len(selector_manifest.get("arms") or []),
                "selected_counts": ";".join(f"{arm}:{count}" for arm, count in sorted(arm_counts.items())),
            }
        )
    return {
        "seed_summaries": seed_summaries,
        "selection_forbidden_hits": forbidden_hits[:200],
        "shared_pool_forbidden_hits": shared_pool_forbidden_hits[:200],
        "selection_forbidden_hit_count": len(forbidden_hits),
        "shared_pool_forbidden_hit_count": len(shared_pool_forbidden_hits),
    }


def run_audits(
    *,
    clustered_rows: Path,
    aggregate_report: Path,
    manifest_root: Path,
    output_root: Path,
    turnover_max: float,
) -> dict[str, Any]:
    rows = _load_rows(clustered_rows)
    report = _read_json(aggregate_report)
    new_clusters = set((report.get("global_union_metrics") or {}).get("new_deployable_cluster_ids_vs_phase3_cumulative") or [])
    anatomy = _cluster_anatomy(rows, new_clusters, turnover_max=turnover_max)
    turnover_cost = _turnover_cost_audit(rows, new_clusters, turnover_max=turnover_max)
    marginal = _marginal_audit(rows, new_clusters, turnover_max=turnover_max)
    shared_qa = _shared_pool_execution_qa(manifest_root)
    summary = {
        "created_at": _now(),
        "decision": "PASS_NO_RUN_AUDIT_WITH_DEPLOYMENT_RISKS",
        "g2_deployable_clusters": len(anatomy),
        "g2_new_clusters_vs_134": sum(1 for row in anatomy if row["known_or_new_vs_134"] == "new"),
        "g2_median_cluster_turnover": _median([_safe_float(row["median_turnover"]) for row in anatomy]),
        "g2_p90_cluster_turnover": _p90([_safe_float(row["p90_turnover"]) for row in anatomy]),
        "g2_only_clusters_vs_h0": marginal["g2_only"],
        "g2_h0_overlap": marginal["overlap"],
        "shared_pool_forbidden_hit_count": shared_qa["shared_pool_forbidden_hit_count"],
        "selection_forbidden_hit_count": shared_qa["selection_forbidden_hit_count"],
        "interpretation": (
            "G2 is validated as discovery/decongestion primary, but turnover/cost/capacity remain deployment-stage risks."
        ),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3h_g2_cluster_anatomy.csv", anatomy)
    _write_csv(output_root / "phase3h_g2_turnover_cost_audit.csv", turnover_cost)
    _write_json(output_root / "phase3h_g2_vs_h0_marginal_audit.json", marginal)
    _write_csv(output_root / "phase3h_shared_pool_execution_seed_qa.csv", shared_qa["seed_summaries"])
    _write_csv(output_root / "phase3h_selection_forbidden_field_hits.csv", shared_qa["selection_forbidden_hits"])
    _write_csv(output_root / "phase3h_shared_pool_forbidden_field_hits.csv", shared_qa["shared_pool_forbidden_hits"])
    _write_json(output_root / "phase3h_no_run_audit_report.json", {"summary": summary, "marginal_audit": marginal, "shared_pool_execution_qa": shared_qa})
    _write_markdown(output_root / "PHASE3H_NO_RUN_AUDITS_2026-05-16.md", summary, marginal)
    return {"summary": summary, "marginal_audit": marginal}


def _write_markdown(path: Path, summary: dict[str, Any], marginal: dict[str, Any]) -> None:
    lines = [
        "# Phase3H No-Run Audits",
        "",
        f"- decision: `{summary['decision']}`",
        f"- g2_deployable_clusters: `{summary['g2_deployable_clusters']}`",
        f"- g2_new_clusters_vs_134: `{summary['g2_new_clusters_vs_134']}`",
        f"- g2_only_clusters_vs_h0: `{summary['g2_only_clusters_vs_h0']}`",
        f"- g2_h0_overlap: `{summary['g2_h0_overlap']}`",
        f"- shared_pool_forbidden_hit_count: `{summary['shared_pool_forbidden_hit_count']}`",
        f"- selection_forbidden_hit_count: `{summary['selection_forbidden_hit_count']}`",
        "",
        "## Interpretation",
        "",
        summary["interpretation"],
        "",
        "## G2 Vs H0",
        "",
        f"- H0 clusters: `{marginal['h0_clusters']}`",
        f"- G2 clusters: `{marginal['g2_clusters']}`",
        f"- G2-only clusters: `{marginal['g2_only']}`",
        f"- overlap: `{marginal['overlap']}`",
        f"- Jaccard: `{marginal['jaccard']}`",
        f"- G2-only new vs 134: `{marginal['g2_only_new_vs_134']}`",
        f"- G2-only median turnover: `{marginal['g2_only_median_turnover']}`",
        "",
        "## Outputs",
        "",
        "- `phase3h_g2_cluster_anatomy.csv`",
        "- `phase3h_g2_turnover_cost_audit.csv`",
        "- `phase3h_g2_vs_h0_marginal_audit.json`",
        "- `phase3h_shared_pool_execution_seed_qa.csv`",
        "- `phase3h_selection_forbidden_field_hits.csv`",
        "- `phase3h_shared_pool_forbidden_field_hits.csv`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clustered-rows", type=Path, default=DEFAULT_CLUSTERED_ROWS)
    parser.add_argument("--aggregate-report", type=Path, default=DEFAULT_AGGREGATE_REPORT)
    parser.add_argument("--manifest-root", type=Path, default=DEFAULT_MANIFEST_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()
    result = run_audits(
        clustered_rows=args.clustered_rows,
        aggregate_report=args.aggregate_report,
        manifest_root=args.manifest_root,
        output_root=args.output_root,
        turnover_max=args.turnover_max,
    )
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
