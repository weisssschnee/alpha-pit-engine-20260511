"""Phase3K-B locked filter generalization over fresh G2 output.

This aggregate applies fixed J2/J4_relaxed rules to fresh G2 deployable
clusters. It does not tune thresholds and does not use old cluster IDs as the
filter.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.runtime.phase3j_liquidity_capacity_preflight import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _attach_cluster_liquidity,
    _cluster_rows,
    _load_recent_quarter_market_panel,
    _prepare_liquidity_frame,
    _quantile,
    _read_json,
    _round,
    _safe_float,
    _signal_evaluation_frame,
    _write_csv,
)
from our_system_phase2.services.artifact_schema import write_json_artifact


PHASE3K_B_VERSION = "phase3k-b-locked-filter-generalization-v1-2026-05-16"
DISCOVERY_BASELINE = 149


def _load_strict_rows_from_run_root(root: Path, seeds: list[int]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for seed in seeds:
        path = root / f"s{seed}" / "official_replay" / "i0" / "phase3_strict_rows.json"
        if not path.exists():
            missing.append(str(path))
            continue
        payload = _read_json(path)
        strict_rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
        if not isinstance(strict_rows, list):
            missing.append(f"{path}::strict_rows_not_list")
            continue
        for index, row in enumerate(strict_rows):
            item = dict(row)
            item["phase3k_seed"] = seed
            item["phase3i_seed"] = seed
            item["phase3i_arm_short"] = "i0"
            item["phase3k_original_signal_cluster_id"] = item.get("signal_cluster_id")
            if item.get("signal_cluster_id"):
                item["signal_cluster_id"] = f"s{seed}_{item['signal_cluster_id']}"
            item["phase3k_row_index"] = index
            item["phase3k_source_strict_path"] = str(path)
            item["ablation_arm"] = item.get("ablation_arm") or "Phase3I_I0_G2_primary"
            rows.append(item)
    return rows, missing


def _load_strict_rows_from_file(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    payload = _read_json(path)
    strict_rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
    if not isinstance(strict_rows, list):
        raise TypeError(f"expected strict_rows list in {path}")
    rows = []
    for index, row in enumerate(strict_rows):
        item = dict(row)
        item["phase3k_seed"] = item.get("phase3i_seed") or item.get("phase3h_seed") or 0
        item["phase3i_seed"] = item.get("phase3i_seed") or item["phase3k_seed"]
        item["phase3i_arm_short"] = item.get("phase3i_arm_short") or "i0"
        item["phase3k_original_signal_cluster_id"] = item.get("signal_cluster_id")
        if item.get("signal_cluster_id") and str(item["phase3k_seed"]) not in {"0", "None", ""}:
            item["signal_cluster_id"] = f"s{item['phase3k_seed']}_{item['signal_cluster_id']}"
        item["phase3k_row_index"] = index
        item["phase3k_source_strict_path"] = str(path)
        rows.append(item)
    return rows, []


def _raw_share(rows: list[dict[str, Any]]) -> float:
    raw_counts = [int(row.get("raw_pass_count") or 0) for row in rows]
    return max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else 0.0


def _source_top_share(rows: list[dict[str, Any]]) -> float:
    counts = Counter(str(row.get("source_lane") or "unknown") for row in rows)
    return counts.most_common(1)[0][1] / max(1, len(rows)) if counts else 0.0


def _build_j2_locked_rule(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the locked J2 v1 rule family without old cluster IDs.

    Rule: keep the lower-turnover 70% of J0 by p90 replay turnover, then
    reduce raw-pass concentration while preserving at least 60% cluster
    retention. This mirrors the Phase3J J2 construction used before the
    relaxed liquidity overlay was frozen.
    """

    p90_values = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in records) if value is not None]
    p90_cut = _quantile(p90_values, 0.70)
    j2 = [row for row in records if (_safe_float(row.get("p90_replay_turnover")) or 999.0) <= (p90_cut or 999.0)]
    min_retained = max(1, int(math.ceil(len(records) * 0.60)))
    while len(j2) > min_retained and _raw_share(j2) > 0.25:
        j2.remove(max(j2, key=lambda item: int(item.get("raw_pass_count") or 0)))
    return sorted(j2, key=lambda item: str(item.get("cluster_id")))


