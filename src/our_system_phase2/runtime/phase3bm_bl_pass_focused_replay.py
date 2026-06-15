"""Focused true-1min replay materialization for Phase3BL pass candidates.

This stage takes only candidates that passed Phase3BL on their primary horizon,
reruns denser true-1min signal materialization, and adds direction-adjusted
crowding checks. It is still diagnostic-only and does not modify X0/R3.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from our_system_phase2.runtime.phase3bl_bk_priority_signal_materialization import (
    DEFAULT_BK_AUDIT,
    DEFAULT_SHARD_ROOT,
    _candidate_direction,
    _discover_panels,
    _f,
    _fmt,
    _load_priority_candidates,
    _run_materialization,
    _write_csv,
    _write_json,
)


REPO = Path(__file__).resolve().parents[3]
DEFAULT_BL_AGGREGATE = Path("reports/phase3bl_bk_priority_signal_materialization_20260615/phase3bl_candidate_horizon_aggregate.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bm_bl_pass_focused_replay_20260615")
DEFAULT_REPORT_ROOT = Path("reports/phase3bm_bl_pass_focused_replay_20260615")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _primary_bl_pass_ranks(path: Path) -> set[str]:
    rows = _read_csv(path)
    ranks: set[str] = set()
    for row in rows:
        if str(row.get("horizon_min")) != str(row.get("primary_horizon_min")):
            continue
        if row.get("phase3bl_decision") != "bl_signal_materialized_pass":
            continue
        if str(row.get("blocker_flags") or "").strip():
            continue
        ranks.add(str(row.get("phase3bk_rank")))
    if not ranks:
        raise RuntimeError(f"no primary-horizon Phase3BL pass rows found in {path}")
    return ranks


def _direction_by_hash(candidates: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row["expression_hash"]): _candidate_direction(row) for row in candidates}


def _direction_adjust_pairwise(pairwise_rows: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    directions = _direction_by_hash(candidates)
    by_hash = {str(row["expression_hash"]): row for row in candidates}
    out: list[dict[str, Any]] = []
    for row in pairwise_rows:
        left = str(row.get("left_expression_hash") or "")
        right = str(row.get("right_expression_hash") or "")
        raw = _f(row.get("signal_rank_corr"), float("nan"))
        left_dir = directions.get(left, 1)
        right_dir = directions.get(right, 1)
        directed = None if not math.isfinite(raw) else raw * left_dir * right_dir
        item = {
            **row,
            "left_phase3bk_rank": by_hash.get(left, {}).get("phase3bk_rank", ""),
            "right_phase3bk_rank": by_hash.get(right, {}).get("phase3bk_rank", ""),
            "left_expected_direction": left_dir,
            "right_expected_direction": right_dir,
            "direction_adjusted_corr": directed,
            "abs_direction_adjusted_corr": None if directed is None else abs(float(directed)),
            "crowding_flag": bool(directed is not None and abs(float(directed)) >= 0.7),
        }
        out.append(item)
    out.sort(key=lambda item: _f(item.get("abs_direction_adjusted_corr"), -1.0), reverse=True)
    return out


def _summarize_primary(aggregate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = [
        row
        for row in aggregate_rows
        if int(row.get("horizon_min") or -1) == int(row.get("primary_horizon_min") or -2)
    ]
    primary.sort(key=lambda row: int(float(row.get("phase3bk_rank") or 999999)))
    return primary


def _final_decisions(primary_rows: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    crowded_hashes: set[str] = set()
    for row in pairwise_rows:
        if str(row.get("crowding_flag")).lower() == "true" or row.get("crowding_flag") is True:
            crowded_hashes.add(str(row.get("left_expression_hash") or ""))
            crowded_hashes.add(str(row.get("right_expression_hash") or ""))
    decisions: list[dict[str, Any]] = []
    for row in primary_rows:
        blockers = [item for item in str(row.get("blocker_flags") or "").split("|") if item]
        if str(row.get("expression_hash")) in crowded_hashes:
            blockers.append("direction_adjusted_signal_crowding_ge_0.70")
        aligned_ic = _f(row.get("aligned_ic_mean"), float("nan"))
        if not math.isfinite(aligned_ic) or aligned_ic <= 0.03:
            blockers.append("weak_dense_primary_aligned_ic")
        decision = "bm_full_replay_priority"
        if blockers:
            decision = "bm_crowded_sibling_or_watch"
        decisions.append(
            {
                **row,
                "phase3bm_blocker_flags": "|".join(dict.fromkeys(blockers)),
                "phase3bm_decision": decision,
            }
        )
    return decisions


def _render_md(summary: dict[str, Any], decisions: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BM BL Pass Focused Replay 2026-06-15",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Scope",
        "",
        f"- input BL pass candidates: `{summary['candidate_count']}`",
        f"- true-1min shard panels: `{summary['panel_count']}`",
        f"- sampled signal trade_times per shard: `{summary['sample_trade_times_per_shard']}`",
        f"- total eval rows: `{summary['total_eval_rows']}`",
        "",
        "## Candidate Decisions",
        "",
        "| bk_rank | h | fields | aligned_ic | spread | turnover | BM decision | blockers |",
        "|---:|---:|---|---:|---:|---:|---|---|",
    ]
    for row in decisions:
        lines.append(
            f"| {row['phase3bk_rank']} | {row['horizon_min']} | `{row['fields']}` | "
            f"{_fmt(row.get('aligned_ic_mean'))} | {_fmt(row.get('aligned_spread_mean'))} | "
            f"{_fmt(row.get('mean_one_way_turnover'))} | `{row['phase3bm_decision']}` | "
            f"`{row.get('phase3bm_blocker_flags') or ''}` |"
        )
    lines.extend(["", "## Direction-Adjusted Crowding", "", "| left rank | right rank | raw corr | directed corr | crowding |", "|---:|---:|---:|---:|---|"])
    for row in pairwise_rows:
        lines.append(
            f"| {row.get('left_phase3bk_rank')} | {row.get('right_phase3bk_rank')} | "
            f"{_fmt(row.get('signal_rank_corr'))} | {_fmt(row.get('direction_adjusted_corr'))} | "
            f"`{row.get('crowding_flag')}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is true `trade_time` 1min materialization with contiguous warmup windows.",
            "- Direction-adjusted correlation is used for economic crowding.",
            "- X0/R3 remains read-only; no production or promotion decision.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bk-audit", type=Path, default=DEFAULT_BK_AUDIT)
    parser.add_argument("--bl-aggregate", type=Path, default=DEFAULT_BL_AGGREGATE)
    parser.add_argument("--shard-root", type=Path, default=DEFAULT_SHARD_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-shards", type=int, default=16)
    parser.add_argument("--sample-trade-times-per-shard", type=int, default=240)
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=20)
    args = parser.parse_args(argv)

    bk_audit = _resolve(args.bk_audit)
    bl_aggregate = _resolve(args.bl_aggregate)
    shard_root = _resolve(args.shard_root)
    output_root = _resolve(args.output_root)
    report_root = _resolve(args.report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    pass_ranks = _primary_bl_pass_ranks(bl_aggregate)
    candidates = [
        row
        for row in _load_priority_candidates(bk_audit, limit=None)
        if str(row.get("phase3bk_rank")) in pass_ranks
    ]
    if not candidates:
        raise RuntimeError("BL pass ranks did not match BK candidates")
    horizons = tuple(int(item.strip()) for item in str(args.horizons).split(",") if item.strip())
    panels = _discover_panels(shard_root, args.max_shards)
    metric_rows, aggregate_rows, meta = _run_materialization(
        candidates=candidates,
        panels=panels,
        horizons=horizons,
        sample_trade_times_per_shard=args.sample_trade_times_per_shard,
        min_obs_per_time=args.min_obs_per_time,
    )
    raw_pairwise = meta.pop("pairwise_rows")
    pairwise_rows = _direction_adjust_pairwise(raw_pairwise, candidates)
    primary_rows = _summarize_primary(aggregate_rows)
    decisions = _final_decisions(primary_rows, pairwise_rows)
    total_eval_rows = sum(int(shard.get("eval_rows") or 0) for shard in meta["shards"])
    full_replay_priority_count = sum(1 for row in decisions if row["phase3bm_decision"] == "bm_full_replay_priority")
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BM_BL_PASS_FOCUSED_REPLAY_COMPLETE_DIAGNOSTIC_ONLY",
        "bk_audit": str(bk_audit),
        "bl_aggregate": str(bl_aggregate),
        "shard_root": str(shard_root),
        "output_root": str(output_root),
        "report_root": str(report_root),
        "candidate_count": len(candidates),
        "candidate_ranks": sorted(pass_ranks, key=lambda item: int(float(item))),
        "panel_count": len(panels),
        "sample_trade_times_per_shard": args.sample_trade_times_per_shard,
        "horizons_min": list(horizons),
        "total_eval_rows": total_eval_rows,
        "direction_adjusted_crowding_threshold": 0.7,
        "full_replay_priority_count": full_replay_priority_count,
        "hard_boundary": [
            "true trade_time minute panels only",
            "direction-adjusted signal crowding blocks duplicate economic structures",
            "X0/R3 read-only; no promotion decision",
        ],
        **meta,
    }

    _write_csv(output_root / "phase3bm_candidate_horizon_shard_metrics.csv", metric_rows)
    _write_csv(output_root / "phase3bm_candidate_horizon_aggregate.csv", aggregate_rows)
    _write_csv(output_root / "phase3bm_candidate_decisions.csv", decisions)
    _write_csv(output_root / "phase3bm_direction_adjusted_pairwise_corr.csv", pairwise_rows)
    _write_json(output_root / "phase3bm_bl_pass_focused_replay_summary.json", summary)
    _write_csv(report_root / "phase3bm_candidate_decisions.csv", decisions)
    _write_csv(report_root / "phase3bm_direction_adjusted_pairwise_corr.csv", pairwise_rows)
    _write_json(report_root / "phase3bm_bl_pass_focused_replay_summary.json", {**summary, "decisions": decisions})
    (report_root / "PHASE3BM_BL_PASS_FOCUSED_REPLAY_20260615.md").write_text(
        _render_md(summary, decisions, pairwise_rows),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
