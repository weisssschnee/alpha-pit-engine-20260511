"""Audit Phase3AB recent/R3 challenger candidates against locked X0/R3.

This is a no-search, no-promotion audit. It takes the strongest Phase3AB
deep-validation candidates, rebuilds their daily portfolio returns on the long
PIT panel, and tests whether they add marginal value to the locked X0/R3
shadow object. Official X0/R3 is read-only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.stock_pit_compact_ensemble import (
    build_stock_pit_compact_top6_daily_portfolio,
)
from our_system_phase2.runtime.phase3ab_candidate_deep_validation import (
    DEFAULT_DATASET,
    EVAL_START,
    FALLBACK_DATASET,
    OOS_2026_END,
    OOS_2026_START,
    SIGNAL_CLOCK_AFTER_OPEN,
    _candidate_daily,
    _max_drawdown,
    _metrics,
    _round,
)
from our_system_phase2.services.real_market_validation import _signal_evaluation_frame
from our_system_phase2.services.real_market_validation import _available_market_panel_usecols, _prepare_market_panel
from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


VERSION = "phase3ab-r3-challenger-audit-v1-2026-05-30"
DEFAULT_INPUT = Path("reports/phase3ab_deep_validation_compare_20260530/phase3ab_deep_deduped_best.csv")
DEFAULT_OUTPUT = Path("reports/phase3ab_r3_challenger_audit_20260530")
DEFAULT_X0_OBJECT = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_X0_DAILY = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_LOAD_START = pd.Timestamp("2025-01-01")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _prefixed(prefix: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}


def _select_candidates(
    rows: list[dict[str, str]],
    *,
    min_oos_sortino: float,
    min_oos_ann: float,
    max_candidates: int,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        expr_hash = str(row.get("expr_hash") or "")
        expression = str(row.get("expression") or "")
        if not expr_hash or not expression or expr_hash in seen:
            continue
        sortino = _float(row.get("oos_2026_net10_sortino"))
        ann = _float(row.get("oos_2026_net10_ann"))
        if sortino is None or ann is None:
            continue
        if sortino < min_oos_sortino or ann < min_oos_ann:
            continue
        selected.append(row)
        seen.add(expr_hash)
        if max_candidates > 0 and len(selected) >= max_candidates:
            break
    return selected


def _load_audit_frame(dataset: Path, load_start: pd.Timestamp) -> pd.DataFrame:
    usecols = _available_market_panel_usecols(dataset)
    frame = pd.read_parquet(dataset, columns=usecols)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"] >= load_start].copy()
    return _prepare_market_panel(frame, source_path=dataset)


def _bucket_by_train_thresholds(values: pd.Series, train_mask: pd.Series, prefix: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = pd.Series(f"{prefix}_unknown", index=numeric.index, dtype=object)
    train_values = numeric[train_mask & numeric.notna()]
    if train_values.nunique(dropna=True) < 3:
        return labels
    q1 = float(train_values.quantile(1 / 3))
    q2 = float(train_values.quantile(2 / 3))
    labels[numeric <= q1] = f"{prefix}_low"
    labels[(numeric > q1) & (numeric <= q2)] = f"{prefix}_mid"
    labels[numeric > q2] = f"{prefix}_high"
    return labels


def _build_official_x0_base(dataset: Path, x0_daily_path: Path) -> pd.DataFrame:
    """Load the locked X0 daily series and rebuild the official R3 gate.

    The locked X0 shadow object was frozen from phase3n daily cluster returns,
    not from the compact top-6 formula helper defaults. Use the frozen daily
    return file as the incumbent source of truth.
    """
    returns = pd.read_csv(x0_daily_path, parse_dates=["date"])
    panel_cols = [
        col
        for col in ["date", "code", "close", "amount", "rt_change_pct"]
        if col in _available_market_panel_usecols(dataset)
    ]
    # Match Phase3O2 exactly: regime state is built from the raw long panel, not
    # the shortened candidate-audit frame. Rolling/lagged market state changes
    # if the panel is truncated.
    regime_panel = pd.read_parquet(dataset, columns=panel_cols)
    regime = build_pit_market_regime_state_frame(regime_panel)
    merged = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    train_mask = (merged["date"] >= "2025-07-01") & (merged["date"] <= "2025-12-31")
    labels = _bucket_by_train_thresholds(merged["liquidity_ratio_lag1"], train_mask, "liquidity")
    merged["liquidity_bucket"] = labels
    merged["R3_liquidity_low"] = labels.eq("liquidity_low")
    merged["x0_net10"] = pd.to_numeric(merged["candidate_book_6"], errors="coerce").fillna(0.0)
    return merged[["date", "x0_net10", "R3_liquidity_low", "liquidity_bucket"]].copy()


def _oos_mask(daily: pd.DataFrame) -> pd.Series:
    date = pd.to_datetime(daily["date"], errors="coerce")
    return (date >= OOS_2026_START) & (date <= OOS_2026_END)


def _align_candidate(base: pd.DataFrame, candidate_daily: pd.DataFrame) -> pd.DataFrame:
    cand = candidate_daily.copy()
    cand["date"] = pd.to_datetime(cand["date"], errors="coerce")
    cand_turnover = pd.to_numeric(cand.get("average_one_way_turnover"), errors="coerce")
    cand_net10 = pd.to_numeric(cand.get("long_net_10bps"), errors="coerce")
    cand_raw = pd.to_numeric(cand.get("long_ret"), errors="coerce")
    keep = pd.DataFrame(
        {
            "date": cand["date"],
            "candidate_net10": cand_net10,
            "candidate_raw": cand_raw,
            "candidate_turnover": cand_turnover,
        }
    )
    return base.merge(keep, on="date", how="left")


def _active_corr(aligned: pd.DataFrame) -> float | None:
    mask = aligned["R3_liquidity_low"].fillna(False).astype(bool) & aligned["candidate_net10"].notna()
    joined = pd.DataFrame(
        {
            "candidate": pd.to_numeric(aligned.loc[mask, "candidate_net10"], errors="coerce").to_numpy(),
            "x0": pd.to_numeric(aligned.loc[mask, "x0_net10"], errors="coerce").to_numpy(),
        }
    ).dropna()
    if len(joined) < 5 or joined["candidate"].nunique() <= 1 or joined["x0"].nunique() <= 1:
        return None
    return _round(joined["candidate"].corr(joined["x0"]))


def _candidate_eval_rows(
    row: dict[str, str],
    aligned: pd.DataFrame,
    *,
    x0_r3_metrics: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    work = aligned[_oos_mask(aligned)].copy()
    r3 = work["R3_liquidity_low"].fillna(False).astype(bool)
    cand_cash = pd.to_numeric(work["candidate_net10"], errors="coerce").fillna(0.0)
    x0_cash = pd.to_numeric(work["x0_net10"], errors="coerce").fillna(0.0)
    candidate_r3 = cand_cash.where(r3, 0.0)
    x0_r3 = x0_cash.where(r3, 0.0)
    blend7 = ((x0_cash * 6.0) + cand_cash) / 7.0
    blend7 = blend7.where(r3, 0.0)
    blend10 = ((x0_cash * 0.9) + (cand_cash * 0.1)).where(r3, 0.0)
    sign_flip_r3 = (-cand_cash).where(r3, 0.0)
    turnover = pd.to_numeric(work.get("candidate_turnover"), errors="coerce")

    cand_full_metrics = _metrics(cand_cash)
    cand_r3_metrics = _metrics(candidate_r3)
    blend7_metrics = _metrics(blend7)
    blend10_metrics = _metrics(blend10)
    flip_metrics = _metrics(sign_flip_r3)

    ann_delta = _round((blend7_metrics.get("ann_compound") or 0.0) - (x0_r3_metrics.get("ann_compound") or 0.0))
    sortino_delta = _round((blend7_metrics.get("sortino") or 0.0) - (x0_r3_metrics.get("sortino") or 0.0))
    dd_delta = _round((blend7_metrics.get("max_drawdown") or 0.0) - (x0_r3_metrics.get("max_drawdown") or 0.0), 8)
    sign_flip_strong = bool(
        (flip_metrics.get("ann_compound") is not None and float(flip_metrics["ann_compound"]) > 0.20)
        or (flip_metrics.get("sortino") is not None and float(flip_metrics["sortino"]) > 1.0)
    )

    decision = "HOLD_R3_CHALLENGER_DIAGNOSTIC"
    if sign_flip_strong:
        decision = "HOLD_SIGN_FLIP_SYMMETRY_RISK"
    elif (ann_delta or 0.0) > 0.03 and (sortino_delta or 0.0) > 0.0 and (dd_delta or 0.0) >= -0.01:
        decision = "ALLOW_SMALL_OVERLAY_DIAGNOSTIC"
    elif (ann_delta or 0.0) <= 0.0:
        decision = "REJECT_OVERLAY_NO_MARGINAL_VALUE"

    audit = {
        "candidate_id": row.get("candidate_id"),
        "expr_hash": row.get("expr_hash"),
        "source_lane": row.get("source_lane"),
        "validation_label": row.get("validation_label"),
        "validation_duplicate_count": row.get("validation_duplicate_count"),
        "deep_score": row.get("deep_score"),
        "original_deep_oos_2026_net10_ann": row.get("oos_2026_net10_ann"),
        "original_deep_oos_2026_net10_sortino": row.get("oos_2026_net10_sortino"),
        "r3_active_days": int(r3.sum()),
        "oos_days": int(len(work)),
        "candidate_median_turnover": _round(turnover.median()),
        "candidate_p90_turnover": _round(turnover.quantile(0.90)),
        "corr_candidate_to_x0_r3_active": _active_corr(work),
        **_prefixed("x0_r3", x0_r3_metrics),
        **_prefixed("candidate_full", cand_full_metrics),
        **_prefixed("candidate_r3", cand_r3_metrics),
        **_prefixed("blend7_r3", blend7_metrics),
        **_prefixed("blend10_r3", blend10_metrics),
        **_prefixed("sign_flip_r3", flip_metrics),
        "blend7_r3_delta_ann_vs_x0_r3": ann_delta,
        "blend7_r3_delta_sortino_vs_x0_r3": sortino_delta,
        "blend7_r3_delta_maxdd_vs_x0_r3": dd_delta,
        "sign_flip_strong": sign_flip_strong,
        "overlay_decision": decision,
        "expression": row.get("expression"),
    }

    daily_rows: list[dict[str, Any]] = []
    for date, gate, x0_ret, cand_ret, cand_gate_ret, blend7_ret, blend10_ret, flip_ret in zip(
        work["date"],
        r3,
        x0_r3,
        cand_cash,
        candidate_r3,
        blend7,
        blend10,
        sign_flip_r3,
    ):
        daily_rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "candidate_id": row.get("candidate_id"),
                "expr_hash": row.get("expr_hash"),
                "R3_liquidity_low": bool(gate),
                "x0_r3_return": _round(x0_ret, 10),
                "candidate_return": _round(cand_ret, 10),
                "candidate_r3_return": _round(cand_gate_ret, 10),
                "blend7_r3_return": _round(blend7_ret, 10),
                "blend10_r3_return": _round(blend10_ret, 10),
                "sign_flip_r3_return": _round(flip_ret, 10),
            }
        )
    return audit, daily_rows


_AB_PATTERN = re.compile(
    r"Mom\(\$close,\s*(?P<mom_a>\d+)\).*?Mom\(\$close,\s*(?P<mom_b>\d+)\).*?"
    r"Mean\(\$(?P<field>[A-Za-z_]+),\s*(?P<mean_a>\d+)\).*?Mean\(\$(?P=field),\s*(?P<mean_b>\d+)\)",
    re.IGNORECASE,
)


def _ablation_expressions(expression: str) -> list[tuple[str, str]]:
    match = _AB_PATTERN.search(expression)
    if not match:
        return []
    mom_a = int(match.group("mom_a"))
    mom_b = int(match.group("mom_b"))
    field = match.group("field")
    mean_a = int(match.group("mean_a"))
    mean_b = int(match.group("mean_b"))
    return [
        ("momentum_spread_only", f"Neg(CSRank(Sub(Mom($close,{mom_a}),Mom($close,{mom_b}))))"),
        ("ratio_curve_only", f"Neg(CSRank(Div(Mean(${field},{mean_a}),Mean(${field},{mean_b}))))"),
    ]


def _run_ablations(
    *,
    candidates: list[dict[str, str]],
    base: pd.DataFrame,
    frame: pd.DataFrame,
    signal_frame: pd.DataFrame,
    field_lags: dict[str, int],
    top_bottom_quantile: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cache: dict[str, pd.DataFrame] = {}
    for candidate in candidates:
        original_expr = str(candidate.get("expression") or "")
        ablations = _ablation_expressions(original_expr)
        if not ablations:
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "expr_hash": candidate.get("expr_hash"),
                    "ablation_name": "parse_failed",
                    "status": "skipped",
                    "reason": "expression_not_recognized",
                    "original_expression": original_expr,
                }
            )
            continue
        for name, expression in ablations:
            try:
                if expression not in cache:
                    cache[expression] = _candidate_daily(
                        frame,
                        signal_frame,
                        field_lags,
                        expression,
                        top_bottom_quantile=top_bottom_quantile,
                    )
                aligned = _align_candidate(base, cache[expression])
                work = aligned[_oos_mask(aligned)].copy()
                r3 = work["R3_liquidity_low"].fillna(False).astype(bool)
                cand_cash = pd.to_numeric(work["candidate_net10"], errors="coerce").fillna(0.0)
                cand_r3 = cand_cash.where(r3, 0.0)
                turnover = pd.to_numeric(work.get("candidate_turnover"), errors="coerce")
                rows.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "expr_hash": candidate.get("expr_hash"),
                        "ablation_name": name,
                        "status": "ok",
                        "ablation_expression": expression,
                        "oos_full_ann": _metrics(cand_cash).get("ann_compound"),
                        "oos_full_sortino": _metrics(cand_cash).get("sortino"),
                        "oos_r3_ann": _metrics(cand_r3).get("ann_compound"),
                        "oos_r3_sortino": _metrics(cand_r3).get("sortino"),
                        "median_turnover": _round(turnover.median()),
                        "p90_turnover": _round(turnover.quantile(0.90)),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - audit should continue and record failures.
                rows.append(
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "expr_hash": candidate.get("expr_hash"),
                        "ablation_name": name,
                        "status": "failed",
                        "reason": type(exc).__name__,
                        "error": str(exc),
                        "ablation_expression": expression,
                    }
                )
    return rows


def _attach_ablation_flags(audit_rows: list[dict[str, Any]], ablation_rows: list[dict[str, Any]]) -> None:
    by_expr: dict[str, list[dict[str, Any]]] = {}
    for row in ablation_rows:
        by_expr.setdefault(str(row.get("expr_hash") or ""), []).append(row)
    for row in audit_rows:
        rows = [item for item in by_expr.get(str(row.get("expr_hash") or ""), []) if item.get("status") == "ok"]
        best_r3_sortino = None
        best_name = None
        for item in rows:
            value = _float(item.get("oos_r3_sortino"))
            if value is not None and (best_r3_sortino is None or value > best_r3_sortino):
                best_r3_sortino = value
                best_name = str(item.get("ablation_name") or "")
        original = _float(row.get("candidate_r3_sortino"))
        explained = False
        if original is not None and best_r3_sortino is not None:
            explained = best_r3_sortino >= original * 0.80
        row["best_ablation_r3_sortino"] = _round(best_r3_sortino)
        row["best_ablation_name"] = best_name
        row["low_order_ablation_explains_r3"] = explained
        if explained and row.get("overlay_decision") == "ALLOW_SMALL_OVERLAY_DIAGNOSTIC":
            row["overlay_decision"] = "HOLD_LOW_ORDER_ABLATION_EXPLAINS_R3"


def _render_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Phase3AB R3 Challenger Audit",
        "",
        f"- version: `{report['version']}`",
        f"- input: `{report['input_csv']}`",
        f"- dataset: `{report['dataset']}`",
        f"- selected_candidates: `{report['selected_candidates']}`",
        f"- official_x0_r3_policy: `{report['official_x0_r3_policy']}`",
        f"- x0_r3_2026_ann: `{report['x0_r3_metrics'].get('ann_compound')}`",
        f"- x0_r3_2026_sortino: `{report['x0_r3_metrics'].get('sortino')}`",
        "",
        "## Interpretation",
        "",
        "- This is not a search run and does not modify the locked X0/R3 object.",
        "- Candidates are treated as recent/R3 challengers, not all-history alpha.",
        "- Promotion requires marginal value against X0/R3, sign-flip sanity, and low-order ablation checks.",
        "",
        "## Candidate Audit",
        "",
        "| rank | candidate | decision | cand R3 ann | cand R3 sortino | blend ann delta | blend sortino delta | corr X0 | sign flip | best ablation | expr_hash |",
        "|---:|---|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            "| {idx} | `{cid}` | {decision} | {r3ann} | {r3sortino} | {dann} | {dsortino} | {corr} | {flip} | {ablation} | `{expr}` |".format(
                idx=idx,
                cid=row.get("candidate_id", ""),
                decision=row.get("overlay_decision", ""),
                r3ann=row.get("candidate_r3_ann_compound", ""),
                r3sortino=row.get("candidate_r3_sortino", ""),
                dann=row.get("blend7_r3_delta_ann_vs_x0_r3", ""),
                dsortino=row.get("blend7_r3_delta_sortino_vs_x0_r3", ""),
                corr=row.get("corr_candidate_to_x0_r3_active", ""),
                flip=row.get("sign_flip_strong", ""),
                ablation=row.get("best_ablation_name", ""),
                expr=row.get("expr_hash", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Bias Audit Summary",
            "",
            "- Look-ahead: uses `SIGNAL_CLOCK_AFTER_OPEN`, one-day execution lag, and lagged R3 liquidity state inherited from the locked regime builder.",
            "- Discovery status: Phase3AB candidates remain discovery/replay candidates from the recent mature-chain search; this audit is post-discovery challenger validation.",
            "- OOS scope: 2026 slice is recent OOS only; pre-2025/full-history weakness remains a blocker for all-regime promotion.",
            "- Cost: net returns use 10 bps turnover cost proxy; no minute slippage or real capacity is confirmed.",
            "",
            "## Outputs",
            "",
            f"- audit_csv: `{report['paths']['audit_csv']}`",
            f"- daily_csv: `{report['paths']['daily_csv']}`",
            f"- ablation_csv: `{report['paths']['ablation_csv']}`",
            f"- json: `{report['paths']['json']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run(
    *,
    input_csv: Path,
    dataset: Path,
    output_root: Path,
    x0_object: Path,
    x0_daily: Path,
    min_oos_sortino: float,
    min_oos_ann: float,
    max_candidates: int,
    top_bottom_quantile: float,
    run_ablations: bool,
    load_start: pd.Timestamp,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    all_rows = _read_csv(input_csv)
    candidates = _select_candidates(
        all_rows,
        min_oos_sortino=min_oos_sortino,
        min_oos_ann=min_oos_ann,
        max_candidates=max_candidates,
    )
    frame = _load_audit_frame(dataset, load_start)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    x0_base = _build_official_x0_base(dataset, x0_daily)
    base = x0_base[_oos_mask(x0_base)].copy()
    base["x0_r3"] = pd.to_numeric(base["x0_net10"], errors="coerce").fillna(0.0).where(
        base["R3_liquidity_low"].fillna(False).astype(bool),
        0.0,
    )
    x0_r3_metrics = _metrics(base["x0_r3"])

    audit_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    paths = {
        "audit_csv": str(output_root / "phase3ab_r3_challenger_audit.csv"),
        "daily_csv": str(output_root / "phase3ab_r3_challenger_daily.csv"),
        "ablation_csv": str(output_root / "phase3ab_r3_challenger_ablation.csv"),
        "failures_csv": str(output_root / "phase3ab_r3_challenger_failures.csv"),
        "json": str(output_root / "phase3ab_r3_challenger_audit.json"),
        "markdown": str(output_root / "PHASE3AB_R3_CHALLENGER_AUDIT_2026-05-30.md"),
    }
    progress_path = output_root / "phase3ab_r3_challenger_progress.json"
    for idx, candidate in enumerate(candidates, start=1):
        write_json_artifact(
            progress_path,
            {
                "status": "running",
                "current_index": idx,
                "selected_candidates": len(candidates),
                "candidate_id": candidate.get("candidate_id"),
                "expr_hash": candidate.get("expr_hash"),
            },
        )
        try:
            daily = _candidate_daily(
                frame,
                signal_frame,
                signal_clock_report["field_lags"],
                str(candidate.get("expression") or ""),
                top_bottom_quantile=top_bottom_quantile,
            )
            aligned = _align_candidate(x0_base, daily)
            audit, rows = _candidate_eval_rows(candidate, aligned, x0_r3_metrics=x0_r3_metrics)
            audit_rows.append(audit)
            daily_rows.extend(rows)
            _write_csv(Path(paths["audit_csv"]), audit_rows)
            _write_csv(Path(paths["daily_csv"]), daily_rows)
        except Exception as exc:  # noqa: BLE001 - audit should continue and record failed formulas.
            failures.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "expr_hash": candidate.get("expr_hash"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "expression": candidate.get("expression"),
                }
            )
            _write_csv(Path(paths["failures_csv"]), failures)

    if run_ablations:
        ablation_rows = _run_ablations(
            candidates=candidates,
            base=x0_base,
            frame=frame,
            signal_frame=signal_frame,
            field_lags=signal_clock_report["field_lags"],
            top_bottom_quantile=top_bottom_quantile,
        )
    else:
        ablation_rows = [
            {
                "candidate_id": candidate.get("candidate_id"),
                "expr_hash": candidate.get("expr_hash"),
                "ablation_name": "not_run",
                "status": "skipped",
                "reason": "disabled_by_run_argument",
            }
            for candidate in candidates
        ]
    _attach_ablation_flags(audit_rows, ablation_rows)
    audit_rows.sort(
        key=lambda row: (
            float(row.get("blend7_r3_delta_ann_vs_x0_r3") or -999.0),
            float(row.get("candidate_r3_sortino") or -999.0),
        ),
        reverse=True,
    )

    decision_counts: dict[str, int] = {}
    for row in audit_rows:
        key = str(row.get("overlay_decision") or "")
        decision_counts[key] = decision_counts.get(key, 0) + 1

    _write_csv(Path(paths["audit_csv"]), audit_rows)
    _write_csv(Path(paths["daily_csv"]), daily_rows)
    _write_csv(Path(paths["ablation_csv"]), ablation_rows)
    _write_csv(Path(paths["failures_csv"]), failures)
    x0_object_payload: dict[str, Any] = {}
    if x0_object.exists():
        x0_object_payload = json.loads(x0_object.read_text(encoding="utf-8"))
    report = {
        "version": VERSION,
        "scope": "no_search_r3_challenger_audit",
        "decision": "HOLD_RESEARCH_RECENT_R3_CHALLENGER_VALIDATION",
        "input_csv": str(input_csv),
        "dataset": str(dataset),
        "output_root": str(output_root),
        "selected_candidates": len(candidates),
        "succeeded": len(audit_rows),
        "failed": len(failures),
        "min_oos_sortino": float(min_oos_sortino),
        "min_oos_ann": float(min_oos_ann),
        "top_bottom_quantile": float(top_bottom_quantile),
        "run_ablations": bool(run_ablations),
        "load_start": pd.Timestamp(load_start).date().isoformat(),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "official_x0_r3_policy": "read_only_no_change",
        "x0_object": str(x0_object),
        "x0_daily": str(x0_daily),
        "x0_object_id": x0_object_payload.get("object_id"),
        "x0_r3_metrics": x0_r3_metrics,
        "decision_counts": decision_counts,
        "paths": paths,
        "top_rows": audit_rows[:20],
    }
    write_json_artifact(Path(paths["json"]), report)
    Path(paths["markdown"]).write_text(_render_markdown(report, audit_rows), encoding="utf-8")
    write_json_artifact(
        progress_path,
        {
            "status": "completed",
            "selected_candidates": len(candidates),
            "succeeded": len(audit_rows),
            "failed": len(failures),
            "output_root": str(output_root),
        },
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase3AB recent/R3 challengers against locked X0/R3.")
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET if DEFAULT_DATASET.exists() else FALLBACK_DATASET)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--x0-object", type=Path, default=DEFAULT_X0_OBJECT)
    parser.add_argument("--x0-daily", type=Path, default=DEFAULT_X0_DAILY)
    parser.add_argument("--min-oos-sortino", type=float, default=2.0)
    parser.add_argument("--min-oos-ann", type=float, default=0.45)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--skip-ablations", action="store_true", help="Skip slow low-order ablation evaluation.")
    parser.add_argument("--load-start", type=pd.Timestamp, default=DEFAULT_LOAD_START)
    args = parser.parse_args()
    report = run(
        input_csv=args.input_csv,
        dataset=args.dataset,
        output_root=args.output_root,
        x0_object=args.x0_object,
        x0_daily=args.x0_daily,
        min_oos_sortino=float(args.min_oos_sortino),
        min_oos_ann=float(args.min_oos_ann),
        max_candidates=max(0, int(args.max_candidates)),
        top_bottom_quantile=float(args.top_bottom_quantile),
        run_ablations=not bool(args.skip_ablations),
        load_start=pd.Timestamp(args.load_start),
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output_root": report["output_root"],
                "selected_candidates": report["selected_candidates"],
                "succeeded": report["succeeded"],
                "failed": report["failed"],
                "decision_counts": report["decision_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
