"""Mid-scale true-1min algorithm practice benchmark.

Phase3BR sits between a smoke test and a broad search. It compares generator
arms in a realistic factor-search loop and scores them by research-pool quality,
not by first clean followup. This prevents tiny residual probes from looking
better than scalable algorithms just because one or two rows survived.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from our_system_phase2.runtime.phase3bq_compute_allocation_benchmark import (
    _fmt,
    _hot_path_scan,
    _package_versions,
    _resolve,
    _write_csv,
    _write_json,
)


REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3br_midscale_algorithm_practice_20260615")
DEFAULT_REPORT_ROOT = Path("reports/phase3br_midscale_algorithm_practice_20260615")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _arm_specs() -> list[dict[str, Any]]:
    return [
        {
            "arm_id": "template_control_96x4x40",
            "family": "template_quota_control",
            "route": "phase3bo-mature-cem-bridge-true1min-pack",
            "args": ["--max-candidates", "96", "--max-shards", "4", "--sample-trade-times-per-shard", "40"],
            "summary": "phase3bo_mature_cem_bridge_summary.json",
            "decisions": "phase3bo_top_decisions.csv",
            "decision_col": "phase3bo_decision",
            "blocker_col": "phase3bo_blocker_flags",
            "purpose": "control arm: simple mature bridge, useful for throughput and leakage baseline",
        },
        {
            "arm_id": "rx_ucb_mid_128x4x40",
            "family": "rx_ucb",
            "route": "phase3bp-true1min-search-algorithm-smoke",
            "args": [
                "--algorithm-mode",
                "rx_ucb",
                "--max-candidates",
                "128",
                "--max-shards",
                "4",
                "--sample-trade-times-per-shard",
                "40",
                "--top-decisions",
                "80",
            ],
            "summary": "phase3bp_true1min_search_algorithm_summary.json",
            "decisions": "phase3bp_top_decisions.csv",
            "decision_col": "phase3bp_decision",
            "blocker_col": "phase3bp_blocker_flags",
            "purpose": "typed broad search arm with UCB prior and search-memory blocking",
        },
        {
            "arm_id": "rx_ucb_fresh_128x4x40",
            "family": "rx_ucb_high_exploration",
            "route": "phase3bp-true1min-search-algorithm-smoke",
            "args": [
                "--algorithm-mode",
                "rx_ucb",
                "--policy-exploration",
                "0.85",
                "--max-candidates",
                "128",
                "--max-shards",
                "4",
                "--sample-trade-times-per-shard",
                "40",
                "--top-decisions",
                "80",
            ],
            "summary": "phase3bp_true1min_search_algorithm_summary.json",
            "decisions": "phase3bp_top_decisions.csv",
            "decision_col": "phase3bp_decision",
            "blocker_col": "phase3bp_blocker_flags",
            "purpose": "freshness arm: higher exploration to test whether prior lock-in causes collapse",
        },
        {
            "arm_id": "cem_elite_mid_128x4x40",
            "family": "cem_elite",
            "route": "phase3bp-true1min-search-algorithm-smoke",
            "args": [
                "--algorithm-mode",
                "cem_elite",
                "--cem-population-size",
                "1024",
                "--cem-elite-frac",
                "0.14",
                "--cem-rounds",
                "4",
                "--max-candidates",
                "128",
                "--max-shards",
                "4",
                "--sample-trade-times-per-shard",
                "40",
                "--top-decisions",
                "80",
            ],
            "summary": "phase3bp_true1min_search_algorithm_summary.json",
            "decisions": "phase3bp_top_decisions.csv",
            "decision_col": "phase3bp_decision",
            "blocker_col": "phase3bp_blocker_flags",
            "purpose": "CEM-style elite resampling arm with enough population to observe adaptation",
        },
        {
            "arm_id": "hybrid_rx_cem_mid_160x4x40",
            "family": "hybrid_rx_cem",
            "route": "phase3bp-true1min-search-algorithm-smoke",
            "args": [
                "--algorithm-mode",
                "hybrid_rx_cem",
                "--cem-population-size",
                "1280",
                "--cem-elite-frac",
                "0.16",
                "--cem-rounds",
                "4",
                "--max-candidates",
                "160",
                "--max-shards",
                "4",
                "--sample-trade-times-per-shard",
                "40",
                "--top-decisions",
                "96",
            ],
            "summary": "phase3bp_true1min_search_algorithm_summary.json",
            "decisions": "phase3bp_top_decisions.csv",
            "decision_col": "phase3bp_decision",
            "blocker_col": "phase3bp_blocker_flags",
            "purpose": "combined arm: typed coverage plus CEM elite mutation",
        },
        {
            "arm_id": "residual_capped_40x2x24",
            "family": "residual_capped_probe",
            "route": "phase3bp-true1min-search-algorithm-smoke",
            "args": [
                "--algorithm-mode",
                "rx_ucb",
                "--max-candidates",
                "40",
                "--max-shards",
                "2",
                "--sample-trade-times-per-shard",
                "24",
                "--top-decisions",
                "40",
                "--include-residual",
            ],
            "summary": "phase3bp_true1min_search_algorithm_summary.json",
            "decisions": "phase3bp_top_decisions.csv",
            "decision_col": "phase3bp_decision",
            "blocker_col": "phase3bp_blocker_flags",
            "purpose": "capped residual probe only; cannot win allocation on tiny survivor count alone",
        },
    ]


def _run_arm(spec: dict[str, Any], *, output_root: Path, report_root: Path, timeout_seconds: int) -> dict[str, Any]:
    arm_output = output_root / spec["arm_id"]
    arm_report = report_root / spec["arm_id"]
    command = [
        sys.executable,
        "app.py",
        spec["route"],
        "--allow-diagnostic",
        "--",
        *spec["args"],
        "--output-root",
        str(arm_output),
        "--report-root",
        str(arm_report),
    ]
    started = time.perf_counter()
    status = "completed"
    stdout_tail = ""
    stderr_tail = ""
    try:
        proc = subprocess.run(command, cwd=REPO, text=True, capture_output=True, timeout=timeout_seconds)
        elapsed = time.perf_counter() - started
        stdout_tail = proc.stdout[-3000:]
        stderr_tail = proc.stderr[-3000:]
        if proc.returncode != 0:
            status = "failed"
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        status = "timeout"
        stdout_tail = (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else ""
        stderr_tail = (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else ""

    summary_path = arm_report / spec["summary"]
    decisions_path = arm_report / spec["decisions"]
    candidate_path = arm_report / ("phase3bo_candidate_pack.csv" if spec["route"].startswith("phase3bo") else "phase3bp_candidate_pack.csv")
    summary = _read_json(summary_path)
    decisions = _read_csv(decisions_path)
    candidates = _read_csv(candidate_path)
    blocker_col = spec["blocker_col"]
    decision_col = spec["decision_col"]

    hard_blocked = []
    non_future = []
    research_pool = []
    for row in decisions:
        blockers = str(row.get(blocker_col) or row.get("blocker_flags") or "")
        future = "future_signal_wrong_lag_too_strong" in blockers
        crowded = "signal_corr_abs" in blockers
        turnover = _float(row.get("mean_one_way_turnover"), 0.0)
        abs_ic = abs(_float(row.get("abs_aligned_ic_mean") or row.get("aligned_ic_mean"), 0.0))
        stable = int(_float(row.get("positive_horizon_count"), 0.0))
        if future or crowded:
            hard_blocked.append(row)
        if not future:
            non_future.append(row)
        if (not future) and turnover <= 0.98 and abs_ic >= 0.025 and stable >= 1:
            research_pool.append(row)

    fields = {str(row.get("fields") or "") for row in decisions if row.get("fields")}
    lanes = {str(row.get("factor_lane") or "") for row in decisions if row.get("factor_lane")}
    candidate_fields = {str(row.get("fields") or "") for row in candidates if row.get("fields")}
    top_abs = sorted([abs(_float(row.get("abs_aligned_ic_mean") or row.get("aligned_ic_mean"), 0.0)) for row in decisions], reverse=True)
    top10_mean = sum(top_abs[:10]) / max(1, min(10, len(top_abs)))
    eval_rows = int(summary.get("total_eval_rows") or 0)
    candidate_count = int(summary.get("candidate_count") or len(candidates))
    panel_count = int(summary.get("panel_count") or 0)
    sample_times = int(summary.get("sample_trade_times_per_shard") or 0)
    followup_count = sum(1 for row in decisions if "followup" in str(row.get(decision_col) or ""))
    research_quality = (
        (0.45 * len(research_pool) / max(1, len(decisions)))
        + (0.20 * len(non_future) / max(1, len(decisions)))
        + (0.15 * min(1.0, len(lanes) / 16.0))
        + (0.12 * min(1.0, len(fields) / 24.0))
        + (0.08 * min(1.0, top10_mean / 0.08))
    )
    if spec["family"] == "residual_capped_probe":
        research_quality *= 0.70

    return {
        "arm_id": spec["arm_id"],
        "family": spec["family"],
        "status": status,
        "elapsed_seconds": round(elapsed, 3),
        "candidate_count": candidate_count,
        "decision_rows": len(decisions),
        "panel_count": panel_count,
        "sample_trade_times_per_shard": sample_times,
        "total_eval_rows": eval_rows,
        "rows_per_second": round(eval_rows / elapsed, 3) if elapsed > 0 else 0.0,
        "candidate_eval_units_per_second": round((max(1, candidate_count) * max(1, panel_count) * max(1, sample_times)) / elapsed, 3)
        if elapsed > 0
        else 0.0,
        "followup_count_legacy": followup_count,
        "hard_blocked_count": len(hard_blocked),
        "hard_blocked_ratio": round(len(hard_blocked) / max(1, len(decisions)), 6),
        "non_future_count": len(non_future),
        "research_pool_count": len(research_pool),
        "research_pool_ratio": round(len(research_pool) / max(1, len(decisions)), 6),
        "unique_lane_count": len(lanes),
        "unique_decision_fieldset_count": len(fields),
        "unique_candidate_fieldset_count": len(candidate_fields),
        "top10_abs_ic_mean": round(top10_mean, 10),
        "best_abs_ic": round(max(top_abs, default=0.0), 10),
        "research_quality_score": round(research_quality, 8),
        "summary_path": str(summary_path),
        "decisions_path": str(decisions_path),
        "candidate_path": str(candidate_path),
        "purpose": spec["purpose"],
        "command": " ".join(command),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def _recommend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    if not completed:
        return {"decision": "HOLD_RESEARCH", "reason": "no completed arm"}
    scalable = [row for row in completed if row["family"] != "residual_capped_probe"]
    ranked = sorted(scalable or completed, key=lambda row: (float(row["research_quality_score"]), float(row["candidate_eval_units_per_second"])), reverse=True)
    residual = next((row for row in completed if row["family"] == "residual_capped_probe"), None)
    return {
        "decision": "MID_SCALE_ALGORITHM_PRACTICE_COMPLETE_USE_SCORED_ALLOCATION",
        "primary_arm": ranked[0]["arm_id"],
        "ranked_arms": [row["arm_id"] for row in ranked],
        "residual_policy": "cap at probe budget; do not let tiny survivor count dominate allocation"
        if residual
        else "not run",
        "next_budget_split": {
            "rx_ucb_or_best_scalable_arm": "40%",
            "fresh_high_exploration": "20%",
            "cem_or_hybrid_if_research_pool_positive": "20%",
            "template_control": "10%",
            "residual_probe": "10% max until full evaluator is optimized",
        },
        "reason": "ranking uses research-pool quality, hard-blocked ratio, diversity, and throughput; legacy followup count is diagnostic only",
    }


def _render_md(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BR Mid-scale Algorithm Practice 2026-06-15",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Purpose",
        "",
        "Run a medium true-1min algorithm practice pass that is larger than smoke but smaller than prior broad searches.",
        "The scoring target is research-pool quality, not first clean followup.",
        "",
        "Research pool means a non-future-leaking followup queue for deeper review.",
        "It may still include crowded signals; crowding is reported separately and is not promotion evidence.",
        "",
        "## Arm Results",
        "",
        "| arm | family | status | sec | candidates | rows | rows/sec | legacy followup | hard-blocked | research pool | lanes | fieldsets | top10 abs IC | score |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['arm_id']}` | `{row['family']}` | `{row['status']}` | {_fmt(row['elapsed_seconds'])} | "
            f"{row['candidate_count']} | {row['total_eval_rows']} | {_fmt(row['rows_per_second'])} | "
            f"{row['followup_count_legacy']} | {_fmt(row['hard_blocked_ratio'])} | {row['research_pool_count']} | "
            f"{row['unique_lane_count']} | {row['unique_decision_fieldset_count']} | {_fmt(row['top10_abs_ic_mean'])} | {_fmt(row['research_quality_score'])} |"
        )
    rec = summary["recommendation"]
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- primary scalable arm: `{rec.get('primary_arm')}`",
            f"- ranked scalable arms: `{rec.get('ranked_arms')}`",
            f"- residual policy: {rec.get('residual_policy')}",
            f"- reason: {rec.get('reason')}",
            "",
            "## Budget",
            "",
        ]
    )
    for key, value in (rec.get("next_budget_split") or {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- True `trade_time` 1min only.",
            "- No X0/R3 modification.",
            "- This is algorithm adaptation and factor-search practice, not alpha promotion.",
            "- Legacy followup is reported but not used as the main winner metric.",
            "- `research pool` excludes future-lag but does not equal deployable; crowded members need later orthogonalization or rejection.",
            "",
            "## Acceleration And Reproducibility",
            "",
            f"- python executable: `{summary['python_executable']}`",
            f"- package matrix: `{summary['package_versions']}`",
            f"- hot path scan: `{summary['hot_path_scan']}`",
            f"- commands are embedded in `phase3br_midscale_algorithm_practice_summary.json`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--timeout-seconds-per-arm", type=int, default=1800)
    args = parser.parse_args(argv)

    output_root = _resolve(args.output_root)
    report_root = _resolve(args.report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    rows = [_run_arm(spec, output_root=output_root, report_root=report_root, timeout_seconds=args.timeout_seconds_per_arm) for spec in _arm_specs()]
    recommendation = _recommend(rows)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "20260615_phase3br_midscale_algorithm_practice",
        "decision": "PHASE3BR_MIDSCALE_ALGORITHM_PRACTICE_COMPLETE_DIAGNOSTIC_ONLY",
        "objective": "compare true1min search algorithm adaptation under medium budget using research-pool quality metrics",
        "python_executable": sys.executable,
        "package_versions": _package_versions(),
        "hot_path_scan": _hot_path_scan(),
        "arm_count": len(rows),
        "arms": rows,
        "recommendation": recommendation,
        "hard_boundary": [
            "true trade_time minute panels only",
            "medium algorithm practice only",
            "legacy followup is not promotion evidence",
            "residual probe cannot win allocation by tiny survivor count",
            "no X0/R3 modification",
        ],
        "reproducibility": {
            "status": "partial",
            "reason": "commands and parameters are recorded; minute shard data is referenced by existing runtime shard paths",
        },
    }
    _write_json(output_root / "phase3br_midscale_algorithm_practice_summary.json", summary)
    _write_json(report_root / "phase3br_midscale_algorithm_practice_summary.json", summary)
    _write_csv(report_root / "phase3br_arm_results.csv", rows)
    (report_root / "PHASE3BR_MIDSCALE_ALGORITHM_PRACTICE_20260615.md").write_text(_render_md(summary, rows), encoding="utf-8")
    print(json.dumps({"status": "ok", **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
