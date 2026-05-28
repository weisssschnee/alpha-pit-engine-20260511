"""Phase3Z48 event-veto gate audit.

This diagnostic tests whether the sparse negative-event structures found in
Phase3Z47 can add marginal value as stock-level vetoes for the locked X0/R3
book. It does not alter official X0/R3, G2, J2/J4, or Phase3P state.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame
from our_system_phase2.services.real_market_validation import (
    DEFAULT_EXECUTION_LAG_DAYS,
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_market_panel,
    _signal_evaluation_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


DEFAULT_DATASET = Path(
    r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
)
DEFAULT_ALPHA_CARDS = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_alpha_cards.csv")
DEFAULT_SHADOW_OBJECT = Path("runtime/baselines/phase3o_x0_official_shadow_v1.json")
DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_RUN_PLAN = Path("runtime/run_plans/phase3z48_event_veto_gate_audit_run_plan.json")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3z48_event_veto_gate_audit_20260529")
REPORT_FILENAME = "PHASE3Z48_EVENT_VETO_GATE_AUDIT_2026-05-29.md"

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
OFFICIAL_CLUSTERS = ("cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004")


@dataclass(frozen=True, slots=True)
class VetoTrigger:
    trigger_id: str
    field: str
    actor_motif: str
    event_family: str


TRIGGERS: tuple[VetoTrigger, ...] = (
    VetoTrigger("break_after_streak_ge2", "break_board_after_streak_ge_2", "high_board_chaser_unwind", "limit_break"),
    VetoTrigger("break_after_streak_ge3", "break_board_after_streak_ge_3", "high_board_chaser_unwind", "limit_break"),
    VetoTrigger("open_not_close_up", "limit_up_open_not_close", "open_board_liquidity_failure", "limit_open_break"),
    VetoTrigger("touch_not_close_up", "limit_up_touch_not_close", "intraday_touch_exhaustion", "limit_break"),
)

MODES = ("long_pool_veto", "universe_veto")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_compound": None,
            "sharpe": None,
            "sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "total_return": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _r3_gate_from_panel(frame: pd.DataFrame) -> pd.DataFrame:
    panel = frame[["date", "code", "close", "amount", "rt_change_pct"]].copy()
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    train_mask = (regime["date"] >= TRAIN_START) & (regime["date"] <= TRAIN_END)
    labels = _bucket_by_train_thresholds(regime["liquidity_ratio_lag1"], train_mask, "liquidity")
    return pd.DataFrame({"date": regime["date"], "R3_liquidity_low": labels == "liquidity_low"})


def _cluster_formulas(alpha_cards: Path, shadow_object: Path) -> dict[str, str]:
    if shadow_object.exists():
        payload = _read_json(shadow_object)
        formulas = payload.get("cluster_formulas", {})
        out = {}
        for cluster in OFFICIAL_CLUSTERS:
            short_id = cluster.replace("cluster_", "")
            expr = str(formulas.get(short_id) or formulas.get(cluster) or "").strip()
            if expr:
                out[cluster] = expr
        missing = [cluster for cluster in OFFICIAL_CLUSTERS if cluster not in out]
        if not missing:
            return out
    rows = _read_csv(alpha_cards)
    out: dict[str, str] = {}
    for row in rows:
        cluster_id = str(row.get("cluster_id") or "")
        if cluster_id in OFFICIAL_CLUSTERS:
            expr = str(row.get("representative_expression") or "").strip()
            if expr:
                out[cluster_id] = expr
    missing = [cluster for cluster in OFFICIAL_CLUSTERS if cluster not in out]
    if missing:
        raise ValueError(f"missing_official_cluster_formulas:{missing}")
    return out


def _daily_spread_with_veto(
    work: pd.DataFrame,
    *,
    top_bottom_quantile: float,
    mode: str,
    veto_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    previous_top: set[str] | None = None
    previous_bottom: set[str] | None = None
    for date, day in work.groupby("date", sort=True):
        if len(day) < 5 or day["signal"].nunique(dropna=True) < 2:
            continue
        long_blocked = day["entry_limit_up"] | day["entry_suspended"]
        short_blocked = day["entry_limit_down"] | day["entry_suspended"]
        veto_mask = day[veto_column].fillna(False).astype(bool)
        if mode == "long_pool_veto":
            long_blocked = long_blocked | veto_mask
        elif mode == "universe_veto":
            long_blocked = long_blocked | veto_mask
            short_blocked = short_blocked | veto_mask
        else:
            raise ValueError(f"unsupported_veto_mode:{mode}")

        long_pool = day[~long_blocked]
        short_pool = day[~short_blocked]
        long_ret = None
        short_ret = None
        top_codes: set[str] | None = None
        bottom_codes: set[str] | None = None
        veto_hit_count = int(veto_mask.sum())
        long_pool_removed = int((veto_mask & ~(day["entry_limit_up"] | day["entry_suspended"])).sum())
        short_pool_removed = int((veto_mask & ~(day["entry_limit_down"] | day["entry_suspended"])).sum()) if mode == "universe_veto" else 0

        if len(long_pool) >= 5 and long_pool["signal"].nunique(dropna=True) >= 2:
            long_count = max(1, int(math.ceil(len(long_pool) * top_bottom_quantile)))
            top = long_pool.sort_values(["signal", "code"], ascending=[False, True]).head(long_count)
            long_ret = float(top["forward_return"].mean()) if pd.notna(top["forward_return"].mean()) else None
            top_codes = set(top["code"].astype(str))
        if len(short_pool) >= 5 and short_pool["signal"].nunique(dropna=True) >= 2:
            short_count = max(1, int(math.ceil(len(short_pool) * top_bottom_quantile)))
            bottom = short_pool.sort_values(["signal", "code"], ascending=[True, True]).head(short_count)
            short_ret = float(bottom["forward_return"].mean()) if pd.notna(bottom["forward_return"].mean()) else None
            bottom_codes = set(bottom["code"].astype(str))

        if previous_top is None or previous_bottom is None or top_codes is None or bottom_codes is None:
            turnover = None
        else:
            top_turnover = 1.0 - (len(top_codes & previous_top) / max(1, len(top_codes)))
            bottom_turnover = 1.0 - (len(bottom_codes & previous_bottom) / max(1, len(bottom_codes)))
            turnover = (top_turnover + bottom_turnover) / 2.0
        if top_codes is not None:
            previous_top = top_codes
        if bottom_codes is not None:
            previous_bottom = bottom_codes

        rows.append(
            {
                "date": date,
                "long_short_return": long_ret - short_ret if long_ret is not None and short_ret is not None else None,
                "average_one_way_turnover": turnover,
                "veto_hit_count": veto_hit_count,
                "long_pool_removed": long_pool_removed,
                "short_pool_removed": short_pool_removed,
                "eligible_count": int(len(day)),
            }
        )
    return pd.DataFrame(rows)


def _build_cluster_work(
    frame: pd.DataFrame,
    *,
    formulas: dict[str, str],
    top_bottom_quantile: float,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    cache: dict[str, pd.Series] = {}
    cluster_work: dict[str, pd.DataFrame] = {}
    base_daily: dict[str, pd.Series] = {}
    for cluster_id, expression in formulas.items():
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=cache,
            field_lags=signal_clock_report["field_lags"],
        )
        work, _tradability = _tradable_signal_work_frame(
            frame,
            signal,
            horizon_days=1,
            execution_lag_days=DEFAULT_EXECUTION_LAG_DAYS,
            feature_lag_days=0,
            evaluation_start_date=None,
            evaluation_end_date=None,
            field_lags=signal_clock_report["field_lags"],
        )
        daily = _daily_spread_with_veto(
            work.assign(__no_veto__=False),
            top_bottom_quantile=top_bottom_quantile,
            mode="long_pool_veto",
            veto_column="__no_veto__",
        )
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        base_daily[cluster_id] = daily.set_index("date")["long_short_return"].astype(float)
        cluster_work[cluster_id] = work
    return cluster_work, pd.DataFrame(base_daily).sort_index()


def _book_series(cluster_daily: pd.DataFrame) -> pd.Series:
    return cluster_daily.loc[:, list(OFFICIAL_CLUSTERS)].mean(axis=1, skipna=True)


def _evaluate_book_delta(
    *,
    label: str,
    trigger: VetoTrigger,
    mode: str,
    cluster_work: dict[str, pd.DataFrame],
    base_book: pd.Series,
    r3_by_date: pd.Series,
    frame_event_mask: pd.Series,
    top_bottom_quantile: float,
    oos_mask_by_date: pd.Series,
) -> tuple[dict[str, Any], pd.Series]:
    daily_columns: dict[str, pd.Series] = {}
    hit_rows: list[pd.DataFrame] = []
    for cluster_id, work in cluster_work.items():
        veto = frame_event_mask.reindex(work.index).fillna(False).astype(bool)
        work_with_veto = work.copy()
        work_with_veto["__event_veto__"] = veto.to_numpy()
        daily = _daily_spread_with_veto(
            work_with_veto,
            top_bottom_quantile=top_bottom_quantile,
            mode=mode,
            veto_column="__event_veto__",
        )
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        hit_rows.append(daily[["date", "veto_hit_count", "long_pool_removed", "short_pool_removed", "eligible_count"]])
        daily_columns[cluster_id] = daily.set_index("date")["long_short_return"].astype(float)
    veto_book = _book_series(pd.DataFrame(daily_columns).sort_index())
    base_aligned = base_book.reindex(veto_book.index).fillna(0.0)
    r3 = r3_by_date.reindex(veto_book.index).fillna(False).astype(bool)
    oos = oos_mask_by_date.reindex(veto_book.index).fillna(False).astype(bool)
    base_r3 = base_aligned.where(r3, 0.0)
    veto_r3 = veto_book.where(r3, 0.0)
    delta = veto_r3 - base_r3
    hit = pd.concat(hit_rows, ignore_index=True)
    hit_by_date = hit.groupby("date", sort=True).sum(numeric_only=True)
    active_veto_dates = (hit_by_date["long_pool_removed"] > 0).reindex(veto_book.index).fillna(False)
    active_oos = oos & r3 & active_veto_dates
    row = {
        "label": label,
        "trigger_id": trigger.trigger_id,
        "actor_motif": trigger.actor_motif,
        "event_family": trigger.event_family,
        "field": trigger.field,
        "mode": mode,
        "oos_calendar_days": int(oos.sum()),
        "oos_r3_active_days": int((oos & r3).sum()),
        "veto_active_r3_days": int(active_oos.sum()),
        "veto_active_r3_ratio": _round(active_oos.sum() / max(1, int((oos & r3).sum()))),
        "mean_long_pool_removed_per_active_day": _round(hit_by_date.loc[active_veto_dates, "long_pool_removed"].mean() if active_veto_dates.any() else 0.0),
        "mean_event_hit_count_per_active_day": _round(hit_by_date.loc[active_veto_dates, "veto_hit_count"].mean() if active_veto_dates.any() else 0.0),
        "base_full_ann": _metrics(base_r3[oos])["ann_compound"],
        "veto_full_ann": _metrics(veto_r3[oos])["ann_compound"],
        "delta_ann": _round((_metrics(veto_r3[oos])["ann_compound"] or 0.0) - (_metrics(base_r3[oos])["ann_compound"] or 0.0)),
        "base_total_return": _metrics(base_r3[oos])["total_return"],
        "veto_total_return": _metrics(veto_r3[oos])["total_return"],
        "delta_total_return": _round(float((1.0 + veto_r3[oos]).prod() - (1.0 + base_r3[oos]).prod())),
        "base_sharpe": _metrics(base_r3[oos])["sharpe"],
        "veto_sharpe": _metrics(veto_r3[oos])["sharpe"],
        "base_max_drawdown": _metrics(base_r3[oos])["max_drawdown"],
        "veto_max_drawdown": _metrics(veto_r3[oos])["max_drawdown"],
        "active_veto_delta_mean": _round(delta[active_oos].mean(), 8) if active_oos.any() else None,
        "active_veto_delta_median": _round(delta[active_oos].median(), 8) if active_oos.any() else None,
        "active_veto_delta_hit_rate": _round((delta[active_oos] > 0.0).mean()) if active_oos.any() else None,
        "missed_positive_base_return": _round(base_r3[active_oos & (delta < 0.0)].sum(), 8) if active_oos.any() else None,
        "avoided_negative_base_return": _round((-base_r3[active_oos & (delta > 0.0) & (base_r3 < 0.0)]).sum(), 8) if active_oos.any() else None,
    }
    return row, veto_r3


def _random_mask_like_event(work_index: pd.Index, event_mask: pd.Series, frame: pd.DataFrame, rng: np.random.Generator) -> pd.Series:
    event_frame = pd.DataFrame({"date": frame["date"], "event": event_mask.fillna(False).astype(bool)})
    counts = event_frame.groupby("date", sort=False)["event"].sum().astype(int)
    random = pd.Series(False, index=frame.index)
    for date, count in counts[counts > 0].items():
        idx = frame.index[frame["date"] == date].to_numpy()
        if len(idx) == 0:
            continue
        chosen = rng.choice(idx, size=min(int(count), len(idx)), replace=False)
        random.loc[chosen] = True
    return random.reindex(work_index).fillna(False).astype(bool)


def _placebo_p95(
    *,
    trigger: VetoTrigger,
    mode: str,
    frame: pd.DataFrame,
    cluster_work: dict[str, pd.DataFrame],
    base_book: pd.Series,
    r3_by_date: pd.Series,
    event_mask: pd.Series,
    top_bottom_quantile: float,
    oos_mask_by_date: pd.Series,
    draws: int,
) -> dict[str, Any]:
    if draws <= 0:
        return {
            "placebo_draws": 0,
            "random_delta_ann_mean": None,
            "random_delta_ann_p50": None,
            "random_delta_ann_p95": None,
        }
    rng = np.random.default_rng(abs(hash((trigger.trigger_id, mode, "z48"))) & 0xFFFF_FFFF)
    deltas: list[float] = []
    for draw in range(draws):
        random_frame_mask = _random_mask_like_event(frame.index, event_mask, frame, rng)
        row, _series = _evaluate_book_delta(
            label=f"{trigger.trigger_id}_{mode}_random_{draw:03d}",
            trigger=trigger,
            mode=mode,
            cluster_work=cluster_work,
            base_book=base_book,
            r3_by_date=r3_by_date,
            frame_event_mask=random_frame_mask,
            top_bottom_quantile=top_bottom_quantile,
            oos_mask_by_date=oos_mask_by_date,
        )
        deltas.append(float(row.get("delta_ann") or 0.0))
    values = pd.Series(deltas, dtype=float)
    return {
        "placebo_draws": int(draws),
        "random_delta_ann_mean": _round(values.mean()),
        "random_delta_ann_p50": _round(values.quantile(0.50)),
        "random_delta_ann_p95": _round(values.quantile(0.95)),
    }


def _decision(row: dict[str, Any]) -> str:
    delta_ann = float(row.get("delta_ann") or 0.0)
    p95 = row.get("random_delta_ann_p95")
    if row.get("veto_active_r3_days", 0) < 5:
        return "HOLD_INSUFFICIENT_VETO_ACTIVE_DAYS"
    if delta_ann <= 0.0:
        return "REJECT_NO_X0_R3_DELTA"
    if row.get("random_delta_ann_p95") is None:
        return "HOLD_PLACEBO_NOT_RUN"
    if p95 is not None and delta_ann <= float(p95):
        return "HOLD_RANDOM_VETO_NOT_BEATEN"
    if (row.get("veto_sharpe") or 0.0) < (row.get("base_sharpe") or 0.0):
        return "HOLD_SHARPE_NOT_IMPROVED"
    return "EVENT_VETO_RESEARCH_CANDIDATE"


def _random_day_veto_placebo(
    returns: pd.Series,
    r3: pd.Series,
    oos: pd.Series,
    veto_count: int,
    *,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    if draws <= 0 or veto_count <= 0:
        return {
            "placebo_draws": int(draws),
            "random_delta_ann_mean": None,
            "random_delta_ann_p50": None,
            "random_delta_ann_p95": None,
        }
    eligible = np.flatnonzero((oos & r3).to_numpy())
    if len(eligible) == 0:
        return {
            "placebo_draws": int(draws),
            "random_delta_ann_mean": None,
            "random_delta_ann_p50": None,
            "random_delta_ann_p95": None,
        }
    veto_count = min(int(veto_count), len(eligible))
    base = returns.where(oos & r3, 0.0)
    base_ann = _metrics(base[oos])["ann_compound"] or 0.0
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(draws):
        mask = pd.Series(False, index=returns.index)
        chosen = rng.choice(eligible, size=veto_count, replace=False)
        mask.iloc[chosen] = True
        vetoed = returns.where((oos & r3) & (~mask), 0.0)
        deltas.append(float((_metrics(vetoed[oos])["ann_compound"] or 0.0) - base_ann))
    values = pd.Series(deltas, dtype=float)
    return {
        "placebo_draws": int(draws),
        "random_delta_ann_mean": _round(values.mean()),
        "random_delta_ann_p50": _round(values.quantile(0.50)),
        "random_delta_ann_p95": _round(values.quantile(0.95)),
    }


def _run_market_day_veto(
    *,
    dataset_path: Path,
    daily_returns: Path,
    run_plan_path: Path,
    output_root: Path,
    placebo_draws: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_plan = _read_json(run_plan_path)
    if run_plan.get("official_stats_allowed"):
        raise RuntimeError("phase3z48_run_plan_must_not_allow_official_stats")

    raw_regime_panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    raw_regime_panel["date"] = pd.to_datetime(raw_regime_panel["date"], errors="coerce")
    r3_frame = _r3_gate_from_panel(raw_regime_panel)
    frame = _load_market_panel(dataset_path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    daily = pd.read_csv(daily_returns, parse_dates=["date"]).sort_values("date")
    returns = pd.to_numeric(daily["candidate_book_6"], errors="coerce").fillna(0.0)
    dates = pd.to_datetime(daily["date"], errors="coerce")
    merged = pd.DataFrame({"date": dates, "candidate_book_6": returns})
    merged = merged.merge(r3_frame, on="date", how="left")
    merged["R3_liquidity_low"] = merged["R3_liquidity_low"].fillna(False).astype(bool)
    oos = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    train = (merged["date"] >= TRAIN_START) & (merged["date"] <= TRAIN_END)
    base_r3 = merged["candidate_book_6"].where(oos & merged["R3_liquidity_low"], 0.0)
    base_metrics = _metrics(base_r3[oos])

    rows: list[dict[str, Any]] = []
    daily_delta_rows: list[dict[str, Any]] = []
    for trigger in TRIGGERS:
        if trigger.field not in frame.columns:
            rows.append({"trigger_id": trigger.trigger_id, "field": trigger.field, "decision": "SKIP_FIELD_MISSING"})
            continue
        event = pd.to_numeric(frame[trigger.field], errors="coerce").fillna(0.0).gt(0.0)
        counts = (
            pd.DataFrame({"date": frame["date"], "event": event.astype(int), "row": 1})
            .groupby("date", sort=True)
            .sum(numeric_only=True)
        )
        counts["event_density"] = counts["event"] / counts["row"].replace(0, np.nan)
        probe = merged.merge(counts[["event", "row", "event_density"]], on="date", how="left")
        probe[["event", "row", "event_density"]] = probe[["event", "row", "event_density"]].fillna(0.0)
        train_density = probe.loc[train & probe["event_density"].gt(0), "event_density"]
        thresholds: dict[str, float] = {"any_event": 1e-12}
        if not train_density.empty:
            thresholds["train_p80_density"] = float(train_density.quantile(0.80))
            thresholds["train_p90_density"] = float(train_density.quantile(0.90))
        for threshold_name, threshold in thresholds.items():
            veto_day = probe["event_density"] >= threshold
            vetoed = merged["candidate_book_6"].where(oos & merged["R3_liquidity_low"] & (~veto_day), 0.0)
            veto_metrics = _metrics(vetoed[oos])
            delta_ann = (veto_metrics["ann_compound"] or 0.0) - (base_metrics["ann_compound"] or 0.0)
            delta_total = float((1.0 + vetoed[oos]).prod() - (1.0 + base_r3[oos]).prod())
            active = oos & merged["R3_liquidity_low"] & veto_day
            placebo = _random_day_veto_placebo(
                merged["candidate_book_6"],
                merged["R3_liquidity_low"],
                oos,
                int(active.sum()),
                draws=placebo_draws,
                seed=abs(hash((trigger.trigger_id, threshold_name, "market_day"))) & 0xFFFF_FFFF,
            )
            row = {
                "audit_mode": "market_day_veto",
                "trigger_id": trigger.trigger_id,
                "actor_motif": trigger.actor_motif,
                "event_family": trigger.event_family,
                "field": trigger.field,
                "threshold_name": threshold_name,
                "threshold": _round(threshold, 10),
                "oos_calendar_days": int(oos.sum()),
                "oos_r3_active_days": int((oos & merged["R3_liquidity_low"]).sum()),
                "veto_active_r3_days": int(active.sum()),
                "veto_active_r3_ratio": _round(active.sum() / max(1, int((oos & merged["R3_liquidity_low"]).sum()))),
                "mean_event_count_on_veto_days": _round(probe.loc[active, "event"].mean() if active.any() else 0.0),
                "mean_event_density_on_veto_days": _round(probe.loc[active, "event_density"].mean() if active.any() else 0.0),
                "base_full_ann": base_metrics["ann_compound"],
                "veto_full_ann": veto_metrics["ann_compound"],
                "delta_ann": _round(delta_ann),
                "base_total_return": base_metrics["total_return"],
                "veto_total_return": veto_metrics["total_return"],
                "delta_total_return": _round(delta_total),
                "base_sharpe": base_metrics["sharpe"],
                "veto_sharpe": veto_metrics["sharpe"],
                "base_max_drawdown": base_metrics["max_drawdown"],
                "veto_max_drawdown": veto_metrics["max_drawdown"],
                "removed_day_mean_return": _round(merged.loc[active, "candidate_book_6"].mean(), 8) if active.any() else None,
                "removed_day_total_return": _round(float(merged.loc[active, "candidate_book_6"].sum()), 8) if active.any() else None,
                **placebo,
            }
            row["beats_random_delta_p95"] = (
                row.get("random_delta_ann_p95") is not None
                and float(row.get("delta_ann") or 0.0) > float(row["random_delta_ann_p95"])
            )
            row["decision"] = _decision(row)
            rows.append(row)
            for idx in probe.index[oos]:
                date = pd.Timestamp(probe.loc[idx, "date"]).date().isoformat()
                daily_delta_rows.append(
                    {
                        "date": date,
                        "trigger_id": trigger.trigger_id,
                        "threshold_name": threshold_name,
                        "r3_active": bool(merged.loc[idx, "R3_liquidity_low"]),
                        "veto_day": bool(veto_day.loc[idx]),
                        "x0_r3_return": _round(base_r3.loc[idx], 8),
                        "veto_r3_return": _round(vetoed.loc[idx], 8),
                        "delta": _round(vetoed.loc[idx] - base_r3.loc[idx], 8),
                        "event_count": int(probe.loc[idx, "event"]),
                        "event_density": _round(probe.loc[idx, "event_density"], 8),
                    }
                )

    candidate_count = sum(row.get("decision") == "EVENT_VETO_RESEARCH_CANDIDATE" for row in rows)
    decision_counts: dict[str, int] = {}
    for row in rows:
        decision_counts[str(row.get("decision"))] = decision_counts.get(str(row.get("decision")), 0) + 1
    decision = (
        "HOLD_Z48_MARKET_DAY_VETO_HAS_RESEARCH_CANDIDATES"
        if candidate_count
        else "HOLD_Z48_MARKET_DAY_VETO_NO_X0_R3_IMPROVEMENT"
    )

    _write_csv(output_root / "phase3z48_event_veto_gate_audit.csv", rows)
    _write_csv(output_root / "phase3z48_event_veto_daily_delta.csv", daily_delta_rows)
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_market_day_event_veto_delta_vs_locked_X0_R3_no_official_promotion",
        "dataset": str(dataset_path),
        "daily_returns": str(daily_returns),
        "run_plan": str(run_plan_path),
        "row_count": int(len(frame)),
        "date_min": str(frame["date"].min().date()),
        "date_max": str(frame["date"].max().date()),
        "code_count": int(frame["code"].nunique()),
        "placebo_draws": int(placebo_draws),
        "candidate_count": int(candidate_count),
        "decision_counts": decision_counts,
        "base_x0_r3_oos_metrics": base_metrics,
        "top_rows": sorted(
            rows,
            key=lambda item: (
                item.get("decision") == "EVENT_VETO_RESEARCH_CANDIDATE",
                float(item.get("delta_ann") or -999.0),
            ),
            reverse=True,
        )[:8],
        "hard_boundary": "Z48 market-day veto cannot alter X0/R3, G2, J2/J4, Phase3P, or formula search state.",
        "outputs": {
            "audit_csv": str(output_root / "phase3z48_event_veto_gate_audit.csv"),
            "daily_delta_csv": str(output_root / "phase3z48_event_veto_daily_delta.csv"),
            "summary_json": str(output_root / "phase3z48_event_veto_gate_audit.json"),
            "summary_md": str(output_root / REPORT_FILENAME),
        },
    }
    _write_json(output_root / "phase3z48_event_veto_gate_audit.json", summary)
    lines = [
        "# Phase3Z48 Event Veto Gate Audit",
        "",
        f"- decision: `{decision}`",
        f"- candidate_count: `{candidate_count}`",
        f"- audit_mode: `market_day_veto`",
        "- scope: diagnostic only; locked X0/R3 is read-only.",
        "",
        "## Results",
        "",
        "| trigger | threshold | veto R3 days | delta ann | veto ann | base ann | random p95 | removed day mean | decision |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(rows, key=lambda item: float(item.get("delta_ann") or -999.0), reverse=True):
        lines.append(
            f"| {row.get('trigger_id')} | `{row.get('threshold_name')}` | {row.get('veto_active_r3_days')} | "
            f"{row.get('delta_ann')} | {row.get('veto_full_ann')} | {row.get('base_full_ann')} | "
            f"{row.get('random_delta_ann_p95')} | {row.get('removed_day_mean_return')} | `{row.get('decision')}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- This run tests market-day event-density vetoes, not stock-level position vetoes.",
            "- A pass means the event may justify a later gate research track; it is not official promotion.",
            "- Same-count random day veto controls whether cashing a similar number of R3 days has comparable improvement.",
        ]
    )
    (output_root / REPORT_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run(
    *,
    dataset_path: Path,
    alpha_cards: Path,
    shadow_object: Path,
    daily_returns: Path,
    run_plan_path: Path,
    output_root: Path,
    placebo_draws: int,
    top_bottom_quantile: float,
    audit_mode: str,
) -> dict[str, Any]:
    if audit_mode == "market_day":
        return _run_market_day_veto(
            dataset_path=dataset_path,
            daily_returns=daily_returns,
            run_plan_path=run_plan_path,
            output_root=output_root,
            placebo_draws=placebo_draws,
        )
    if audit_mode != "stock_level":
        raise ValueError(f"unsupported_audit_mode:{audit_mode}")
    output_root.mkdir(parents=True, exist_ok=True)
    run_plan = _read_json(run_plan_path)
    if run_plan.get("official_stats_allowed"):
        raise RuntimeError("phase3z48_run_plan_must_not_allow_official_stats")

    formulas = _cluster_formulas(alpha_cards, shadow_object)
    frame = _load_market_panel(dataset_path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    cluster_work, base_daily_matrix = _build_cluster_work(
        frame,
        formulas=formulas,
        top_bottom_quantile=top_bottom_quantile,
    )
    base_book = _book_series(base_daily_matrix)
    r3_frame = _r3_gate_from_panel(frame)
    r3_by_date = r3_frame.set_index("date")["R3_liquidity_low"].astype(bool)
    all_dates = pd.Series(base_book.index, index=base_book.index)
    oos_mask_by_date = (all_dates >= OOS_START) & (all_dates <= OOS_END)

    rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    for trigger in TRIGGERS:
        if trigger.field not in frame.columns:
            rows.append(
                {
                    "trigger_id": trigger.trigger_id,
                    "field": trigger.field,
                    "decision": "SKIP_FIELD_MISSING",
                }
            )
            continue
        event_mask = pd.to_numeric(frame[trigger.field], errors="coerce").fillna(0.0).gt(0.0)
        for mode in MODES:
            row, series = _evaluate_book_delta(
                label=f"{trigger.trigger_id}_{mode}",
                trigger=trigger,
                mode=mode,
                cluster_work=cluster_work,
                base_book=base_book,
                r3_by_date=r3_by_date,
                frame_event_mask=event_mask,
                top_bottom_quantile=top_bottom_quantile,
                oos_mask_by_date=oos_mask_by_date,
            )
            row.update(
                _placebo_p95(
                    trigger=trigger,
                    mode=mode,
                    frame=frame,
                    cluster_work=cluster_work,
                    base_book=base_book,
                    r3_by_date=r3_by_date,
                    event_mask=event_mask,
                    top_bottom_quantile=top_bottom_quantile,
                    oos_mask_by_date=oos_mask_by_date,
                    draws=placebo_draws,
                )
            )
            row["beats_random_delta_p95"] = (
                row.get("random_delta_ann_p95") is not None
                and float(row.get("delta_ann") or 0.0) > float(row["random_delta_ann_p95"])
            )
            row["decision"] = _decision(row)
            rows.append(row)
            for date, value in series[oos_mask_by_date].items():
                daily_rows.append(
                    {
                        "date": pd.Timestamp(date).date().isoformat(),
                        "trigger_id": trigger.trigger_id,
                        "mode": mode,
                        "x0_r3_return": _round(base_book.reindex(series.index).fillna(0.0).where(r3_by_date.reindex(series.index).fillna(False), 0.0).loc[date], 8),
                        "veto_r3_return": _round(value, 8),
                        "delta": _round(value - base_book.reindex(series.index).fillna(0.0).where(r3_by_date.reindex(series.index).fillna(False), 0.0).loc[date], 8),
                    }
                )

    candidate_count = sum(row.get("decision") == "EVENT_VETO_RESEARCH_CANDIDATE" for row in rows)
    decision = (
        "HOLD_Z48_EVENT_VETO_HAS_RESEARCH_CANDIDATES"
        if candidate_count
        else "HOLD_Z48_EVENT_VETO_NO_X0_R3_IMPROVEMENT"
    )
    decision_counts: dict[str, int] = {}
    for row in rows:
        decision_counts[str(row.get("decision"))] = decision_counts.get(str(row.get("decision")), 0) + 1

    _write_csv(output_root / "phase3z48_event_veto_gate_audit.csv", rows)
    _write_csv(output_root / "phase3z48_event_veto_daily_delta.csv", daily_rows)
    summary = {
        "created_at": _now(),
        "decision": decision,
        "scope": "diagnostic_only_event_veto_delta_vs_locked_X0_R3_no_official_promotion",
        "dataset": str(dataset_path),
        "alpha_cards": str(alpha_cards),
        "shadow_object": str(shadow_object),
        "run_plan": str(run_plan_path),
        "row_count": int(len(frame)),
        "date_min": str(frame["date"].min().date()),
        "date_max": str(frame["date"].max().date()),
        "code_count": int(frame["code"].nunique()),
        "top_bottom_quantile": float(top_bottom_quantile),
        "placebo_draws": int(placebo_draws),
        "candidate_count": int(candidate_count),
        "decision_counts": decision_counts,
        "top_rows": sorted(
            rows,
            key=lambda item: (
                item.get("decision") == "EVENT_VETO_RESEARCH_CANDIDATE",
                float(item.get("delta_ann") or -999.0),
            ),
            reverse=True,
        )[:8],
        "hard_boundary": "Z48 cannot alter X0/R3, G2, J2/J4, Phase3P, or formula search state.",
        "outputs": {
            "audit_csv": str(output_root / "phase3z48_event_veto_gate_audit.csv"),
            "daily_delta_csv": str(output_root / "phase3z48_event_veto_daily_delta.csv"),
            "summary_json": str(output_root / "phase3z48_event_veto_gate_audit.json"),
            "summary_md": str(output_root / REPORT_FILENAME),
        },
    }
    _write_json(output_root / "phase3z48_event_veto_gate_audit.json", summary)

    lines = [
        "# Phase3Z48 Event Veto Gate Audit",
        "",
        f"- decision: `{decision}`",
        f"- candidate_count: `{candidate_count}`",
        f"- dataset: `{dataset_path}`",
        f"- date_range: `{summary['date_min']}` to `{summary['date_max']}`",
        "- scope: diagnostic only; locked X0/R3 is read-only.",
        "",
        "## Results",
        "",
        "| trigger | mode | active R3 days | delta ann | veto ann | base ann | random p95 | Sharpe | decision |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(rows, key=lambda item: float(item.get("delta_ann") or -999.0), reverse=True):
        lines.append(
            f"| {row.get('trigger_id')} | `{row.get('mode')}` | {row.get('veto_active_r3_days')} | "
            f"{row.get('delta_ann')} | {row.get('veto_full_ann')} | {row.get('base_full_ann')} | "
            f"{row.get('random_delta_ann_p95')} | {row.get('veto_sharpe')} | `{row.get('decision')}` |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A pass here means the event may be worth a later veto-gate research track, not official promotion.",
            "- Same-count random veto controls whether the improvement is more than randomly removing a similar number of stock-date rows.",
            "- Full-calendar X0/R3 delta is the headline; event standalone returns are not used for promotion.",
        ]
    )
    (output_root / REPORT_FILENAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--alpha-cards", type=Path, default=DEFAULT_ALPHA_CARDS)
    parser.add_argument("--shadow-object", type=Path, default=DEFAULT_SHADOW_OBJECT)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--run-plan", type=Path, default=DEFAULT_RUN_PLAN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--placebo-draws", type=int, default=30)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--audit-mode", choices=["market_day", "stock_level"], default="market_day")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(
        dataset_path=args.dataset_path,
        alpha_cards=args.alpha_cards,
        shadow_object=args.shadow_object,
        daily_returns=args.daily_returns,
        run_plan_path=args.run_plan,
        output_root=args.output_root,
        placebo_draws=args.placebo_draws,
        top_bottom_quantile=args.top_bottom_quantile,
        audit_mode=args.audit_mode,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
