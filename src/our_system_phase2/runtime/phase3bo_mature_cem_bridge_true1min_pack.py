"""Bridge mature search-control ideas back into true-1min candidate generation.

Phase3BO is deliberately not a daily-stock-PIT CEM launch. The mature daily
route still defaults to an old 1D stock panel, so this stage keeps the true
`trade_time` shard boundary and ports the useful parts only: policy-aware lane
quotas, memory blocking, family caps, and explicit source attribution.

Diagnostic-only. X0/R3 remains read-only.
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

from our_system_phase2.runtime.phase3bl_bk_priority_signal_materialization import (
    DEFAULT_SHARD_ROOT,
    _discover_panels,
    _f,
    _fields,
    _fmt,
    _max_expression_window,
    _run_materialization,
    _write_csv,
    _write_json,
)
from our_system_phase2.runtime.phase3bn_open_diversified_true1min_canary import (
    DEFAULT_MEMORY_ROOT,
    _load_memory_hashes,
    _prior_hashes,
)


REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bo_mature_cem_bridge_true1min_pack_20260615")
DEFAULT_REPORT_ROOT = Path("reports/phase3bo_mature_cem_bridge_true1min_pack_20260615")
EPS = "0.000001"

MATURE_CEM_FILES = [
    "src/our_system_phase2/runtime/phase3ab_launch_large_search.py",
    "src/our_system_phase2/runtime/stock_pit_large_search_supervisor.py",
    "src/our_system_phase2/runtime/stock_pit_large_search_worker.py",
    "src/our_system_phase2/services/stock_pit_forward_first_search.py",
    "src/our_system_phase2/services/stock_pit_ledger_policy.py",
]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _hash(text: str, length: int = 24) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _read_csv(path: Path) -> list[dict[str, str]]:
    path = _resolve(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _fieldset_key(expression: str) -> str:
    return "|".join(_fields(expression))


def _lane_quota(max_candidates: int, lane_count: int, *, min_per_lane: int = 4) -> int:
    return max(min_per_lane, int(math.ceil(max(1, max_candidates) / max(1, lane_count))))


def _add(
    rows: list[dict[str, Any]],
    seen: set[str],
    blocked: set[str],
    lane_counts: Counter[str],
    fieldset_counts: Counter[str],
    expression: str,
    *,
    factor_lane: str,
    source_lane: str,
    note: str,
    max_per_lane: int,
    max_per_fieldset: int,
    expected_direction: int = 1,
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    memory_key = f"phase3bo:{digest}"
    if digest in seen or digest in blocked or memory_key in blocked:
        return
    fields_key = _fieldset_key(expression)
    if lane_counts[factor_lane] >= max_per_lane:
        return
    if fieldset_counts[fields_key] >= max_per_fieldset:
        return
    seen.add(digest)
    lane_counts[factor_lane] += 1
    fieldset_counts[fields_key] += 1
    fields = _fields(expression)
    rows.append(
        {
            "candidate_id": f"phase3bo_mature_bridge_{len(rows) + 1:05d}",
            "expression_hash": digest,
            "expression": expression,
            "factor_lane": factor_lane,
            "source_lane": source_lane,
            "source_generator": "phase3bo_mature_cem_bridge_true1min_pack_v1",
            "fields": "|".join(fields),
            "fields_list": fields,
            "max_window": _max_expression_window(expression),
            "search_memory_key": memory_key,
            "expected_direction": expected_direction,
            "x0_r3_role": "read_only_research_candidate",
            "note": note,
        }
    )


def _build_candidates(max_candidates: int, blocked: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    lane_counts: Counter[str] = Counter()
    fieldset_counts: Counter[str] = Counter()
    lanes = [
        "opening_divergence_representative",
        "opening_amount_pressure_orthogonal",
        "opening_range_location",
        "amount_volume_flow",
        "intraday_efficiency_fresh",
        "range_volatility_residual",
        "bounded_vwap_mixed",
    ]
    quota = _lane_quota(max_candidates, len(lanes), min_per_lane=5)
    max_per_fieldset = 3
    windows = [2, 3, 5, 8, 10, 15, 20, 30]
    prefixes = ["m1_first5", "m1_first15", "m1_first30"]

    # Keep only one narrow representative family from BN, then force other axes.
    for prefix in ["m1_first5", "m1_first15"]:
        for window in [20, 30]:
            _add(
                rows,
                seen,
                blocked,
                lane_counts,
                fieldset_counts,
                f"CSRank(Sub(ZScore(${prefix}_vwap_return_vs_open),ZScore(Delta($ret_1m,{window}))))",
                factor_lane="opening_divergence_representative",
                source_lane="phase3bo_bn_representative",
                note="one representative of BN opening-vs-intraday divergence; lane capped to prevent collapse",
                max_per_lane=4,
                max_per_fieldset=2,
            )

    for prefix in prefixes:
        for window in windows:
            _add(
                rows,
                seen,
                blocked,
                lane_counts,
                fieldset_counts,
                f"CSRank(Sub(ZScore(Div(${prefix}_amount,Add(Abs(Mean($amount,{window})),{EPS}))),ZScore(Div(${prefix}_vol,Add(Abs(Mean($volume,{window})),{EPS})))))",
                factor_lane="opening_amount_pressure_orthogonal",
                source_lane="phase3bo_policy_quota_fresh",
                note="opening amount pressure net of share-volume pressure",
                max_per_lane=quota,
                max_per_fieldset=max_per_fieldset,
            )
            _add(
                rows,
                seen,
                blocked,
                lane_counts,
                fieldset_counts,
                f"CSRank(Mul(ZScore(Div(${prefix}_amount,Add(Abs(Mean($amount,{window})),{EPS}))),ZScore(Div(${prefix}_range,Add(Abs($open),{EPS})))))",
                factor_lane="opening_range_location",
                source_lane="phase3bo_policy_quota_fresh",
                note="opening amount impulse gated by opening range",
                max_per_lane=quota,
                max_per_fieldset=max_per_fieldset,
            )

    range_norm = f"Div(Sub($high,$low),Add(Abs($open),{EPS}))"
    bar_loc = f"Div(Sub($close,$low),Add(Abs(Sub($high,$low)),{EPS}))"
    for window in windows:
        _add(
            rows,
            seen,
            blocked,
            lane_counts,
            fieldset_counts,
            f"CSRank(Sub(ZScore(Delta($amount,{window})),ZScore(Delta($volume,{window}))))",
            factor_lane="amount_volume_flow",
            source_lane="phase3bo_policy_quota_fresh",
            note="amount acceleration minus volume acceleration",
            max_per_lane=quota,
            max_per_fieldset=max_per_fieldset,
        )
        _add(
            rows,
            seen,
            blocked,
            lane_counts,
            fieldset_counts,
            f"CSRank(Div(ZScore(Delta($intraday_ret_from_open,{window})),Add(Abs(ZScore(Std($ret_1m,{window}))),{EPS})))",
            factor_lane="intraday_efficiency_fresh",
            source_lane="phase3bo_policy_quota_fresh",
            note="intraday return efficiency, not a close/vwap residual",
            max_per_lane=quota,
            max_per_fieldset=max_per_fieldset,
        )
        _add(
            rows,
            seen,
            blocked,
            lane_counts,
            fieldset_counts,
            f"CSRank(Sub(ZScore(Std({range_norm},{window})),ZScore(Std($ret_1m,{window}))))",
            factor_lane="range_volatility_residual",
            source_lane="phase3bo_policy_quota_fresh",
            note="bar range volatility after minute-return volatility",
            max_per_lane=quota,
            max_per_fieldset=max_per_fieldset,
        )
        _add(
            rows,
            seen,
            blocked,
            lane_counts,
            fieldset_counts,
            f"CSRank(Sub(ZScore({bar_loc}),ZScore(Mean({bar_loc},{window}))))",
            factor_lane="opening_range_location",
            source_lane="phase3bo_policy_quota_fresh",
            note="price location shift inside minute high-low range",
            max_per_lane=quota,
            max_per_fieldset=max_per_fieldset,
        )
        _add(
            rows,
            seen,
            blocked,
            lane_counts,
            fieldset_counts,
            f"CSRank(Sub(ZScore(Div($m1_first5_amount,Add(Abs(Mean($amount,{window})),{EPS}))),ZScore(Delta($vwap,{window}))))",
            factor_lane="bounded_vwap_mixed",
            source_lane="phase3bo_policy_quota_fresh",
            note="bounded vwap exposure mixed with opening amount",
            max_per_lane=max(3, quota // 2),
            max_per_fieldset=2,
        )

    return rows[:max_candidates]


def _aggregate_decisions(aggregate_rows: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for row in aggregate_rows:
        by_hash.setdefault(str(row.get("expression_hash")), []).append(row)
    crowded: set[str] = set()
    for row in pairwise_rows:
        if abs(_f(row.get("signal_rank_corr"), 0.0)) >= 0.75:
            crowded.add(str(row.get("left_expression_hash")))
            crowded.add(str(row.get("right_expression_hash")))
    decisions: list[dict[str, Any]] = []
    for expr_hash, rows in by_hash.items():
        rows = sorted(rows, key=lambda item: abs(_f(item.get("aligned_ic_mean"), 0.0)), reverse=True)
        best = dict(rows[0])
        stable = sum(1 for row in rows if abs(_f(row.get("aligned_ic_mean"), 0.0)) > 0.02)
        blockers: list[str] = []
        if expr_hash in crowded:
            blockers.append("signal_corr_abs_ge_0.75")
        inherited_blockers = {
            item.strip()
            for item in str(best.get("blocker_flags") or "").split("|")
            if item.strip()
        }
        if "future_signal_wrong_lag_too_strong" in inherited_blockers:
            blockers.append("future_signal_wrong_lag_too_strong")
        if stable < 2:
            blockers.append("too_few_positive_horizons")
        if _f(best.get("mean_one_way_turnover"), 0.0) > 0.95:
            blockers.append("extreme_turnover")
        aligned_ic = _f(best.get("aligned_ic_mean"), float("nan"))
        abs_ic = abs(aligned_ic) if math.isfinite(aligned_ic) else float("nan")
        if not math.isfinite(abs_ic) or abs_ic <= 0.03:
            blockers.append("weak_dense_primary_abs_ic")
        best["open_direction"] = "long_top" if aligned_ic >= 0 else "short_top"
        best["abs_aligned_ic_mean"] = abs_ic
        best["positive_horizon_count"] = stable
        best["phase3bo_blocker_flags"] = "|".join(blockers)
        best["phase3bo_decision"] = "bo_followup_priority" if not blockers and abs_ic > 0.035 else "bo_watch_or_reject"
        decisions.append(best)
    decisions.sort(key=lambda item: (_f(item.get("abs_aligned_ic_mean"), -999.0), int(item.get("positive_horizon_count") or 0)), reverse=True)
    return decisions[:top_n]


def _lane_summary(decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_lane: dict[str, list[dict[str, Any]]] = {}
    for row in decisions:
        by_lane.setdefault(str(row.get("factor_lane")), []).append(row)
    out: list[dict[str, Any]] = []
    for lane, rows in by_lane.items():
        out.append(
            {
                "factor_lane": lane,
                "count": len(rows),
                "best_abs_aligned_ic": max((abs(_f(row.get("aligned_ic_mean"), 0.0)) for row in rows), default=None),
                "followup_count": sum(1 for row in rows if row.get("phase3bo_decision") == "bo_followup_priority"),
            }
        )
    out.sort(key=lambda row: (_f(row.get("best_abs_aligned_ic"), -999.0), int(row.get("followup_count") or 0)), reverse=True)
    return out


def _cem_audit() -> dict[str, Any]:
    return {
        "mature_chain_cem_assessment": "partially_reused_before_phase3bo",
        "direct_cem_filename_found": False,
        "mature_algorithm_files": MATURE_CEM_FILES,
        "mature_algorithm_components": [
            "rx_typed_beam candidate expansion",
            "bandit/UCB search-control policy",
            "previous expression/skeleton memory",
            "family share cap",
            "successive halving validation option",
        ],
        "phase3bn_usage": {
            "used_true_1min_trade_time": True,
            "used_search_memory_hash_block": True,
            "used_mature_rx_typed_beam": False,
            "used_mature_bandit_ucb_policy": False,
            "assessment": "useful canary but not a full mature-chain CEM invocation",
        },
        "phase3bo_fix": {
            "daily_default_dataset_blocked": True,
            "true_1min_shards_required": True,
            "lane_quota_enabled": True,
            "family_fieldset_cap_enabled": True,
            "bn_crowded_family_capped_to_representatives": True,
        },
    }


def _render_md(summary: dict[str, Any], decisions: list[dict[str, Any]], lane_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BO Mature CEM Bridge True-1min Pack 2026-06-15",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Plain Answer",
        "",
        "- The old mature chain does not expose a single `cem.py` file.",
        "- Its CEM-like logic is `rx_typed_beam` plus bandit/UCB policy routing plus family/memory guards.",
        "- Phase3BN used true 1min data, but did not fully call that mature policy stack.",
        "- Phase3BO fixes the route by keeping true 1min shards and adding mature-style quotas, memory, and crowding caps.",
        "",
        "## Scope",
        "",
        f"- candidates generated: `{summary['candidate_count']}`",
        f"- true-1min shard panels: `{summary['panel_count']}`",
        f"- sampled signal trade_times per shard: `{summary['sample_trade_times_per_shard']}`",
        f"- total eval rows: `{summary['total_eval_rows']}`",
        f"- followup priority: `{summary['followup_priority_count']}`",
        "",
        "## Lane Counts",
        "",
        "| lane | count | best abs aligned IC | followup |",
        "|---|---:|---:|---:|",
    ]
    for row in lane_rows:
        lines.append(f"| `{row['factor_lane']}` | {row['count']} | {_fmt(row.get('best_abs_aligned_ic'))} | {row['followup_count']} |")
    lines.extend(["", "## Top Decisions", "", "| rank | lane | h | fields | abs IC | direction | turnover | decision | blockers |", "|---:|---|---:|---|---:|---|---:|---|---|"])
    for idx, row in enumerate(decisions[:20], 1):
        lines.append(
            f"| {idx} | `{row['factor_lane']}` | {row['horizon_min']} | `{row['fields']}` | "
            f"{_fmt(row.get('abs_aligned_ic_mean'))} | `{row.get('open_direction')}` | {_fmt(row.get('mean_one_way_turnover'))} | "
            f"`{row['phase3bo_decision']}` | `{row.get('phase3bo_blocker_flags') or ''}` |"
        )
    lines.extend(
        [
            "",
            "## Mature Algorithm Files",
            "",
            *[f"- `{path}`" for path in MATURE_CEM_FILES],
            "",
            "## Boundary",
            "",
            "- True `trade_time` 1min shards only.",
            "- No old 1D default stock-PIT panel is used.",
            "- X0/R3 remains read-only.",
            "- Diagnostic pack, not alpha promotion proof.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-root", type=Path, default=DEFAULT_SHARD_ROOT)
    parser.add_argument("--memory-root", type=Path, default=DEFAULT_MEMORY_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=96)
    parser.add_argument("--top-decisions", type=int, default=32)
    parser.add_argument("--max-shards", type=int, default=6)
    parser.add_argument("--sample-trade-times-per-shard", type=int, default=60)
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=20)
    args = parser.parse_args(argv)

    output_root = _resolve(args.output_root)
    report_root = _resolve(args.report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    blocked = _load_memory_hashes(args.memory_root) | _prior_hashes(
        [
            Path("reports/phase3bk_bj_top64_strict_audit_20260615/phase3bk_bj_top64_candidate_audit.csv"),
            Path("reports/phase3bl_bk_priority_signal_materialization_20260615/phase3bl_candidate_horizon_aggregate.csv"),
            Path("reports/phase3bm_bl_pass_focused_replay_20260615/phase3bm_candidate_decisions.csv"),
            Path("reports/phase3bn_open_diversified_true1min_canary_20260615/phase3bn_top_decisions.csv"),
        ]
    )
    candidates = _build_candidates(args.max_candidates, blocked)
    horizons = tuple(int(item.strip()) for item in str(args.horizons).split(",") if item.strip())
    panels = _discover_panels(_resolve(args.shard_root), args.max_shards)
    metric_rows, aggregate_rows, meta = _run_materialization(
        candidates=candidates,
        panels=panels,
        horizons=horizons,
        sample_trade_times_per_shard=args.sample_trade_times_per_shard,
        min_obs_per_time=args.min_obs_per_time,
    )
    pairwise_rows = meta.pop("pairwise_rows")
    decisions = _aggregate_decisions(aggregate_rows, pairwise_rows, args.top_decisions)
    lane_rows = _lane_summary(decisions)
    total_eval_rows = sum(int(shard.get("eval_rows") or 0) for shard in meta["shards"])
    followup_count = sum(1 for row in decisions if row.get("phase3bo_decision") == "bo_followup_priority")
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BO_MATURE_CEM_BRIDGE_TRUE1MIN_COMPLETE_DIAGNOSTIC_ONLY",
        "candidate_count": len(candidates),
        "blocked_hash_count": len(blocked),
        "panel_count": len(panels),
        "sample_trade_times_per_shard": args.sample_trade_times_per_shard,
        "horizons_min": list(horizons),
        "total_eval_rows": total_eval_rows,
        "followup_priority_count": followup_count,
        "output_root": str(output_root),
        "report_root": str(report_root),
        "cem_audit": _cem_audit(),
        "hard_boundary": [
            "true trade_time minute panels only",
            "old daily stock-PIT default dataset not used",
            "mature CEM-like controls bridged but not daily CEM launched",
            "X0/R3 read-only",
        ],
        **meta,
    }
    _write_csv(output_root / "phase3bo_candidate_pack.csv", candidates)
    _write_csv(output_root / "phase3bo_candidate_horizon_shard_metrics.csv", metric_rows)
    _write_csv(output_root / "phase3bo_candidate_horizon_aggregate.csv", aggregate_rows)
    _write_csv(output_root / "phase3bo_pairwise_signal_rank_corr.csv", pairwise_rows)
    _write_csv(output_root / "phase3bo_top_decisions.csv", decisions)
    _write_json(output_root / "phase3bo_mature_cem_bridge_summary.json", summary)
    _write_csv(report_root / "phase3bo_candidate_pack.csv", candidates)
    _write_csv(report_root / "phase3bo_top_decisions.csv", decisions)
    _write_csv(report_root / "phase3bo_lane_summary.csv", lane_rows)
    _write_json(report_root / "phase3bo_mature_cem_bridge_summary.json", {**summary, "top_decisions": decisions[:10]})
    (report_root / "PHASE3BO_MATURE_CEM_BRIDGE_TRUE1MIN_PACK_20260615.md").write_text(
        _render_md(summary, decisions, lane_rows),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
