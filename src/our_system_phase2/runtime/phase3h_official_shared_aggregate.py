"""Aggregate Phase3H shared-pool official runs.

This is an execution/decision aggregate for H0/H1/H2 official replay plus H3
selector-only parity. It intentionally reports arm-level replay outcomes; a
separate cross-seed global recluster can still be run when promotion-grade
cluster accounting is required.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


ARM_LABELS = {
    "h0": "H0_G0_stable",
    "h1": "H1_G2_signal_vector_control",
    "h2": "H2_G2_turnover_calibrated",
    "h3": "H3_G2_registry_canonicalized",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if value == value]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _report_path(root: Path, seed: int, arm: str) -> Path:
    return root / f"s{seed}" / "official_replay" / arm / "phase3_repair_report.json"


def _strict_rows_path(root: Path, seed: int, arm: str) -> Path:
    return root / f"s{seed}" / "official_replay" / arm / "phase3_strict_rows.json"


def _selector_audit_path(root: Path, seed: int) -> Path:
    return root / f"s{seed}" / "selector_audit" / "phase3h_selector_only_dryrun_audit.json"


def _manifest_path(root: Path, seed: int) -> Path:
    return root / f"s{seed}" / "phase3h_shared_official_seed_manifest.json"


def _selector_audit_csv_path(root: Path, seed: int, arm: str) -> Path:
    return root / f"s{seed}" / "selector" / arm / "phase3e_selector_audit.csv"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _selected_selector_rows(root: Path, seed: int, arm: str) -> list[dict[str, Any]]:
    path = _selector_audit_csv_path(root, seed, arm)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if _truthy(row.get("selected_for_audit"))]


def _cluster_share(report: dict[str, Any], cluster_id: str) -> float | None:
    clusters = report.get("signal_cluster_report", {}).get("clusters") or []
    denominator = sum(int(cluster.get("cluster_replay_contribution_count") or 0) for cluster in clusters)
    if denominator <= 0:
        return None
    numerator = sum(
        int(cluster.get("cluster_replay_contribution_count") or 0)
        for cluster in clusters
        if str(cluster.get("signal_cluster_id") or "") == cluster_id
    )
    return numerator / denominator


def _arm_metrics(root: Path, seeds: list[int], arm: str) -> dict[str, Any]:
    reports = []
    strict_rows: list[dict[str, Any]] = []
    missing = []
    for seed in seeds:
        path = _report_path(root, seed, arm)
        if not path.exists():
            missing.append(str(path))
            continue
        report = _read_json(path)
        reports.append({"seed": seed, "report": report})
        rows_path = _strict_rows_path(root, seed, arm)
        if rows_path.exists():
            strict_rows.extend(_read_json(rows_path).get("strict_rows") or [])

    deployable = [int(item["report"].get("main_kpi", {}).get("primary", {}).get("cost_turnover_deployable_unique_clusters") or 0) for item in reports]
    audited = [int(item["report"].get("main_kpi", {}).get("primary", {}).get("audited_count") or 0) for item in reports]
    raw_non_gap = [int(item["report"].get("main_kpi", {}).get("secondary", {}).get("raw_non_gap_replay_pass") or 0) for item in reports]
    top_share = [
        value
        for value in (
            _safe_float(item["report"].get("main_kpi", {}).get("secondary", {}).get("top_cluster_raw_pass_share"))
            for item in reports
        )
        if value is not None
    ]
    median_turnover_proxy = [
        value
        for value in (
            _safe_float(item["report"].get("selector_queue_metrics", {}).get("median_turnover_proxy"))
            for item in reports
        )
        if value is not None
    ]
    replay_turnovers = [
        value
        for value in (_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in strict_rows)
        if value is not None
    ]
    strict_turnovers = [
        value
        for value in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in strict_rows)
        if value is not None
    ]
    cluster_001 = [
        value
        for value in (_cluster_share(item["report"], "cluster_001") for item in reports)
        if value is not None
    ]
    cluster_003 = [
        value
        for value in (_cluster_share(item["report"], "cluster_003") for item in reports)
        if value is not None
    ]
    selected_queue_corrs = []
    selected_queue_turnovers = []
    for seed in seeds:
        for row in _selected_selector_rows(root, seed, arm):
            corr = _safe_float(row.get("max_corr_to_selected_queue_signal"))
            if corr is not None:
                selected_queue_corrs.append(corr)
            turnover = _safe_float(row.get("turnover_proxy"))
            if turnover is not None:
                selected_queue_turnovers.append(turnover)
    deployable_sum = sum(deployable)
    raw_non_gap_sum = sum(raw_non_gap)
    return {
        "arm": arm,
        "label": ARM_LABELS.get(arm, arm),
        "reports_found": len(reports),
        "missing_reports": missing,
        "audited": sum(audited),
        "deployable_clusters_sum": deployable_sum,
        "deployable_per_256": (sum(deployable) / sum(audited) * 256.0) if sum(audited) else None,
        "raw_non_gap_pass_sum": raw_non_gap_sum,
        "raw_deployable_ratio": (raw_non_gap_sum / deployable_sum) if deployable_sum else None,
        "top_cluster_share_mean": _mean(top_share),
        "top_cluster_share_max": max(top_share) if top_share else None,
        "median_turnover_proxy": _median(median_turnover_proxy),
        "median_replay_turnover": _median(replay_turnovers),
        "median_strict_turnover": _median(strict_turnovers),
        "selected_queue_signal_corr_median": _median(selected_queue_corrs),
        "selected_queue_turnover_proxy_median": _median(selected_queue_turnovers),
        "cluster_001_replay_share_mean": _mean(cluster_001),
        "cluster_003_replay_share_mean": _mean(cluster_003),
        "new_vs_134": None,
        "new_vs_134_status": "not_available_without_cross_seed_registry_recluster",
        "strict_row_count": len(strict_rows),
    }


def _selector_metrics(root: Path, seeds: list[int]) -> dict[str, Any]:
    audits = []
    missing = []
    for seed in seeds:
        path = _selector_audit_path(root, seed)
        if not path.exists():
            missing.append(str(path))
            continue
        audits.append(_read_json(path))

    h1_h2 = []
    h1_h3 = []
    h2_turnover_advantage = []
    for audit in audits:
        overlaps = audit.get("queue_overlaps") or {}
        if "H1_vs_H2" in overlaps:
            value = _safe_float(overlaps["H1_vs_H2"].get("overlap_ratio_min_denom"))
            if value is not None:
                h1_h2.append(value)
        if "H1_vs_H3" in overlaps:
            value = _safe_float(overlaps["H1_vs_H3"].get("overlap_ratio_min_denom"))
            if value is not None:
                h1_h3.append(value)
        arms = {str(row.get("short")): row for row in (audit.get("arms") or [])}
        h1 = _safe_float((arms.get("H1") or {}).get("median_turnover_proxy"))
        h2 = _safe_float((arms.get("H2") or {}).get("median_turnover_proxy"))
        if h1 is not None and h2 is not None:
            h2_turnover_advantage.append(h1 - h2)

    return {
        "selector_audits_found": len(audits),
        "missing_selector_audits": missing,
        "h1_h2_overlap_mean": _mean(h1_h2),
        "h1_h3_overlap_mean": _mean(h1_h3),
        "h2_turnover_proxy_advantage_mean": _mean(h2_turnover_advantage),
    }


def _decision(metrics: dict[str, dict[str, Any]], selector: dict[str, Any]) -> dict[str, Any]:
    h0 = metrics.get("h0", {})
    h1 = metrics.get("h1", {})
    h2 = metrics.get("h2", {})
    h1_minus_h0 = (h1.get("deployable_clusters_sum") or 0) - (h0.get("deployable_clusters_sum") or 0)
    h2_minus_h1 = (h2.get("deployable_clusters_sum") or 0) - (h1.get("deployable_clusters_sum") or 0)
    h2_turnover_better = False
    h1_turnover = h1.get("median_replay_turnover") or h1.get("median_turnover_proxy")
    h2_turnover = h2.get("median_replay_turnover") or h2.get("median_turnover_proxy")
    if h1_turnover is not None and h2_turnover is not None:
        h2_turnover_better = h2_turnover < h1_turnover
    h1_promote = h1_minus_h0 >= 5 and (h1.get("top_cluster_share_max") or 1.0) < (h0.get("top_cluster_share_max") or 1.0)
    h2_production = h1_promote and h2_minus_h1 >= -2 and h2_turnover_better
    return {
        "h1_minus_h0_deployable": h1_minus_h0,
        "h2_minus_h1_deployable": h2_minus_h1,
        "h2_turnover_better_than_h1": h2_turnover_better,
        "h1_g2_primary_incumbent_condition": bool(h1_promote),
        "h2_production_candidate_condition": bool(h2_production),
        "h1_h3_parity_mean": selector.get("h1_h3_overlap_mean"),
        "decision": "PROMOTE_H1_G2" if h1_promote else "HOLD_G2_PROMOTION",
        "production_candidate": "H2_G2_turnover_calibrated" if h2_production else None,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Phase3H Official Shared Aggregate",
        "",
        f"- created_at: {payload['created_at']}",
        f"- run_root: `{payload['run_root']}`",
        f"- seeds: {payload['seeds']}",
        f"- aggregate_scope: {payload['aggregate_scope']}",
        f"- decision: **{payload['decision']['decision']}**",
        "",
        "## Arm Metrics",
        "",
        "| arm | audited | deployable_sum | raw_non_gap | raw/deployable | top_share_max | cluster001 | cluster003 | replay_turnover | queue_corr | reports |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["arms"]:
        lines.append(
            "| {label} | {audited} | {deployable} | {raw} | {ratio} | {top} | {c001} | {c003} | {replay_turnover} | {queue_corr} | {reports} |".format(
                label=row["label"],
                audited=row["audited"],
                deployable=row["deployable_clusters_sum"],
                raw=row["raw_non_gap_pass_sum"],
                ratio="" if row["raw_deployable_ratio"] is None else f"{row['raw_deployable_ratio']:.4f}",
                top="" if row["top_cluster_share_max"] is None else f"{row['top_cluster_share_max']:.4f}",
                c001="" if row["cluster_001_replay_share_mean"] is None else f"{row['cluster_001_replay_share_mean']:.4f}",
                c003="" if row["cluster_003_replay_share_mean"] is None else f"{row['cluster_003_replay_share_mean']:.4f}",
                replay_turnover="" if row["median_replay_turnover"] is None else f"{row['median_replay_turnover']:.6f}",
                queue_corr="" if row["selected_queue_signal_corr_median"] is None else f"{row['selected_queue_signal_corr_median']:.6f}",
                reports=row["reports_found"],
            )
        )
    lines.extend(
        [
            "",
            "## Selector Parity",
            "",
            f"- H1/H2 overlap mean: {payload['selector_metrics'].get('h1_h2_overlap_mean')}",
            f"- H1/H3 overlap mean: {payload['selector_metrics'].get('h1_h3_overlap_mean')}",
            f"- H2 turnover proxy advantage mean: {payload['selector_metrics'].get('h2_turnover_proxy_advantage_mean')}",
            "",
            "## Notes",
            "",
            "- This is a shared-pool official execution aggregate.",
            "- H3 is expected to be selector-only parity unless replay reports are present.",
            "- `new_vs_134` requires cross-seed registry/global reclustering and is marked unavailable here when absent.",
            "- Cross-seed promotion-grade global reclustering remains a separate accounting step.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--arms", nargs="*", default=["h0", "h1", "h2"])
    args = parser.parse_args()

    metrics = {arm: _arm_metrics(args.root, args.seeds, arm) for arm in args.arms}
    selector = _selector_metrics(args.root, args.seeds)
    decision = _decision(metrics, selector)
    manifests = [str(_manifest_path(args.root, seed)) for seed in args.seeds if _manifest_path(args.root, seed).exists()]
    payload = {
        "created_at": utc_now_iso(),
        "run_root": str(args.root),
        "seeds": args.seeds,
        "aggregate_scope": "arm_level_shared_official_not_cross_seed_global_recluster",
        "arms": list(metrics.values()),
        "selector_metrics": selector,
        "seed_manifests": manifests,
        "decision": decision,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_root / "phase3h_official_shared_aggregate.json", payload)
    _write_markdown(args.output_root / "PHASE3H_OFFICIAL_SHARED_AGGREGATE_2026-05-15.md", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
