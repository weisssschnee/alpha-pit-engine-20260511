"""Audit Phase3BA true-1min candidate stability and parent-family strength."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
ROWS_NAME = "phase3as_true_1min_sidecar_canary_eval_rows.csv"
DEFAULT_RUN_ROOT = Path("runtime/phase3ba_company_focused_minute_expansion_20260612")
DEFAULT_REPORT_ROOT = Path("reports/phase3ba_stability_parent_audit_20260613")
DEFAULT_AX_TOP = Path("reports/phase3ax_company_capacity_flow_refinement_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_AZB_TOP = Path("reports/phase3azb_company_opening_window_corrected_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")
DEFAULT_AY_TOP = Path("reports/phase3ay_company_x0_minute_transfer_aggregate_20260612/phase3au_true1min_shard_fresh_top.csv")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    value_float = _safe_float(value)
    return int(value_float) if value_float is not None else 0


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _std(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) > 1 else 0.0 if values else None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_shard_rows(run_root: Path) -> list[dict[str, Any]]:
    run_root = _resolve(run_root)
    rows: list[dict[str, Any]] = []
    for shard_dir in sorted(run_root.glob("shard_??_as_v*")):
        rows_path = shard_dir / ROWS_NAME
        if not rows_path.exists():
            continue
        shard = shard_dir.name.split("_as_", 1)[0]
        with rows_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                row: dict[str, Any] = dict(raw)
                row["shard"] = shard
                rows.append(row)
    return rows


def _parent_summary(path: Path, label: str) -> dict[str, Any]:
    rows = _read_csv(path)
    vals = [_safe_float(row.get("mean_ic_abs_mean")) for row in rows]
    vals = [value for value in vals if value is not None]
    top = rows[0] if rows else {}
    return {
        "label": label,
        "path": str(_resolve(path)),
        "row_count": len(rows),
        "top_candidate_id": top.get("candidate_id", ""),
        "top_factor_lane": top.get("factor_lane", ""),
        "top_mean_ic_abs_mean": _safe_float(top.get("mean_ic_abs_mean")),
        "mean_top200_ic_abs_mean": _mean(vals[:200]),
    }


def _candidate_stability(rows: list[dict[str, Any]], *, min_ic_count: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _safe_int(row.get("ic_count")) < min_ic_count:
            continue
        candidate_id = str(row.get("candidate_id") or "")
        horizon = _safe_int(row.get("horizon_min"))
        if candidate_id and horizon:
            groups[(candidate_id, horizon)].append(row)

    out: list[dict[str, Any]] = []
    for (candidate_id, horizon), values in groups.items():
        abs_ics = [float(v) for v in (_safe_float(row.get("ic_abs_mean")) for row in values) if v is not None]
        signed = [float(v) for v in (_safe_float(row.get("ic_mean")) for row in values) if v is not None]
        counts = [_safe_int(row.get("ic_count")) for row in values]
        first = values[0]
        positive = sum(1 for value in signed if value > 0)
        negative = sum(1 for value in signed if value < 0)
        dominant_sign = "positive" if positive >= negative else "negative"
        sign_consistency = max(positive, negative) / len(signed) if signed else 0.0
        mean_abs = _mean(abs_ics) or 0.0
        std_abs = _std(abs_ics) or 0.0
        stability_score = mean_abs * sign_consistency * (1.0 / (1.0 + std_abs))
        out.append(
            {
                "candidate_id": candidate_id,
                "horizon_min": horizon,
                "factor_lane": first.get("factor_lane", ""),
                "fields": first.get("fields", ""),
                "expression_hash": first.get("expression_hash", ""),
                "shard_coverage": len({str(row.get("shard")) for row in values}),
                "mean_ic_abs_mean": mean_abs,
                "std_ic_abs_mean": std_abs,
                "min_ic_abs_mean": min(abs_ics) if abs_ics else None,
                "max_ic_abs_mean": max(abs_ics) if abs_ics else None,
                "mean_ic_mean": _mean(signed),
                "dominant_sign": dominant_sign,
                "sign_consistency": sign_consistency,
                "mean_ic_count": _mean([float(value) for value in counts]),
                "min_ic_count": min(counts) if counts else None,
                "stability_score": stability_score,
                "expression": first.get("expression", ""),
            }
        )
    return sorted(
        out,
        key=lambda row: (
            int(row.get("shard_coverage") or 0),
            float(row.get("stability_score") or -1.0),
            float(row.get("mean_ic_abs_mean") or -1.0),
        ),
        reverse=True,
    )


def _lane_summary(stability_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stability_rows:
        groups[str(row.get("factor_lane") or "")].append(row)
    out: list[dict[str, Any]] = []
    for lane, values in groups.items():
        scores = [float(row.get("stability_score") or 0.0) for row in values]
        abs_ics = [float(row.get("mean_ic_abs_mean") or 0.0) for row in values]
        top = max(values, key=lambda row: float(row.get("stability_score") or 0.0))
        out.append(
            {
                "factor_lane": lane,
                "candidate_horizon_count": len(values),
                "unique_candidate_count": len({str(row.get("candidate_id")) for row in values}),
                "mean_stability_score": _mean(scores),
                "max_stability_score": max(scores) if scores else None,
                "mean_ic_abs_mean": _mean(abs_ics),
                "max_ic_abs_mean": max(abs_ics) if abs_ics else None,
                "top_candidate_id": top.get("candidate_id", ""),
                "top_horizon_min": top.get("horizon_min", ""),
                "top_fields": top.get("fields", ""),
            }
        )
    return sorted(out, key=lambda row: float(row.get("mean_stability_score") or -1.0), reverse=True)


def _render_markdown(summary: dict[str, Any], candidate_rows: list[dict[str, Any]], lane_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BA Stability And Parent Audit",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Scope",
        "",
        f"- run root: `{summary['run_root']}`",
        f"- shard rows: `{summary['raw_row_count']}`",
        f"- candidates audited: `{summary['unique_candidate_count']}`",
        f"- horizons audited: `{summary['candidate_horizon_count']}`",
        "- X0/R3: read-only",
        "",
        "## Parent Benchmarks",
        "",
    ]
    for parent in summary["parent_summaries"]:
        lines.append(
            "- {label}: top `{candidate}` lane `{lane}` mean_abs_ic `{ic}`".format(
                label=parent["label"],
                candidate=parent.get("top_candidate_id") or "",
                lane=parent.get("top_factor_lane") or "",
                ic=parent.get("top_mean_ic_abs_mean"),
            )
        )
    lines.extend(["", "## Lane Stability", "", "| lane | count | mean stability | max abs IC | top candidate | top fields |", "|---|---:|---:|---:|---|---|"])
    for row in lane_rows[:12]:
        lines.append(
            "| `{lane}` | {count} | {score:.6f} | {ic:.6f} | `{candidate}` | `{fields}` |".format(
                lane=row.get("factor_lane", ""),
                count=row.get("candidate_horizon_count", ""),
                score=float(row.get("mean_stability_score") or 0.0),
                ic=float(row.get("max_ic_abs_mean") or 0.0),
                candidate=row.get("top_candidate_id", ""),
                fields=row.get("top_fields", ""),
            )
        )
    lines.extend(["", "## Top Stable Candidates", "", "| rank | candidate | horizon | lane | stability | mean abs IC | sign consistency | fields |", "|---:|---|---:|---|---:|---:|---:|---|"])
    for idx, row in enumerate(candidate_rows[:25], start=1):
        lines.append(
            "| {rank} | `{candidate}` | {horizon} | `{lane}` | {score:.6f} | {ic:.6f} | {sign:.3f} | `{fields}` |".format(
                rank=idx,
                candidate=row.get("candidate_id", ""),
                horizon=row.get("horizon_min", ""),
                lane=row.get("factor_lane", ""),
                score=float(row.get("stability_score") or 0.0),
                ic=float(row.get("mean_ic_abs_mean") or 0.0),
                sign=float(row.get("sign_consistency") or 0.0),
                fields=row.get("fields", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Phase3BA should be treated as research evidence, not deployable alpha proof.",
            "- The strongest direction is old/core minute transfer plus capacity-flow.",
            "- Opening-window features are useful mainly as interaction or residual controls.",
            "- Next follow-up should test parent overlap, polarity, and horizon stability before any X0/R3 marginal audit.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_audit(
    *,
    run_root: Path,
    report_root: Path,
    ax_top: Path,
    azb_top: Path,
    ay_top: Path,
    min_ic_count: int,
) -> dict[str, Any]:
    run_root = _resolve(run_root)
    report_root = _resolve(report_root)
    rows = _read_shard_rows(run_root)
    candidate_rows = _candidate_stability(rows, min_ic_count=min_ic_count)
    lane_rows = _lane_summary(candidate_rows)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BA_STABILITY_PARENT_AUDIT_HOLD_RESEARCH",
        "run_root": str(run_root),
        "report_root": str(report_root),
        "min_ic_count": min_ic_count,
        "raw_row_count": len(rows),
        "candidate_horizon_count": len(candidate_rows),
        "unique_candidate_count": len({str(row.get("candidate_id")) for row in candidate_rows}),
        "parent_summaries": [
            _parent_summary(ax_top, "AX capacity-flow"),
            _parent_summary(azb_top, "AZB opening-window"),
            _parent_summary(ay_top, "AY X0/core minute transfer"),
        ],
        "outputs": {
            "candidate_stability_csv": str(report_root / "phase3ba_candidate_stability.csv"),
            "lane_summary_csv": str(report_root / "phase3ba_lane_stability_summary.csv"),
            "summary_json": str(report_root / "phase3ba_stability_parent_audit_summary.json"),
            "markdown": str(report_root / "PHASE3BA_STABILITY_PARENT_AUDIT_20260613.md"),
        },
        "hard_rules": [
            "true trade_time 1min shard outputs only",
            "X0/R3 read-only",
            "research-only; not alpha proof",
        ],
    }
    report_root.mkdir(parents=True, exist_ok=True)
    _write_csv(report_root / "phase3ba_candidate_stability.csv", candidate_rows)
    _write_csv(report_root / "phase3ba_lane_stability_summary.csv", lane_rows)
    _write_json(report_root / "phase3ba_stability_parent_audit_summary.json", {"summary": summary})
    (report_root / "PHASE3BA_STABILITY_PARENT_AUDIT_20260613.md").write_text(
        _render_markdown(summary, candidate_rows, lane_rows),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--ax-top", type=Path, default=DEFAULT_AX_TOP)
    parser.add_argument("--azb-top", type=Path, default=DEFAULT_AZB_TOP)
    parser.add_argument("--ay-top", type=Path, default=DEFAULT_AY_TOP)
    parser.add_argument("--min-ic-count", type=int, default=450)
    args = parser.parse_args()
    summary = build_audit(
        run_root=args.run_root,
        report_root=args.report_root,
        ax_top=args.ax_top,
        azb_top=args.azb_top,
        ay_top=args.ay_top,
        min_ic_count=args.min_ic_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