def _percentile(value: float | None, values: list[float]) -> float | None:
    if value is None or not values:
        return None
    return sum(1 for item in values if item <= value) / len(values)


def _build_j4_relaxed_locked_rule(j2_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply locked J4_relaxed v1 overlay to a fresh J2 book."""

    amounts = [value for value in (_safe_float(row.get("median_amount_20d")) for row in j2_rows) if value is not None]
    capacities = [value for value in (_safe_float(row.get("capacity_proxy")) for row in j2_rows) if value is not None]
    costs = [value for value in (_safe_float(row.get("cost_adjusted_score")) for row in j2_rows) if value is not None]
    amount_cut = _quantile(amounts, 0.05)
    capacity_cut = _quantile(capacities, 0.05)
    total_raw = sum(int(row.get("raw_pass_count") or 0) for row in j2_rows) or 1
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for row in j2_rows:
        amount = _safe_float(row.get("median_amount_20d"))
        capacity = _safe_float(row.get("capacity_proxy"))
        cost = _safe_float(row.get("cost_adjusted_score"))
        limit_hit = _safe_float(row.get("limit_hit_rate")) or 0.0
        susp = _safe_float(row.get("suspension_rate")) or 0.0
        low_amount = amount_cut is not None and amount is not None and amount < amount_cut
        low_capacity = capacity_cut is not None and capacity is not None and capacity < capacity_cut
        low_liquidity = low_amount and low_capacity
        feasibility_bad = limit_hit > 0.20 or susp > 0.01
        if low_liquidity or feasibility_bad:
            item = dict(row)
            item.update(
                {
                    "remove_reason": "low_amount_and_low_capacity" if low_liquidity else "limit_or_suspension_feasibility",
                    "capacity_percentile": _round(_percentile(capacity, capacities)),
                    "amount_percentile": _round(_percentile(amount, amounts)),
                    "cost_percentile": _round(_percentile(cost, costs)),
                    "raw_share": _round(int(row.get("raw_pass_count") or 0) / total_raw),
                }
            )
            removed.append(item)
        else:
            kept.append(row)
    return sorted(kept, key=lambda item: str(item.get("cluster_id"))), sorted(removed, key=lambda item: str(item.get("cluster_id")))


def _book_rows(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    j0 = sorted(records, key=lambda item: str(item.get("cluster_id")))
    j2 = _build_j2_locked_rule(j0)
    j4, _removed = _build_j4_relaxed_locked_rule(j2)
    return {"J0_fresh": j0, "J2_fresh": j2, "J4_relaxed_fresh": j4}


def _seed_book_rows(records: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for seed in sorted({str(row.get("phase3k_seed")) for row in records}):
        subset = [row for row in records if str(row.get("phase3k_seed")) == seed]
        if subset:
            out[seed] = _book_rows(subset)
    return out


def _weights(rows: list[dict[str, Any]], mode: str) -> list[float]:
    raw = []
    for row in rows:
        if mode == "inverse_turnover":
            raw.append(1.0 / max(0.02, _safe_float(row.get("p90_replay_turnover")) or 999.0))
        elif mode == "liquidity_adjusted":
            amount = _safe_float(row.get("median_amount_20d")) or 0.0
            turnover = _safe_float(row.get("p90_replay_turnover")) or 999.0
            raw.append(math.sqrt(max(0.0, amount)) / max(0.02, turnover))
        else:
            raw.append(1.0)
    total = sum(raw) or 1.0
    return [value / total for value in raw]


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def _book_proxy(name: str, rows: list[dict[str, Any]], *, baseline_count: int) -> dict[str, Any]:
    p90_turnovers = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in rows) if value is not None]
    median_turnovers = [value for value in (_safe_float(row.get("median_replay_turnover")) for row in rows) if value is not None]
    capacities = [value for value in (_safe_float(row.get("capacity_proxy")) for row in rows) if value is not None]
    limit_susp = [(_safe_float(row.get("limit_hit_rate")) or 0.0) + (_safe_float(row.get("suspension_rate")) or 0.0) for row in rows]
    item: dict[str, Any] = {
        "book": name,
        "cluster_count": len(rows),
        "retention_vs_j0": _round(len(rows) / max(1, baseline_count)),
        "median_turnover": _round(_median(median_turnovers)),
        "p90_turnover": _round(_quantile(p90_turnovers, 0.9)),
        "capacity_proxy_median": _round(_median(capacities)),
        "limit_suspension_loss_proxy": _round(sum(limit_susp) / max(1, len(limit_susp)) if limit_susp else None),
    }
    for mode in ["equal", "inverse_turnover", "liquidity_adjusted"]:
        weights = _weights(rows, mode)
        scores = [_safe_float(row.get("cost_adjusted_score")) or 0.0 for row in rows]
        weighted_score = sum(weight * score for weight, score in zip(weights, scores))
        total_abs = sum(abs(weight * score) for weight, score in zip(weights, scores)) or 1.0
        item[f"{mode}_cost_adjusted_return_proxy"] = _round(weighted_score)
        item[f"{mode}_book_ir_proxy"] = _round(weighted_score)
        item[f"{mode}_max_cluster_weight"] = _round(max(weights) if weights else None)
        item[f"{mode}_top_cluster_contribution"] = _round(max((abs(weight * score) for weight, score in zip(weights, scores)), default=0.0) / total_abs)
    raw_counts = [int(row.get("raw_pass_count") or 0) for row in rows]
    item["max_raw_share"] = _round(max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else None)
    item["source_lane_top_share"] = _round(_source_top_share(rows))
    item["new_vs_149_retained"] = None
    item["new_vs_149_status"] = "not_available_without_full_149_representative_registry"
    return item


def _removed_diagnostics(j2_rows: list[dict[str, Any]], j4_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    j4_ids = {str(row.get("cluster_id")) for row in j4_rows}
    _kept, removed = _build_j4_relaxed_locked_rule(j2_rows)
    output = []
    for row in removed:
        if str(row.get("cluster_id")) in j4_ids:
            continue
        output.append(
            {
                "cluster_id": row.get("cluster_id"),
                "capacity_proxy": row.get("capacity_proxy"),
                "capacity_percentile": row.get("capacity_percentile"),
                "cost_adjusted_score": row.get("cost_adjusted_score"),
                "cost_percentile": row.get("cost_percentile"),
                "turnover": row.get("p90_replay_turnover"),
                "raw_share": row.get("raw_share"),
                "source_lane": row.get("source_lane"),
                "limit_hit_rate": row.get("limit_hit_rate"),
                "suspension_rate": row.get("suspension_rate"),
                "remove_reason": row.get("remove_reason"),
                "representative_expression": row.get("representative_expression"),
                "bad_quality_flag": bool(
                    (_safe_float(row.get("capacity_percentile")) or 1.0) <= 0.20
                    or (_safe_float(row.get("cost_adjusted_score")) or 0.0) < 0.0
                    or (_safe_float(row.get("limit_hit_rate")) or 0.0) > 0.20
                    or (_safe_float(row.get("suspension_rate")) or 0.0) > 0.01
                ),
            }
        )
    return output


def _decision(metrics: dict[str, dict[str, Any]], removed: list[dict[str, Any]]) -> dict[str, Any]:
    j0 = metrics["J0_fresh"]
    j2 = metrics["J2_fresh"]
    j4 = metrics["J4_relaxed_fresh"]
    j2_retention = j2.get("retention_vs_j0") or 0.0
    j2_pass = bool(
        0.60 <= j2_retention <= 0.80
        and (j2.get("p90_turnover") or 999.0) < (j0.get("p90_turnover") or 0.0)
        and (j2.get("max_raw_share") or 999.0) <= 0.20
        and (j2.get("equal_cost_adjusted_return_proxy") or -999.0) >= (j0.get("equal_cost_adjusted_return_proxy") or 999.0)
    )
    bad_removed = sum(1 for row in removed if row.get("bad_quality_flag"))
    removed_quality_rate = bad_removed / max(1, len(removed)) if removed else None
    j4_pass = bool(
        j4.get("cluster_count", 0) >= max(1, (j2.get("cluster_count") or 0) - 2)
        and (j4.get("p90_turnover") or 999.0) <= (j2.get("p90_turnover") or 0.0) + 0.01
        and (j4.get("equal_cost_adjusted_return_proxy") or -999.0) >= (j2.get("equal_cost_adjusted_return_proxy") or 999.0)
        and (j4.get("liquidity_adjusted_book_ir_proxy") or -999.0) >= (j2.get("liquidity_adjusted_book_ir_proxy") or 999.0)
        and (removed_quality_rate is None or removed_quality_rate >= 0.5)
    )
    if j2_pass and j4_pass:
        decision = "PASS_KB_J2_AND_J4_RELAXED_GENERALIZATION"
    elif j2_pass:
        decision = "PASS_KB_J2_HOLD_J4_RELAXED"
    else:
        decision = "HOLD_KB_LOCKED_FILTER_GENERALIZATION"
    return {
        "decision": decision,
        "j2_pass": j2_pass,
        "j4_relaxed_pass": j4_pass,
        "removed_cluster_count": len(removed),
        "removed_bad_quality_count": bad_removed,
        "removed_bad_quality_rate": _round(removed_quality_rate),
        "notes": [
            "K-B applies locked rules to fresh G2 output; it does not use old locked cluster IDs.",
            "new_vs_149_retained is not asserted unless a full 149 representative registry is available.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    metrics = report["book_metrics"]
    decision = report["decision"]
    lines = [
        "# Phase3K-B Locked Filter Generalization - 2026-05-16",
        "",
        f"Decision: `{decision['decision']}`",
        "",
        "This aggregate applies locked J2/J4_relaxed rules to fresh G2 output. It does not tune thresholds and does not filter by old cluster IDs.",
        "",
        "## Book Metrics",
        "",
        "| book | clusters | retention | p90 turnover | max raw share | cap proxy median | equal score | equal IR | liq IR | source top |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ["J0_fresh", "J2_fresh", "J4_relaxed_fresh"]:
        item = metrics[name]
        lines.append(
            f"| {name} | {item.get('cluster_count')} | {item.get('retention_vs_j0')} | {item.get('p90_turnover')} | {item.get('max_raw_share')} | {item.get('capacity_proxy_median')} | {item.get('equal_cost_adjusted_return_proxy')} | {item.get('equal_book_ir_proxy')} | {item.get('liquidity_adjusted_book_ir_proxy')} | {item.get('source_lane_top_share')} |"
        )
    lines.extend(
        [
            "",
            "## Removed Cluster Diagnostics",
            "",
            f"- removed clusters: `{decision['removed_cluster_count']}`",
            f"- removed bad-quality count: `{decision['removed_bad_quality_count']}`",
            f"- removed bad-quality rate: `{decision['removed_bad_quality_rate']}`",
            "",
            "## Scope",
            "",
            "- Book-readiness validation only.",
            "- No production deployment, live capacity, or fill model is confirmed.",
            "- Full `new_vs_149_retained` requires a complete 149 representative registry; this artifact records the gap rather than fabricating the metric.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=None)
    parser.add_argument("--strict-rows", type=Path, default=None)
    parser.add_argument("--seeds", nargs="*", type=int, default=[47, 48, 49, 50])
    parser.add_argument("--dataset-path", type=Path, default=Path(r"G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3k_b_locked_filter_generalization_20260516"))
    parser.add_argument("--top-quantile", type=float, default=0.02)
    parser.add_argument("--turnover-max", type=float, default=0.75)
    parser.add_argument("--recent-quarter-window-count", type=int, default=2)
    parser.add_argument("--recent-warmup-days", type=int, default=60)
    args = parser.parse_args()

    if args.strict_rows is not None:
        strict_rows, missing = _load_strict_rows_from_file(args.strict_rows)
        input_mode = "strict_rows_file"
    elif args.run_root is not None:
        strict_rows, missing = _load_strict_rows_from_run_root(args.run_root, list(args.seeds))
        input_mode = "fresh_run_root"
    else:
        raise SystemExit("provide --run-root or --strict-rows")
    if missing:
        raise FileNotFoundError(f"missing strict rows: {missing}")

    frame, _evaluation_start, _evaluation_end = _load_recent_quarter_market_panel(
        args.dataset_path,
        quarter_window_count=args.recent_quarter_window_count,
        warmup_days=args.recent_warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    liquidity_frame = _prepare_liquidity_frame(frame)
    cluster_records = _cluster_rows(strict_rows, arm="i0", turnover_max=args.turnover_max)
    cluster_records = _attach_cluster_liquidity(
        cluster_records,
        signal_frame=signal_frame,
        liquidity_frame=liquidity_frame,
        field_lags=signal_clock_report["field_lags"],
        top_quantile=args.top_quantile,
    )
    books = _book_rows(cluster_records)
    j4_removed = _removed_diagnostics(books["J2_fresh"], books["J4_relaxed_fresh"])
    book_metrics = {
        name: _book_proxy(name, rows, baseline_count=len(books["J0_fresh"]))
        for name, rows in books.items()
    }
    decision = _decision(book_metrics, j4_removed)
    seed_books = _seed_book_rows(cluster_records)
    seed_metrics = []
    for seed, seed_book in seed_books.items():
        for name, rows in seed_book.items():
            seed_metrics.append(
                {
                    "seed": seed,
                    **_book_proxy(name, rows, baseline_count=len(seed_book["J0_fresh"])),
                }
            )
    report = {
        "created_at": utc_now_iso(),
        "experiment_id": "20260516_phase3k_b_locked_filter_generalization",
        "version": PHASE3K_B_VERSION,
        "status": "completed",
        "input_mode": input_mode,
        "run_root": str(args.run_root) if args.run_root is not None else None,
        "strict_rows": str(args.strict_rows) if args.strict_rows is not None else None,
        "dataset_path": str(args.dataset_path),
        "seeds": list(args.seeds),
        "decision": decision,
        "book_rule_definitions": {
            "J0_fresh": "all fresh G2 deployable signal clusters",
            "J2_fresh": "locked J2 v1 rule: lower-turnover 70% by p90 turnover, then raw concentration cap while retaining at least 60%",
            "J4_relaxed_fresh": "locked J4 relaxed v1 overlay: remove J2 clusters only if both amount and capacity are below 5th percentile or limit/suspension feasibility fails",
        },
        "book_metrics": book_metrics,
        "seed_book_metrics": seed_metrics,
        "removed_clusters": j4_removed,
        "signal_cluster_report": {
            "cluster_mode": "fresh_replay_signal_cluster_ids_prefixed_by_seed",
            "note": "K-B does not re-run expensive signal-vector reclustering; fresh seed-local replay clusters are made unique by seed prefix.",
        },
        "bias_scope": {
            "mode": "fresh G2 locked-filter generalization",
            "not_confirmed": [
                "production deployment",
                "live capacity",
                "execution fill model",
                "mature capacity model",
            ],
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3k_b_locked_filter_generalization.json", report)
    _write_csv(args.output_dir / "phase3k_b_book_metrics.csv", list(book_metrics.values()))
    _write_csv(args.output_dir / "phase3k_b_seed_book_metrics.csv", seed_metrics)
    _write_csv(args.output_dir / "phase3k_b_cluster_metrics.csv", cluster_records)
    member_rows = []
    for book_name, rows in books.items():
        for row in rows:
            item = dict(row)
            item["book"] = book_name
            member_rows.append(item)
    _write_csv(args.output_dir / "phase3k_b_book_members.csv", member_rows)
    _write_csv(args.output_dir / "phase3k_b_j4_removed_clusters.csv", j4_removed)
    (args.output_dir / "PHASE3K_B_LOCKED_FILTER_GENERALIZATION_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
