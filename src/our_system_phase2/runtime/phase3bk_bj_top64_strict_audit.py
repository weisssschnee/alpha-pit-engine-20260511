"""Audit Phase3BJ top64 before any deeper true-1min replay.

Phase3BJ already evaluated the broad surrogate pack across 16 true-1min shards.
This module consumes the aggregate audit, verifies the top64 shortlist against
search memory and expression crowding, and produces a Phase3BK candidate ledger.

It deliberately does not claim final signal-vector novelty: Phase3BJ did not
persist per-minute signal vectors, so this stage only performs metric-vector
clustering plus exact memory checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_BJ_AUDIT_ROOT = Path("reports/phase3bj_company_large_1min_surrogate_20260614_aggregate_audit")
DEFAULT_MEMORY_ROOT = Path("runtime/search_memory")
DEFAULT_REPORT_ROOT = Path("reports/phase3bk_bj_top64_strict_audit_20260615")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _fmt(row.get(key, "")) for key in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.10g}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def _f(value: Any, default: float = float("nan")) -> float:
    try:
        if value in (None, ""):
            return default
        out = float(value)
        return out if math.isfinite(out) else default
    except Exception:
        return default


def _b(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _load_memory(memory_root: Path) -> tuple[set[str], set[str]]:
    expr_hashes: set[str] = set()
    keys: set[str] = set()
    if not memory_root.exists():
        return expr_hashes, keys
    paths = sorted(memory_root.rglob("phase3aj_search_memory_ledger.json"))
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        entries = payload.get("memory_entries") if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            expr_hash = str(entry.get("expression_hash") or "")
            key = str(entry.get("search_memory_key") or "")
            if expr_hash:
                expr_hashes.add(expr_hash)
            if key:
                keys.add(key)
    return expr_hashes, keys


def _expr_family(expression: str) -> str:
    expr = re.sub(r"\s+", "", expression or "")
    expr = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", "$FIELD", expr)
    expr = re.sub(r"\b\d+(?:\.\d+)?\b", "N", expr)
    return _stable_hash(expr)


def _ops_signature(expression: str) -> str:
    ops = re.findall(r"\b[A-Za-z][A-Za-z0-9_]*(?=\()", expression or "")
    return ">".join(ops[:16])


def _vectorize(rows_by_hash: dict[str, list[dict[str, str]]], expr_hash: str) -> list[float]:
    rows = rows_by_hash.get(expr_hash, [])
    by_h = {int(_f(row.get("horizon_min"), 0)): row for row in rows}
    vec: list[float] = []
    for horizon in (1, 5, 15, 30):
        row = by_h.get(horizon, {})
        vec.extend(
            [
                _f(row.get("ic_mean_median"), 0.0),
                _f(row.get("ic_abs_mean_mean"), 0.0),
                _f(row.get("spread_mean_mean"), 0.0) * 1000.0,
                _f(row.get("ic_direction_share"), 0.0),
            ]
        )
    return vec


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _cluster_metric_vectors(rows: list[dict[str, Any]], threshold: float = 0.94) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for row in rows:
        vector = row["_metric_vector"]
        placed = False
        for cluster in clusters:
            if _cosine(vector, cluster["_centroid"]) >= threshold:
                cluster["members"].append(row["expression_hash"])
                n = len(cluster["members"])
                cluster["_centroid"] = [(old * (n - 1) + new) / n for old, new in zip(cluster["_centroid"], vector)]
                cluster["best_score"] = max(cluster["best_score"], row["max_directional_robust_score"])
                placed = True
                break
        if not placed:
            clusters.append(
                {
                    "metric_cluster_id": f"bk_metric_{len(clusters) + 1:03d}",
                    "members": [row["expression_hash"]],
                    "best_score": row["max_directional_robust_score"],
                    "_centroid": list(vector),
                }
            )
    for cluster in clusters:
        cluster["member_count"] = len(cluster["members"])
        cluster["member_hashes"] = "|".join(cluster["members"])
        del cluster["_centroid"]
    return clusters


def _build_candidate_rows(shortlist: list[dict[str, str]], aggregate: list[dict[str, str]], memory_exprs: set[str], memory_keys: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in aggregate:
        rows_by_hash[row.get("expression_hash") or ""].append(row)

    out: list[dict[str, Any]] = []
    for rank, row in enumerate(shortlist, 1):
        expr_hash = row.get("expression_hash") or ""
        all_h = rows_by_hash.get(expr_hash, [])
        best_h = max(all_h, key=lambda item: _f(item.get("directional_robust_score"), -999), default=row)
        scores = [_f(item.get("directional_robust_score"), float("nan")) for item in all_h]
        dir_shares = [_f(item.get("ic_direction_share"), float("nan")) for item in all_h]
        expressions = [item.get("expression") or "" for item in all_h if item.get("expression")]
        expression = expressions[0] if expressions else row.get("expression", "")
        family = _expr_family(expression)
        search_key = f"phase3bj_large_1min:{expr_hash}"
        exact_memory_hit = expr_hash in memory_exprs or search_key in memory_keys
        max_score = max((x for x in scores if not math.isnan(x)), default=float("nan"))
        mean_score = sum(x for x in scores if not math.isnan(x)) / max(1, len([x for x in scores if not math.isnan(x)]))
        min_dir = min((x for x in dir_shares if not math.isnan(x)), default=float("nan"))
        horizon_pass = sum(1 for item in all_h if _f(item.get("directional_robust_score"), 0.0) >= 0.03 and _f(item.get("ic_direction_share"), 0.0) >= 0.75)
        tier = "reject"
        if not exact_memory_hit and max_score >= 0.055 and horizon_pass >= 1 and min_dir >= 0.75:
            tier = "bk_replay_priority"
        elif not exact_memory_hit and max_score >= 0.04 and horizon_pass >= 1:
            tier = "bk_watchlist"
        out.append(
            {
                "phase3bk_rank": rank,
                "phase3bj_rank_unique_expression": row.get("phase3bj_rank_unique_expression", rank),
                "decision_tier": tier,
                "expression_hash": expr_hash,
                "candidate_ids": row.get("candidate_ids", ""),
                "best_horizon_min": best_h.get("horizon_min", row.get("horizon_min", "")),
                "factor_lane": row.get("factor_lane") or best_h.get("factor_lane", ""),
                "fields": row.get("fields") or best_h.get("fields", ""),
                "max_directional_robust_score": max_score,
                "mean_directional_robust_score": mean_score,
                "best_ic_mean_median": best_h.get("ic_mean_median", ""),
                "best_ic_direction_share": best_h.get("ic_direction_share", ""),
                "best_spread_mean": best_h.get("spread_mean_mean", ""),
                "horizon_pass_count": horizon_pass,
                "exact_memory_hit": exact_memory_hit,
                "memory_hit_any_in_bj": _b(row.get("memory_hit_any")) or _b(best_h.get("memory_hit_any")),
                "fresh_eligible_any": _b(row.get("fresh_eligible_any")) or _b(best_h.get("fresh_eligible_any")),
                "expression_family_hash": family,
                "ops_signature": _ops_signature(expression),
                "expression": expression,
                "_metric_vector": _vectorize(rows_by_hash, expr_hash),
            }
        )

    family_counts = Counter(item["expression_family_hash"] for item in out)
    ops_counts = Counter(item["ops_signature"] for item in out)
    for item in out:
        item["family_crowding_count"] = family_counts[item["expression_family_hash"]]
        item["ops_crowding_count"] = ops_counts[item["ops_signature"]]
        if item["decision_tier"] == "bk_replay_priority" and item["family_crowding_count"] >= 8:
            item["decision_tier"] = "bk_replay_priority_crowded_family"

    clusters = _cluster_metric_vectors(out)
    cluster_by_hash: dict[str, dict[str, Any]] = {}
    for cluster in clusters:
        for expr_hash in cluster["members"]:
            cluster_by_hash[expr_hash] = cluster
    for item in out:
        cluster = cluster_by_hash.get(item["expression_hash"], {})
        item["metric_cluster_id"] = cluster.get("metric_cluster_id", "")
        item["metric_cluster_size"] = cluster.get("member_count", 0)
        del item["_metric_vector"]

    out.sort(
        key=lambda item: (
            item["decision_tier"].startswith("bk_replay_priority"),
            _f(item["max_directional_robust_score"], -999),
            -int(item["family_crowding_count"]),
        ),
        reverse=True,
    )
    return out, clusters


def _summarize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_lane[str(row.get("factor_lane", ""))].append(row)
        by_field[str(row.get("fields", ""))].append(row)

    def summarize(grouped: dict[str, list[dict[str, Any]]], key: str) -> list[dict[str, Any]]:
        out = []
        for name, vals in grouped.items():
            priority = [v for v in vals if str(v.get("decision_tier", "")).startswith("bk_replay_priority")]
            out.append(
                {
                    key: name,
                    "count": len(vals),
                    "priority_count": len(priority),
                    "best_score": max((_f(v.get("max_directional_robust_score"), -999) for v in vals), default=float("nan")),
                    "mean_score": sum(_f(v.get("max_directional_robust_score"), 0.0) for v in vals) / len(vals),
                    "memory_hit_count": sum(1 for v in vals if v.get("exact_memory_hit")),
                }
            )
        out.sort(key=lambda row: (-int(row["priority_count"]), -_f(row["best_score"], -999)))
        return out

    return summarize(by_lane, "factor_lane"), summarize(by_field, "fields")


def _render_md(summary: dict[str, Any], rows: list[dict[str, Any]], lane_rows: list[dict[str, Any]]) -> str:
    top = rows[:20]
    lines = [
        "# Phase3BK BJ Top64 Strict Audit 2026-06-15",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Coverage",
        "",
        f"- shortlist candidates: `{summary['shortlist_count']}`",
        f"- aggregate expression-horizon rows: `{summary['aggregate_rows']}`",
        f"- exact search-memory hits: `{summary['exact_memory_hit_count']}`",
        f"- metric-vector clusters: `{summary['metric_cluster_count']}`",
        f"- replay priority rows: `{summary['replay_priority_count']}`",
        "",
        "## Boundary",
        "",
        "- This consumes Phase3BJ true-1min strict-eval outputs.",
        "- This is still diagnostic and does not modify X0/R3.",
        "- This stage performs metric-vector reclustering, not final signal-vector reclustering.",
        "- Final novelty requires materialized sampled signal vectors for selected candidates.",
        "",
        "## Top Phase3BK Candidates",
        "",
        "| rank | tier | h | factor | fields | score | dir | memory | family crowd | expression |",
        "|---:|---|---:|---|---|---:|---:|---|---:|---|",
    ]
    for idx, row in enumerate(top, 1):
        lines.append(
            f"| {idx} | `{row['decision_tier']}` | {row['best_horizon_min']} | `{row['factor_lane']}` | "
            f"`{row['fields']}` | {_f(row['max_directional_robust_score'], 0.0):.6g} | "
            f"{_f(row['best_ic_direction_share'], 0.0):.2f} | {row['exact_memory_hit']} | "
            f"{row['family_crowding_count']} | `{row['expression']}` |"
        )
    lines.extend(["", "## Factor Lane Summary", "", "| factor_lane | count | priority | best | mean | memory hits |", "|---|---:|---:|---:|---:|---:|"])
    for row in lane_rows:
        lines.append(
            f"| `{row['factor_lane']}` | {row['count']} | {row['priority_count']} | "
            f"{_f(row['best_score'], 0.0):.6g} | {_f(row['mean_score'], 0.0):.6g} | {row['memory_hit_count']} |"
        )
    lines.extend(
        [
            "",
            "## Next Gate",
            "",
            "Run Phase3BL/Phase3BK-signal materialization for the priority set only:",
            "",
            "1. materialize sampled per-minute signal vectors for priority candidates;",
            "2. compare against frozen 149 / existing minute survivor signal caches;",
            "3. rerun cost/turnover and wrong-lag checks;",
            "4. only then discuss challenger or overlay tests.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bj-audit-root", type=Path, default=DEFAULT_BJ_AUDIT_ROOT)
    parser.add_argument("--memory-root", type=Path, default=DEFAULT_MEMORY_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args(argv)

    bj_root = _resolve(args.bj_audit_root)
    memory_root = _resolve(args.memory_root)
    report_root = _resolve(args.report_root)

    shortlist_path = bj_root / "phase3bj_phase3bk_shortlist_top64.csv"
    aggregate_path = bj_root / "phase3bj_aggregate_by_expression_horizon.csv"
    if not shortlist_path.exists():
        raise FileNotFoundError(shortlist_path)
    if not aggregate_path.exists():
        raise FileNotFoundError(aggregate_path)

    shortlist = _read_csv(shortlist_path)
    aggregate = _read_csv(aggregate_path)
    memory_exprs, memory_keys = _load_memory(memory_root)
    candidate_rows, cluster_rows = _build_candidate_rows(shortlist, aggregate, memory_exprs, memory_keys)
    lane_rows, field_rows = _summarize(candidate_rows)

    priority_count = sum(1 for row in candidate_rows if str(row["decision_tier"]).startswith("bk_replay_priority"))
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BK_BJ_TOP64_STRICT_AUDIT_COMPLETE_DIAGNOSTIC_ONLY",
        "bj_audit_root": str(bj_root),
        "memory_root": str(memory_root),
        "report_root": str(report_root),
        "shortlist_count": len(shortlist),
        "aggregate_rows": len(aggregate),
        "memory_expr_hashes": len(memory_exprs),
        "memory_keys": len(memory_keys),
        "exact_memory_hit_count": sum(1 for row in candidate_rows if row["exact_memory_hit"]),
        "metric_cluster_count": len(cluster_rows),
        "replay_priority_count": priority_count,
        "watchlist_count": sum(1 for row in candidate_rows if row["decision_tier"] == "bk_watchlist"),
        "signal_vector_recluster_status": "NOT_DONE_REQUIRES_SIGNAL_MATERIALIZATION",
        "hard_boundary": [
            "metric-vector clustering is not final signal-vector novelty proof",
            "X0/R3 read-only",
            "no production or promotion decision",
        ],
    }

    fields = [
        "phase3bk_rank",
        "decision_tier",
        "expression_hash",
        "candidate_ids",
        "best_horizon_min",
        "factor_lane",
        "fields",
        "max_directional_robust_score",
        "mean_directional_robust_score",
        "best_ic_mean_median",
        "best_ic_direction_share",
        "best_spread_mean",
        "horizon_pass_count",
        "exact_memory_hit",
        "memory_hit_any_in_bj",
        "fresh_eligible_any",
        "family_crowding_count",
        "ops_crowding_count",
        "metric_cluster_id",
        "metric_cluster_size",
        "expression_family_hash",
        "ops_signature",
        "expression",
    ]
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "phase3bk_bj_top64_candidate_audit.csv", candidate_rows, fields)
    _write_csv(
        report_root / "phase3bk_metric_vector_clusters.csv",
        cluster_rows,
        ["metric_cluster_id", "member_count", "best_score", "member_hashes"],
    )
    _write_csv(
        report_root / "phase3bk_factor_lane_summary.csv",
        lane_rows,
        ["factor_lane", "count", "priority_count", "best_score", "mean_score", "memory_hit_count"],
    )
    _write_csv(
        report_root / "phase3bk_field_summary.csv",
        field_rows,
        ["fields", "count", "priority_count", "best_score", "mean_score", "memory_hit_count"],
    )
    _write_json(report_root / "phase3bk_bj_top64_strict_audit_summary.json", {**summary, "top_candidates": candidate_rows[:20]})
    (report_root / "PHASE3BK_BJ_TOP64_STRICT_AUDIT_20260615.md").write_text(
        _render_md(summary, candidate_rows, lane_rows),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "report_root": str(report_root), **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
