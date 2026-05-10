from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.real_market_validation import (
    DEFAULT_EXECUTION_LAG_DAYS,
    SIGNAL_CLOCK_AFTER_OPEN,
    _available_market_panel_usecols,
    _limit_state_masks,
    _prepare_market_panel,
    _signal_evaluation_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


FROZEN_TOP6_ENSEMBLE: tuple[dict[str, Any], ...] = (
    {
        "candidate_id": "stockpit-compact-65b27be6d609",
        "research_family": "low_amount_crowding",
        "expression": "Neg(CSRank(Div(Mean($amount,10),Mean($amount,34))))",
        "validation_best_freq": 3,
        "validation_best_net": 0.000316,
        "predev_frozen_net": 0.0007,
    },
    {
        "candidate_id": "stockpit-compact-13a867506b13",
        "research_family": "low_volume_crowding",
        "expression": "Neg(CSRank(Div(Mean($volume,10),Mean($volume,34))))",
        "validation_best_freq": 2,
        "validation_best_net": 0.000352,
        "predev_frozen_net": 0.000553,
    },
    {
        "candidate_id": "stockpit-compact-82c9b149ee76",
        "research_family": "vol_scaled_reversal",
        "expression": "Neg(CSRank(Div(Mom($close,3),Std($ret,10))))",
        "validation_best_freq": 3,
        "validation_best_net": 0.000349,
        "predev_frozen_net": 0.000647,
    },
    {
        "candidate_id": "stockpit-compact-2442a7c29e43",
        "research_family": "vol_scaled_reversal",
        "expression": "Neg(CSRank(Div(Mom($close,3),Std($ret,20))))",
        "validation_best_freq": 3,
        "validation_best_net": 0.000381,
        "predev_frozen_net": 0.000639,
    },
    {
        "candidate_id": "stockpit-compact-6e62925db22c",
        "research_family": "open_price_position_reversal",
        "expression": "Neg(CSRank(Div(Sub($open,Mean($low,5)),Sub(Mean($high,5),Mean($low,5)))))",
        "validation_best_freq": 3,
        "validation_best_net": 0.00052,
        "predev_frozen_net": 0.000489,
    },
    {
        "candidate_id": "stockpit-compact-486021dfbd22",
        "research_family": "open_price_position_reversal",
        "expression": "Neg(CSRank(Div(Sub($open,Mean($low,20)),Sub(Mean($high,20),Mean($low,20)))))",
        "validation_best_freq": 3,
        "validation_best_net": 0.000396,
        "predev_frozen_net": 0.000477,
    },
)

DEFAULT_COST_BPS_GRID = (10.0, 20.0, 30.0)
DEFAULT_REBALANCE_FREQUENCY_DAYS = 3
DEFAULT_TOP_BOTTOM_QUANTILE = 0.2
DEFAULT_SECTOR_CAP_RATIO_PER_SIDE = 0.2


def _round_float(value: Any, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _sortino(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    downside = clean[clean < 0.0]
    if downside.empty:
        return _round_float(clean.mean())
    downside_std = float(downside.std(ddof=0))
    if downside_std <= 0.0:
        return None
    return _round_float(float(clean.mean() / downside_std * math.sqrt(len(clean))))


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    equity = (1.0 + clean).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    return _round_float(drawdown.min())


def _mean_or_none(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return _round_float(clean.mean()) if not clean.empty else None


def _raw_mean_or_none(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return float(clean.mean()) if not clean.empty else None


def _quantile_or_none(values: pd.Series, quantile: float) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return _round_float(clean.quantile(quantile)) if not clean.empty else None


def _load_panel(path: Path | str, *, max_rows: int | None = None) -> pd.DataFrame:
    path_obj = Path(path)
    if path_obj.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path_obj)
        if max_rows is not None:
            frame = frame.head(max_rows)
    else:
        frame = pd.read_csv(path_obj, usecols=_available_market_panel_usecols(path_obj), nrows=max_rows)
    return _prepare_market_panel(frame)


def build_stock_pit_compact_top6_ensemble_signal(
    frame: pd.DataFrame,
    *,
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
    component_specs: tuple[dict[str, Any], ...] = FROZEN_TOP6_ENSEMBLE,
) -> tuple[pd.Series, dict[str, Any]]:
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=signal_clock)
    cache: dict[str, pd.Series] = {}
    components: list[pd.Series] = []
    for spec in component_specs:
        raw = evaluate_panel_expression(
            signal_frame,
            str(spec["expression"]),
            cache=cache,
            field_lags=signal_clock_report["field_lags"],
        )
        components.append(raw.groupby(signal_frame["date"]).rank(pct=True))
    if not components:
        raise ValueError("component_specs_must_not_be_empty")
    ensemble = pd.concat(components, axis=1).mean(axis=1, skipna=True)
    return ensemble, signal_clock_report


def _entry_aligned_series(frame: pd.DataFrame, column: str, *, execution_lag_days: int) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    values = frame[column]
    if execution_lag_days <= 0:
        return values
    return values.groupby(frame["code"], sort=False).shift(-execution_lag_days)


def _select_sector_capped_codes(
    pool: pd.DataFrame,
    *,
    side_count: int,
    descending: bool,
    sector_cap_ratio: float,
) -> list[str]:
    if side_count <= 0 or pool.empty:
        return []
    ordered = pool.sort_values(["signal", "code"], ascending=[not descending, True])
    if "sector" not in ordered.columns or sector_cap_ratio <= 0.0:
        return [str(code) for code in ordered.head(side_count)["code"]]
    sector_limit = max(1, int(math.ceil(side_count * sector_cap_ratio)))
    selected: list[str] = []
    sector_counts: dict[str, int] = {}
    for row in ordered.itertuples(index=False):
        sector = str(getattr(row, "sector", "__missing_sector__"))
        if sector_counts.get(sector, 0) >= sector_limit:
            continue
        selected.append(str(getattr(row, "code")))
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= side_count:
            break
    return selected


def _side_capacity(day: pd.DataFrame, codes: set[str], *, prefix: str) -> dict[str, Any]:
    selected = day[day["code"].astype(str).isin(codes)]
    amounts = pd.to_numeric(selected["entry_amount"], errors="coerce").dropna()
    sector_counts = selected["sector"].astype(str).value_counts(normalize=True) if "sector" in selected else pd.Series(dtype=float)
    return {
        f"{prefix}_count": int(len(selected)),
        f"{prefix}_sector_count": int(selected["sector"].nunique(dropna=True)) if "sector" in selected else 0,
        f"{prefix}_max_sector_weight": _round_float(sector_counts.max()) if not sector_counts.empty else None,
        f"{prefix}_entry_amount_median": _round_float(amounts.median()) if not amounts.empty else None,
        f"{prefix}_entry_amount_p10": _round_float(amounts.quantile(0.10)) if not amounts.empty else None,
        f"{prefix}_entry_amount_p01": _round_float(amounts.quantile(0.01)) if not amounts.empty else None,
    }


def build_stock_pit_compact_top6_daily_portfolio(
    frame: pd.DataFrame,
    *,
    signal: pd.Series,
    evaluation_start_date: pd.Timestamp | None = None,
    evaluation_end_date: pd.Timestamp | None = None,
    horizon_days: int = 1,
    execution_lag_days: int = DEFAULT_EXECUTION_LAG_DAYS,
    rebalance_frequency_days: int = DEFAULT_REBALANCE_FREQUENCY_DAYS,
    top_bottom_quantile: float = DEFAULT_TOP_BOTTOM_QUANTILE,
    sector_cap_ratio_per_side: float = DEFAULT_SECTOR_CAP_RATIO_PER_SIDE,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    work, masks = _tradable_signal_work_frame(
        frame,
        signal,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        feature_lag_days=0,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
    )
    work = work.copy()
    work["entry_amount"] = _entry_aligned_series(frame, "amount", execution_lag_days=execution_lag_days).loc[work.index]
    if "sector" in frame.columns:
        work["sector"] = frame["sector"].astype(str).loc[work.index].fillna("__missing_sector__")

    rows: list[dict[str, Any]] = []
    current_top: set[str] | None = None
    current_bottom: set[str] | None = None
    rebalance_index = 0
    for date, day in work.groupby("date", sort=True):
        day = day.copy()
        day["code"] = day["code"].astype(str)
        should_rebalance = current_top is None or current_bottom is None or rebalance_index % rebalance_frequency_days == 0
        if should_rebalance:
            long_pool = day[~(day["entry_limit_up"] | day["entry_suspended"])]
            short_pool = day[~(day["entry_limit_down"] | day["entry_suspended"])]
            long_count = max(1, int(math.ceil(len(long_pool) * top_bottom_quantile)))
            short_count = max(1, int(math.ceil(len(short_pool) * top_bottom_quantile)))
            next_top = set(
                _select_sector_capped_codes(
                    long_pool,
                    side_count=long_count,
                    descending=True,
                    sector_cap_ratio=sector_cap_ratio_per_side,
                )
            )
            next_bottom = set(
                _select_sector_capped_codes(
                    short_pool,
                    side_count=short_count,
                    descending=False,
                    sector_cap_ratio=sector_cap_ratio_per_side,
                )
            )
            top_turnover = 1.0 if current_top is None else 1.0 - (len(next_top & current_top) / max(1, len(next_top)))
            bottom_turnover = 1.0 if current_bottom is None else 1.0 - (
                len(next_bottom & current_bottom) / max(1, len(next_bottom))
            )
            current_top = next_top
            current_bottom = next_bottom
        else:
            top_turnover = 0.0
            bottom_turnover = 0.0

        long_day = day[day["code"].isin(current_top or set())]
        short_day = day[day["code"].isin(current_bottom or set())]
        long_ret = _raw_mean_or_none(long_day["forward_return"])
        short_ret = _raw_mean_or_none(short_day["forward_return"])
        average_turnover = (top_turnover + bottom_turnover) / 2.0
        row = {
            "date": pd.Timestamp(date).date().isoformat(),
            "long_ret": long_ret,
            "short_ret": short_ret,
            "raw_ls": long_ret - short_ret if long_ret is not None and short_ret is not None else None,
            "top_turnover": top_turnover,
            "bottom_turnover": bottom_turnover,
            "average_one_way_turnover": average_turnover,
            "rebalanced": bool(should_rebalance),
        }
        row.update(_side_capacity(day, current_top or set(), prefix="long"))
        row.update(_side_capacity(day, current_bottom or set(), prefix="short"))
        rows.append(row)
        rebalance_index += 1

    return pd.DataFrame(rows), masks


def _stress_rows(daily: pd.DataFrame, *, cost_bps_grid: tuple[float, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cost_bps in cost_bps_grid:
        cost_rate = float(cost_bps) / 10_000.0
        for mode, raw_column in (("long_short", "raw_ls"), ("long_only", "long_ret")):
            raw = pd.to_numeric(daily[raw_column], errors="coerce")
            turnover = pd.to_numeric(daily["average_one_way_turnover"], errors="coerce").fillna(0.0)
            net = raw - (turnover * cost_rate)
            rows.append(
                {
                    "mode": mode,
                    "cost_bps": float(cost_bps),
                    "day_count": int(net.dropna().shape[0]),
                    "raw_mean": _mean_or_none(raw),
                    "net_mean": _mean_or_none(net),
                    "net_sortino": _sortino(net),
                    "avg_turnover": _mean_or_none(turnover),
                    "max_drawdown": _max_drawdown(net),
                    "positive_day_ratio": _round_float(float((net.dropna() > 0.0).mean())) if not net.dropna().empty else None,
                }
            )
    return rows


def _capacity_summary(daily: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for column in (
        "long_count",
        "short_count",
        "long_sector_count",
        "short_sector_count",
        "long_max_sector_weight",
        "short_max_sector_weight",
        "long_entry_amount_median",
        "long_entry_amount_p10",
        "long_entry_amount_p01",
        "short_entry_amount_median",
        "short_entry_amount_p10",
        "short_entry_amount_p01",
    ):
        summary[f"{column}_mean"] = _mean_or_none(daily[column]) if column in daily else None
        summary[f"{column}_p10"] = _quantile_or_none(daily[column], 0.10) if column in daily else None
    return summary


def _tradability_mask_report(masks: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(masks["available"]),
        "limit_up_source": masks["limit_up_source"],
        "limit_down_source": masks["limit_down_source"],
        "derived_from_rt_change": bool(masks["derived_from_rt_change"]),
    }


def build_stock_pit_compact_top6_ensemble_report(
    slices: list[dict[str, Any]],
    *,
    component_specs: tuple[dict[str, Any], ...] = FROZEN_TOP6_ENSEMBLE,
    experiment_id: str = "20260429_stock_pit_compact_top6_ensemble_reusable_report",
    signal_clock: str = SIGNAL_CLOCK_AFTER_OPEN,
    horizon_days: int = 1,
    execution_lag_days: int = DEFAULT_EXECUTION_LAG_DAYS,
    rebalance_frequency_days: int = DEFAULT_REBALANCE_FREQUENCY_DAYS,
    top_bottom_quantile: float = DEFAULT_TOP_BOTTOM_QUANTILE,
    sector_cap_ratio_per_side: float = DEFAULT_SECTOR_CAP_RATIO_PER_SIDE,
    cost_bps_grid: tuple[float, ...] = DEFAULT_COST_BPS_GRID,
    max_rows: int | None = None,
    include_daily: bool = True,
) -> dict[str, Any]:
    report_slices: list[dict[str, Any]] = []
    for spec in slices:
        if "frame" in spec:
            frame = _prepare_market_panel(spec["frame"].copy())
            dataset_path = str(spec.get("dataset_path", "memory://stock-pit-compact-ensemble"))
        else:
            dataset_path = str(spec["dataset_path"])
            frame = _load_panel(dataset_path, max_rows=max_rows)
        start = pd.Timestamp(spec["evaluation_start_date"]) if spec.get("evaluation_start_date") is not None else None
        end = pd.Timestamp(spec["evaluation_end_date"]) if spec.get("evaluation_end_date") is not None else None
        signal, signal_clock_report = build_stock_pit_compact_top6_ensemble_signal(
            frame,
            signal_clock=signal_clock,
            component_specs=component_specs,
        )
        daily, masks = build_stock_pit_compact_top6_daily_portfolio(
            frame,
            signal=signal,
            evaluation_start_date=start,
            evaluation_end_date=end,
            horizon_days=horizon_days,
            execution_lag_days=execution_lag_days,
            rebalance_frequency_days=rebalance_frequency_days,
            top_bottom_quantile=top_bottom_quantile,
            sector_cap_ratio_per_side=sector_cap_ratio_per_side,
        )
        item = {
            "label": str(spec["label"]),
            "dataset_path": dataset_path,
            "evaluation_start_date": start.date().isoformat() if start is not None else None,
            "evaluation_end_date": end.date().isoformat() if end is not None else None,
            "day_count": int(len(daily)),
            "signal_clock_report": signal_clock_report,
            "tradability_masks": _tradability_mask_report(masks),
            "stress": _stress_rows(daily, cost_bps_grid=cost_bps_grid),
            "capacity_summary": _capacity_summary(daily),
        }
        if include_daily:
            item["daily"] = daily.to_dict(orient="records")
        report_slices.append(item)

    return {
        "experiment_id": experiment_id,
        "created_at": utc_now_iso(),
        "component_set": "stock_pit_compact_top6_frozen",
        "selected_candidates": [dict(spec) for spec in component_specs],
        "parameters": {
            "signal_clock": signal_clock,
            "field_lag_policy": "all component expressions receive signal_clock field_lags",
            "execution_lag_days": int(execution_lag_days),
            "horizon_days": int(horizon_days),
            "rebalance_frequency_days": int(rebalance_frequency_days),
            "top_bottom_quantile": float(top_bottom_quantile),
            "sector_cap_ratio_per_side": float(sector_cap_ratio_per_side),
            "sector_cap_policy": "applied only when a sector column is present in the input panel",
            "cost_bps_grid": [float(item) for item in cost_bps_grid],
            "modes": ["long_short", "long_only"],
            "capacity_proxy": "T+1 entry-day amount distribution of selected baskets",
        },
        "bias_audit": {
            "feature_timestamp": "after_open may use current open; full-day bar fields are field-lagged",
            "execution": "T+1 close-to-close forward return; entry limit-up blocks long entry and entry limit-down blocks short entry",
            "exit_filter_policy": "exit-day limit states are reported by lower-level validation but not used to drop rows",
            "discovery_status": "frozen reproduction of prior stock-PIT compact pocket",
            "decision": "HOLD_RESEARCH",
        },
        "slices": report_slices,
        "commercial_edge_claim_allowed": False,
        "decision": "HOLD_RESEARCH",
    }


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_stock_pit_compact_top6_ensemble_report(
    output_path: Path | str,
    slices: list[dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    report = build_stock_pit_compact_top6_ensemble_report(slices, **kwargs)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
    return report
