"""Phase3J no-run cluster book filter audit.

This script does not run replay or generate candidates. It consumes the
Phase3I official global clustered rows and evaluates whether deployment filters
should be applied at cluster/book level instead of candidate pre-filter level.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.stock_pit_phase3_repair import _deployable_pass, _non_gap_replay_pass


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
    return float(statistics.median(clean))


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


def _operators(expression: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression or "")


def _field_family(field: str) -> str:
    name = field.strip("$").lower()
    if name in {"open", "high", "low", "close", "vwap"}:
        return "price"
    if name in {"amount", "volume", "turnover", "turnover_rate"}:
        return "flow"
    if "market_cap" in name or name in {"float_share", "total_share"}:
        return "size_capital"
    if "ret" in name or "return" in name:
        return "return"
    return "other"


def _field_families(expression: str) -> list[str]:
    fields = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")
    return sorted({_field_family(field) for field in fields})


def _source_lane(row: dict[str, Any]) -> str:
    return str(row.get("phase3_budget_bucket") or row.get("proposal_kind") or row.get("proof_variant") or "unknown")


def _feature_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "cluster_turnover": ["strict_mean_one_way_turnover", "portfolio_replay_avg_one_way_turnover"],
        "cost_proxy": ["strict_cost_adjusted_sortino", "strict_mean_cost_adjusted_window_spread"],
        "liquidity_proxy": ["liquidity_proxy", "mean_long_selected_amount", "mean_window_long_selected_amount"],
        "capacity_proxy": ["capacity_proxy", "mean_long_selected_final_total_market_cap", "mean_long_selected_final_float_market_cap"],
        "corr_to_149_registry_proxy": ["corr_to_149_registry_proxy", "max_corr_to_149_registry", "nearest_149_cluster_id"],
    }
    out: dict[str, Any] = {}
    denominator = max(1, len(rows))
    for name, candidates in fields.items():
        count = 0
        used = None
        for row in rows:
            for field in candidates:
                if row.get(field) not in {None, ""}:
                    count += 1
                    used = used or field
                    break
        out[name] = {"coverage": round(count / denominator, 6), "used_field": used}
    return out


def _cluster_records(rows: list[dict[str, Any]], *, arm: str, turnover_max: float) -> list[dict[str, Any]]:
    arm_rows = [row for row in rows if str(row.get("phase3i_arm_short")) == arm]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in arm_rows:
        cluster_id = str(row.get("signal_cluster_id") or "cluster_missing")
        grouped[cluster_id].append(row)

    records: list[dict[str, Any]] = []
    for cluster_id, group in sorted(grouped.items()):
        non_gap = [row for row in group if _non_gap_replay_pass(row)]
        deployable = [row for row in group if _deployable_pass(row, turnover_max=turnover_max)]
        if not deployable:
            continue
        representative = max(
            deployable,
            key=lambda row: _safe_float(row.get("strict_cost_adjusted_sortino")) or -999.0,
        )
        strict_turnover = [
            value
            for value in (_safe_float(row.get("strict_mean_one_way_turnover")) for row in deployable)
            if value is not None
        ]
        replay_turnover = [
            value
            for value in (_safe_float(row.get("portfolio_replay_avg_one_way_turnover")) for row in deployable)
            if value is not None
        ]
        cost_sortino = [
            value
            for value in (_safe_float(row.get("strict_cost_adjusted_sortino")) for row in deployable)
            if value is not None
        ]
        lane_counts = Counter(_source_lane(row) for row in deployable)
        expression = str(representative.get("expression") or "")
        records.append(
            {
                "cluster_id": cluster_id,
                "representative_expression": expression,
                "representative_candidate_id": representative.get("candidate_id"),
                "raw_pass_count": len(non_gap),
                "deployable_count": len(deployable),
                "source_lane": lane_counts.most_common(1)[0][0] if lane_counts else "unknown",
                "source_concentration": round(lane_counts.most_common(1)[0][1] / max(1, len(deployable)), 6) if lane_counts else None,
                "source_lane_counts": dict(lane_counts),
                "field_families": _field_families(expression),
                "operator_families": sorted(set(_operators(expression))),
                "median_strict_turnover": _round(_median(strict_turnover)),
                "p90_strict_turnover": _round(_quantile(strict_turnover, 0.9)),
                "median_replay_turnover": _round(_median(replay_turnover)),
                "p90_replay_turnover": _round(_quantile(replay_turnover, 0.9)),
                "median_cost_adjusted_sortino": _round(_median(cost_sortino)),
                "max_corr_to_prior_in_phase3i": _round(max((_safe_float(row.get("max_abs_signal_corr_to_prior")) or 0.0) for row in group)),
                "new_vs_149": None,
                "new_vs_149_status": "not_available_without_full_149_registry_mapping",
                "liquidity_proxy": None,
                "capacity_proxy": None,
                "cost_proxy": _round(_median(cost_sortino)),
            }
        )
    return records


def _book_metrics(name: str, records: list[dict[str, Any]], *, baseline_count: int) -> dict[str, Any]:
    med_turnover = [value for value in (_safe_float(row.get("median_replay_turnover")) for row in records) if value is not None]
    p90_turnover = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in records) if value is not None]
    source_counts = Counter(str(row.get("source_lane") or "unknown") for row in records)
    raw_counts = [int(row.get("raw_pass_count") or 0) for row in records]
    deployable_counts = [int(row.get("deployable_count") or 0) for row in records]
    cost_scores = [value for value in (_safe_float(row.get("cost_proxy")) for row in records) if value is not None]
    return {
        "book": name,
        "book_cluster_count": len(records),
        "retention_vs_j0": round(len(records) / max(1, baseline_count), 6),
        "median_cluster_median_replay_turnover": _round(_median(med_turnover)),
        "p90_cluster_p90_replay_turnover": _round(_quantile(p90_turnover, 0.9)),
        "max_cluster_raw_pass_share": _round(max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else None),
        "max_cluster_deployable_share": _round(max(deployable_counts) / max(1, sum(deployable_counts)) if deployable_counts else None),
        "source_lane_top_share": _round(source_counts.most_common(1)[0][1] / max(1, len(records)) if source_counts else None),
        "source_lane_top": source_counts.most_common(1)[0][0] if source_counts else None,
        "source_lane_counts": dict(source_counts),
        "median_cost_proxy": _round(_median(cost_scores)),
    }


def _build_books(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not records:
        return {"J0": [], "J1": [], "J2": [], "J3": []}
    p90_values = [value for value in (_safe_float(row.get("p90_replay_turnover")) for row in records) if value is not None]
    p90_cut = _quantile(p90_values, 0.70)
    j0 = list(records)
    j1 = [row for row in records if (_safe_float(row.get("p90_replay_turnover")) or 999.0) <= (p90_cut or 999.0)]

    # Balanced book: start from J1, then remove only the cluster-level sources
    # of concentration. This deliberately avoids the Phase3I mistake of
    # pre-filtering too aggressively before discovery.
    j2 = list(j1)
    min_retained = max(1, int(math.ceil(len(j0) * 0.60)))

    def raw_share(book: list[dict[str, Any]]) -> float:
        raw_counts = [int(item.get("raw_pass_count") or 0) for item in book]
        return max(raw_counts) / max(1, sum(raw_counts)) if raw_counts else 0.0

    while len(j2) > min_retained and raw_share(j2) > 0.25:
        victim = max(j2, key=lambda item: int(item.get("raw_pass_count") or 0))
        j2.remove(victim)

    while len(j2) > min_retained:
        source_counts = Counter(str(item.get("source_lane") or "unknown") for item in j2)
        top_source, top_count = source_counts.most_common(1)[0]
        if top_count / max(1, len(j2)) <= 0.55:
            break
        candidates = [item for item in j2 if str(item.get("source_lane") or "unknown") == top_source]
        victim = max(
            candidates,
            key=lambda item: (
                int(item.get("raw_pass_count") or 0),
                _safe_float(item.get("p90_replay_turnover")) or 0.0,
            ),
        )
        j2.remove(victim)

    # Capacity/liquidity is not available in the Phase3I strict rows. J3 is a
    # diagnostic cost-proxy fallback, not a promotion-grade capacity book.
    cost_values = [value for value in (_safe_float(row.get("cost_proxy")) for row in j2) if value is not None]
    cost_cut = _quantile(cost_values, 0.30)
    j3 = [row for row in j2 if (_safe_float(row.get("cost_proxy")) or -999.0) >= (cost_cut or -999.0)]
    return {"J0": j0, "J1": j1, "J2": j2, "J3": j3}


def _write_cluster_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fieldnames = [
        "cluster_id",
        "representative_candidate_id",
        "representative_expression",
        "raw_pass_count",
        "deployable_count",
        "source_lane",
        "source_concentration",
        "field_families",
        "operator_families",
        "median_replay_turnover",
        "p90_replay_turnover",
        "median_strict_turnover",
        "p90_strict_turnover",
        "median_cost_adjusted_sortino",
        "max_corr_to_prior_in_phase3i",
        "new_vs_149",
        "new_vs_149_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            item = dict(row)
            item["field_families"] = "|".join(item.get("field_families") or [])
            item["operator_families"] = "|".join(item.get("operator_families") or [])
            writer.writerow({key: item.get(key) for key in fieldnames})


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3J Cluster Book Filter Audit - 2026-05-16",
        "",
        f"Decision: `{report['decision']}`",
        "",
        "This is a no-run cluster-level audit. It does not generate candidates and does not run replay.",
        "",
        "## Book Metrics",
        "",
        "| book | clusters | retention | median turnover | p90 turnover | max raw share | source top share | median cost proxy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ["J0", "J1", "J2", "J3"]:
        item = report["book_metrics"][name]
        lines.append(
            "| {book} | {count} | {retention} | {median} | {p90} | {raw} | {source} | {cost} |".format(
                book=name,
                count=item["book_cluster_count"],
                retention=item["retention_vs_j0"],
                median=item["median_cluster_median_replay_turnover"],
                p90=item["p90_cluster_p90_replay_turnover"],
                raw=item["max_cluster_raw_pass_share"],
                source=item["source_lane_top_share"],
                cost=item["median_cost_proxy"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- J1 retention vs J0: `{report['book_metrics']['J1']['retention_vs_j0']}`.",
            f"- J1 p90 cluster turnover improves from `{report['book_metrics']['J0']['p90_cluster_p90_replay_turnover']}` to `{report['book_metrics']['J1']['p90_cluster_p90_replay_turnover']}`.",
            f"- J2 p90 cluster turnover is `{report['book_metrics']['J2']['p90_cluster_p90_replay_turnover']}` with source top share `{report['book_metrics']['J2']['source_lane_top_share']}`.",
            "- J3 is diagnostic only because liquidity/capacity proxy coverage is not available in the Phase3I strict-row artifact.",
            "",
            "## Bias / Promotion Scope",
            "",
            "- Cost and turnover are present.",
            "- Capacity/liquidity is missing, so no book is production-promotion grade.",
            "- `new_vs_149` is not asserted until a full 149 registry mapping is available.",
            "- Result supports post-discovery cluster filtering, not live deployment.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("reports/phase3i_official_s43_s46_v2_20260516/phase3I_official_global_clustered_rows.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/phase3j_cluster_book_filter_audit_20260516"))
    parser.add_argument("--arm", default="i0")
    parser.add_argument("--turnover-max", type=float, default=0.75)
    args = parser.parse_args()

    payload = _read_json(args.input)
    rows = payload.get("strict_rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise TypeError(f"expected strict row list in {args.input}")
    records = _cluster_records(rows, arm=args.arm, turnover_max=args.turnover_max)
    books = _build_books(records)
    metrics = {name: _book_metrics(name, book_rows, baseline_count=len(books["J0"])) for name, book_rows in books.items()}
    feature_coverage = _feature_coverage([row for row in rows if str(row.get("phase3i_arm_short")) == args.arm])
    j1 = metrics["J1"]
    j0 = metrics["J0"]
    j1_retention_ok = 0.60 <= float(j1["retention_vs_j0"] or 0.0) <= 0.80
    j1_turnover_ok = (j1["p90_cluster_p90_replay_turnover"] or 999.0) < (j0["p90_cluster_p90_replay_turnover"] or -999.0)
    decision = "PASS_CLUSTER_LEVEL_FILTER_DIRECTION" if j1_retention_ok and j1_turnover_ok else "HOLD_CLUSTER_LEVEL_FILTER_DIRECTION"
    report = {
        "created_at": utc_now_iso(),
        "status": "completed",
        "decision": decision,
        "input": str(args.input),
        "arm": args.arm,
        "objective": "Audit whether deployment hardening should move from candidate pre-filtering to cluster-level book filtering.",
        "book_definitions": {
            "J0": "All I0/G2 deployable clusters from Phase3I official global aggregate.",
            "J1": "Low-turnover book: keep clusters with p90 replay turnover <= J0 70th percentile.",
            "J2": "Balanced book: J1 plus source-lane and raw-cluster concentration controls.",
            "J3": "Diagnostic cost-proxy fallback; not true capacity/liquidity because those proxies are unavailable.",
        },
        "feature_coverage": feature_coverage,
        "cluster_count": len(records),
        "book_metrics": metrics,
        "bias_audit": {
            "lookahead": "no new features or labels computed; no-run posthoc audit over completed strict rows",
            "costs": "10bps replay cost present in source rows",
            "turnover": "strict and replay turnover present",
            "capacity_liquidity": "missing; J3 blocked from promotion-grade use",
            "discovery_vs_deployment": "supports cluster-level deployment filtering after G2 discovery, not candidate-level search promotion",
            "decision": "HOLD_RESEARCH_FOR_PRODUCTION_BOOK",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(args.output_dir / "phase3j_cluster_book_filter_audit.json", report)
    _write_cluster_csv(args.output_dir / "phase3j_cluster_metrics.csv", records)
    for name, book_rows in books.items():
        _write_cluster_csv(args.output_dir / f"phase3j_book_{name.lower()}_clusters.csv", book_rows)
    (args.output_dir / "PHASE3J_CLUSTER_BOOK_FILTER_AUDIT_2026-05-16.md").write_text(_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
