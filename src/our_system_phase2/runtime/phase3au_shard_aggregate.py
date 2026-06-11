"""Aggregate Phase3AU true-1min shard AS outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
DEFAULT_RUN_ROOT = Path("runtime/phase3au_company_full_true1min_sharded_20260611")
DEFAULT_REPORT_ROOT = Path("reports/phase3au_company_full_true1min_sharded_20260611")
SUMMARY_NAME = "phase3as_true_1min_sidecar_canary_eval_summary.json"
ROWS_NAME = "phase3as_true_1min_sidecar_canary_eval_rows.csv"
AGGREGATE_VERSION = "phase3au-shard-aggregate-v1-2026-06-11"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _shard_id(path: Path) -> str:
    match = re.search(r"shard_(\d+)", path.name)
    return f"shard_{int(match.group(1)):02d}" if match else path.name


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _iter_attempts(run_root: Path) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for summary_path in sorted(run_root.glob(f"shard_*/{SUMMARY_NAME}")):
        attempt_dir = summary_path.parent
        summary = _read_json(summary_path) or {}
        rows_path = attempt_dir / ROWS_NAME
        attempts.append(
            {
                "shard": _shard_id(attempt_dir),
                "attempt": attempt_dir.name,
                "attempt_dir": str(attempt_dir),
                "summary_path": str(summary_path),
                "rows_path": str(rows_path),
                "rows_exists": rows_path.exists(),
                "decision": summary.get("decision", ""),
                "error_count": summary.get("error_count", ""),
                "input_candidate_count": summary.get("input_candidate_count", ""),
                "evaluated_candidate_count": summary.get("evaluated_candidate_count", ""),
                "memory_hit_count": summary.get("memory_hit_count", ""),
                "panel_rows": summary.get("panel_rows", ""),
                "panel_codes": summary.get("panel_codes", ""),
                "evaluated_trade_time_count": summary.get("evaluated_trade_time_count", ""),
                "original_trade_time_count": summary.get("original_trade_time_count", ""),
                "panel_read_column_count": summary.get("panel_read_column_count", ""),
                "expression_field_count": summary.get("expression_field_count", ""),
                "lazy_sidecar_enabled": (summary.get("lazy_sidecar") or {}).get("enabled", ""),
                "lazy_loaded_field_count": len((summary.get("lazy_sidecar") or {}).get("loaded_fields") or []),
            }
        )
    return attempts


def _latest_attempts(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_shard: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        summary_path = Path(str(attempt["summary_path"]))
        mtime = summary_path.stat().st_mtime if summary_path.exists() else 0.0
        attempt["_mtime"] = mtime
        current = by_shard.get(str(attempt["shard"]))
        if current is None or mtime >= float(current.get("_mtime") or 0.0):
            by_shard[str(attempt["shard"])] = attempt
    return [by_shard[key] for key in sorted(by_shard)]


def _read_rows(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attempt in attempts:
        rows_path = Path(str(attempt["rows_path"]))
        if not rows_path.exists():
            continue
        with rows_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row = dict(raw)
                row["shard"] = attempt["shard"]
                row["attempt"] = attempt["attempt"]
                row["memory_hit"] = _safe_bool(row.get("memory_hit"))
                row["fresh_eligible"] = _safe_bool(row.get("fresh_eligible"))
                for key in [
                    "horizon_min",
                    "ic_mean",
                    "ic_abs_mean",
                    "ic_std",
                    "ic_t",
                    "ic_count",
                    "spread_mean",
                    "spread_abs_mean",
                    "spread_t",
                    "spread_count",
                    "spread_hit_rate",
                    "signal_nonnull",
                    "signal_unique",
                ]:
                    value = _safe_float(row.get(key))
                    row[key] = value
                rows.append(row)
    return rows


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _aggregate_by_expr(rows: list[dict[str, Any]], *, min_ic_count: int, fresh: bool | None) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if fresh is not None and bool(row.get("fresh_eligible")) is not fresh:
            continue
        ic_count = _safe_int(row.get("ic_count")) or 0
        if ic_count < min_ic_count:
            continue
        key = (str(row.get("expression_hash") or row.get("candidate_id") or ""), int(_safe_int(row.get("horizon_min")) or 0))
        if not key[0]:
            continue
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for (expr_hash, horizon), values in groups.items():
        abs_ics = [float(v["ic_abs_mean"]) for v in values if _safe_float(v.get("ic_abs_mean")) is not None]
        ic_means = [float(v["ic_mean"]) for v in values if _safe_float(v.get("ic_mean")) is not None]
        spreads = [float(v["spread_mean"]) for v in values if _safe_float(v.get("spread_mean")) is not None]
        counts = [_safe_int(v.get("ic_count")) or 0 for v in values]
        best = max(values, key=lambda v: (_safe_float(v.get("ic_abs_mean")) or -1.0, _safe_int(v.get("ic_count")) or 0))
        output.append(
            {
                "expression_hash": expr_hash,
                "candidate_id": best.get("candidate_id", ""),
                "horizon_min": horizon,
                "fields": best.get("fields", ""),
                "expression": best.get("expression", ""),
                "lane": best.get("lane", ""),
                "factor_lane": best.get("factor_lane", ""),
                "source_lane": best.get("source_lane", ""),
                "source_generator": best.get("source_generator", ""),
                "fresh_eligible": bool(best.get("fresh_eligible")),
                "memory_hit": bool(best.get("memory_hit")),
                "shard_coverage": len({str(v.get("shard")) for v in values}),
                "row_count": len(values),
                "mean_ic_abs_mean": _mean(abs_ics),
                "max_ic_abs_mean": max(abs_ics) if abs_ics else None,
                "mean_ic_mean": _mean(ic_means),
                "mean_ic_count": _mean([float(v) for v in counts]),
                "min_ic_count": min(counts) if counts else None,
                "mean_spread_mean": _mean(spreads),
                "shards": "|".join(sorted({str(v.get("shard")) for v in values})),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            int(row.get("shard_coverage") or 0),
            float(row.get("mean_ic_abs_mean") or -1.0),
            float(row.get("mean_ic_count") or -1.0),
        ),
        reverse=True,
    )


def _source_attribution(rows: list[dict[str, Any]], *, min_ic_count: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if (_safe_int(row.get("ic_count")) or 0) < min_ic_count:
            continue
        key = (
            str(row.get("lane") or ""),
            str(row.get("factor_lane") or ""),
            str(row.get("source_lane") or ""),
            "fresh" if row.get("fresh_eligible") else "memory_hit",
        )
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for key, values in groups.items():
        abs_ics = [float(v["ic_abs_mean"]) for v in values if _safe_float(v.get("ic_abs_mean")) is not None]
        candidates = {str(v.get("candidate_id") or "") for v in values if v.get("candidate_id")}
        exprs = {str(v.get("expression_hash") or "") for v in values if v.get("expression_hash")}
        shards = {str(v.get("shard") or "") for v in values if v.get("shard")}
        best = max(values, key=lambda v: (_safe_float(v.get("ic_abs_mean")) or -1.0, _safe_int(v.get("ic_count")) or 0))
        output.append(
            {
                "lane": key[0],
                "factor_lane": key[1],
                "source_lane": key[2],
                "fresh_bucket": key[3],
                "row_count": len(values),
                "unique_candidate_count": len(candidates),
                "unique_expression_count": len(exprs),
                "shard_coverage": len(shards),
                "mean_ic_abs_mean": _mean(abs_ics),
                "max_ic_abs_mean": max(abs_ics) if abs_ics else None,
                "top_candidate_id": best.get("candidate_id", ""),
                "top_fields": best.get("fields", ""),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            int(row.get("shard_coverage") or 0),
            float(row.get("mean_ic_abs_mean") or -1.0),
            int(row.get("unique_candidate_count") or 0),
        ),
        reverse=True,
    )


def _render_markdown(summary: dict[str, Any], fresh_top: list[dict[str, Any]], memory_top: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3AU True 1min Shard Aggregate",
        "",
        f"decision: `{summary['decision']}`",
        "",
        f"- generated_at: `{summary['created_at']}`",
        f"- version: `{summary['version']}`",
        f"- completed shards: `{summary['completed_shards']}`",
        f"- attempt count: `{summary['attempt_count']}`",
        f"- candidate rows: `{summary['candidate_result_rows']}`",
        f"- unique candidates: `{summary['unique_candidate_count']}`",
        f"- unique expressions: `{summary['unique_expression_count']}`",
        f"- robust min ic_count: `{summary['robust_min_ic_count']}`",
        "",
        "## Interpretation",
        "",
        "- This aggregate uses true `trade_time` 1min shard outputs only.",
        "- Search-memory hits and fresh structures are separated.",
        "- This is cross-shard smoke evidence, not alpha proof and not X0/R3 promotion evidence.",
        "",
        "## Fresh Robust Top",
        "",
        "| rank | candidate | horizon | shards | mean abs IC | fields |",
        "|---:|---|---:|---:|---:|---|",
    ]
    for idx, row in enumerate(fresh_top[:20], start=1):
        lines.append(
            "| {rank} | `{candidate}` | {horizon} | {shards} | {ic:.6f} | `{fields}` |".format(
                rank=idx,
                candidate=row.get("candidate_id", ""),
                horizon=row.get("horizon_min", ""),
                shards=row.get("shard_coverage", ""),
                ic=float(row.get("mean_ic_abs_mean") or 0.0),
                fields=row.get("fields", ""),
            )
        )
    lines.extend(["", "## Memory-Hit Robust Top", "", "| rank | candidate | horizon | shards | mean abs IC | fields |", "|---:|---|---:|---:|---:|---|"])
    for idx, row in enumerate(memory_top[:20], start=1):
        lines.append(
            "| {rank} | `{candidate}` | {horizon} | {shards} | {ic:.6f} | `{fields}` |".format(
                rank=idx,
                candidate=row.get("candidate_id", ""),
                horizon=row.get("horizon_min", ""),
                shards=row.get("shard_coverage", ""),
                ic=float(row.get("mean_ic_abs_mean") or 0.0),
                fields=row.get("fields", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- summary JSON: `{summary['paths']['summary_json']}`",
            f"- attempt status CSV: `{summary['paths']['attempt_status_csv']}`",
            f"- fresh top CSV: `{summary['paths']['fresh_top_csv']}`",
            f"- memory-hit top CSV: `{summary['paths']['memory_top_csv']}`",
            f"- source attribution CSV: `{summary['paths']['source_attribution_csv']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_aggregate(*, run_root: Path, report_root: Path, min_ic_count: int) -> dict[str, Any]:
    run_root = _resolve(run_root)
    report_root = _resolve(report_root)
    attempts = _iter_attempts(run_root)
    latest_attempts = _latest_attempts(attempts)
    rows = _read_rows(latest_attempts)
    fresh_top = _aggregate_by_expr(rows, min_ic_count=min_ic_count, fresh=True)
    memory_top = _aggregate_by_expr(rows, min_ic_count=min_ic_count, fresh=False)
    source_rows = _source_attribution(rows, min_ic_count=min_ic_count)

    paths = {
        "summary_json": str(report_root / "phase3au_true1min_shard_aggregate_summary.json"),
        "attempt_status_csv": str(report_root / "phase3au_true1min_shard_attempt_status.csv"),
        "fresh_top_csv": str(report_root / "phase3au_true1min_shard_fresh_top.csv"),
        "memory_top_csv": str(report_root / "phase3au_true1min_shard_memory_hit_top.csv"),
        "source_attribution_csv": str(report_root / "phase3au_true1min_shard_source_attribution.csv"),
        "markdown": str(report_root / "PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md"),
    }
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": AGGREGATE_VERSION,
        "decision": "PHASE3AU_TRUE1MIN_SHARDS_AGGREGATED_HOLD_RESEARCH",
        "run_root": str(run_root),
        "report_root": str(report_root),
        "attempt_count": len(attempts),
        "completed_shards": sorted({str(attempt.get("shard")) for attempt in latest_attempts if attempt.get("rows_exists")}),
        "candidate_result_rows": len(rows),
        "unique_candidate_count": len({str(row.get("candidate_id") or "") for row in rows if row.get("candidate_id")}),
        "unique_expression_count": len({str(row.get("expression_hash") or "") for row in rows if row.get("expression_hash")}),
        "fresh_result_rows": sum(1 for row in rows if row.get("fresh_eligible")),
        "memory_hit_result_rows": sum(1 for row in rows if row.get("memory_hit")),
        "fresh_top_count": len(fresh_top),
        "memory_top_count": len(memory_top),
        "robust_min_ic_count": min_ic_count,
        "paths": paths,
        "hard_rules": [
            "true 1min means actual trade_time cross-section",
            "memory_hit rows are separated from fresh rows",
            "aggregate is not alpha proof and cannot modify X0/R3",
        ],
    }
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "phase3au_true1min_shard_attempt_status.csv", attempts)
    top_fields = [
        "expression_hash",
        "candidate_id",
        "horizon_min",
        "fields",
        "lane",
        "factor_lane",
        "source_lane",
        "source_generator",
        "fresh_eligible",
        "memory_hit",
        "shard_coverage",
        "row_count",
        "mean_ic_abs_mean",
        "max_ic_abs_mean",
        "mean_ic_mean",
        "mean_ic_count",
        "min_ic_count",
        "mean_spread_mean",
        "shards",
        "expression",
    ]
    _write_csv(report_root / "phase3au_true1min_shard_fresh_top.csv", fresh_top, top_fields)
    _write_csv(report_root / "phase3au_true1min_shard_memory_hit_top.csv", memory_top, top_fields)
    _write_csv(report_root / "phase3au_true1min_shard_source_attribution.csv", source_rows)
    _write_json(report_root / "phase3au_true1min_shard_aggregate_summary.json", {"summary": summary})
    (report_root / "PHASE3AU_TRUE1MIN_SHARD_AGGREGATE_20260611.md").write_text(
        _render_markdown(summary, fresh_top, memory_top),
        encoding="utf-8",
    )
    return {"summary": summary, "fresh_top": fresh_top[:20], "memory_top": memory_top[:20]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--min-ic-count", type=int, default=20)
    args = parser.parse_args()
    result = build_aggregate(run_root=args.run_root, report_root=args.report_root, min_ic_count=args.min_ic_count)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
