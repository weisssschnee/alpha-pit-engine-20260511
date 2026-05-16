"""Phase3I feature preflight.

No replay is run here. The script checks whether the shared pre-replay pool has
the features needed for I1/I2/I3 selector-only experiments.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.services.phase3e_selectors import Phase3ERegistryContext, feature_row
from our_system_phase2.services.phase3g_signal_vector_store import Phase3GSignalVectorStore
from our_system_phase2.services.stock_pit_phase3_repair import PHASE3H_CUMULATIVE_BASELINE_PATH


DEFAULT_OUTPUT_ROOT = Path("reports/phase3i_feature_preflight_20260516")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


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


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _coverage(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(1 for row in rows if row.get(key) is not None and row.get(key) != "") / max(1, len(rows)), 6)


def _p90(values: list[float]) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    index = min(len(clean) - 1, math.ceil(0.9 * len(clean)) - 1)
    return round(clean[index], 6)


def _pool_rows(pool: dict[str, Any]) -> list[dict[str, Any]]:
    return list(pool.get("candidate_pool") or [])


def run_preflight(*, pool_path: Path, output_root: Path, baseline_path: Path) -> dict[str, Any]:
    pool = _read_json(pool_path)
    rows = _pool_rows(pool)
    context = Phase3ERegistryContext.from_path(baseline_path)
    signal_store = Phase3GSignalVectorStore(dataset_path=pool.get("dataset_path"))
    features = [feature_row(row, context, signal_vector_store=signal_store) for row in rows]

    source_lane_turnover: list[dict[str, Any]] = []
    lane_groups: dict[str, list[float]] = {}
    for item in features:
        turnover = _safe_float(item.get("turnover_proxy"))
        if turnover is None:
            continue
        lane_groups.setdefault(str(item.get("source_lane") or "unknown"), []).append(turnover)
    for lane, values in sorted(lane_groups.items()):
        source_lane_turnover.append(
            {
                "source_lane": lane,
                "rows_with_turnover": len(values),
                "p90_turnover_proxy": _p90(values),
            }
        )

    signal_vector_ready = _coverage(features, "signal_vector_ready")
    # selected_queue_signal_corr is a post-selection dynamic metric. At
    # preflight time the correct gate is whether candidate signal vectors can
    # be computed, not whether a selected queue already exists.
    selected_queue_signal_corr_ready = signal_vector_ready
    coverage = {
        "cluster_turnover": _coverage(features, "turnover_proxy"),
        "p90_turnover": _coverage(features, "turnover_proxy"),
        "source_lane_turnover": round(len(lane_groups) / max(1, len(set(str(item.get("source_lane") or "unknown") for item in features))), 6),
        "cost_proxy": _coverage(features, "cost_adjusted_proxy"),
        "liquidity_proxy": _coverage(features, "liquidity_proxy"),
        "capacity_proxy": _coverage(features, "capacity_proxy"),
        "corr_to_149_registry_proxy": _coverage(features, "max_corr_to_103_registry"),
        "selected_queue_signal_corr": selected_queue_signal_corr_ready,
        "signal_vector_ready": signal_vector_ready,
        "operator_pathology_flag": _coverage(features, "operator_pathology_flag"),
        "complexity_score": _coverage(features, "complexity_score"),
    }
    i1_pass = all(coverage[key] > 0 for key in ["cluster_turnover", "p90_turnover", "source_lane_turnover", "selected_queue_signal_corr"])
    i2_pass = max(coverage["liquidity_proxy"], coverage["capacity_proxy"]) >= 0.8
    i3_pass = (
        coverage["corr_to_149_registry_proxy"] > 0
        and coverage["selected_queue_signal_corr"] > 0
        and (coverage["cluster_turnover"] > 0 or coverage["cost_proxy"] > 0)
    )
    decision = "PASS_PHASE3I_FEATURE_PREFLIGHT" if i1_pass and i3_pass else "HOLD_PHASE3I_FEATURE_PREFLIGHT"
    report = {
        "created_at": _now(),
        "decision": decision,
        "pool_path": str(pool_path),
        "baseline_path": str(baseline_path),
        "candidate_count": len(rows),
        "coverage": coverage,
        "requirements": {
            "I1": {
                "minimum_pass": i1_pass,
                "requires": ["cluster_turnover", "p90_turnover", "source_lane_turnover", "selected_queue_signal_corr"],
            },
            "I2": {
                "minimum_pass": i2_pass,
                "status": "promotion_eligible" if i2_pass else "diagnostic_only",
                "requires": ["liquidity_proxy_or_capacity_proxy"],
            },
            "I3": {
                "minimum_pass": i3_pass,
                "requires": ["corr_to_149_registry_proxy", "selected_queue_signal_corr", "turnover_or_cost_proxy"],
            },
        },
        "source_lane_counts": dict(Counter(str(item.get("source_lane") or "unknown") for item in features)),
        "source_lane_turnover": source_lane_turnover,
        "notes": {
            "selected_queue_signal_corr": "preflight checks signal-vector readiness; actual selected-queue correlation is measured in selector-only dry run"
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "phase3i_feature_preflight.json", report)
    _write_csv(output_root / "phase3i_source_lane_turnover.csv", source_lane_turnover)
    _write_markdown(output_root / "PHASE3I_FEATURE_PREFLIGHT_2026-05-16.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    coverage = report["coverage"]
    lines = [
        "# Phase3I Feature Preflight",
        "",
        f"- decision: `{report['decision']}`",
        f"- candidate_count: `{report['candidate_count']}`",
        f"- I1_minimum_pass: `{report['requirements']['I1']['minimum_pass']}`",
        f"- I2_status: `{report['requirements']['I2']['status']}`",
        f"- I3_minimum_pass: `{report['requirements']['I3']['minimum_pass']}`",
        "",
        "## Coverage",
        "",
        "| feature | coverage |",
        "| --- | ---: |",
    ]
    for key, value in coverage.items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- I1 can proceed only if turnover and source-lane turnover are available.",
            "- I2 is promotion-eligible only if liquidity or capacity proxy coverage is sufficient; otherwise it remains diagnostic-only.",
            "- I3 remains `book-proxy hardened`, not true book residual.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--baseline", type=Path, default=PHASE3H_CUMULATIVE_BASELINE_PATH)
    args = parser.parse_args()
    report = run_preflight(pool_path=args.pool, output_root=args.output_root, baseline_path=args.baseline)
    print(json.dumps({key: report[key] for key in ["created_at", "decision", "coverage", "requirements"]}, ensure_ascii=False, indent=2))
    return 0 if report["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
