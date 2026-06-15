"""True-1min search algorithm smoke test.

Phase3BP compares a conservative BO-style template reference against a broader
true-1min native rx/UCB-style generator. This is still a smoke test: it measures
whether the generator core deserves a larger run, not whether any candidate is
production-ready.
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

import numpy as np

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
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bp_true1min_search_algorithm_smoke_20260615")
DEFAULT_REPORT_ROOT = Path("reports/phase3bp_true1min_search_algorithm_smoke_20260615")
EPS = "0.000001"
OP_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(")
WIN_RE = re.compile(r"(?<![A-Za-z0-9_])([1-9][0-9]{0,2})(?![A-Za-z0-9_])")


PRIOR_DECISION_FILES = [
    Path("reports/phase3bn_open_diversified_true1min_canary_20260615/phase3bn_top_decisions.csv"),
    Path("reports/phase3bo_mature_cem_bridge_true1min_pack_20260615/phase3bo_top_decisions.csv"),
    Path("reports/phase3bm_bl_pass_focused_replay_20260615/phase3bm_candidate_decisions.csv"),
]
PRIOR_HASH_FILES = [
    Path("reports/phase3bk_bj_top64_strict_audit_20260615/phase3bk_bj_top64_candidate_audit.csv"),
    Path("reports/phase3bl_bk_priority_signal_materialization_20260615/phase3bl_candidate_horizon_aggregate.csv"),
    Path("reports/phase3bm_bl_pass_focused_replay_20260615/phase3bm_candidate_decisions.csv"),
    Path("reports/phase3bn_open_diversified_true1min_canary_20260615/phase3bn_top_decisions.csv"),
    Path("reports/phase3bo_mature_cem_bridge_true1min_pack_20260615/phase3bo_top_decisions.csv"),
]
OPERATORS = {"Abs", "Add", "CSRank", "CSResidual", "Delay", "Div", "Mean", "Mom", "Mul", "Neg", "Sign", "Std", "Sub", "ZScore", "Delta"}


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


def _operators(expression: str) -> set[str]:
    return {match.group(1) for match in OP_RE.finditer(expression or "") if match.group(1) in OPERATORS}


def _windows(expression: str) -> set[str]:
    return {match.group(1) for match in WIN_RE.finditer(expression or "") if 1 <= int(match.group(1)) <= 252}


def _prior_reward(row: dict[str, Any]) -> float:
    abs_ic = abs(
        _f(
            row.get("abs_aligned_ic_mean")
            or row.get("aligned_ic_mean")
            or row.get("ic_mean")
            or row.get("mean_window_rank_ic"),
            0.0,
        )
    )
    decision = " ".join(str(row.get(key) or "") for key in ("phase3bo_decision", "phase3bn_decision", "phase3bm_decision", "phase3bl_decision"))
    blockers = " ".join(str(row.get(key) or "") for key in ("phase3bo_blocker_flags", "phase3bn_blocker_flags", "blocker_flags"))
    reward = abs_ic
    if "followup_priority" in decision:
        reward += 0.035
    if "pass" in decision:
        reward += 0.015
    if "future_signal_wrong_lag_too_strong" in blockers:
        reward -= 0.18
    if "signal_corr_abs" in blockers:
        reward -= 0.06
    if "weak_dense" in blockers:
        reward -= 0.04
    if "too_few_positive_horizons" in blockers:
        reward -= 0.03
    return float(max(-0.25, min(0.25, reward)))


def _ucb(values: list[float], total: int, *, exploration: float) -> float:
    if not values:
        return 0.40 * exploration
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    uncertainty = math.sqrt(max(0.0, math.log(max(2, total + 1))) / max(1, len(values)))
    return mean + (exploration * uncertainty)


def _build_policy(prior_files: list[Path], *, exploration: float) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[float]]] = {
        "field": defaultdict(list),
        "operator": defaultdict(list),
        "window": defaultdict(list),
        "lane": defaultdict(list),
        "fieldset": defaultdict(list),
    }
    examples: list[dict[str, Any]] = []
    total = 0
    for path in prior_files:
        for row in _read_csv(path):
            expression = str(row.get("expression") or "")
            if not expression:
                continue
            reward = _prior_reward(row)
            total += 1
            lane = str(row.get("factor_lane") or row.get("primitive_family") or "unknown")
            fields = _fields(expression)
            fieldset = "|".join(fields)
            buckets["lane"][lane].append(reward)
            buckets["fieldset"][fieldset].append(reward)
            for field in fields:
                buckets["field"][field].append(reward)
            for operator in _operators(expression):
                buckets["operator"][operator].append(reward)
            for window in _windows(expression):
                buckets["window"][window].append(reward)
            if len(examples) < 20:
                examples.append({"source": str(path), "lane": lane, "reward": round(reward, 6), "expression": expression})
    scores = {
        kind: {key: round(_ucb(values, total, exploration=exploration), 6) for key, values in values_by_key.items()}
        for kind, values_by_key in buckets.items()
    }
    return {
        "policy_version": "phase3bp_true1min_ucb_smoke_v1",
        "scope": "true1min_prior_routing_not_production_reward",
        "total_observation_count": total,
        "exploration": float(exploration),
        "scores": scores,
        "examples": examples,
        "top_keys": {
            kind: sorted(values.items(), key=lambda item: item[1], reverse=True)[:12]
            for kind, values in scores.items()
        },
    }


def _policy_score(expression: str, lane: str, policy: dict[str, Any]) -> float:
    scores = policy.get("scores") or {}
    fields = _fields(expression)
    ops = _operators(expression)
    wins = _windows(expression)
    fieldset = "|".join(fields)
    lane_score = float((scores.get("lane") or {}).get(lane, 0.0))
    field_score = np.mean([float((scores.get("field") or {}).get(field, 0.0)) for field in fields]) if fields else 0.0
    op_score = np.mean([float((scores.get("operator") or {}).get(op, 0.0)) for op in ops]) if ops else 0.0
    win_score = np.mean([float((scores.get("window") or {}).get(win, 0.0)) for win in wins]) if wins else 0.0
    fieldset_score = float((scores.get("fieldset") or {}).get(fieldset, 0.0))
    novelty_bonus = 0.01 * sum(1 for field in fields if field not in (scores.get("field") or {}))
    return float((0.22 * lane_score) + (0.24 * field_score) + (0.16 * op_score) + (0.10 * win_score) + (0.18 * fieldset_score) + novelty_bonus)


def _add_candidate(
    rows: list[dict[str, Any]],
    seen: set[str],
    blocked: set[str],
    expression: str,
    *,
    lane: str,
    source_generator: str,
    note: str,
    policy: dict[str, Any],
) -> None:
    expression = expression.strip()
    digest = _hash(expression)
    if digest in seen or digest in blocked:
        return
    memory_key = f"phase3bp:{digest}"
    if memory_key in blocked:
        return
    seen.add(digest)
    fields = _fields(expression)
    rows.append(
        {
            "candidate_id": f"phase3bp_{len(rows) + 1:05d}",
            "expression_hash": digest,
            "expression": expression,
            "factor_lane": lane,
            "source_lane": source_generator,
            "source_generator": source_generator,
            "fields": "|".join(fields),
            "fields_list": fields,
            "max_window": _max_expression_window(expression),
            "search_memory_key": memory_key,
            "policy_score": round(_policy_score(expression, lane, policy), 8),
            "expected_direction": 1,
            "x0_r3_role": "read_only_research_candidate",
            "note": note,
        }
    )


def _raw_atoms() -> list[dict[str, Any]]:
    windows = [2, 3, 5, 8, 10, 15, 20, 30]
    pairs = [(2, 5), (3, 8), (5, 15), (8, 20), (10, 30)]
    prefixes = ["m1_first5", "m1_first15", "m1_first30"]
    atoms: list[dict[str, Any]] = []
    range_norm = f"Div(Sub($high,$low),Add(Abs($open),{EPS}))"
    bar_loc = f"Div(Sub($close,$low),Add(Abs(Sub($high,$low)),{EPS}))"
    for window in windows:
        atoms.extend(
            [
                {"name": f"ret_delta_{window}", "lane": "rx_intraday_return", "expr": f"Delta($ret_1m,{window})", "side": "event"},
                {"name": f"intraday_delta_{window}", "lane": "rx_intraday_return", "expr": f"Delta($intraday_ret_from_open,{window})", "side": "event"},
                {"name": f"range_vol_{window}", "lane": "rx_range_location", "expr": f"Std({range_norm},{window})", "side": "state"},
                {"name": f"bar_loc_shift_{window}", "lane": "rx_range_location", "expr": f"Sub({bar_loc},Mean({bar_loc},{window}))", "side": "event"},
                {"name": f"amount_delta_{window}", "lane": "rx_flow_amount_volume", "expr": f"Delta($amount,{window})", "side": "state"},
                {"name": f"volume_delta_{window}", "lane": "rx_flow_amount_volume", "expr": f"Delta($volume,{window})", "side": "state"},
                {"name": f"ret_vol_{window}", "lane": "rx_volatility_state", "expr": f"Std($ret_1m,{window})", "side": "state"},
            ]
        )
    for short, long in pairs:
        atoms.extend(
            [
                {
                    "name": f"amount_curve_{short}_{long}",
                    "lane": "rx_flow_amount_volume",
                    "expr": f"Div(Mean($amount,{short}),Add(Abs(Mean($amount,{long})),{EPS}))",
                    "side": "state",
                },
                {
                    "name": f"volume_curve_{short}_{long}",
                    "lane": "rx_flow_amount_volume",
                    "expr": f"Div(Mean($volume,{short}),Add(Abs(Mean($volume,{long})),{EPS}))",
                    "side": "state",
                },
            ]
        )
    for prefix in prefixes:
        atoms.extend(
            [
                {"name": f"{prefix}_amount", "lane": "rx_opening_amount", "expr": f"Div(${prefix}_amount,Add(Abs($amount),{EPS}))", "side": "event"},
                {"name": f"{prefix}_vol", "lane": "rx_opening_amount", "expr": f"Div(${prefix}_vol,Add(Abs($volume),{EPS}))", "side": "state"},
                {"name": f"{prefix}_range", "lane": "rx_opening_range", "expr": f"Div(${prefix}_range,Add(Abs($open),{EPS}))", "side": "event"},
                {"name": f"{prefix}_vwap_open", "lane": "rx_opening_divergence", "expr": f"${prefix}_vwap_return_vs_open", "side": "event"},
            ]
        )
    return atoms


def _generate_rx_ucb_candidates(
    max_candidates: int,
    blocked: set[str],
    policy: dict[str, Any],
    *,
    include_residual: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    atoms = _raw_atoms()
    for atom in atoms:
        for transform, expression in {
            "rank": f"CSRank(ZScore({atom['expr']}))",
            "inverted": f"Neg(CSRank(ZScore({atom['expr']})))",
        }.items():
            _add_candidate(
                rows,
                seen,
                blocked,
                expression,
                lane=f"{atom['lane']}::{transform}",
                source_generator="phase3bp_true1min_rx_ucb_native",
                note=f"rx atom transform {atom['name']}",
                policy=policy,
            )
    event_atoms = [atom for atom in atoms if atom["side"] == "event"]
    state_atoms = [atom for atom in atoms if atom["side"] == "state"]
    for left in event_atoms:
        for right in state_atoms:
            if left["name"].split("_")[0] == right["name"].split("_")[0]:
                continue
            lane = f"rx_interaction::{left['lane']}::{right['lane']}"
            variants = {
                "product": f"CSRank(Mul(ZScore({left['expr']}),ZScore({right['expr']})))",
                "spread": f"CSRank(Sub(ZScore({left['expr']}),ZScore({right['expr']})))",
            }
            if include_residual:
                variants["residual"] = f"CSRank(CSResidual(CSRank({left['expr']}),CSRank({right['expr']})))"
            for kind, expression in variants.items():
                _add_candidate(
                    rows,
                    seen,
                    blocked,
                    expression,
                    lane=f"{lane}::{kind}",
                    source_generator="phase3bp_true1min_rx_ucb_native",
                    note=f"rx interaction {left['name']} x {right['name']} {kind}",
                    policy=policy,
                )
    rows.sort(key=lambda row: (float(row.get("policy_score") or 0.0), -int(row.get("max_window") or 0), row["expression_hash"]), reverse=True)
    selected: list[dict[str, Any]] = []
    lane_counts: Counter[str] = Counter()
    fieldset_counts: Counter[str] = Counter()
    lane_cap = max(3, int(math.ceil(max_candidates * 0.10)))
    fieldset_cap = 4
    for row in rows:
        lane = str(row.get("factor_lane"))
        fieldset = str(row.get("fields"))
        if lane_counts[lane] >= lane_cap:
            continue
        if fieldset_counts[fieldset] >= fieldset_cap:
            continue
        selected.append(row)
        lane_counts[lane] += 1
        fieldset_counts[fieldset] += 1
        if len(selected) >= max_candidates:
            break
    return selected


def _aggregate_decisions(
    aggregate_rows: list[dict[str, Any]],
    pairwise_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    candidate_meta = {str(row.get("expression_hash")): dict(row) for row in candidates}
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
        meta = candidate_meta.get(expr_hash, {})
        for key in ("candidate_id", "source_generator", "source_lane", "policy_score", "note"):
            if key in meta:
                best[key] = meta[key]
        stable = sum(1 for row in rows if abs(_f(row.get("aligned_ic_mean"), 0.0)) > 0.02)
        inherited = {item.strip() for item in str(best.get("blocker_flags") or "").split("|") if item.strip()}
        blockers: list[str] = []
        if expr_hash in crowded:
            blockers.append("signal_corr_abs_ge_0.75")
        if "future_signal_wrong_lag_too_strong" in inherited:
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
        best["phase3bp_blocker_flags"] = "|".join(blockers)
        best["phase3bp_decision"] = "bp_followup_priority" if not blockers and abs_ic > 0.035 else "bp_watch_or_reject"
        decisions.append(best)
    decisions.sort(key=lambda item: (_f(item.get("abs_aligned_ic_mean"), -999.0), int(item.get("positive_horizon_count") or 0)), reverse=True)
    return decisions[:top_n]


def _summarize_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    out: list[dict[str, Any]] = []
    for value, items in grouped.items():
        out.append(
            {
                key: value,
                "count": len(items),
                "best_abs_aligned_ic": max((abs(_f(row.get("aligned_ic_mean"), 0.0)) for row in items), default=None),
                "followup_count": sum(1 for row in items if row.get("phase3bp_decision") == "bp_followup_priority"),
                "future_wrong_lag_count": sum(1 for row in items if "future_signal_wrong_lag_too_strong" in str(row.get("phase3bp_blocker_flags") or "")),
            }
        )
    out.sort(key=lambda row: (_f(row.get("best_abs_aligned_ic"), -999.0), int(row.get("followup_count") or 0)), reverse=True)
    return out


def _render_md(summary: dict[str, Any], generator_rows: list[dict[str, Any]], lane_rows: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3BP True-1min Search Algorithm Smoke 2026-06-15",
        "",
        f"Decision: `{summary['decision']}`",
        "",
        "## Scope",
        "",
        f"- generator mode: `{summary['generator_mode']}`",
        f"- candidates generated: `{summary['candidate_count']}`",
        f"- true-1min shard panels: `{summary['panel_count']}`",
        f"- sampled signal trade_times per shard: `{summary['sample_trade_times_per_shard']}`",
        f"- total eval rows: `{summary['total_eval_rows']}`",
        f"- followup priority: `{summary['followup_priority_count']}`",
        "",
        "## Generator Comparison",
        "",
        "| generator | count | best abs aligned IC | followup | future-wrong-lag |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in generator_rows:
        lines.append(
            f"| `{row['source_generator']}` | {row['count']} | {_fmt(row.get('best_abs_aligned_ic'))} | {row['followup_count']} | {row['future_wrong_lag_count']} |"
        )
    lines.extend(["", "## Lane Summary", "", "| lane | count | best abs aligned IC | followup | future-wrong-lag |", "|---|---:|---:|---:|---:|"])
    for row in lane_rows[:20]:
        lines.append(
            f"| `{row['factor_lane']}` | {row['count']} | {_fmt(row.get('best_abs_aligned_ic'))} | {row['followup_count']} | {row['future_wrong_lag_count']} |"
        )
    lines.extend(["", "## Top Decisions", "", "| rank | generator | lane | h | fields | abs IC | direction | turnover | decision | blockers |", "|---:|---|---|---:|---|---:|---|---:|---|---|"])
    for idx, row in enumerate(decisions[:25], 1):
        lines.append(
            f"| {idx} | `{row.get('source_generator')}` | `{row.get('factor_lane')}` | {row.get('horizon_min')} | `{row.get('fields')}` | "
            f"{_fmt(row.get('abs_aligned_ic_mean'))} | `{row.get('open_direction')}` | {_fmt(row.get('mean_one_way_turnover'))} | "
            f"`{row.get('phase3bp_decision')}` | `{row.get('phase3bp_blocker_flags') or ''}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This tests the search algorithm, not production alpha.",
            "- `future_signal_wrong_lag_too_strong` is treated as a hard smoke blocker.",
            "- True `trade_time` 1min shards only; no old 1D stock-PIT default panel.",
            "- X0/R3 remains read-only.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-root", type=Path, default=DEFAULT_SHARD_ROOT)
    parser.add_argument("--memory-root", type=Path, default=DEFAULT_MEMORY_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-candidates", type=int, default=160)
    parser.add_argument("--top-decisions", type=int, default=48)
    parser.add_argument("--max-shards", type=int, default=8)
    parser.add_argument("--sample-trade-times-per-shard", type=int, default=60)
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=20)
    parser.add_argument("--policy-exploration", type=float, default=0.45)
    parser.add_argument("--include-residual", action="store_true")
    args = parser.parse_args(argv)

    output_root = _resolve(args.output_root)
    report_root = _resolve(args.report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    policy = _build_policy(PRIOR_DECISION_FILES, exploration=args.policy_exploration)
    blocked = _load_memory_hashes(args.memory_root) | _prior_hashes(PRIOR_HASH_FILES)
    candidates = _generate_rx_ucb_candidates(
        args.max_candidates,
        blocked,
        policy,
        include_residual=bool(args.include_residual),
    )
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
    decisions = _aggregate_decisions(aggregate_rows, pairwise_rows, candidates, args.top_decisions)
    generator_rows = _summarize_by(decisions, "source_generator")
    lane_rows = _summarize_by(decisions, "factor_lane")
    total_eval_rows = sum(int(shard.get("eval_rows") or 0) for shard in meta["shards"])
    followup_count = sum(1 for row in decisions if row.get("phase3bp_decision") == "bp_followup_priority")
    best_followup = next((row for row in decisions if row.get("phase3bp_decision") == "bp_followup_priority"), None)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_COMPLETE_DIAGNOSTIC_ONLY",
        "generator_mode": "true1min_rx_ucb_native_smoke",
        "include_residual": bool(args.include_residual),
        "candidate_count": len(candidates),
        "blocked_hash_count": len(blocked),
        "panel_count": len(panels),
        "sample_trade_times_per_shard": args.sample_trade_times_per_shard,
        "horizons_min": list(horizons),
        "total_eval_rows": total_eval_rows,
        "followup_priority_count": followup_count,
        "best_followup": best_followup,
        "policy": policy,
        "output_root": str(output_root),
        "report_root": str(report_root),
        "hard_boundary": [
            "true trade_time minute panels only",
            "old daily stock-PIT default dataset not used",
            "search algorithm smoke only, not production proof",
            "future wrong-lag is a hard blocker",
            "X0/R3 read-only",
        ],
        **meta,
    }
    _write_csv(output_root / "phase3bp_candidate_pack.csv", candidates)
    _write_csv(output_root / "phase3bp_candidate_horizon_shard_metrics.csv", metric_rows)
    _write_csv(output_root / "phase3bp_candidate_horizon_aggregate.csv", aggregate_rows)
    _write_csv(output_root / "phase3bp_pairwise_signal_rank_corr.csv", pairwise_rows)
    _write_csv(output_root / "phase3bp_top_decisions.csv", decisions)
    _write_json(output_root / "phase3bp_true1min_search_algorithm_summary.json", summary)
    _write_csv(report_root / "phase3bp_candidate_pack.csv", candidates)
    _write_csv(report_root / "phase3bp_top_decisions.csv", decisions)
    _write_csv(report_root / "phase3bp_generator_summary.csv", generator_rows)
    _write_csv(report_root / "phase3bp_lane_summary.csv", lane_rows)
    _write_json(report_root / "phase3bp_true1min_search_algorithm_summary.json", {**summary, "top_decisions": decisions[:12]})
    (report_root / "PHASE3BP_TRUE1MIN_SEARCH_ALGORITHM_SMOKE_20260615.md").write_text(
        _render_md(summary, generator_rows, lane_rows, decisions),
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
