"""Phase3J-3 J4 liquidity-aware filter sensitivity.

This is a no-run sensitivity pass over Phase3J-2 cluster metrics. It searches
cluster-level filter thresholds only; it does not generate formulas, run replay,
or change G2 discovery selection.
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


def _book_metrics(name: str, rows: list[dict[str, Any]], *, baseline_count: int) -> dict[str, Any]:
    raw_counts = [int(float(row.get("raw_pass_count") or 0)) for row in rows]
    source_counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source_lane") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    cost_scores = [_safe_float(row.get("cost_adjusted_score")) or 0.0 for row in rows]
    p90_turnovers = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in rows) if value is not None]
    median_turnovers = [value for value in (_safe_float(row.get("median_replay_turnover")) for row in rows) if value is not None]
    capacities = [value for value in (_safe_float(row.get("capacity_proxy")) for row in rows) if value is not None]
    amounts = [value for value in (_safe_float(row.get("median_amount_20d")) for row in rows) if value is not None]
    loss = [(_safe_float(row.get("limit_hit_rate")) or 0.0) + (_safe_float(row.get("suspension_rate")) or 0.0) for row in rows]
    equal_score = sum(cost_scores) / max(1, len(cost_scores))
    return {
        "name": name,
        "cluster_count": len(rows),
        "retention_vs_j0": _round(len(rows) / max(1, baseline_count)),
        "median_turnover": _round(_median(median_turnovers)),
        "p90_turnover": _round(_quantile(p90_turnovers, 0.9)),
        "capacity_proxy_median": _round(_median(capacities)),
        "amount_20d_median": _round(_median(amounts)),
        "limit_suspension_loss_proxy": _round(sum(loss) / max(1, len(loss)) if loss else None),
        "max_raw_share": _round(max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else None),
        "source_lane_top_share": _round(max(source_counts.values()) / max(1, len(rows)) if source_counts else None),
        "equal_cost_adjusted_score": _round(equal_score),
    }


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
        if gate_mode == "or":
            low_liquidity = amount_bad or capacity_bad
        else:
            low_liquidity = amount_bad and capacity_bad
        limit_hit = _safe_float(row.get("limit_hit_rate")) or 0.0
        susp = _safe_float(row.get("suspension_rate")) or 0.0
        if low_liquidity:
            continue
        if limit_hit > limit_max or susp > susp_max:
            continue
        out.append(row)
    return out


def _variant_pass(metrics: dict[str, Any], *, j2: dict[str, Any]) -> bool:
    return bool(
        metrics["cluster_count"] >= 18
        and (metrics["p90_turnover"] or 999.0) <= 0.28
        and (metrics["max_raw_share"] or 999.0) <= 0.15
        and (metrics["capacity_proxy_median"] or 0.0) > (j2["capacity_proxy_median"] or 0.0)
        and (metrics["equal_cost_adjusted_score"] or 0.0) >= (j2["equal_cost_adjusted_score"] or 0.0) * 0.95
    )


def _markdown(report: dict[str, Any]) -> str:
    best = report["best_variant"]
    lines = [
        "# Phase3J J4 Filter Sensitivity - 2026-05-16",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "This is a no-run sensitivity audit over cluster-level filters. It does not run search or replay.",
        "",
        "## Baselines",
        "",
        "| book | clusters | retention | p90 turnover | capacity median | max raw share | score |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ["J0", "J2", "J4_original"]:
        item = report["baselines"][key]
        lines.append(
            f"| {key} | {item['cluster_count']} | {item['retention_vs_j0']} | {item['p90_turnover']} | {item['capacity_proxy_median']} | {item['max_raw_share']} | {item['equal_cost_adjusted_score']} |"
        )
    lines.extend(
        [
            "",
            "## Best Relaxed J4",
            "",
            f"- name: `{best.get('name')}`",
            f"- pass: `{best.get('pass_gate')}`",
            f"- clusters: `{best.get('cluster_count')}`",
            f"- p90 turnover: `{best.get('p90_turnover')}`",
            f"- capacity proxy median: `{best.get('capacity_proxy_median')}`",
            f"- max raw share: `{best.get('max_raw_share')}`",
            f"- equal cost-adjusted score: `{best.get('equal_cost_adjusted_score')}`",
            f"- filter: amount_q `{best.get('amount_q')}`, capacity_q `{best.get('capacity_q')}`, mode `{best.get('gate_mode')}`, limit_max `{best.get('limit_max')}`, susp_max `{best.get('susp_max')}`",
            "",
            "## Interpretation",
            "",
            "- If the best variant passes, use it as the next J4 candidate for a proper book replay/check.",
            "- If it does not pass, keep J2 as book-readiness candidate and treat liquidity/capacity filtering as offline research.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--j0", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j0_clusters.csv"))
    parser.add_argument("--j2", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j2_clusters.csv"))
    parser.add_argument("--j4", type=Path, default=Path("reports/phase3j_liquidity_capacity_preflight_20260516/phase3j_book_j4_clusters.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3j_j4_filter_sensitivity_20260516"))
    args = parser.parse_args()

    j0_rows = _read_csv(args.j0)
    j2_rows = _read_csv(args.j2)
    j4_rows = _read_csv(args.j4)
    j0 = _book_metrics("J0", j0_rows, baseline_count=len(j0_rows))
    j2 = _book_metrics("J2", j2_rows, baseline_count=len(j0_rows))
    j4_original = _book_metrics("J4_original", j4_rows, baseline_count=len(j0_rows))

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
                    metrics = _book_metrics(
                        f"J4_relaxed_a{amount_q}_c{capacity_q}_{gate_mode}_l{limit_max}",
                        rows,
                        baseline_count=len(j0_rows),
                    )
                    metrics.update(
                        {
                            "amount_q": amount_q,
                            "capacity_q": capacity_q,
                            "gate_mode": gate_mode,
                            "limit_max": limit_max,
                            "susp_max": 0.01,
                            "pass_gate": _variant_pass(metrics, j2=j2),
                        }
                    )
                    variants.append(metrics)

    variants.sort(
        key=lambda item: (
            0 if item["pass_gate"] else 1,
            -int(item["cluster_count"]),
            item["p90_turnover"] or 999.0,
            -(item["capacity_proxy_median"] or 0.0),
            -(item["equal_cost_adjusted_score"] or 0.0),
        )
    )
    best = variants[0] if variants else {}
    decision = "PASS_RELAXED_J4_CANDIDATE" if best.get("pass_gate") else "HOLD_RELAXED_J4_CANDIDATE"
    report = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "decision": decision,
        "objective": "Find a less destructive J4 liquidity/capacity cluster-level filter without rerunning search.",
        "baselines": {"J0": j0, "J2": j2, "J4_original": j4_original},
        "best_variant": best,
        "top_variants": variants[:20],
        "all_variant_count": len(variants),
        "bias_scope": {
            "mode": "no-run posthoc filter sensitivity",
            "not_confirmed": ["production deployment", "live execution", "true capacity fill model"],
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3j_j4_filter_sensitivity.json", report)
    _write_csv(args.output_dir / "phase3j_j4_filter_sensitivity_top_variants.csv", variants[:50])
    # Also write the selected cluster list for the best variant.
    best_rows = _filter_rows(
        j2_rows,
        amount_q=float(best.get("amount_q") or 0.0),
        capacity_q=float(best.get("capacity_q") or 0.0),
        gate_mode=str(best.get("gate_mode") or "and"),
        limit_max=float(best.get("limit_max") or 0.2),
        susp_max=float(best.get("susp_max") or 0.01),
    )
    _write_csv(args.output_dir / "phase3j_book_j4_relaxed_candidate_clusters.csv", best_rows)
    (args.output_dir / "PHASE3J_J4_FILTER_SENSITIVITY_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
