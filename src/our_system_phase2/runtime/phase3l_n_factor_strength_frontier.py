"""Phase3L-N factor strength frontier for the frozen daily proof book.

This is a no-search, daily-only audit. It estimates:

* strongest single daily-proof cluster,
* in-sample theoretical equal-weight subset upper bound,
* best current selectable daily-proof subset under diversification/turnover
  constraints.

It does not claim production readiness, true book marginal value, or minute
execution capacity.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_BOOK = Path("reports/phase3l_k_daily_proof_book_20260517/phase3l_daily_strong_proof_book.csv")
DEFAULT_DAILY_RETURNS = Path("reports/phase3l_l_regime_proxy_audit_20260517/phase3l_l_daily_returns_by_survivor.csv")
DEFAULT_REGIME_PROXY = Path("reports/phase3l_l_regime_proxy_audit_20260517/phase3l_l_regime_proxy_cluster_summary.csv")
DEFAULT_MINUTE_PREFLIGHT = Path("reports/phase3l_m_minute_execution_preflight_20260517/phase3l_m_minute_execution_preflight.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3l_n_factor_strength_frontier_20260517")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, ndigits: int = 6) -> float | None:
    number = _safe_float(value)
    return round(float(number), ndigits) if number is not None else None


def _quantile(values: list[float], q: float) -> float | None:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return clean[int(pos)]
    return clean[lo] * (hi - pos) + clean[hi] * (pos - lo)


def _sortino(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    downside = clean[clean < 0]
    if downside.empty:
        return round(float(clean.mean()), 6)
    std = float(downside.std(ddof=0))
    if not math.isfinite(std) or std <= 1e-12:
        return None
    return round(float(clean.mean() / std * math.sqrt(len(clean))), 6)


def _sharpe(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    std = float(clean.std(ddof=0))
    if not math.isfinite(std) or std <= 1e-12:
        return None
    return round(float(clean.mean() / std * math.sqrt(len(clean))), 6)


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return None
    curve = clean.cumsum()
    drawdown = curve - curve.cummax()
    return round(float(drawdown.min()), 8)


def _rank01(values: dict[str, float | None], *, lower_is_better: bool = False) -> dict[str, float]:
    clean = {key: value for key, value in values.items() if value is not None and math.isfinite(float(value))}
    if not clean:
        return {key: 0.5 for key in values}
    ordered = sorted(clean.items(), key=lambda item: float(item[1]), reverse=not lower_is_better)
    if len(ordered) == 1:
        ranks = {ordered[0][0]: 1.0}
    else:
        ranks = {key: 1.0 - index / (len(ordered) - 1) for index, (key, _value) in enumerate(ordered)}
    return {key: round(float(ranks.get(key, 0.0)), 6) for key in values}


def _load_daily_matrix(daily_rows: list[dict[str, str]]) -> pd.DataFrame:
    frame = pd.DataFrame(daily_rows)
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["long_short_return"] = pd.to_numeric(frame["long_short_return"], errors="coerce")
    frame["global_signal_cluster_id"] = frame["global_signal_cluster_id"].astype(str)
    pivot = frame.pivot_table(
        index="date",
        columns="global_signal_cluster_id",
        values="long_short_return",
        aggfunc="mean",
    ).sort_index()
    return pivot


def _book_metrics(
    clusters: tuple[str, ...],
    *,
    matrix: pd.DataFrame,
    cluster_meta: dict[str, dict[str, Any]],
    corr: pd.DataFrame,
    label: str,
) -> dict[str, Any]:
    sub = matrix.loc[:, list(clusters)].copy()
    book_return = sub.mean(axis=1, skipna=True)
    turnovers = [_safe_float(cluster_meta[cluster].get("turnover"), 0.0) or 0.0 for cluster in clusters]
    sources = Counter(str(cluster_meta[cluster].get("source_lane") or "unknown") for cluster in clusters)
    entry_types = Counter(str(cluster_meta[cluster].get("entry_type") or "unknown") for cluster in clusters)
    pair_corrs: list[float] = []
    for left, right in itertools.combinations(clusters, 2):
        value = _safe_float(corr.loc[left, right] if left in corr.index and right in corr.columns else None)
        if value is not None:
            pair_corrs.append(value)
    source_top_share = max(sources.values()) / max(1, len(clusters)) if sources else None
    return {
        "book_label": label,
        "cluster_count": len(clusters),
        "clusters": "|".join(clusters),
        "source_distribution": json.dumps(dict(sorted(sources.items())), ensure_ascii=False),
        "entry_type_distribution": json.dumps(dict(sorted(entry_types.items())), ensure_ascii=False),
        "source_top_share": _round(source_top_share),
        "mean_daily_return": _round(book_return.mean(), 8),
        "median_daily_return": _round(book_return.median(), 8),
        "hit_rate": _round((book_return.dropna() > 0).mean()),
        "sortino_proxy": _round(_sortino(book_return)),
        "sharpe_proxy": _round(_sharpe(book_return)),
        "max_drawdown_proxy": _round(_max_drawdown(book_return), 8),
        "median_turnover": _round(_quantile(turnovers, 0.5)),
        "p90_turnover": _round(_quantile(turnovers, 0.9)),
        "max_turnover": _round(max(turnovers) if turnovers else None),
        "mean_pairwise_corr": _round(float(np.mean(pair_corrs)) if pair_corrs else 0.0),
        "max_pairwise_corr": _round(float(np.max(pair_corrs)) if pair_corrs else 0.0),
        "min_score": _round(min((_safe_float(cluster_meta[cluster].get("score"), 0.0) or 0.0) for cluster in clusters)),
        "median_score": _round(_quantile([_safe_float(cluster_meta[cluster].get("score"), 0.0) or 0.0 for cluster in clusters], 0.5)),
        "min_strict_cost_adjusted_sortino": _round(
            min((_safe_float(cluster_meta[cluster].get("strict_cost_adjusted_sortino"), 0.0) or 0.0) for cluster in clusters)
        ),
    }


def _cluster_strength_rows(
    *,
    book_rows: list[dict[str, str]],
    regime_rows: list[dict[str, str]],
    matrix: pd.DataFrame,
    corr: pd.DataFrame,
) -> list[dict[str, Any]]:
    regime_by_cluster = {str(row.get("global_signal_cluster_id")): row for row in regime_rows}
    base: dict[str, dict[str, Any]] = {}
    for row in book_rows:
        cluster = str(row.get("global_signal_cluster_id"))
        series = matrix[cluster] if cluster in matrix.columns else pd.Series(dtype=float)
        peer_corrs = []
        if cluster in corr.index:
            peer_corrs = [
                abs(float(value))
                for other, value in corr.loc[cluster].items()
                if other != cluster and pd.notna(value)
            ]
        regime = regime_by_cluster.get(cluster, {})
        base[cluster] = {
            "global_signal_cluster_id": cluster,
            "source_cluster_id": row.get("source_cluster_id"),
            "entry_type": row.get("entry_type"),
            "source_lane": row.get("source_lane"),
            "score": _safe_float(row.get("score")),
            "turnover": _safe_float(row.get("turnover")),
            "strict_cost_adjusted_sortino": _safe_float(row.get("strict_cost_adjusted_sortino")),
            "sign_flip_score": _safe_float(row.get("sign_flip_score")),
            "daily_sortino_proxy": _sortino(series),
            "daily_sharpe_proxy": _sharpe(series),
            "daily_hit_rate": float((pd.to_numeric(series, errors="coerce").dropna() > 0).mean()) if not series.dropna().empty else None,
            "mean_daily_return": float(pd.to_numeric(series, errors="coerce").mean()) if not series.dropna().empty else None,
            "avg_abs_corr_to_other_survivors": float(np.mean(peer_corrs)) if peer_corrs else 0.0,
            "max_abs_corr_to_other_survivors": float(np.max(peer_corrs)) if peer_corrs else 0.0,
            "regime_proxy_decision": regime.get("proxy_decision"),
            "regime_axis_pass_count": _safe_float(regime.get("axis_pass_count"), 0.0),
            "regime_usable_axis_count": _safe_float(regime.get("usable_axis_count"), 0.0),
            "expression": row.get("expression"),
        }
    ranks = {
        "score_rank": _rank01({k: v.get("score") for k, v in base.items()}),
        "strict_rank": _rank01({k: v.get("strict_cost_adjusted_sortino") for k, v in base.items()}),
        "daily_sortino_rank": _rank01({k: v.get("daily_sortino_proxy") for k, v in base.items()}),
        "hit_rank": _rank01({k: v.get("daily_hit_rate") for k, v in base.items()}),
        "turnover_rank": _rank01({k: v.get("turnover") for k, v in base.items()}, lower_is_better=True),
        "corr_rank": _rank01({k: v.get("avg_abs_corr_to_other_survivors") for k, v in base.items()}, lower_is_better=True),
    }
    rows: list[dict[str, Any]] = []
    for cluster, row in base.items():
        regime_component = (row["regime_axis_pass_count"] or 0.0) / max(1.0, row["regime_usable_axis_count"] or 1.0)
        sign_flip_penalty = 0.08 if (row.get("sign_flip_score") or 0.0) > 0.0 else 0.0
        strength = (
            0.22 * ranks["score_rank"][cluster]
            + 0.18 * ranks["strict_rank"][cluster]
            + 0.20 * ranks["daily_sortino_rank"][cluster]
            + 0.12 * ranks["hit_rank"][cluster]
            + 0.12 * ranks["turnover_rank"][cluster]
            + 0.08 * ranks["corr_rank"][cluster]
            + 0.08 * regime_component
            - sign_flip_penalty
        )
        out = dict(row)
        out.update(
            {
                "strength_score": round(float(strength), 6),
                "regime_component": round(float(regime_component), 6),
                "sign_flip_positive_penalty": sign_flip_penalty,
                "daily_hit_rate": _round(row.get("daily_hit_rate")),
                "mean_daily_return": _round(row.get("mean_daily_return"), 8),
                "avg_abs_corr_to_other_survivors": _round(row.get("avg_abs_corr_to_other_survivors")),
                "max_abs_corr_to_other_survivors": _round(row.get("max_abs_corr_to_other_survivors")),
            }
        )
        rows.append(out)
    return sorted(rows, key=lambda item: float(item.get("strength_score") or 0.0), reverse=True)


def _select_balanced_frontier(frontier: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        row
        for row in frontier
        if int(row["cluster_count"]) >= 6
        and (_safe_float(row.get("p90_turnover"), 1.0) or 1.0) <= 0.18
        and (_safe_float(row.get("max_turnover"), 1.0) or 1.0) <= 0.21
        and (_safe_float(row.get("source_top_share"), 1.0) or 1.0) <= 0.50
        and (_safe_float(row.get("max_pairwise_corr"), 1.0) or 1.0) <= 0.95
    ]
    if not candidates:
        candidates = [row for row in frontier if int(row["cluster_count"]) >= 6]
    for row in candidates:
        row["balanced_selection_score"] = round(
            float(row.get("sortino_proxy") or 0.0)
            - 0.60 * float(row.get("p90_turnover") or 0.0)
            - 0.35 * float(row.get("mean_pairwise_corr") or 0.0)
            - 0.25 * float(row.get("source_top_share") or 0.0)
            + 0.04 * int(row.get("cluster_count") or 0),
            6,
        )
    return max(candidates, key=lambda row: float(row.get("balanced_selection_score") or -1e18))


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    strongest = report["strongest_single_cluster"]
    oracle = report["oracle_best_subset"]
    balanced = report["balanced_selectable_subset"]
    lines = [
        "# Phase3L-N Factor Strength Frontier",
        "",
        f"- generated_at: {summary['created_at']}",
        f"- decision: `{summary['decision']}`",
        f"- cluster_count: {summary['cluster_count']}",
        f"- daily_window: {summary['daily_start']} to {summary['daily_end']}",
        "",
        "## Conclusions",
        "",
        f"- Strongest single cluster: `{strongest['global_signal_cluster_id']}` score={strongest['strength_score']} source={strongest['source_lane']}.",
        f"- Theoretical in-sample best equal-weight subset: `{oracle['clusters']}` sortino={oracle['sortino_proxy']} p90_turnover={oracle['p90_turnover']}.",
        f"- Best current selectable subset: `{balanced['clusters']}` sortino={balanced['sortino_proxy']} p90_turnover={balanced['p90_turnover']} source_top_share={balanced['source_top_share']}.",
        f"- Current evidence level: `{summary['current_evidence_level']}`.",
        "",
        "## Evidence Boundary",
        "",
        "- This is daily-only, in-sample over the available validation window.",
        "- The oracle subset is a theoretical upper bound, not a deployable selection rule.",
        "- Minute execution, true capacity, and live validation remain unconfirmed.",
        "",
        "## Top Clusters",
        "",
        "| rank | cluster | strength | score | strict_sortino | daily_sortino | turnover | source | expression |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for index, row in enumerate(report["cluster_strength"][:9], start=1):
        expr = str(row.get("expression") or "")
        if len(expr) > 90:
            expr = expr[:87] + "..."
        lines.append(
            "| {rank} | {cluster} | {strength} | {score} | {strict} | {daily} | {turnover} | {source} | `{expr}` |".format(
                rank=index,
                cluster=row.get("global_signal_cluster_id"),
                strength=row.get("strength_score"),
                score=_round(row.get("score")),
                strict=_round(row.get("strict_cost_adjusted_sortino")),
                daily=_round(row.get("daily_sortino_proxy")),
                turnover=_round(row.get("turnover")),
                source=row.get("source_lane"),
                expr=expr,
            )
        )
    lines.extend(["", "## Outputs", ""])
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def run(
    *,
    book_path: Path,
    daily_returns_path: Path,
    regime_proxy_path: Path,
    minute_preflight_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    book_rows = _read_csv(book_path)
    daily_rows = _read_csv(daily_returns_path)
    regime_rows = _read_csv(regime_proxy_path) if regime_proxy_path.exists() else []
    matrix = _load_daily_matrix(daily_rows)
    corr = matrix.corr().fillna(0.0) if not matrix.empty else pd.DataFrame()
    cluster_meta = {str(row["global_signal_cluster_id"]): dict(row) for row in book_rows}
    cluster_strength = _cluster_strength_rows(book_rows=book_rows, regime_rows=regime_rows, matrix=matrix, corr=corr)

    frontier: list[dict[str, Any]] = []
    clusters = tuple(cluster_meta.keys())
    for size in range(1, len(clusters) + 1):
        for subset in itertools.combinations(clusters, size):
            frontier.append(_book_metrics(subset, matrix=matrix, cluster_meta=cluster_meta, corr=corr, label=f"subset_{size}"))
    oracle_candidates = [row for row in frontier if int(row["cluster_count"]) >= 3]
    oracle = max(oracle_candidates, key=lambda row: float(row.get("sortino_proxy") or -1e18))
    balanced = _select_balanced_frontier(frontier)
    all_book = next(row for row in frontier if int(row["cluster_count"]) == len(clusters))
    strongest = cluster_strength[0] if cluster_strength else {}
    minute_summary: dict[str, Any] = {}
    if minute_preflight_path.exists():
        minute_summary = json.loads(minute_preflight_path.read_text(encoding="utf-8-sig")).get("summary", {})

    current_evidence_level = (
        "LEVEL_3_DAILY_STRONG_PROOF_BOOK_EX_REGIME_AND_EX_MINUTE"
        if len(clusters) >= 8
        and int(all_book.get("cluster_count") or 0) >= 8
        and (minute_summary.get("decision") == "PASS_MINUTE_DATA_AVAILABLE")
        else "LEVEL_2_5_DAILY_STRONG_PROOF_BOOK_NO_EXECUTION_CAPACITY"
    )
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_n_factor_strength_frontier",
        "decision": "PASS_PHASE3L_N_DAILY_FACTOR_STRENGTH_FRONTIER",
        "scope": "daily_only_factor_strength_frontier_no_new_search",
        "cluster_count": len(clusters),
        "daily_start": matrix.index.min().date().isoformat() if not matrix.empty else None,
        "daily_end": matrix.index.max().date().isoformat() if not matrix.empty else None,
        "current_evidence_level": current_evidence_level,
        "theoretical_boundary": "oracle subset is in-sample daily upper bound and must not be used as deployable rule",
        "best_selectable_boundary": "balanced subset is daily-proof selection; execution/capacity still blocked",
        "all_book": all_book,
        "oracle_best_subset": oracle,
        "balanced_selectable_subset": balanced,
        "strongest_single_cluster": strongest,
        "minute_preflight_decision": minute_summary.get("decision"),
        "outputs": {
            "report_json": str(output_root / "phase3l_n_factor_strength_frontier.json"),
            "report_md": str(output_root / "PHASE3L_N_FACTOR_STRENGTH_FRONTIER_2026-05-17.md"),
            "cluster_strength_csv": str(output_root / "phase3l_n_cluster_strength.csv"),
            "book_frontier_csv": str(output_root / "phase3l_n_book_frontier.csv"),
        },
        "remaining_blockers": [
            "true_regime_bucket_replay_not_run",
            "minute_execution_capacity_not_run",
            "live_execution_not_confirmed",
        ],
    }
    report = {
        "summary": summary,
        "cluster_strength": cluster_strength,
        "strongest_single_cluster": strongest,
        "oracle_best_subset": oracle,
        "balanced_selectable_subset": balanced,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "phase3l_n_cluster_strength.csv", cluster_strength)
    _write_csv(output_root / "phase3l_n_book_frontier.csv", sorted(frontier, key=lambda row: float(row.get("sortino_proxy") or -1e18), reverse=True))
    _write_json(output_root / "phase3l_n_factor_strength_frontier.json", report)
    (output_root / "PHASE3L_N_FACTOR_STRENGTH_FRONTIER_2026-05-17.md").write_text(
        _render_markdown(report),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, default=DEFAULT_BOOK)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--regime-proxy", type=Path, default=DEFAULT_REGIME_PROXY)
    parser.add_argument("--minute-preflight", type=Path, default=DEFAULT_MINUTE_PREFLIGHT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        book_path=args.book,
        daily_returns_path=args.daily_returns,
        regime_proxy_path=args.regime_proxy,
        minute_preflight_path=args.minute_preflight,
        output_root=args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
