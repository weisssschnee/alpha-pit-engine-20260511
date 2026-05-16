"""Phase3I selector delta audit.

This is a read-only audit. It compares selector-only queues against I0/G2 to
explain why I1/I3/I2 changed the queue and whether those changes moved target
metrics in the intended direction.
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
from statistics import pstdev
from typing import Any

from our_system_phase2.services.variation import canonicalize_expression_light


DEFAULT_RUN_ROOT = Path("reports/phase3i_selector_only_s41_20260516/selector")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3i_selector_delta_audit_20260516")

ARMS = {
    "I0": "i0",
    "I1": "i1",
    "I2": "i2",
    "I3": "i3",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _median(values: list[float]) -> float | None:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 6)
    return round((clean[mid - 1] + clean[mid]) / 2.0, 6)


def _p90(values: list[float]) -> float | None:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return None
    idx = min(len(clean) - 1, math.ceil(0.9 * len(clean)) - 1)
    return round(clean[idx], 6)


def _mean(values: list[float]) -> float | None:
    clean = [v for v in values if math.isfinite(v)]
    return round(sum(clean) / len(clean), 6) if clean else None


def _std(values: list[float]) -> float | None:
    clean = [v for v in values if math.isfinite(v)]
    return round(float(pstdev(clean)), 6) if len(clean) >= 2 else None


def _expr_key(row: dict[str, Any]) -> str:
    expr = str(row.get("expression") or "")
    canonical = canonicalize_expression_light(expr)
    if canonical:
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return str(row.get("candidate_id") or row.get("expr_hash") or "")


def _selected(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if _truthy(row.get("selected_for_audit"))]


def _arm_rows(run_root: Path, short: str) -> list[dict[str, str]]:
    return _read_csv(run_root / short / "phase3e_selector_audit.csv")


def _metric_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    out: list[float] = []
    for row in rows:
        value = _safe_float(row.get(field))
        if value is not None:
            out.append(value)
    return out


def _stats(rows: list[dict[str, Any]], *, metric: str) -> dict[str, Any]:
    values = _metric_values(rows, metric)
    return {
        "count": len(rows),
        f"median_{metric}": _median(values),
        f"p90_{metric}": _p90(values),
        f"max_{metric}": round(max(values), 6) if values else None,
        "source_lane_counts": dict(Counter(str(row.get("source_lane") or "unknown") for row in rows)),
        "median_base_e3_score": _median(_metric_values(rows, "base_e3_score")),
        "median_turnover_penalty": _median(_metric_values(rows, "turnover_penalty")),
        "median_signal_corr_penalty": _median(_metric_values(rows, "vector_diversity_penalty")),
        "median_final_score": _median(_metric_values(rows, "selection_score_final")),
    }


def _row_extract(row: dict[str, Any], group: str) -> dict[str, Any]:
    return {
        "group": group,
        "candidate_id": row.get("candidate_id"),
        "source_lane": row.get("source_lane"),
        "expression": row.get("expression"),
        "base_e3_score": _safe_float(row.get("base_e3_score")),
        "base_quality": _safe_float(row.get("base_quality")),
        "turnover_proxy": _safe_float(row.get("turnover_proxy")),
        "p90_turnover_proxy": _safe_float(row.get("turnover_proxy")),
        "turnover_structure_risk": _safe_float(row.get("turnover_structure_risk")),
        "turnover_penalty": _safe_float(row.get("turnover_penalty")),
        "max_corr_to_selected_queue_signal": _safe_float(row.get("max_corr_to_selected_queue_signal")),
        "mean_corr_to_selected_queue_signal": _safe_float(row.get("mean_corr_to_selected_queue_signal")),
        "vector_diversity_penalty": _safe_float(row.get("vector_diversity_penalty")),
        "known_signal_cluster_id": row.get("known_signal_cluster_id"),
        "provisional_signal_cluster_id": row.get("provisional_signal_cluster_id"),
        "nearest_134_signal_cluster_id": row.get("nearest_134_signal_cluster_id"),
        "known_signal_cluster_count_before_pick": _safe_float(row.get("known_signal_cluster_count_before_pick")),
        "provisional_signal_cluster_count_before_pick": _safe_float(row.get("provisional_signal_cluster_count_before_pick")),
        "selection_score_final": _safe_float(row.get("selection_score_final")),
        "selection_rank": _safe_float(row.get("selection_rank")),
        "cap_reject_reason": row.get("cap_reject_reason"),
    }


def _delta(base_rows: list[dict[str, str]], other_rows: list[dict[str, str]], *, metric: str) -> dict[str, Any]:
    base_selected = {_expr_key(row): row for row in _selected(base_rows)}
    other_selected = {_expr_key(row): row for row in _selected(other_rows)}
    added_keys = sorted(set(other_selected) - set(base_selected))
    removed_keys = sorted(set(base_selected) - set(other_selected))
    added = [other_selected[key] for key in added_keys]
    removed = [base_selected[key] for key in removed_keys]
    return {
        "added": added,
        "removed": removed,
        "summary": {
            "added": _stats(added, metric=metric),
            "removed": _stats(removed, metric=metric),
            "overlap_count": len(set(other_selected) & set(base_selected)),
            "base_selected_count": len(base_selected),
            "other_selected_count": len(other_selected),
        },
    }


def _scale(rows: list[dict[str, str]], *, selected_only: bool) -> dict[str, Any]:
    scoped = _selected(rows) if selected_only else rows
    return {
        "row_scope": "selected" if selected_only else "all_audit_rows",
        "row_count": len(scoped),
        "std_base_e3_score": _std(_metric_values(scoped, "base_e3_score")),
        "std_turnover_penalty": _std(_metric_values(scoped, "turnover_penalty")),
        "std_signal_corr_penalty": _std(_metric_values(scoped, "vector_diversity_penalty")),
        "std_registry_novelty": _std(_metric_values(scoped, "novelty_vs_134_signal_vector")),
        "std_final_score": _std(_metric_values(scoped, "selection_score_final")),
    }


def run_delta_audit(*, run_root: Path, output_root: Path) -> dict[str, Any]:
    arm_rows = {label: _arm_rows(run_root, short) for label, short in ARMS.items()}
    i1 = _delta(arm_rows["I0"], arm_rows["I1"], metric="turnover_proxy")
    i3 = _delta(arm_rows["I0"], arm_rows["I3"], metric="max_corr_to_selected_queue_signal")
    i2 = _delta(arm_rows["I0"], arm_rows["I2"], metric="liquidity_proxy")
    scale_rows = []
    for label, rows in arm_rows.items():
        scale_rows.append({"arm": label, **_scale(rows, selected_only=True)})
        scale_rows.append({"arm": label, **_scale(rows, selected_only=False)})

    def flag_direction(delta: dict[str, Any], *, metric_name: str, worse_when: str) -> bool:
        added = delta["summary"]["added"].get(f"median_{metric_name}")
        removed = delta["summary"]["removed"].get(f"median_{metric_name}")
        if added is None or removed is None:
            return False
        return bool(added > removed) if worse_when == "higher" else bool(added < removed)

    findings = {
        "I1_added_turnover_worse_than_removed": flag_direction(i1, metric_name="turnover_proxy", worse_when="higher"),
        "I3_added_signal_corr_worse_than_removed": flag_direction(i3, metric_name="max_corr_to_selected_queue_signal", worse_when="higher"),
        "I2_added_liquidity_better_than_removed": flag_direction(i2, metric_name="liquidity_proxy", worse_when="lower") is False
        and (i2["summary"]["added"].get("median_liquidity_proxy") or 0) > (i2["summary"]["removed"].get("median_liquidity_proxy") or 0),
    }
    decision = "HOLD_SELECTOR_REPAIR_REQUIRED"
    report = {
        "created_at": _now(),
        "decision": decision,
        "run_root": str(run_root),
        "findings": findings,
        "i1_vs_i0_turnover_delta": i1["summary"],
        "i3_vs_i0_signal_corr_delta": i3["summary"],
        "i2_vs_i0_liquidity_delta": i2["summary"],
        "score_component_scale": scale_rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "phase3i_selector_delta_audit.json", report)
    _write_csv(output_root / "phase3i_i1_vs_i0_turnover_delta_rows.csv", [_row_extract(row, "I1_added") for row in i1["added"]] + [_row_extract(row, "I0_removed") for row in i1["removed"]])
    _write_csv(output_root / "phase3i_i3_vs_i0_signal_corr_delta_rows.csv", [_row_extract(row, "I3_added") for row in i3["added"]] + [_row_extract(row, "I0_removed") for row in i3["removed"]])
    _write_csv(output_root / "phase3i_i2_vs_i0_liquidity_delta_rows.csv", [_row_extract(row, "I2_added") for row in i2["added"]] + [_row_extract(row, "I0_removed") for row in i2["removed"]])
    _write_csv(output_root / "phase3i_score_component_scale.csv", scale_rows)
    _write_markdown(output_root / "PHASE3I_SELECTOR_DELTA_AUDIT_2026-05-16.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase3I Selector Delta Audit",
        "",
        f"- decision: `{report['decision']}`",
        f"- run_root: `{report['run_root']}`",
        "",
        "## Findings",
        "",
    ]
    for key, value in report["findings"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            "## Delta Summaries",
            "",
            "### I1 vs I0 Turnover",
            "```json",
            json.dumps(report["i1_vs_i0_turnover_delta"], indent=2, ensure_ascii=False),
            "```",
            "",
            "### I3 vs I0 Signal Correlation",
            "```json",
            json.dumps(report["i3_vs_i0_signal_corr_delta"], indent=2, ensure_ascii=False),
            "```",
            "",
            "### I2 vs I0 Liquidity",
            "```json",
            json.dumps(report["i2_vs_i0_liquidity_delta"], indent=2, ensure_ascii=False),
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    report = run_delta_audit(run_root=args.run_root, output_root=args.output_root)
    print(json.dumps({key: report[key] for key in ["created_at", "decision", "findings"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

