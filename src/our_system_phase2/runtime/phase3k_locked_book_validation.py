"""Phase3K-A locked existing book validation.

This script validates locked J2/J4_relaxed cluster lists without search,
candidate generation, replay, or threshold tuning. It consumes the Phase3J
locked filter artifact and existing cluster metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact


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


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    return float(statistics.median(clean)) if clean else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
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


def _rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("cluster_id")): row for row in rows}


def _pick_rows(j0_rows: list[dict[str, Any]], cluster_ids: list[str]) -> list[dict[str, Any]]:
    by_id = _rows_by_id(j0_rows)
    return [by_id[cluster_id] for cluster_id in cluster_ids if cluster_id in by_id]


def _weights(rows: list[dict[str, Any]], mode: str) -> list[float]:
    raw = []
    for row in rows:
        if mode == "inverse_turnover":
            turnover = _safe_float(row.get("p90_replay_turnover")) or 999.0
            raw.append(1.0 / max(0.02, turnover))
        elif mode == "liquidity_adjusted":
            amount = _safe_float(row.get("median_amount_20d")) or 0.0
            turnover = _safe_float(row.get("p90_replay_turnover")) or 999.0
            raw.append(math.sqrt(max(0.0, amount)) / max(0.02, turnover))
        else:
            raw.append(1.0)
    total = sum(raw) or 1.0
    return [value / total for value in raw]


def _weighted_score(rows: list[dict[str, Any]], weights: list[float], *, stress: float = 0.0) -> float:
    scores = []
    for row in rows:
        score = _safe_float(row.get("cost_adjusted_score")) or 0.0
        turnover = _safe_float(row.get("p90_replay_turnover")) or 0.0
        scores.append(score - stress * turnover)
    return sum(weight * score for weight, score in zip(weights, scores))


def _top_contribution(rows: list[dict[str, Any]], weights: list[float], *, stress: float = 0.0) -> float | None:
    parts = []
    for row, weight in zip(rows, weights):
        score = _safe_float(row.get("cost_adjusted_score")) or 0.0
        turnover = _safe_float(row.get("p90_replay_turnover")) or 0.0
        parts.append(abs(weight * (score - stress * turnover)))
    total = sum(parts)
    return max(parts) / total if total else None


def _source_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row.get("source_lane") or "unknown") for row in rows)


def _numbers(rows: list[dict[str, Any]], field: str) -> list[float]:
    return [value for value in (_safe_float(row.get(field)) for row in rows) if value is not None]


def _stress_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    equal = _weights(rows, "equal")
    for stress in [0.0, 0.25, 0.5, 1.0, 2.0]:
        key = str(stress).replace(".", "p")
        stressed_scores = []
        for row in rows:
            score = _safe_float(row.get("cost_adjusted_score")) or 0.0
            turnover = _safe_float(row.get("p90_replay_turnover")) or 0.0
            stressed_scores.append(score - stress * turnover)
        out[f"stress_{key}_equal_score"] = _round(sum(weight * score for weight, score in zip(equal, stressed_scores)))
        out[f"stress_{key}_survival_count"] = sum(1 for score in stressed_scores if score > 0)
        out[f"stress_{key}_survival_rate"] = _round(out[f"stress_{key}_survival_count"] / max(1, len(rows)))
    return out


def _book_metrics(name: str, rows: list[dict[str, Any]], *, baseline_count: int) -> dict[str, Any]:
    raw_counts = [int(float(row.get("raw_pass_count") or 0)) for row in rows]
    deployable_counts = [int(float(row.get("deployable_count") or 0)) for row in rows]
    source_counts = _source_counts(rows)
    p90_turnovers = _numbers(rows, "p90_replay_turnover")
    median_turnovers = _numbers(rows, "median_replay_turnover")
    limit_susp = [(_safe_float(row.get("limit_hit_rate")) or 0.0) + (_safe_float(row.get("suspension_rate")) or 0.0) for row in rows]
    out: dict[str, Any] = {
        "book": name,
        "cluster_count": len(rows),
        "retention_vs_k0": _round(len(rows) / max(1, baseline_count)),
        "median_turnover": _round(_median(median_turnovers)),
        "p90_turnover": _round(_quantile(p90_turnovers, 0.9)),
        "max_raw_share": _round(max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else None),
        "max_deployable_share": _round(max(deployable_counts) / max(1, sum(deployable_counts)) if deployable_counts else None),
        "source_lane_top": source_counts.most_common(1)[0][0] if source_counts else None,
        "source_lane_top_share": _round(source_counts.most_common(1)[0][1] / max(1, len(rows)) if source_counts else None),
        "source_lane_counts": dict(source_counts),
        "limit_suspension_loss_proxy": _round(sum(limit_susp) / max(1, len(limit_susp)) if limit_susp else None),
        "median_capacity_proxy": _round(_median(_numbers(rows, "capacity_proxy"))),
        "median_amount_20d": _round(_median(_numbers(rows, "median_amount_20d"))),
        "median_tradable_breadth": _round(_median(_numbers(rows, "tradable_breadth"))),
        "p10_tradable_breadth": _round(_quantile(_numbers(rows, "tradable_breadth"), 0.1)),
        "median_selected_date_count": _round(_median(_numbers(rows, "selected_date_count"))),
        "p10_selected_date_count": _round(_quantile(_numbers(rows, "selected_date_count"), 0.1)),
        "median_effective_signal_count": _round(_median(_numbers(rows, "effective_signal_count"))),
        "p10_effective_signal_count": _round(_quantile(_numbers(rows, "effective_signal_count"), 0.1)),
        "subperiod_validation_mode": "proxy_only_selected_date_and_breadth_no_new_replay",
    }
    for mode in ["equal", "inverse_turnover", "liquidity_adjusted"]:
        weights = _weights(rows, mode)
        score = _weighted_score(rows, weights)
        out[f"{mode}_cost_adjusted_proxy"] = _round(score)
        out[f"{mode}_max_cluster_weight"] = _round(max(weights) if weights else None)
        out[f"{mode}_top_cluster_contribution"] = _round(_top_contribution(rows, weights))
    out.update(_stress_metrics(rows))
    return out


def _cluster_087_audit(row: dict[str, Any] | None, *, j2_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if row is None:
        return {"cluster_id": "cluster_087", "found": False}
    capacity_values = _numbers(j2_rows, "capacity_proxy")
    cost_values = _numbers(j2_rows, "cost_adjusted_score")
    capacity = _safe_float(row.get("capacity_proxy"))
    cost = _safe_float(row.get("cost_adjusted_score"))
    capacity_rank = None
    if capacity is not None and capacity_values:
        capacity_rank = sum(1 for value in capacity_values if value <= capacity) / len(capacity_values)
    cost_rank = None
    if cost is not None and cost_values:
        cost_rank = sum(1 for value in cost_values if value <= cost) / len(cost_values)
    return {
        "cluster_id": "cluster_087",
        "found": True,
        "representative_candidate_id": row.get("representative_candidate_id"),
        "representative_expression": row.get("representative_expression"),
        "source_lane": row.get("source_lane"),
        "capacity_proxy": _round(capacity),
        "capacity_percentile_within_j2": _round(capacity_rank),
        "cost_adjusted_score": _round(cost),
        "cost_score_percentile_within_j2": _round(cost_rank),
        "p90_replay_turnover": _round(_safe_float(row.get("p90_replay_turnover"))),
        "median_amount_20d": _round(_safe_float(row.get("median_amount_20d"))),
        "limit_hit_rate": _round(_safe_float(row.get("limit_hit_rate"))),
        "suspension_rate": _round(_safe_float(row.get("suspension_rate"))),
        "deletion_interpretation": "supports hygiene removal if low capacity and negative cost-adjusted score persist",
    }


def _markdown(report: dict[str, Any]) -> str:
    books = report["book_metrics"]
    c087 = report["cluster_087_audit"]
    lines = [
        "# Phase3K-A Locked Book Validation - 2026-05-16",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "This is a no-search validation over locked Phase3J books. It does not generate formulas, reselect clusters, or tune thresholds.",
        "",
        "## Compared Books",
        "",
        "| metric | K0 J0 all | K1 J2 locked | K2 J4 relaxed locked |",
        "| --- | ---: | ---: | ---: |",
    ]
    keys = [
        "cluster_count",
        "median_turnover",
        "p90_turnover",
        "max_raw_share",
        "source_lane_top_share",
        "limit_suspension_loss_proxy",
        "median_capacity_proxy",
        "equal_cost_adjusted_proxy",
        "liquidity_adjusted_cost_adjusted_proxy",
        "liquidity_adjusted_top_cluster_contribution",
        "stress_1p0_survival_rate",
        "median_selected_date_count",
        "p10_tradable_breadth",
    ]
    for key in keys:
        lines.append(f"| {key} | {books['K0_J0_all'].get(key)} | {books['K1_J2_filter_v1'].get(key)} | {books['K2_J4_relaxed_filter_v1'].get(key)} |")
    lines.extend(
        [
            "",
            "## Cluster 087",
            "",
            f"- found: `{c087.get('found')}`",
            f"- source lane: `{c087.get('source_lane')}`",
            f"- capacity proxy: `{c087.get('capacity_proxy')}`",
            f"- capacity percentile within J2: `{c087.get('capacity_percentile_within_j2')}`",
            f"- cost-adjusted score: `{c087.get('cost_adjusted_score')}`",
            f"- cost score percentile within J2: `{c087.get('cost_score_percentile_within_j2')}`",
            f"- expression: `{c087.get('representative_expression')}`",
            "",
            "## Interpretation",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["interpretation"])
    lines.extend(
        [
            "",
            "## Bias Scope",
            "",
            "- K-A validates locked cluster-level proxies only.",
            "- Subperiod stability is proxy-only here because no new subperiod replay is run.",
            "- Capacity and execution remain research proxies, not production proof.",
            "- K-B fresh G2 validation is still required for rule generalization.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locked", type=Path, default=Path("runtime/baselines/phase3j_locked_book_filters.json"))
    parser.add_argument("--j0", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j0_clusters.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3k_locked_book_validation_20260516"))
    args = parser.parse_args()

    locked = _read_json(args.locked)
    j0_rows = _read_csv(args.j0)
    j2_ids = [str(value) for value in locked["baseline_book_candidate"]["cluster_ids"]]
    j4_ids = [str(value) for value in locked["liquidity_aware_overlay_candidate"]["cluster_ids"]]
    j2_rows = _pick_rows(j0_rows, j2_ids)
    j4_rows = _pick_rows(j0_rows, j4_ids)
    j0_by_id = _rows_by_id(j0_rows)
    missing_j2 = sorted(set(j2_ids) - set(row["cluster_id"] for row in j2_rows))
    missing_j4 = sorted(set(j4_ids) - set(row["cluster_id"] for row in j4_rows))
    if missing_j2 or missing_j4:
        raise ValueError(f"locked clusters missing from J0 metrics: J2={missing_j2}, J4={missing_j4}")

    books = {
        "K0_J0_all": _book_metrics("K0_J0_all", j0_rows, baseline_count=len(j0_rows)),
        "K1_J2_filter_v1": _book_metrics("K1_J2_filter_v1", j2_rows, baseline_count=len(j0_rows)),
        "K2_J4_relaxed_filter_v1": _book_metrics("K2_J4_relaxed_filter_v1", j4_rows, baseline_count=len(j0_rows)),
    }
    cluster_087 = _cluster_087_audit(j0_by_id.get("cluster_087"), j2_rows=j2_rows)
    j2 = books["K1_J2_filter_v1"]
    j4 = books["K2_J4_relaxed_filter_v1"]
    j4_cost_not_worse = (j4["equal_cost_adjusted_proxy"] or -999.0) >= (j2["equal_cost_adjusted_proxy"] or 999.0)
    j4_liq_not_worse = (j4["liquidity_adjusted_cost_adjusted_proxy"] or -999.0) >= (j2["liquidity_adjusted_cost_adjusted_proxy"] or 999.0)
    j4_turnover_not_materially_worse = (j4["p90_turnover"] or 999.0) <= (j2["p90_turnover"] or 0.0) + 0.01
    c087_bad = bool((cluster_087.get("cost_adjusted_score") or 0.0) < 0.0 and (cluster_087.get("capacity_percentile_within_j2") or 1.0) <= 0.20)
    if j4_cost_not_worse and j4_liq_not_worse and j4_turnover_not_materially_worse and c087_bad:
        decision = "PASS_KA_J4_RELAXED_HYGIENE_OVERLAY"
    else:
        decision = "HOLD_KA_J4_RELAXED_REQUIRES_FORWARD_VALIDATION"
    interpretation = [
        "J2 remains the baseline book-readiness book.",
        "J4_relaxed is evaluated as a hygiene overlay, not a mature capacity model.",
        "J4_relaxed removes only cluster_087; any improvement should be interpreted narrowly.",
    ]
    if c087_bad:
        interpretation.append("cluster_087 remains a plausible removal target: low capacity percentile and negative cost-adjusted score.")
    if j4_cost_not_worse and j4_liq_not_worse:
        interpretation.append("J4_relaxed does not degrade equal or liquidity-adjusted cost proxy versus J2 in this locked audit.")
    if not j4_turnover_not_materially_worse:
        interpretation.append("J4_relaxed p90 turnover is materially worse than J2 under the current tolerance.")

    report = {
        "created_at": utc_now_iso(),
        "experiment_id": "20260516_phase3k_a_locked_book_validation",
        "status": "completed",
        "decision": decision,
        "objective": "Validate locked existing J2/J4_relaxed book clusters without search or threshold tuning.",
        "locked_filter_hash": locked.get("filter_version_hash"),
        "inputs": {
            "locked_filter_json": str(args.locked),
            "j0_cluster_metrics": str(args.j0),
        },
        "book_metrics": books,
        "cluster_087_audit": cluster_087,
        "interpretation": interpretation,
        "bias_scope": {
            "mode": "no-search locked cluster-level validation",
            "not_confirmed": [
                "fresh filter generalization",
                "true subperiod replay stability",
                "production deployment",
                "live capacity",
                "execution fill model",
            ],
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3k_locked_book_validation.json", report)
    metrics_rows = list(books.values())
    _write_csv(args.output_dir / "phase3k_book_metrics.csv", metrics_rows)
    member_rows = []
    for book_name, rows in [("K0_J0_all", j0_rows), ("K1_J2_filter_v1", j2_rows), ("K2_J4_relaxed_filter_v1", j4_rows)]:
        for row in rows:
            item = dict(row)
            item["book"] = book_name
            member_rows.append(item)
    _write_csv(args.output_dir / "phase3k_cluster_members.csv", member_rows)
    _write_csv(args.output_dir / "phase3k_cluster_087_audit.csv", [cluster_087])
    (args.output_dir / "PHASE3K_A_LOCKED_BOOK_VALIDATION_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
