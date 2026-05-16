"""Freeze Phase3L daily proof survivor book.

This takes the Phase3L-J globally reclustered survivor rows and keeps one
representative per global signal cluster. It is a daily evidence artifact, not
a production deployment claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GLOBAL_RESULTS = Path("reports/phase3l_j_survivor_global_recluster_20260517/phase3l_j_survivor_global_results.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_k_daily_proof_book_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _quantile(values: list[float], q: float) -> float | None:
    values = sorted(value for value in values if math.isfinite(value))
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[int(pos)]
    return values[lo] * (hi - pos) + values[hi] * (pos - lo)


def _best_per_cluster(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("decision") != "GLOBAL_DAILY_PASS_EX_REGIME":
            continue
        cluster = str(row.get("global_signal_cluster_id") or "")
        if not cluster:
            continue
        item: dict[str, Any] = dict(row)
        item["score_float"] = _safe_float(row.get("score"), -1e18)
        item["turnover_float"] = _safe_float(row.get("turnover"))
        old = best.get(cluster)
        if old is None or (item["score_float"] or -1e18) > (_safe_float(old.get("score_float"), -1e18) or -1e18):
            best[cluster] = item
    return sorted(best.values(), key=lambda row: (_safe_float(row.get("score_float"), -1e18) or -1e18), reverse=True)


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "unknown") for row in rows).items()))


def _render_markdown(summary: dict[str, Any], book: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3L-K Daily Proof Book Freeze",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- book_cluster_count: {summary['book_cluster_count']}",
        f"- median_turnover: {summary['median_turnover']}",
        f"- p90_turnover: {summary['p90_turnover']}",
        f"- source_lane_top_share: {summary['source_lane_top_share']}",
        f"- sign_flip_pass_count: {summary['sign_flip_pass_count']}",
        "",
        "## Interpretation",
        "",
        "- This is a daily strong proof book, ex-regime and ex-minute-execution.",
        "- One representative is kept per global survivor signal cluster.",
        "- This should not be described as production-ready or capacity validated.",
        "",
        "## Book",
        "",
        "| global_cluster | source_cluster | type | score | turnover | source_lane | expression |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in book:
        expr = str(row.get("expression") or "")
        if len(expr) > 120:
            expr = expr[:117] + "..."
        lines.append(
            "| {global_signal_cluster_id} | {source_cluster_id} | {entry_type} | {score} | {turnover} | {source_lane} | `{expr}` |".format(
                expr=expr,
                **row,
            )
        )
    lines.append("")
    return "\n".join(lines)


def run(*, global_results: Path, output_root: Path, cluster_gate: int) -> dict[str, Any]:
    rows = _read_csv(global_results)
    book = _best_per_cluster(rows)
    turnovers = [value for value in (_safe_float(row.get("turnover")) for row in book) if value is not None]
    source_counts = _distribution(book, "source_lane")
    top_source_count = max(source_counts.values()) if source_counts else 0
    sign_flip_pass_count = sum(str(row.get("sign_flip_non_gap_or_deployable_passed")).lower() == "true" for row in book)
    source_lane_top_share = top_source_count / max(1, len(book))
    decision = (
        "PASS_PHASE3L_K_DAILY_STRONG_PROOF_BOOK_EX_REGIME"
        if len(book) >= cluster_gate and sign_flip_pass_count == 0
        else "HOLD_PHASE3L_K_DAILY_PROOF_BOOK_INSUFFICIENT"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_k_daily_proof_book_freeze",
        "decision": decision,
        "input": {
            "global_results": str(global_results),
            "sha256": _sha256(global_results),
        },
        "cluster_gate": cluster_gate,
        "input_pass_row_count": sum(1 for row in rows if row.get("decision") == "GLOBAL_DAILY_PASS_EX_REGIME"),
        "book_cluster_count": len(book),
        "full_formula_survivor_count": sum(1 for row in book if row.get("entry_type") == "full_formula_survivor"),
        "low_order_rescue_count": sum(1 for row in book if row.get("entry_type") == "low_order_rescue"),
        "median_turnover": round(_quantile(turnovers, 0.5), 6) if turnovers else None,
        "p90_turnover": round(_quantile(turnovers, 0.9), 6) if turnovers else None,
        "max_turnover": round(max(turnovers), 6) if turnovers else None,
        "min_score": round(min((_safe_float(row.get("score")) or 0.0) for row in book), 6) if book else None,
        "median_score": round(_quantile([_safe_float(row.get("score")) or 0.0 for row in book], 0.5), 6) if book else None,
        "source_distribution": source_counts,
        "source_lane_top_share": round(source_lane_top_share, 6),
        "sign_flip_pass_count": sign_flip_pass_count,
        "remaining_blockers": [
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
            "live_execution_not_confirmed",
        ],
        "scope": "daily_validated_ex_regime_alpha_cluster_proof_pack",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_daily_strong_proof_book.csv", book)
    _write_json(output_root / "phase3l_daily_proof_book_report.json", {"summary": summary, "book": book})
    (output_root / "PHASE3L_K_DAILY_PROOF_BOOK_FREEZE_2026-05-17.md").write_text(
        _render_markdown(summary, book),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--global-results", type=Path, default=DEFAULT_GLOBAL_RESULTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--cluster-gate", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(global_results=args.global_results, output_root=args.output_root, cluster_gate=args.cluster_gate)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
