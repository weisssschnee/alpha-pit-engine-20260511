"""Freeze Phase3L daily proof objects and generate stress/proof pack artifacts.

No search is run here. This script locks:

* 9-cluster research pool,
* 6-cluster candidate book,
* 3-cluster oracle diagnostic combo.

It also runs daily-only stress diagnostics for the 6-cluster candidate book.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.runtime.phase3l_n_factor_strength_frontier import (
    _book_metrics,
    _load_daily_matrix,
    _max_drawdown,
    _read_csv,
    _round,
    _safe_float,
    _sharpe,
    _sortino,
    _write_csv,
    _write_json,
)


DEFAULT_BOOK = Path("reports/phase3l_k_daily_proof_book_20260517/phase3l_daily_strong_proof_book.csv")
DEFAULT_DAILY_RETURNS = Path("reports/phase3l_l_regime_proxy_audit_20260517/phase3l_l_daily_returns_by_survivor.csv")
DEFAULT_CLUSTER_STRENGTH = Path("reports/phase3l_n_factor_strength_frontier_20260517/phase3l_n_cluster_strength.csv")
DEFAULT_FRONTIER = Path("reports/phase3l_n_factor_strength_frontier_20260517/phase3l_n_factor_strength_frontier.json")
DEFAULT_REGIME_AXIS = Path("reports/phase3l_l_regime_proxy_audit_20260517/phase3l_l_regime_proxy_axis_summary.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517")

CANDIDATE_CLUSTERS = ("cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004")
ORACLE_DIAGNOSTIC_CLUSTERS = ("cluster_005", "cluster_003", "cluster_004")
DEFAULT_COST_BPS = 10.0


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _book_return(clusters: tuple[str, ...], matrix: pd.DataFrame) -> pd.Series:
    return matrix.loc[:, list(clusters)].mean(axis=1, skipna=True)


def _daily_turnover_matrix(daily_rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(daily_rows)
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["average_one_way_turnover"] = pd.to_numeric(frame["average_one_way_turnover"], errors="coerce")
    frame["global_signal_cluster_id"] = frame["global_signal_cluster_id"].astype(str)
    return frame.pivot_table(
        index="date",
        columns="global_signal_cluster_id",
        values="average_one_way_turnover",
        aggfunc="mean",
    ).sort_index()


def _net_book_metrics(
    clusters: tuple[str, ...],
    *,
    return_matrix: pd.DataFrame,
    turnover_matrix: pd.DataFrame,
    cost_bps: float,
    multiplier: float,
) -> dict[str, Any]:
    gross = _book_return(clusters, return_matrix)
    turnover = turnover_matrix.loc[:, [cluster for cluster in clusters if cluster in turnover_matrix.columns]].mean(axis=1, skipna=True)
    net = gross - turnover.fillna(0.0) * (cost_bps / 10000.0) * multiplier
    return {
        "cost_multiplier": multiplier,
        "cost_bps": cost_bps,
        "cluster_count": len(clusters),
        "mean_net_return": _round(net.mean(), 8),
        "sortino_proxy": _round(_sortino(net)),
        "sharpe_proxy": _round(_sharpe(net)),
        "max_drawdown_proxy": _round(_max_drawdown(net), 8),
        "hit_rate": _round((net.dropna() > 0).mean()),
        "mean_turnover": _round(turnover.mean()),
        "p90_turnover": _round(float(turnover.dropna().quantile(0.9)) if not turnover.dropna().empty else None),
    }


def _source_capped_subset(candidate: tuple[str, ...], strength_rows: dict[str, dict[str, Any]], max_per_source: int) -> tuple[str, ...]:
    selected: list[str] = []
    counts: Counter[str] = Counter()
    for cluster in sorted(candidate, key=lambda item: _safe_float(strength_rows[item].get("strength_score"), 0.0) or 0.0, reverse=True):
        source = str(strength_rows[cluster].get("source_lane") or "unknown")
        if counts[source] >= max_per_source:
            continue
        selected.append(cluster)
        counts[source] += 1
    return tuple(selected)


def _candidate_stress(
    *,
    candidate: tuple[str, ...],
    matrix: pd.DataFrame,
    turnover_matrix: pd.DataFrame,
    meta: dict[str, dict[str, Any]],
    corr: pd.DataFrame,
    strength_rows: dict[str, dict[str, Any]],
    cost_bps: float,
) -> dict[str, list[dict[str, Any]]]:
    base = _book_metrics(candidate, matrix=matrix, cluster_meta=meta, corr=corr, label="candidate_book_6")
    leave_one: list[dict[str, Any]] = []
    for cluster in candidate:
        subset = tuple(item for item in candidate if item != cluster)
        metrics = _book_metrics(subset, matrix=matrix, cluster_meta=meta, corr=corr, label=f"remove_{cluster}")
        metrics["removed_cluster"] = cluster
        metrics["sortino_delta_vs_candidate"] = _round((_safe_float(metrics.get("sortino_proxy"), 0.0) or 0.0) - (_safe_float(base.get("sortino_proxy"), 0.0) or 0.0))
        metrics["mean_return_delta_vs_candidate"] = _round((_safe_float(metrics.get("mean_daily_return"), 0.0) or 0.0) - (_safe_float(base.get("mean_daily_return"), 0.0) or 0.0), 8)
        leave_one.append(metrics)

    cost_stress = [
        _net_book_metrics(candidate, return_matrix=matrix, turnover_matrix=turnover_matrix, cost_bps=cost_bps, multiplier=multiplier)
        for multiplier in (1.0, 2.0, 3.0)
    ]

    turnover_stress: list[dict[str, Any]] = []
    for cap in (0.10, 0.12, 0.15, 0.20):
        subset = tuple(cluster for cluster in candidate if (_safe_float(meta[cluster].get("turnover"), 1.0) or 1.0) <= cap)
        if not subset:
            turnover_stress.append({"turnover_cap": cap, "cluster_count": 0})
            continue
        metrics = _book_metrics(subset, matrix=matrix, cluster_meta=meta, corr=corr, label=f"turnover_cap_{cap}")
        metrics["turnover_cap"] = cap
        turnover_stress.append(metrics)

    source_cap_subset = _source_capped_subset(candidate, strength_rows, max_per_source=2)
    source_cap = [_book_metrics(source_cap_subset, matrix=matrix, cluster_meta=meta, corr=corr, label="source_cap_max2")]

    daily = pd.DataFrame({"date": matrix.index, "book_return": _book_return(candidate, matrix).values})
    daily["window"] = daily["date"].map(lambda item: f"{int(item.year)}Q{((int(item.month) - 1) // 3) + 1}")
    subperiod: list[dict[str, Any]] = []
    for window in sorted(daily["window"].dropna().unique()):
        kept = daily[daily["window"] != window]["book_return"]
        subperiod.append(
            {
                "left_out_window": window,
                "remaining_day_count": int(kept.dropna().shape[0]),
                "mean_return": _round(kept.mean(), 8),
                "sortino_proxy": _round(_sortino(kept)),
                "sharpe_proxy": _round(_sharpe(kept)),
                "hit_rate": _round((kept.dropna() > 0).mean()),
                "max_drawdown_proxy": _round(_max_drawdown(kept), 8),
            }
        )

    return {
        "base": [base],
        "leave_one_cluster_out": leave_one,
        "cost_stress": cost_stress,
        "turnover_stress": turnover_stress,
        "source_cap_stress": source_cap,
        "subperiod_leave_one_out": subperiod,
    }


def _role(cluster: str, candidate: tuple[str, ...], oracle: tuple[str, ...], strength_rank: int) -> str:
    if cluster in candidate and strength_rank <= 4:
        return "core"
    if cluster in candidate:
        return "support"
    if cluster in oracle:
        return "diagnostic_oracle_only"
    return "watch"


def _cluster_cards(
    *,
    research_rows: list[dict[str, Any]],
    candidate: tuple[str, ...],
    oracle: tuple[str, ...],
    regime_axis_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    axis_by_cluster: dict[str, list[dict[str, str]]] = {}
    for row in regime_axis_rows:
        axis_by_cluster.setdefault(str(row.get("global_signal_cluster_id")), []).append(row)
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(research_rows, start=1):
        cluster = str(row.get("global_signal_cluster_id"))
        axes = axis_by_cluster.get(cluster, [])
        weak_axes = [
            f"{axis.get('regime_axis')}:{axis.get('axis_decision')}"
            for axis in axes
            if str(axis.get("axis_decision", "")).startswith("HOLD")
        ]
        sign_flip_score = _safe_float(row.get("sign_flip_score"), 0.0) or 0.0
        weakness: list[str] = []
        if cluster in oracle and cluster not in candidate:
            weakness.append("oracle_member_not_formal_selection_rule")
        if sign_flip_score > 0.0:
            weakness.append("positive_sign_flip_score_but_placebo_not_passed")
        if (_safe_float(row.get("turnover"), 0.0) or 0.0) > 0.15:
            weakness.append("high_turnover")
        if weak_axes:
            weakness.append("weak_regime_proxy_axes=" + ";".join(weak_axes[:3]))
        if not weakness:
            weakness.append("no_major_daily_proxy_weakness")
        cards.append(
            {
                "rank": index,
                "cluster_id": cluster,
                "role_in_candidate_book": _role(cluster, candidate, oracle, index),
                "representative_expression": row.get("expression"),
                "source_cluster_id": row.get("source_cluster_id"),
                "source_lane": row.get("source_lane"),
                "entry_type": row.get("entry_type"),
                "strength_score": row.get("strength_score"),
                "daily_sortino_proxy": row.get("daily_sortino_proxy"),
                "strict_cost_adjusted_sortino": row.get("strict_cost_adjusted_sortino"),
                "turnover": row.get("turnover"),
                "daily_hit_rate": row.get("daily_hit_rate"),
                "sign_flip_score": row.get("sign_flip_score"),
                "sign_flip_result": "PASS_PLACEBO_FAILED" if sign_flip_score <= 0.0 else "PLACEBO_SCORE_POSITIVE_BUT_NOT_PASSING",
                "regime_proxy_result": row.get("regime_proxy_decision"),
                "regime_axis_pass_count": row.get("regime_axis_pass_count"),
                "known_weakness": "|".join(weakness),
                "decision": "candidate_book_member" if cluster in candidate else "research_pool_only",
            }
        )
    return cards


def _render_decision_record(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase3L Daily Proof Decision Record",
        "",
        "- decision: `PASS_DAILY_STRONG_PROOF_BOOK_L2_5`",
        "- evidence_level: `L2.5_daily_strong_proof_no_execution`",
        f"- created_at: {summary['created_at']}",
        "",
        "## Frozen Objects",
        "",
        f"- Research pool: `{summary['research_pool']['cluster_count']}` clusters: `{ '|'.join(summary['research_pool']['clusters']) }`",
        f"- Candidate book: `{summary['candidate_book']['cluster_count']}` clusters: `{ '|'.join(summary['candidate_book']['clusters']) }`",
        f"- Oracle combo: `{ '|'.join(summary['oracle_combo']['clusters']) }`",
        "",
        "The oracle combo is diagnostic only. It is not allowed as a formal selection rule because it is an in-sample best subset.",
        "",
        "## Confirmed",
        "",
        "- 9 global signal clusters survive daily proof filters.",
        "- Sign-flip placebo: 0 pass in the globally reclustered survivor audit.",
        "- Regime proxy audit: 9/9 pass on lagged daily multi-axis proxy.",
        "- 6-cluster balanced candidate book selected and frozen.",
        "",
        "## Not Confirmed",
        "",
        "- production readiness",
        "- true execution",
        "- true capacity",
        "- minute slippage",
        "- live / paper survival",
        "- true regime replay",
        "",
        "## Next",
        "",
        "- Run daily locked forward/shadow append only.",
        "- Buy or connect 1min pilot data before execution/capacity claims.",
        "",
    ]
    return "\n".join(lines)


def _render_proof_pack(summary: dict[str, Any], cards: list[dict[str, Any]], stress: dict[str, list[dict[str, Any]]]) -> str:
    candidate = summary["candidate_book"]["metrics"]
    lines = [
        "# Phase3L Alpha Proof Pack",
        "",
        f"- decision: `{summary['decision']}`",
        f"- evidence_level: `{summary['evidence_level']}`",
        f"- candidate_book_clusters: {summary['candidate_book']['cluster_count']}",
        f"- candidate_sortino_proxy: {candidate.get('sortino_proxy')}",
        f"- candidate_p90_turnover: {candidate.get('p90_turnover')}",
        "",
        "## Candidate Book",
        "",
        "| cluster | role | strength | daily_sortino | strict_sortino | turnover | source | weakness |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for card in cards:
        if card["cluster_id"] not in summary["candidate_book"]["clusters"]:
            continue
        lines.append(
            "| {cluster_id} | {role_in_candidate_book} | {strength_score} | {daily_sortino_proxy} | {strict_cost_adjusted_sortino} | {turnover} | {source_lane} | {known_weakness} |".format(
                **card
            )
        )
    lines.extend(
        [
            "",
            "## Leave-One-Out Stress",
            "",
            "| removed | clusters | sortino | delta | p90_turnover |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in stress["leave_one_cluster_out"]:
        lines.append(
            f"| {row.get('removed_cluster')} | {row.get('cluster_count')} | {row.get('sortino_proxy')} | {row.get('sortino_delta_vs_candidate')} | {row.get('p90_turnover')} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This is daily proof, not production proof.",
            "- Oracle combo is diagnostic only.",
            "- Minute execution/capacity and live/paper survival remain blockers.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    *,
    book_path: Path,
    daily_returns_path: Path,
    cluster_strength_path: Path,
    frontier_path: Path,
    regime_axis_path: Path,
    output_root: Path,
    cost_bps: float,
) -> dict[str, Any]:
    book_rows = _read_csv(book_path)
    daily_rows = _read_csv(daily_returns_path)
    strength_rows_list = _read_csv(cluster_strength_path)
    regime_axis_rows = _read_csv(regime_axis_path)
    frontier = _read_json(frontier_path)

    matrix = _load_daily_matrix(daily_rows)
    turnover_matrix = _daily_turnover_matrix(daily_rows)
    corr = matrix.corr().fillna(0.0)
    meta = {str(row["global_signal_cluster_id"]): dict(row) for row in book_rows}
    strength_rows = {str(row["global_signal_cluster_id"]): dict(row) for row in strength_rows_list}
    research_clusters = tuple(str(row.get("global_signal_cluster_id")) for row in book_rows)
    candidate_clusters = CANDIDATE_CLUSTERS
    oracle_clusters = ORACLE_DIAGNOSTIC_CLUSTERS

    candidate_metrics = _book_metrics(candidate_clusters, matrix=matrix, cluster_meta=meta, corr=corr, label="candidate_book_6_locked")
    research_metrics = _book_metrics(research_clusters, matrix=matrix, cluster_meta=meta, corr=corr, label="research_pool_9_locked")
    oracle_metrics = _book_metrics(oracle_clusters, matrix=matrix, cluster_meta=meta, corr=corr, label="oracle_diagnostic_3_locked")
    stress = _candidate_stress(
        candidate=candidate_clusters,
        matrix=matrix,
        turnover_matrix=turnover_matrix,
        meta=meta,
        corr=corr,
        strength_rows=strength_rows,
        cost_bps=cost_bps,
    )
    cards = _cluster_cards(
        research_rows=strength_rows_list,
        candidate=candidate_clusters,
        oracle=oracle_clusters,
        regime_axis_rows=regime_axis_rows,
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_o_daily_proof_freeze_pack",
        "decision": "PASS_DAILY_STRONG_PROOF_BOOK_L2_5",
        "evidence_level": "L2.5_daily_strong_proof_no_execution",
        "scope": "frozen_daily_proof_objects_no_new_search",
        "inputs": {
            "book_path": str(book_path),
            "book_sha256": _sha256(book_path),
            "daily_returns_path": str(daily_returns_path),
            "daily_returns_sha256": _sha256(daily_returns_path),
            "cluster_strength_path": str(cluster_strength_path),
            "frontier_path": str(frontier_path),
        },
        "research_pool": {
            "cluster_count": len(research_clusters),
            "clusters": list(research_clusters),
            "metrics": research_metrics,
        },
        "candidate_book": {
            "cluster_count": len(candidate_clusters),
            "clusters": list(candidate_clusters),
            "metrics": candidate_metrics,
        },
        "oracle_combo": {
            "status": "diagnostic_only_not_formal_selection_rule",
            "clusters": list(oracle_clusters),
            "metrics": oracle_metrics,
            "source_frontier_oracle": frontier.get("oracle_best_subset", {}),
        },
        "not_confirmed": [
            "production_readiness",
            "true_execution",
            "true_capacity",
            "minute_slippage",
            "live_or_paper_survival",
            "true_regime_replay",
        ],
        "outputs": {
            "decision_record_md": str(output_root / "PHASE3L_DAILY_PROOF_DECISION_RECORD_2026-05-17.md"),
            "freeze_json": str(output_root / "phase3l_locked_daily_proof_objects.json"),
            "candidate_book_csv": str(output_root / "phase3l_candidate_book_6_clusters.csv"),
            "alpha_cards_csv": str(output_root / "phase3l_alpha_cards.csv"),
            "stress_json": str(output_root / "phase3l_candidate_book_stress_report.json"),
            "proof_pack_md": str(output_root / "PHASE3L_ALPHA_PROOF_PACK_2026-05-17.md"),
        },
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "phase3l_locked_daily_proof_objects.json", summary)
    _write_json(output_root / "phase3l_candidate_book_stress_report.json", {"summary": summary, "stress": stress})
    _write_csv(output_root / "phase3l_candidate_book_6_clusters.csv", [card for card in cards if card["cluster_id"] in candidate_clusters])
    _write_csv(output_root / "phase3l_alpha_cards.csv", cards)
    for name, rows in stress.items():
        _write_csv(output_root / f"phase3l_stress_{name}.csv", rows)
    (output_root / "PHASE3L_DAILY_PROOF_DECISION_RECORD_2026-05-17.md").write_text(
        _render_decision_record(summary),
        encoding="utf-8",
    )
    (output_root / "PHASE3L_ALPHA_PROOF_PACK_2026-05-17.md").write_text(
        _render_proof_pack(summary, cards, stress),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--cluster-strength", type=Path, default=DEFAULT_CLUSTER_STRENGTH)
    parser.add_argument("--frontier", type=Path, default=DEFAULT_FRONTIER)
    parser.add_argument("--regime-axis", type=Path, default=DEFAULT_REGIME_AXIS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        book_path=args.book,
        daily_returns_path=args.daily_returns,
        cluster_strength_path=args.cluster_strength,
        frontier_path=args.frontier,
        regime_axis_path=args.regime_axis,
        output_root=args.output_root,
        cost_bps=args.cost_bps,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
