"""Audit Phase3BF true-1min results for cross-shard robustness.

This is a research-only audit. It consumes Phase3AS chunk outputs and writes
candidate x horizon stability tables. It does not modify X0/R3.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_HERE = Path(__file__).resolve()
REPO = _HERE.parents[3] if len(_HERE.parents) > 3 else Path.cwd()
DEFAULT_RUN_ROOT = Path("runtime/phase3bf_company_ba_exploit_fresh_20260613")
DEFAULT_REPORT_ROOT = Path("reports/phase3bg_bf_robust_audit_20260614")
SUMMARY_NAME = "phase3as_true_1min_sidecar_canary_eval_summary.json"
ROWS_NAME = "phase3as_true_1min_sidecar_canary_eval_rows.csv"


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    value = _safe_float(value)
    return int(value) if value is not None else 0


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _std(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) >= 2 else None


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


def _chunk_meta(path: Path) -> tuple[str, str]:
    match = re.search(r"shard_(\d+)_chunk_(\d+)", path.parent.name)
    if not match:
        return "", ""
    return f"shard_{int(match.group(1)):02d}", f"chunk_{int(match.group(2)):02d}"


def _read_rows(run_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(run_root.glob(f"shard_*_chunk_*_as_v1/{SUMMARY_NAME}")):
        shard, chunk = _chunk_meta(summary_path)
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        rows_path = summary_path.parent / ROWS_NAME
        attempts.append(
            {
                "shard": shard,
                "chunk": chunk,
                "evaluated_candidate_count": summary.get("evaluated_candidate_count", 0),
                "error_count": summary.get("error_count", 0),
                "memory_hit_count": summary.get("memory_hit_count", 0),
                "rows_exists": rows_path.exists(),
            }
        )
        if not rows_path.exists():
            continue
        with rows_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                row = dict(raw)
                row["shard"] = shard
                row["chunk"] = chunk
                rows.append(row)
    return attempts, rows


def _audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        horizon = str(row.get("horizon_min") or "")
        if candidate_id and horizon:
            grouped[(candidate_id, horizon)].append(row)

    output: list[dict[str, Any]] = []
    for (candidate_id, horizon), values in grouped.items():
        best = values[0]
        shards = sorted({str(v.get("shard") or "") for v in values if v.get("shard")})
        spread_t = [x for x in (_safe_float(v.get("spread_t")) for v in values) if x is not None]
        spread_mean = [x for x in (_safe_float(v.get("spread_mean")) for v in values) if x is not None]
        hit_rate = [x for x in (_safe_float(v.get("spread_hit_rate")) for v in values) if x is not None]
        ic_abs = [x for x in (_safe_float(v.get("ic_abs_mean")) for v in values) if x is not None]
        ic_mean = [x for x in (_safe_float(v.get("ic_mean")) for v in values) if x is not None]
        ic_count = [x for x in (_safe_float(v.get("ic_count")) for v in values) if x is not None]
        pos_spread_t = sum(1 for x in spread_t if x > 0)
        pos_ic = sum(1 for x in ic_mean if x > 0)
        mean_spread_t = _mean(spread_t)
        std_spread_t = _std(spread_t)
        mean_ic_abs = _mean(ic_abs)
        stability_score = None
        if mean_spread_t is not None and std_spread_t is not None and mean_ic_abs is not None:
            stability_score = mean_spread_t / (1.0 + std_spread_t) + mean_ic_abs
        elif mean_spread_t is not None and mean_ic_abs is not None:
            stability_score = mean_spread_t + mean_ic_abs
        output.append(
            {
                "candidate_id": candidate_id,
                "horizon_min": horizon,
                "source_lane": best.get("source_lane", ""),
                "factor_lane": best.get("factor_lane", ""),
                "fields": best.get("fields", ""),
                "expression_hash": best.get("expression_hash", ""),
                "expression": best.get("expression", ""),
                "shard_coverage": len(shards),
                "row_count": len(values),
                "mean_spread_t": mean_spread_t,
                "std_spread_t": std_spread_t,
                "min_spread_t": min(spread_t) if spread_t else None,
                "positive_spread_t_ratio": pos_spread_t / len(spread_t) if spread_t else None,
                "mean_spread_mean": _mean(spread_mean),
                "mean_hit_rate": _mean(hit_rate),
                "mean_ic_abs": mean_ic_abs,
                "mean_ic_mean": _mean(ic_mean),
                "positive_ic_ratio": pos_ic / len(ic_mean) if ic_mean else None,
                "mean_ic_count": _mean(ic_count),
                "stability_score": stability_score,
                "shards": "|".join(shards),
            }
        )
    return sorted(
        output,
        key=lambda r: (
            _safe_int(r.get("shard_coverage")),
            _safe_float(r.get("positive_spread_t_ratio")) or -1,
            _safe_float(r.get("stability_score")) or -999,
            _safe_float(r.get("mean_spread_t")) or -999,
        ),
        reverse=True,
    )


def _lane_summary(audited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in audited:
        grouped[(str(row.get("source_lane") or ""), str(row.get("factor_lane") or ""))].append(row)
    output: list[dict[str, Any]] = []
    for (source_lane, factor_lane), values in grouped.items():
        stable = [
            row
            for row in values
            if _safe_int(row.get("shard_coverage")) >= 16
            and (_safe_float(row.get("positive_spread_t_ratio")) or 0.0) >= 0.75
        ]
        output.append(
            {
                "source_lane": source_lane,
                "factor_lane": factor_lane,
                "candidate_horizon_rows": len(values),
                "stable_rows": len(stable),
                "unique_candidates": len({row.get("candidate_id") for row in values}),
                "mean_stability_score": _mean([x for x in (_safe_float(row.get("stability_score")) for row in values) if x is not None]),
                "stable_mean_spread_t": _mean([x for x in (_safe_float(row.get("mean_spread_t")) for row in stable) if x is not None]),
                "best_candidate": values[0].get("candidate_id", "") if values else "",
            }
        )
    return sorted(output, key=lambda r: (_safe_int(r.get("stable_rows")), _safe_float(r.get("stable_mean_spread_t")) or -999), reverse=True)


def _render(summary: dict[str, Any], top_rows: list[dict[str, Any]], lane_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BG BF Robust Audit",
        "",
        f"decision: `{summary['decision']}`",
        "",
        f"- completed chunks: `{summary['completed_chunks']} / {summary['expected_chunks']}`",
        f"- raw result rows: `{summary['raw_result_rows']}`",
        f"- audited candidate-horizon rows: `{summary['audited_rows']}`",
        f"- stable rows: `{summary['stable_rows']}`",
        "",
        "## Guardrails",
        "",
        "- Input is Phase3BF true 1min shard output with real `trade_time`.",
        "- This is robustness triage, not promotion evidence.",
        "- X0/R3 remains read-only.",
        "",
        "## Lane Summary",
        "",
        "| source | factor lane | rows | stable | best | stable mean spread t |",
        "|---|---|---:|---:|---|---:|",
    ]
    for row in lane_rows[:20]:
        lines.append(
            f"| `{row.get('source_lane','')}` | `{row.get('factor_lane','')}` | {row.get('candidate_horizon_rows','')} | "
            f"{row.get('stable_rows','')} | `{row.get('best_candidate','')}` | {float(row.get('stable_mean_spread_t') or 0):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Robust Top",
            "",
            "| rank | candidate | h | source | factor | pos spread ratio | mean spread t | mean IC abs | score |",
            "|---:|---|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for idx, row in enumerate(top_rows[:30], start=1):
        lines.append(
            f"| {idx} | `{row.get('candidate_id','')}` | {row.get('horizon_min','')} | `{row.get('source_lane','')}` | "
            f"`{row.get('factor_lane','')}` | {float(row.get('positive_spread_t_ratio') or 0):.3f} | "
            f"{float(row.get('mean_spread_t') or 0):.6f} | {float(row.get('mean_ic_abs') or 0):.6f} | "
            f"{float(row.get('stability_score') or 0):.6f} |"
        )
    return "\n".join(lines) + "\n"


def build_audit(*, run_root: Path, report_root: Path) -> dict[str, Any]:
    run_root = _resolve(run_root)
    report_root = _resolve(report_root)
    attempts, rows = _read_rows(run_root)
    audited = _audit_rows(rows)
    lane_rows = _lane_summary(audited)
    stable_rows = [
        row
        for row in audited
        if _safe_int(row.get("shard_coverage")) >= 16
        and (_safe_float(row.get("positive_spread_t_ratio")) or 0.0) >= 0.75
    ]
    top_rows = sorted(stable_rows, key=lambda r: (_safe_float(r.get("stability_score")) or -999), reverse=True)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BG_BF_ROBUST_AUDIT_COMPLETE_HOLD_RESEARCH",
        "run_root": str(run_root),
        "report_root": str(report_root),
        "expected_chunks": 128,
        "completed_chunks": len(attempts),
        "raw_result_rows": len(rows),
        "audited_rows": len(audited),
        "stable_rows": len(stable_rows),
        "source_lane_counts": dict(Counter(str(row.get("source_lane") or "") for row in rows)),
        "hard_rules": ["true_1min_only", "x0_r3_read_only", "robust_audit_not_alpha_proof"],
    }
    report_root.mkdir(parents=True, exist_ok=True)
    _write_json(report_root / "phase3bg_bf_robust_audit_summary.json", summary)
    _write_csv(report_root / "phase3bg_bf_robust_audit_by_candidate_horizon.csv", audited)
    _write_csv(report_root / "phase3bg_bf_robust_top.csv", top_rows)
    _write_csv(report_root / "phase3bg_bf_lane_summary.csv", lane_rows)
    (report_root / "PHASE3BG_BF_ROBUST_AUDIT_20260614.md").write_text(_render(summary, top_rows, lane_rows), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    print(json.dumps(build_audit(run_root=args.run_root, report_root=args.report_root), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
