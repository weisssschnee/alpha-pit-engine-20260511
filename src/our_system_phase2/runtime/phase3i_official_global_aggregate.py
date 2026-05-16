"""Global aggregate for Phase3I official I0/I1_v2 runs.

The per-seed replay reports attach signal clusters independently inside each
seed. This aggregate reloads all strict rows, reclusters them together, and then
computes arm-level metrics from the global cluster labels.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore, _corr
from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass
from our_system_phase2.services.stock_pit_proof_suite import DEFAULT_LOW_CORR_THRESHOLD, _attach_signal_clusters


ARM_LABELS = {
    "i0": "I0_G2_discovery_primary_control",
    "i1v2": "I1_v2_G2_turnover_tail_guard",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    return statistics.median(clean)


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return clean[lo]
    return clean[lo] * (hi - pos) + clean[hi] * (pos - lo)


def _round(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _load_rows(root: Path, seeds: list[int], arms: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for seed in seeds:
        seed_root = root / f"s{seed}_v2_tailguard"
        for arm in arms:
            strict_path = seed_root / arm / "phase3_strict_rows.json"
            report_path = seed_root / arm / "phase3_repair_report.json"
            if not strict_path.exists():
                missing.append(str(strict_path))
                continue
            payload = _read_json(strict_path)
            arm_rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
            if not isinstance(arm_rows, list):
                missing.append(f"{strict_path}::strict_rows_not_list")
                continue
            report = _read_json(report_path) if report_path.exists() else {}
            for index, row in enumerate(arm_rows):
                item = dict(row)
                item["phase3i_seed"] = seed
                item["phase3i_arm_short"] = arm
                item["phase3i_arm_label"] = ARM_LABELS.get(arm, arm)
                item["phase3i_row_index"] = index
                item["phase3i_source_strict_path"] = str(strict_path)
                item["ablation_arm"] = item.get("ablation_arm") or report.get("ablation_arm") or ARM_LABELS.get(arm, arm)
                item["proof_variant"] = item.get("proof_variant") or item.get("phase3_budget_bucket") or arm
                item["strict_selection_role"] = item.get("strict_selection_role") or item.get("selection_policy") or arm
                rows.append(item)
    return rows, missing


def _attach_signal_vector_proxy_clusters(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path,
    threshold: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    store = Phase3GSignalVectorStore(dataset_path=dataset_path, corr_threshold=threshold)
    representatives: list[tuple[str, str, Any]] = []
    enriched_by_key: dict[str, dict[str, Any]] = {}
    pairwise: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: _safe_float(item.get("fast_reward")) or 0.0, reverse=True):
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('phase3i_seed')}::{row.get('phase3i_arm_short')}::{row.get('candidate_id')}::{expression}"
        vector, meta = store.vector_for_expression(expression)
        if vector is None:
            enriched_by_key[row_key] = {
                **row,
                **meta,
                "signal_cluster_id": "cluster_error",
                "signal_cluster_error": meta.get("signal_vector_error") or "missing_signal_vector",
                "max_abs_signal_corr_to_prior": None,
            }
            continue
        best_cluster = None
        best_corr = 0.0
        for cluster_id, representative_expression, representative_vector in representatives:
            corr = abs(_corr(vector, representative_vector))
            pairwise.append(
                {
                    "left_expression": expression,
                    "right_expression": representative_expression,
                    "right_cluster_id": cluster_id,
                    "abs_signal_corr": round(float(corr), 6),
                }
            )
            if corr > best_corr:
                best_corr = corr
                best_cluster = cluster_id
        if best_cluster is not None and best_corr >= threshold:
            cluster_id = best_cluster
        else:
            cluster_id = f"cluster_{len(representatives) + 1:03d}"
            representatives.append((cluster_id, expression, vector))
        enriched_by_key[row_key] = {
            **row,
            **meta,
            "signal_cluster_id": cluster_id,
            "max_abs_signal_corr_to_prior": round(best_corr, 6),
            "phase3i_cluster_mode": "signal_vector_proxy",
        }

    enriched: list[dict[str, Any]] = []
    for row in rows:
        expression = str(row.get("expression") or "")
        row_key = f"{row.get('phase3i_seed')}::{row.get('phase3i_arm_short')}::{row.get('candidate_id')}::{expression}"
        enriched.append(enriched_by_key.get(row_key, {**row, "signal_cluster_id": "cluster_missing"}))

    cluster_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        cluster_rows[str(row.get("signal_cluster_id") or "unknown")].append(row)
    cluster_report = []
    for cluster_id, cluster_members in sorted(cluster_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        replay_pass = sum(1 for item in cluster_members if item.get("portfolio_replay_pass"))
        cluster_report.append(
            {
                "signal_cluster_id": cluster_id,
                "candidate_count": len(cluster_members),
                "cluster_budget_share": round(len(cluster_members) / max(1, len(enriched)), 6),
                "cluster_replay_contribution_count": replay_pass,
                "cluster_replay_pass_rate": round(replay_pass / max(1, len(cluster_members)), 6),
                "representative_expression": cluster_members[0].get("expression"),
            }
        )
    return enriched, {
        "cluster_count": len(cluster_rows),
        "cluster_mode": "signal_vector_proxy",
        "low_corr_threshold_abs_signal_corr": float(threshold),
        "clusters": cluster_report,
        "top_pairwise_abs_correlations": sorted(pairwise, key=lambda item: item["abs_signal_corr"], reverse=True)[:40],
    }


def _metric_for_arm(rows: list[dict[str, Any]], turnover_max: float) -> dict[str, Any]:
    audited = len(rows)
    non_gap = [row for row in rows if _non_gap_replay_pass(row)]
    deployable = [row for row in rows if _deployable_pass(row, turnover_max=turnover_max)]
    non_gap_clusters = [str(row.get("signal_cluster_id")) for row in non_gap if row.get("signal_cluster_id")]
    deployable_clusters = [str(row.get("signal_cluster_id")) for row in deployable if row.get("signal_cluster_id")]
    raw_cluster_counts = Counter(non_gap_clusters)
    deployable_cluster_counts = Counter(deployable_clusters)

    strict_turnover = [
        value
        for value in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in rows)
        if value is not None
    ]
    replay_turnover = [
        value
        for value in (_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in rows)
        if value is not None
    ]
    deployable_replay_turnover = [
        value
        for value in (_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in deployable)
        if value is not None
    ]
    deployable_strict_turnover = [
        value
        for value in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in deployable)
        if value is not None
    ]

    return {
        "audited": audited,
        "raw_non_gap_pass": len(non_gap),
        "raw_non_gap_pass_rate": _round(len(non_gap) / audited if audited else None),
        "unique_signal_clusters": len(set(non_gap_clusters)),
        "deployable_rows": len(deployable),
        "deployable_unique_clusters": len(set(deployable_clusters)),
        "deployable_cluster_per_256": _round(len(set(deployable_clusters)) / audited * 256.0 if audited else None),
        "raw_to_deployable_cluster_ratio": _round(len(non_gap) / len(set(deployable_clusters)) if deployable_clusters else None),
        "top_cluster_raw_pass_share": _round(max(raw_cluster_counts.values()) / len(non_gap) if non_gap else None),
        "top_cluster_id": raw_cluster_counts.most_common(1)[0][0] if raw_cluster_counts else None,
        "top_deployable_cluster_share": _round(
            max(deployable_cluster_counts.values()) / len(deployable) if deployable else None
        ),
        "top_deployable_cluster_id": deployable_cluster_counts.most_common(1)[0][0] if deployable_cluster_counts else None,
        "median_strict_turnover": _round(_median(strict_turnover)),
        "p90_strict_turnover": _round(_quantile(strict_turnover, 0.9)),
        "median_replay_turnover": _round(_median(replay_turnover)),
        "p90_replay_turnover": _round(_quantile(replay_turnover, 0.9)),
        "median_deployable_strict_turnover": _round(_median(deployable_strict_turnover)),
        "p90_deployable_strict_turnover": _round(_quantile(deployable_strict_turnover, 0.9)),
        "median_deployable_replay_turnover": _round(_median(deployable_replay_turnover)),
        "p90_deployable_replay_turnover": _round(_quantile(deployable_replay_turnover, 0.9)),
        "cluster_001_share": _round(raw_cluster_counts.get("cluster_001", 0) / len(non_gap) if non_gap else None),
        "cluster_003_share": _round(raw_cluster_counts.get("cluster_003", 0) / len(non_gap) if non_gap else None),
    }


def _seed_metrics(rows: list[dict[str, Any]], turnover_max: float) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["phase3i_seed"]), str(row["phase3i_arm_short"]))].append(row)
    out = []
    for (seed, arm), group in sorted(grouped.items()):
        item = _metric_for_arm(group, turnover_max)
        item["seed"] = seed
        item["arm"] = arm
        item["arm_label"] = ARM_LABELS.get(arm, arm)
        out.append(item)
    return out


def _decision(arm_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    i0 = arm_metrics.get("i0", {})
    i1 = arm_metrics.get("i1v2", {})
    deployable_delta = (i1.get("deployable_unique_clusters") or 0) - (i0.get("deployable_unique_clusters") or 0)
    median_replay_delta = (i1.get("median_replay_turnover") or 0.0) - (i0.get("median_replay_turnover") or 0.0)
    p90_replay_delta = (i1.get("p90_replay_turnover") or 0.0) - (i0.get("p90_replay_turnover") or 0.0)
    median_strict_delta = (i1.get("median_strict_turnover") or 0.0) - (i0.get("median_strict_turnover") or 0.0)
    p90_strict_delta = (i1.get("p90_strict_turnover") or 0.0) - (i0.get("p90_strict_turnover") or 0.0)
    top_share_ok = (i1.get("top_cluster_raw_pass_share") or 1.0) <= 0.15
    deployable_ok = deployable_delta >= -3
    strict_turnover_ok = median_strict_delta < 0 and p90_strict_delta < 0
    replay_turnover_ok = median_replay_delta < 0 and p90_replay_delta < 0
    pass_condition = bool(deployable_ok and top_share_ok and (strict_turnover_ok or replay_turnover_ok))
    return {
        "deployable_unique_cluster_delta_i1v2_minus_i0": deployable_delta,
        "median_strict_turnover_delta_i1v2_minus_i0": _round(median_strict_delta),
        "p90_strict_turnover_delta_i1v2_minus_i0": _round(p90_strict_delta),
        "median_replay_turnover_delta_i1v2_minus_i0": _round(median_replay_delta),
        "p90_replay_turnover_delta_i1v2_minus_i0": _round(p90_replay_delta),
        "deployable_gate": deployable_ok,
        "top_cluster_gate": top_share_ok,
        "strict_turnover_gate": strict_turnover_ok,
        "replay_turnover_gate": replay_turnover_ok,
        "decision": "PROMOTE_I1_V2_AS_G2_DEPLOYMENT_HARDENED_CANDIDATE" if pass_condition else "KEEP_I0_G2_DISCOVERY_PRIMARY",
        "notes": [
            "Clusters are globally reclustered across all seeds and arms before metrics are computed.",
            "new_vs_149 is not asserted here because the full 149 representative registry is not present in this artifact set.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    metrics = report["arm_metrics"]
    decision = report["decision"]
    lines = [
        "# Phase3I Official Global Aggregate - 2026-05-16",
        "",
        f"Decision: `{decision['decision']}`",
        "",
        "This aggregate reclusters all strict rows across seeds 43-46 and arms I0/I1_v2 before computing metrics.",
        "",
        "## Arm Metrics",
        "",
        "| arm | audited | raw non-gap | deployable clusters | top raw cluster share | median replay turnover | p90 replay turnover | median strict turnover | p90 strict turnover |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ["i0", "i1v2"]:
        item = metrics.get(arm, {})
        lines.append(
            "| {arm} | {audited} | {raw} | {deployable} | {top} | {med_replay} | {p90_replay} | {med_strict} | {p90_strict} |".format(
                arm=arm,
                audited=item.get("audited"),
                raw=item.get("raw_non_gap_pass"),
                deployable=item.get("deployable_unique_clusters"),
                top=item.get("top_cluster_raw_pass_share"),
                med_replay=item.get("median_replay_turnover"),
                p90_replay=item.get("p90_replay_turnover"),
                med_strict=item.get("median_strict_turnover"),
                p90_strict=item.get("p90_strict_turnover"),
            )
        )
    lines.extend(
        [
            "",
            "## Gate Result",
            "",
            f"- Deployable delta I1_v2 - I0: `{decision['deployable_unique_cluster_delta_i1v2_minus_i0']}`",
            f"- Strict turnover delta median / p90: `{decision['median_strict_turnover_delta_i1v2_minus_i0']}` / `{decision['p90_strict_turnover_delta_i1v2_minus_i0']}`",
            f"- Replay turnover delta median / p90: `{decision['median_replay_turnover_delta_i1v2_minus_i0']}` / `{decision['p90_replay_turnover_delta_i1v2_minus_i0']}`",
            f"- Gates: deployable `{decision['deployable_gate']}`, top cluster `{decision['top_cluster_gate']}`, strict turnover `{decision['strict_turnover_gate']}`, replay turnover `{decision['replay_turnover_gate']}`",
            "",
            "## Scope",
            "",
            "- This is a deployment-hardening selector test, not a true book-residual selector.",
            "- `new_vs_149` is intentionally not asserted until a full 149 representative registry is available.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-path", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[43, 44, 45, 46])
    parser.add_argument("--arms", nargs="+", default=["i0", "i1v2"])
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--low-corr-threshold", type=float, default=DEFAULT_LOW_CORR_THRESHOLD)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    parser.add_argument("--cluster-mode", choices=["signal_vector_proxy", "exact"], default="signal_vector_proxy")
    args = parser.parse_args()

    rows, missing = _load_rows(args.root, args.seeds, args.arms)
    if args.cluster_mode == "exact":
        clustered_rows, cluster_report = _attach_signal_clusters(
            rows,
            dataset_path=args.dataset_path,
            threshold=args.low_corr_threshold,
            recent_quarter_window_count=args.recent_quarter_window_count,
            recent_warmup_days=args.recent_warmup_days,
        )
        cluster_label_scope = "global_exact_reclustered_across_all_phase3i_official_seed43_46_rows"
    else:
        clustered_rows, cluster_report = _attach_signal_vector_proxy_clusters(
            rows,
            dataset_path=args.dataset_path,
            threshold=args.low_corr_threshold,
        )
        cluster_label_scope = "global_signal_vector_proxy_reclustered_across_all_phase3i_official_seed43_46_rows"
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in clustered_rows:
        grouped[str(row.get("phase3i_arm_short"))].append(row)
    arm_metrics = {arm: _metric_for_arm(grouped.get(arm, []), args.turnover_max) for arm in args.arms}
    for arm, item in arm_metrics.items():
        item["arm"] = arm
        item["arm_label"] = ARM_LABELS.get(arm, arm)
    report = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "root": str(args.root),
        "dataset_path": str(args.dataset_path),
        "seeds": args.seeds,
        "arms": args.arms,
        "row_count": len(clustered_rows),
        "missing_inputs": missing,
        "cluster_label_scope": cluster_label_scope,
        "cluster_mode": args.cluster_mode,
        "cluster_report": cluster_report,
        "arm_metrics": arm_metrics,
        "seed_metrics": _seed_metrics(clustered_rows, args.turnover_max),
        "decision": _decision(arm_metrics),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3I_official_global_clustered_rows.json", {"strict_rows": clustered_rows})
    write_json_artifact(args.output_dir / "phase3I_official_global_aggregate.json", report)
    (args.output_dir / "PHASE3I_OFFICIAL_GLOBAL_AGGREGATE_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
