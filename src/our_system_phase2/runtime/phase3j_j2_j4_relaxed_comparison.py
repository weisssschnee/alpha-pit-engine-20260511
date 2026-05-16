"""Phase3J J2 vs relaxed-J4 overlap, plateau, and book proxy audit.

No search and no replay are run here. This consumes completed cluster metrics
from Phase3J-2/3 and checks whether relaxed J4 is a stable book-readiness
candidate or only a single-parameter artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore, _corr


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if value == value)
    return float(statistics.median(clean)) if clean else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if value == value)
    if not clean:
        return None
    if len(clean) == 1:
        return float(clean[0])
    pos = (len(clean) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(clean[lo])
    return float(clean[lo] * (hi - pos) + clean[hi] * (pos - lo))


def _round(value: float | None, digits: int = 6) -> float | None:
    return round(value, digits) if value is not None and math.isfinite(value) else None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("cluster_id")): row for row in rows}


def _filter_rows(
    rows: list[dict[str, Any]],
    *,
    amount_q: float,
    capacity_q: float,
    gate_mode: str,
    limit_max: float,
    susp_max: float,
) -> list[dict[str, Any]]:
    amounts = [value for value in (_safe_float(row.get("median_amount_20d")) for row in rows) if value is not None]
    capacities = [value for value in (_safe_float(row.get("capacity_proxy")) for row in rows) if value is not None]
    amount_cut = _quantile(amounts, amount_q) if amount_q > 0 else None
    capacity_cut = _quantile(capacities, capacity_q) if capacity_q > 0 else None
    out = []
    for row in rows:
        amount = _safe_float(row.get("median_amount_20d"))
        capacity = _safe_float(row.get("capacity_proxy"))
        amount_bad = amount_cut is not None and amount is not None and amount < amount_cut
        capacity_bad = capacity_cut is not None and capacity is not None and capacity < capacity_cut
        low_liquidity = (amount_bad or capacity_bad) if gate_mode == "or" else (amount_bad and capacity_bad)
        limit_hit = _safe_float(row.get("limit_hit_rate")) or 0.0
        susp = _safe_float(row.get("suspension_rate")) or 0.0
        if low_liquidity or limit_hit > limit_max or susp > susp_max:
            continue
        out.append(row)
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


def _pairwise_corr(rows: list[dict[str, Any]], store: Phase3GSignalVectorStore) -> tuple[float | None, float | None]:
    vectors = []
    for row in rows:
        vector, _meta = store.vector_for_expression(str(row.get("representative_expression") or ""))
        if vector is not None:
            vectors.append(vector)
    values = []
    for index, left in enumerate(vectors):
        for right in vectors[index + 1 :]:
            values.append(abs(_corr(left, right)))
    return _round(sum(values) / len(values) if values else None), _round(max(values) if values else None)


def _book_proxy(name: str, rows: list[dict[str, Any]], *, baseline_count: int, store: Phase3GSignalVectorStore | None) -> dict[str, Any]:
    p90_values = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in rows) if value is not None]
    median_values = [value for value in (_safe_float(row.get("median_replay_turnover")) for row in rows) if value is not None]
    capacity_values = [value for value in (_safe_float(row.get("capacity_proxy")) for row in rows) if value is not None]
    amount_values = [value for value in (_safe_float(row.get("median_amount_20d")) for row in rows) if value is not None]
    limit_loss = [(_safe_float(row.get("limit_hit_rate")) or 0.0) + (_safe_float(row.get("suspension_rate")) or 0.0) for row in rows]
    raw_counts = [int(float(row.get("raw_pass_count") or 0)) for row in rows]
    source_counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source_lane") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    mean_corr, max_corr = _pairwise_corr(rows, store) if store is not None else (None, None)
    out = {
        "book": name,
        "cluster_count": len(rows),
        "retention_vs_j0": _round(len(rows) / max(1, baseline_count)),
        "median_turnover": _round(_median(median_values)),
        "p90_turnover": _round(_quantile(p90_values, 0.9)),
        "capacity_proxy_median": _round(_median(capacity_values)),
        "amount_20d_median": _round(_median(amount_values)),
        "limit_suspension_loss_proxy": _round(sum(limit_loss) / max(1, len(limit_loss)) if limit_loss else None),
        "max_raw_share": _round(max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else None),
        "source_lane_top_share": _round(max(source_counts.values()) / max(1, len(rows)) if source_counts else None),
        "mean_pairwise_cluster_corr": mean_corr,
        "max_pairwise_cluster_corr": max_corr,
    }
    for mode in ["equal", "inverse_turnover", "liquidity_adjusted"]:
        weights = _weights(rows, mode)
        scores = [_safe_float(row.get("cost_adjusted_score")) or 0.0 for row in rows]
        weighted_score = sum(weight * score for weight, score in zip(weights, scores))
        diversification = math.sqrt(max(1e-9, 1.0 + (mean_corr or 0.0)))
        total_abs = sum(abs(weight * score) for weight, score in zip(weights, scores)) or 1.0
        out[f"{mode}_cost_adjusted_proxy"] = _round(weighted_score)
        out[f"{mode}_book_ir_proxy"] = _round(weighted_score / diversification)
        out[f"{mode}_max_cluster_weight"] = _round(max(weights) if weights else None)
        out[f"{mode}_top_cluster_contribution"] = _round(max((abs(weight * score) for weight, score in zip(weights, scores)), default=0.0) / total_abs)
    return out


def _variant_pass(metrics: dict[str, Any], *, j2: dict[str, Any]) -> bool:
    return bool(
        metrics["cluster_count"] >= 18
        and (metrics["p90_turnover"] or 999.0) <= 0.28
        and (metrics["max_raw_share"] or 999.0) <= 0.15
        and (metrics["capacity_proxy_median"] or 0.0) >= (j2["capacity_proxy_median"] or 0.0)
        and (metrics["equal_cost_adjusted_proxy"] or 0.0) >= (j2["equal_cost_adjusted_proxy"] or 0.0) * 0.95
    )


def _markdown(report: dict[str, Any]) -> str:
    overlap = report["overlap"]
    plateau = report["plateau"]
    proxy = report["book_proxy"]
    lines = [
        "# Phase3J J2 vs J4 Relaxed Comparison - 2026-05-16",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "This is a no-run overlap, plateau, and book proxy audit. It does not run search or replay.",
        "",
        "## Overlap",
        "",
        f"- J2 clusters: `{overlap['j2_count']}`",
        f"- J4 relaxed clusters: `{overlap['j4_count']}`",
        f"- overlap: `{overlap['overlap_count']}`",
        f"- J2-only removed clusters: `{overlap['j2_only_count']}`",
        f"- J4-only added clusters: `{overlap['j4_only_count']}`",
        "",
        "## Sensitivity Plateau",
        "",
        f"- pass variants: `{plateau['pass_count']}` / `{plateau['variant_count']}`",
        f"- local neighborhood variants: `{plateau['local_count']}`",
        f"- local pass variants: `{plateau['local_pass_count']}`",
        f"- near-best variants: `{plateau['near_best_count']}`",
        "",
        "## Book Proxy",
        "",
        "| metric | J2 | J4_relaxed |",
        "| --- | ---: | ---: |",
    ]
    for key in [
        "cluster_count",
        "retention_vs_j0",
        "p90_turnover",
        "capacity_proxy_median",
        "max_raw_share",
        "source_lane_top_share",
        "limit_suspension_loss_proxy",
        "equal_book_ir_proxy",
        "liquidity_adjusted_book_ir_proxy",
        "liquidity_adjusted_max_cluster_weight",
        "liquidity_adjusted_top_cluster_contribution",
    ]:
        lines.append(f"| {key} | {proxy['J2'].get(key)} | {proxy['J4_relaxed'].get(key)} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- J4_relaxed is almost a subset of J2, so it is a light cluster-level prune, not a new book construction.",
            "- If plateau is broad, the light liquidity/capacity constraint is useful. If plateau is narrow, it is likely overfit.",
            "- Production deployment remains unconfirmed; this is a book-readiness proxy only.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--j0", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j0_clusters.csv"))
    parser.add_argument("--j2", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j2_clusters.csv"))
    parser.add_argument("--j4", type=Path, default=Path("reports/phase3j_j4_filter_sensitivity_20260516/phase3j_book_j4_relaxed_candidate_clusters.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3j_j2_j4_relaxed_comparison_20260516"))
    parser.add_argument("--dataset-path", type=Path, default=Path(r"G:\Project_V7_Rotation\scripts\data\phase2_stock_tdx_official_20250806_to_20260508_maxopt.parquet"))
    args = parser.parse_args()

    j0_rows = _read_csv(args.j0)
    j2_rows = _read_csv(args.j2)
    j4_rows = _read_csv(args.j4)
    j2_by_id = {str(row.get("cluster_id")): row for row in j2_rows}
    j4_by_id = {str(row.get("cluster_id")): row for row in j4_rows}
    overlap_ids = sorted(set(j2_by_id) & set(j4_by_id))
    j2_only_ids = sorted(set(j2_by_id) - set(j4_by_id))
    j4_only_ids = sorted(set(j4_by_id) - set(j2_by_id))

    store = Phase3GSignalVectorStore(dataset_path=args.dataset_path)
    j2_proxy = _book_proxy("J2", j2_rows, baseline_count=len(j0_rows), store=store)
    j4_proxy = _book_proxy("J4_relaxed", j4_rows, baseline_count=len(j0_rows), store=store)

    variants = []
    for amount_q in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]:
        for capacity_q in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25]:
            for gate_mode in ["and", "or"]:
                for limit_max in [0.20, 0.25, 0.30]:
                    rows = _filter_rows(
                        j2_rows,
                        amount_q=amount_q,
                        capacity_q=capacity_q,
                        gate_mode=gate_mode,
                        limit_max=limit_max,
                        susp_max=0.01,
                    )
                    metrics = _book_proxy(
                        f"J4_relaxed_a{amount_q}_c{capacity_q}_{gate_mode}_l{limit_max}",
                        rows,
                        baseline_count=len(j0_rows),
                        store=None,
                    )
                    metrics.update(
                        {
                            "amount_q": amount_q,
                            "capacity_q": capacity_q,
                            "gate_mode": gate_mode,
                            "limit_max": limit_max,
                            "susp_max": 0.01,
                            "pass_gate": _variant_pass(metrics, j2=j2_proxy),
                        }
                    )
                    metrics["near_best"] = bool(
                        metrics["cluster_count"] >= 20
                        and (metrics["p90_turnover"] or 999.0) <= (j4_proxy["p90_turnover"] or 999.0) + 0.02
                        and (metrics["max_raw_share"] or 999.0) <= 0.15
                        and (metrics["equal_cost_adjusted_proxy"] or 0.0) >= (j4_proxy["equal_cost_adjusted_proxy"] or 0.0) * 0.98
                    )
                    metrics["local_to_best"] = bool(
                        abs(amount_q - 0.05) <= 0.05
                        and abs(capacity_q - 0.05) <= 0.05
                        and gate_mode == "and"
                        and abs(limit_max - 0.20) <= 0.05
                    )
                    variants.append(metrics)
    variants.sort(
        key=lambda item: (
            0 if item["pass_gate"] else 1,
            -int(item["cluster_count"]),
            item["p90_turnover"] or 999.0,
            -(item["equal_cost_adjusted_proxy"] or 0.0),
        )
    )
    pass_count = sum(1 for item in variants if item["pass_gate"])
    local = [item for item in variants if item["local_to_best"]]
    local_pass = [item for item in local if item["pass_gate"]]
    near_best = [item for item in variants if item["near_best"]]
    decision = (
        "PASS_J4_RELAXED_STABLE_BOOK_CANDIDATE"
        if j4_proxy["cluster_count"] >= 18 and pass_count >= 6 and len(local_pass) >= 2 and len(j2_only_ids) <= 2
        else "HOLD_J4_RELAXED_STABILITY"
    )
    report = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "decision": decision,
        "objective": "Compare J2 and relaxed J4 by overlap, sensitivity stability, and book/execution proxy.",
        "overlap": {
            "j2_count": len(j2_rows),
            "j4_count": len(j4_rows),
            "overlap_count": len(overlap_ids),
            "j2_only_count": len(j2_only_ids),
            "j4_only_count": len(j4_only_ids),
            "j2_only_cluster_ids": j2_only_ids,
            "j4_only_cluster_ids": j4_only_ids,
            "j2_only_rows": [j2_by_id[item] for item in j2_only_ids],
            "j4_only_rows": [j4_by_id[item] for item in j4_only_ids],
        },
        "plateau": {
            "variant_count": len(variants),
            "pass_count": pass_count,
            "local_count": len(local),
            "local_pass_count": len(local_pass),
            "near_best_count": len(near_best),
            "top_variants": variants[:20],
        },
        "book_proxy": {
            "J2": j2_proxy,
            "J4_relaxed": j4_proxy,
        },
        "bias_scope": {
            "mode": "no-run posthoc cluster book audit",
            "not_confirmed": ["production deployment", "live capacity", "fill model", "new alpha discovery"],
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3j_j2_j4_relaxed_comparison.json", report)
    _write_csv(args.output_dir / "phase3j_j2_only_removed_clusters.csv", [j2_by_id[item] for item in j2_only_ids])
    _write_csv(args.output_dir / "phase3j_j4_only_added_clusters.csv", [j4_by_id[item] for item in j4_only_ids])
    _write_csv(args.output_dir / "phase3j_j4_sensitivity_plateau_variants.csv", variants)
    _write_csv(args.output_dir / "phase3j_book_proxy_comparison.csv", [j2_proxy, j4_proxy])
    (args.output_dir / "PHASE3J_J2_J4_RELAXED_COMPARISON_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
