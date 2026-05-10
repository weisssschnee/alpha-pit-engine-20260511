from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.domain.models import utc_now_iso
from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    DEFAULT_RECENT_WARMUP_DAYS,
    _limit_state_masks,
    _load_recent_quarter_market_panel,
    _quarterly_window_label,
    _tradable_daily_ic_spread_turnover_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)


SEARCH_CORE_V20_VERSION = "phase2-search-core-v20-v18-activation-geometry-2026-04-27"
V18_CENTER_EXPRESSION = "CSRank(Div(Mom($close,8),Mean(Mean(Abs($ret),2),2)))"


def _mean_or_none(values: list[float]) -> float | None:
    clean = [float(value) for value in values if pd.notna(value) and math.isfinite(float(value))]
    return round(float(np.mean(clean)), 6) if clean else None


def _sortino(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    downside = clean[clean < 0]
    if downside.empty:
        return round(float(clean.mean()), 6)
    downside_std = float(downside.std(ddof=0))
    if downside_std <= 0:
        return None
    return round(float(clean.mean() / downside_std * math.sqrt(len(clean))), 6)


def _daily_state_features(frame: pd.DataFrame, signal: pd.Series) -> pd.DataFrame:
    masks = _limit_state_masks(frame)
    enriched = frame[["date", "code", "ret", "amount", "volume", "close"]].copy()
    enriched["signal"] = signal
    enriched["limit_up"] = masks["limit_up"]
    enriched["limit_down"] = masks["limit_down"]

    rows: list[dict[str, Any]] = []
    for date, day in enriched.groupby("date", sort=True):
        ret = pd.to_numeric(day["ret"], errors="coerce")
        amount = pd.to_numeric(day["amount"], errors="coerce")
        signal_day = pd.to_numeric(day["signal"], errors="coerce")
        rows.append(
            {
                "date": date,
                "window": _quarterly_window_label(pd.Timestamp(date)),
                "up_ratio": float((ret > 0).mean()),
                "down_ratio": float((ret < 0).mean()),
                "breadth_balance": float((ret > 0).mean() - (ret < 0).mean()),
                "equal_weight_ret": float(ret.mean()) if not ret.dropna().empty else np.nan,
                "abs_ret_mean": float(ret.abs().mean()) if not ret.dropna().empty else np.nan,
                "ret_dispersion": float(ret.std(ddof=0)) if not ret.dropna().empty else np.nan,
                "amount_sum": float(amount.sum()) if not amount.dropna().empty else np.nan,
                "limit_up_ratio": float(pd.Series(day["limit_up"]).mean()),
                "limit_down_ratio": float(pd.Series(day["limit_down"]).mean()),
                "signal_dispersion": float(signal_day.std(ddof=0)) if not signal_day.dropna().empty else np.nan,
                "signal_top_bottom_gap": float(signal_day.quantile(0.8) - signal_day.quantile(0.2))
                if signal_day.dropna().shape[0] >= 5
                else np.nan,
            }
        )

    daily = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    daily["amount_sum_change_5"] = daily["amount_sum"] / daily["amount_sum"].rolling(5, min_periods=3).mean() - 1.0
    daily["breadth_balance_mean_3"] = daily["breadth_balance"].rolling(3, min_periods=2).mean()
    daily["ret_dispersion_change_5"] = daily["ret_dispersion"] / daily["ret_dispersion"].rolling(5, min_periods=3).mean() - 1.0
    return daily


def _gate_specs(features: pd.DataFrame) -> list[dict[str, Any]]:
    feature_names = [
        "up_ratio",
        "breadth_balance",
        "equal_weight_ret",
        "abs_ret_mean",
        "ret_dispersion",
        "amount_sum_change_5",
        "limit_up_ratio",
        "limit_down_ratio",
        "signal_dispersion",
        "signal_top_bottom_gap",
        "breadth_balance_mean_3",
        "ret_dispersion_change_5",
    ]
    specs: list[dict[str, Any]] = []
    for feature in feature_names:
        values = pd.to_numeric(features[feature], errors="coerce").dropna()
        if values.nunique(dropna=True) < 3:
            continue
        for quantile in (0.3, 0.5, 0.7):
            threshold = float(values.quantile(quantile))
            specs.append(
                {
                    "gate_id": f"{feature}_ge_q{int(quantile * 100)}",
                    "feature": feature,
                    "direction": "ge",
                    "quantile": quantile,
                    "threshold": round(threshold, 10),
                }
            )
            specs.append(
                {
                    "gate_id": f"{feature}_le_q{int(quantile * 100)}",
                    "feature": feature,
                    "direction": "le",
                    "quantile": quantile,
                    "threshold": round(threshold, 10),
                }
            )
    return specs


def _active_mask(daily: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
    feature_values = pd.to_numeric(daily[spec["feature"]], errors="coerce")
    if spec["direction"] == "ge":
        return (feature_values >= float(spec["threshold"])).fillna(False)
    return (feature_values <= float(spec["threshold"])).fillna(False)


def _metrics(daily: pd.DataFrame, *, cost_bps: float) -> dict[str, Any]:
    if daily.empty:
        return {
            "day_count": 0,
            "mean_rank_ic": None,
            "rank_ic_hit_rate": None,
            "mean_long_short_return": None,
            "mean_cost_adjusted_spread": None,
            "mean_one_way_turnover": None,
            "cost_adjusted_sortino": None,
            "quarter_count": 0,
            "min_quarter_ic": None,
            "negative_quarter_count": None,
            "quarter_floor_pass": False,
            "windows": [],
        }
    work = daily.copy()
    cost_per_turnover = float(cost_bps) / 10_000.0
    work["cost_adjusted_long_short_return"] = work["long_short_return"] - (
        work["average_one_way_turnover"].fillna(0.0) * cost_per_turnover
    )
    rank_ic = pd.to_numeric(work["rank_ic"], errors="coerce").dropna()
    spread = pd.to_numeric(work["long_short_return"], errors="coerce")
    net = pd.to_numeric(work["cost_adjusted_long_short_return"], errors="coerce")
    turnover = pd.to_numeric(work["average_one_way_turnover"], errors="coerce").dropna()

    windows: list[dict[str, Any]] = []
    for window, window_frame in work.groupby("window", sort=True):
        window_ic = pd.to_numeric(window_frame["rank_ic"], errors="coerce").dropna()
        window_net = pd.to_numeric(window_frame["cost_adjusted_long_short_return"], errors="coerce").dropna()
        windows.append(
            {
                "window": str(window),
                "day_count": int(len(window_frame)),
                "mean_rank_ic": round(float(window_ic.mean()), 6) if not window_ic.empty else None,
                "mean_cost_adjusted_spread": round(float(window_net.mean()), 6) if not window_net.empty else None,
            }
        )
    quarter_ics = [item["mean_rank_ic"] for item in windows if item["mean_rank_ic"] is not None]
    return {
        "day_count": int(len(work)),
        "mean_rank_ic": round(float(rank_ic.mean()), 6) if not rank_ic.empty else None,
        "rank_ic_hit_rate": round(float((rank_ic > 0).mean()), 6) if not rank_ic.empty else None,
        "mean_long_short_return": round(float(spread.mean()), 6) if not spread.dropna().empty else None,
        "mean_cost_adjusted_spread": round(float(net.mean()), 6) if not net.dropna().empty else None,
        "mean_one_way_turnover": round(float(turnover.mean()), 6) if not turnover.empty else None,
        "cost_adjusted_sortino": _sortino(net),
        "quarter_count": len(quarter_ics),
        "min_quarter_ic": round(float(min(quarter_ics)), 6) if quarter_ics else None,
        "negative_quarter_count": int(sum(1 for value in quarter_ics if value < 0)) if quarter_ics else None,
        "quarter_floor_pass": bool(quarter_ics and all(value >= 0 for value in quarter_ics)),
        "windows": windows,
    }


def _activation_daily_dataset(
    expression: str,
    *,
    path: Path | str,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    horizon_days: int,
    execution_lag_days: int,
    top_bottom_quantile: float,
) -> tuple[pd.DataFrame, pd.Timestamp, pd.Timestamp, int, dict[str, Any]]:
    frame, evaluation_start_date, evaluation_end_date = _load_recent_quarter_market_panel(
        path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    cache: dict[str, pd.Series] = {}
    signal = evaluate_panel_expression(frame, expression, cache=cache)
    work, tradability_masks = _tradable_signal_work_frame(
        frame,
        signal,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        evaluation_start_date=evaluation_start_date,
        evaluation_end_date=evaluation_end_date,
    )
    daily = _tradable_daily_ic_spread_turnover_frame(work, top_bottom_quantile=top_bottom_quantile)
    state = _daily_state_features(frame, signal)
    state = state[(state["date"] >= evaluation_start_date) & (state["date"] <= evaluation_end_date)]
    daily = daily.merge(state.drop(columns=["window"]), on="date", how="left")
    return daily, evaluation_start_date, evaluation_end_date, int(len(frame)), tradability_masks


def build_v20_activation_geometry_report(
    expression: str = V18_CENTER_EXPRESSION,
    *,
    path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    recent_quarter_window_count: int = 4,
    recent_warmup_days: int = DEFAULT_RECENT_WARMUP_DAYS,
    horizon_days: int = 1,
    execution_lag_days: int = 1,
    top_bottom_quantile: float = 0.2,
    cost_bps: float = 10.0,
    min_active_day_count: int = 20,
) -> dict[str, Any]:
    daily, evaluation_start_date, evaluation_end_date, loaded_panel_rows, tradability_masks = _activation_daily_dataset(
        expression,
        path=path,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        top_bottom_quantile=top_bottom_quantile,
    )
    baseline = _metrics(daily, cost_bps=cost_bps)

    gates: list[dict[str, Any]] = []
    for spec in _gate_specs(daily):
        active_mask = _active_mask(daily, spec)
        active = daily[active_mask.fillna(False)].copy()
        inactive = daily[~active_mask.fillna(False)].copy()
        active_metrics = _metrics(active, cost_bps=cost_bps)
        if active_metrics["day_count"] < min_active_day_count:
            continue
        inactive_metrics = _metrics(inactive, cost_bps=cost_bps)
        baseline_spread = baseline.get("mean_cost_adjusted_spread")
        active_spread = active_metrics.get("mean_cost_adjusted_spread")
        inactive_spread = inactive_metrics.get("mean_cost_adjusted_spread")
        gates.append(
            {
                **spec,
                "active_metrics": active_metrics,
                "inactive_metrics": inactive_metrics,
                "active_day_ratio": round(active_metrics["day_count"] / max(1, len(daily)), 6),
                "cost_adjusted_spread_lift_vs_baseline": round(float(active_spread - baseline_spread), 6)
                if active_spread is not None and baseline_spread is not None
                else None,
                "cost_adjusted_spread_lift_vs_inactive": round(float(active_spread - inactive_spread), 6)
                if active_spread is not None and inactive_spread is not None
                else None,
                "exploratory_same_sample_gate": True,
            }
        )

    gates.sort(
        key=lambda item: (
            item["active_metrics"].get("quarter_floor_pass") is True,
            item.get("cost_adjusted_spread_lift_vs_baseline") is not None,
            item.get("cost_adjusted_spread_lift_vs_baseline") or -999.0,
            item["active_metrics"].get("mean_cost_adjusted_spread") or -999.0,
            item["active_metrics"].get("mean_rank_ic") or -999.0,
        ),
        reverse=True,
    )
    return {
        "run_id": "phase2-search-core-v20-v18-activation-geometry",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V20_VERSION,
        "expression": expression,
        "dataset_path": str(path),
        "screening_mode": f"recent_{recent_quarter_window_count}_quarter_activation_geometry",
        "recent_quarter_window_count": recent_quarter_window_count,
        "recent_warmup_days": recent_warmup_days,
        "evaluation_start_date": evaluation_start_date.date().isoformat(),
        "evaluation_end_date": evaluation_end_date.date().isoformat(),
        "horizon_days": horizon_days,
        "execution_lag_days": execution_lag_days,
        "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
        "top_bottom_quantile": top_bottom_quantile,
        "cost_bps": cost_bps,
        "loaded_panel_rows": loaded_panel_rows,
        "daily_observation_count": int(len(daily)),
        "tradability_filter_available": bool(tradability_masks["available"]),
        "tradability_limit_up_source": tradability_masks["limit_up_source"],
        "tradability_limit_down_source": tradability_masks["limit_down_source"],
        "baseline_metrics": baseline,
        "gate_count": len(gates),
        "top_gates": gates[:20],
        "all_gates": gates,
        "real_edge_claim_allowed": False,
        "gate_role": "same_sample_activation_hypothesis_not_production_rule",
}


def build_v20_activation_holdout_report(
    expression: str = V18_CENTER_EXPRESSION,
    *,
    path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    recent_quarter_window_count: int = 4,
    recent_warmup_days: int = DEFAULT_RECENT_WARMUP_DAYS,
    horizon_days: int = 1,
    execution_lag_days: int = 1,
    top_bottom_quantile: float = 0.2,
    cost_bps: float = 10.0,
    min_train_active_day_count: int = 20,
    min_test_active_day_count: int = 10,
    top_k_train_gates: int = 10,
) -> dict[str, Any]:
    daily, evaluation_start_date, evaluation_end_date, loaded_panel_rows, tradability_masks = _activation_daily_dataset(
        expression,
        path=path,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        top_bottom_quantile=top_bottom_quantile,
    )
    windows = sorted(str(value) for value in daily["window"].dropna().unique())
    split_index = max(1, len(windows) // 2)
    train_windows = windows[:split_index]
    test_windows = windows[split_index:]
    train = daily[daily["window"].isin(train_windows)].copy()
    test = daily[daily["window"].isin(test_windows)].copy()
    train_baseline = _metrics(train, cost_bps=cost_bps)
    test_baseline = _metrics(test, cost_bps=cost_bps)

    train_gates: list[dict[str, Any]] = []
    for spec in _gate_specs(train):
        train_active_mask = _active_mask(train, spec)
        train_active = train[train_active_mask].copy()
        train_inactive = train[~train_active_mask].copy()
        train_metrics = _metrics(train_active, cost_bps=cost_bps)
        if train_metrics["day_count"] < min_train_active_day_count:
            continue
        train_inactive_metrics = _metrics(train_inactive, cost_bps=cost_bps)
        train_spread = train_metrics.get("mean_cost_adjusted_spread")
        train_baseline_spread = train_baseline.get("mean_cost_adjusted_spread")
        train_inactive_spread = train_inactive_metrics.get("mean_cost_adjusted_spread")
        train_gates.append(
            {
                **spec,
                "train_active_metrics": train_metrics,
                "train_inactive_metrics": train_inactive_metrics,
                "train_active_day_ratio": round(train_metrics["day_count"] / max(1, len(train)), 6),
                "train_cost_adjusted_spread_lift_vs_baseline": round(float(train_spread - train_baseline_spread), 6)
                if train_spread is not None and train_baseline_spread is not None
                else None,
                "train_cost_adjusted_spread_lift_vs_inactive": round(float(train_spread - train_inactive_spread), 6)
                if train_spread is not None and train_inactive_spread is not None
                else None,
            }
        )

    train_gates.sort(
        key=lambda item: (
            item["train_active_metrics"].get("quarter_floor_pass") is True,
            item.get("train_cost_adjusted_spread_lift_vs_baseline") is not None,
            item.get("train_cost_adjusted_spread_lift_vs_baseline") or -999.0,
            item["train_active_metrics"].get("mean_cost_adjusted_spread") or -999.0,
        ),
        reverse=True,
    )

    holdout_gates: list[dict[str, Any]] = []
    for gate in train_gates[:top_k_train_gates]:
        test_active_mask = _active_mask(test, gate)
        test_active = test[test_active_mask].copy()
        test_inactive = test[~test_active_mask].copy()
        test_metrics = _metrics(test_active, cost_bps=cost_bps)
        test_inactive_metrics = _metrics(test_inactive, cost_bps=cost_bps)
        test_spread = test_metrics.get("mean_cost_adjusted_spread")
        test_baseline_spread = test_baseline.get("mean_cost_adjusted_spread")
        test_inactive_spread = test_inactive_metrics.get("mean_cost_adjusted_spread")
        holdout_gates.append(
            {
                **{key: gate[key] for key in ("gate_id", "feature", "direction", "quantile", "threshold")},
                "train_active_metrics": gate["train_active_metrics"],
                "train_inactive_metrics": gate["train_inactive_metrics"],
                "test_active_metrics": test_metrics,
                "test_inactive_metrics": test_inactive_metrics,
                "test_active_day_ratio": round(test_metrics["day_count"] / max(1, len(test)), 6),
                "test_active_day_count_too_small": test_metrics["day_count"] < min_test_active_day_count,
                "test_cost_adjusted_spread_lift_vs_baseline": round(float(test_spread - test_baseline_spread), 6)
                if test_spread is not None and test_baseline_spread is not None
                else None,
                "test_cost_adjusted_spread_lift_vs_inactive": round(float(test_spread - test_inactive_spread), 6)
                if test_spread is not None and test_inactive_spread is not None
                else None,
                "holdout_pass": bool(
                    test_metrics["day_count"] >= min_test_active_day_count
                    and test_metrics.get("mean_cost_adjusted_spread") is not None
                    and test_baseline.get("mean_cost_adjusted_spread") is not None
                    and test_metrics["mean_cost_adjusted_spread"] > test_baseline["mean_cost_adjusted_spread"]
                    and test_metrics.get("mean_rank_ic") is not None
                    and test_baseline.get("mean_rank_ic") is not None
                    and test_metrics["mean_rank_ic"] > test_baseline["mean_rank_ic"]
                ),
            }
        )

    holdout_gates.sort(
        key=lambda item: (
            item["holdout_pass"],
            item.get("test_cost_adjusted_spread_lift_vs_baseline") is not None,
            item.get("test_cost_adjusted_spread_lift_vs_baseline") or -999.0,
            item["test_active_metrics"].get("mean_rank_ic") or -999.0,
        ),
        reverse=True,
    )

    return {
        "run_id": "phase2-search-core-v20-v18-activation-holdout",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V20_VERSION,
        "expression": expression,
        "dataset_path": str(path),
        "screening_mode": f"recent_{recent_quarter_window_count}_quarter_activation_holdout",
        "recent_quarter_window_count": recent_quarter_window_count,
        "recent_warmup_days": recent_warmup_days,
        "evaluation_start_date": evaluation_start_date.date().isoformat(),
        "evaluation_end_date": evaluation_end_date.date().isoformat(),
        "train_windows": train_windows,
        "test_windows": test_windows,
        "horizon_days": horizon_days,
        "execution_lag_days": execution_lag_days,
        "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
        "top_bottom_quantile": top_bottom_quantile,
        "cost_bps": cost_bps,
        "loaded_panel_rows": loaded_panel_rows,
        "daily_observation_count": int(len(daily)),
        "train_day_count": int(len(train)),
        "test_day_count": int(len(test)),
        "tradability_filter_available": bool(tradability_masks["available"]),
        "tradability_limit_up_source": tradability_masks["limit_up_source"],
        "tradability_limit_down_source": tradability_masks["limit_down_source"],
        "train_baseline_metrics": train_baseline,
        "test_baseline_metrics": test_baseline,
        "train_gate_count": len(train_gates),
        "holdout_gate_count": len(holdout_gates),
        "holdout_pass_count": sum(1 for item in holdout_gates if item["holdout_pass"]),
        "top_holdout_gates": holdout_gates[:20],
        "real_edge_claim_allowed": False,
        "gate_role": "two_half_holdout_activation_hypothesis_not_production_rule",
    }


def write_v20_activation_geometry_report(
    output_path: Path | str,
    expression: str = V18_CENTER_EXPRESSION,
    **kwargs: Any,
) -> dict[str, Any]:
    report = build_v20_activation_geometry_report(expression, **kwargs)
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def write_v20_activation_holdout_report(
    output_path: Path | str,
    expression: str = V18_CENTER_EXPRESSION,
    **kwargs: Any,
) -> dict[str, Any]:
    report = build_v20_activation_holdout_report(expression, **kwargs)
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _gate_key(spec: dict[str, Any]) -> str:
    return f"{spec['feature']}_{spec['direction']}_q{int(float(spec['quantile']) * 100)}"


def _split_specs(windows: list[str]) -> list[dict[str, Any]]:
    splits: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...], str]] = set()

    def add(train: list[str], test: list[str], mode: str) -> None:
        if not train or not test:
            return
        key = (tuple(train), tuple(test), mode)
        if key in seen:
            return
        seen.add(key)
        splits.append(
            {
                "split_id": f"{mode}-{len(splits) + 1:02d}",
                "mode": mode,
                "train_windows": train,
                "test_windows": test,
            }
        )

    for train_count in (1, 2):
        for start in range(0, len(windows) - train_count):
            add(windows[start : start + train_count], [windows[start + train_count]], f"rolling_{train_count}q_to_1q")

    for test_index in range(1, len(windows)):
        add(windows[:test_index], [windows[test_index]], "expanding_to_1q")

    return splits


def _evaluate_rolling_split(
    daily: pd.DataFrame,
    split: dict[str, Any],
    *,
    cost_bps: float,
    min_train_active_day_count: int,
    min_test_active_day_count: int,
) -> dict[str, Any]:
    train = daily[daily["window"].isin(split["train_windows"])].copy()
    test = daily[daily["window"].isin(split["test_windows"])].copy()
    train_baseline = _metrics(train, cost_bps=cost_bps)
    test_baseline = _metrics(test, cost_bps=cost_bps)
    gate_rows: list[dict[str, Any]] = []

    for spec in _gate_specs(train):
        train_active_mask = _active_mask(train, spec)
        test_active_mask = _active_mask(test, spec)
        train_active = train[train_active_mask].copy()
        train_inactive = train[~train_active_mask].copy()
        test_active = test[test_active_mask].copy()
        test_inactive = test[~test_active_mask].copy()
        train_active_metrics = _metrics(train_active, cost_bps=cost_bps)
        test_active_metrics = _metrics(test_active, cost_bps=cost_bps)
        if train_active_metrics["day_count"] < min_train_active_day_count:
            continue
        train_inactive_metrics = _metrics(train_inactive, cost_bps=cost_bps)
        test_inactive_metrics = _metrics(test_inactive, cost_bps=cost_bps)

        train_lift = None
        if (
            train_active_metrics.get("mean_cost_adjusted_spread") is not None
            and train_baseline.get("mean_cost_adjusted_spread") is not None
        ):
            train_lift = round(
                float(train_active_metrics["mean_cost_adjusted_spread"] - train_baseline["mean_cost_adjusted_spread"]),
                6,
            )
        test_lift = None
        if (
            test_active_metrics.get("mean_cost_adjusted_spread") is not None
            and test_baseline.get("mean_cost_adjusted_spread") is not None
        ):
            test_lift = round(
                float(test_active_metrics["mean_cost_adjusted_spread"] - test_baseline["mean_cost_adjusted_spread"]),
                6,
            )

        selected_by_train = bool(
            train_active_metrics["day_count"] >= min_train_active_day_count
            and train_active_metrics.get("mean_cost_adjusted_spread") is not None
            and train_baseline.get("mean_cost_adjusted_spread") is not None
            and train_active_metrics["mean_cost_adjusted_spread"] > train_baseline["mean_cost_adjusted_spread"]
            and train_active_metrics.get("mean_rank_ic") is not None
            and train_baseline.get("mean_rank_ic") is not None
            and train_active_metrics["mean_rank_ic"] > train_baseline["mean_rank_ic"]
        )
        test_pass = bool(
            selected_by_train
            and test_active_metrics["day_count"] >= min_test_active_day_count
            and test_active_metrics.get("mean_cost_adjusted_spread") is not None
            and test_baseline.get("mean_cost_adjusted_spread") is not None
            and test_active_metrics["mean_cost_adjusted_spread"] > test_baseline["mean_cost_adjusted_spread"]
            and test_active_metrics.get("mean_rank_ic") is not None
            and test_baseline.get("mean_rank_ic") is not None
            and test_active_metrics["mean_rank_ic"] > test_baseline["mean_rank_ic"]
        )
        gate_rows.append(
            {
                **spec,
                "gate_key": _gate_key(spec),
                "train_active_metrics": train_active_metrics,
                "train_inactive_metrics": train_inactive_metrics,
                "test_active_metrics": test_active_metrics,
                "test_inactive_metrics": test_inactive_metrics,
                "train_cost_adjusted_spread_lift_vs_baseline": train_lift,
                "test_cost_adjusted_spread_lift_vs_baseline": test_lift,
                "selected_by_train": selected_by_train,
                "test_pass": test_pass,
            }
        )

    gate_rows.sort(
        key=lambda item: (
            item["selected_by_train"],
            item["test_pass"],
            item.get("test_cost_adjusted_spread_lift_vs_baseline") is not None,
            item.get("test_cost_adjusted_spread_lift_vs_baseline") or -999.0,
            item["test_active_metrics"].get("mean_rank_ic") or -999.0,
        ),
        reverse=True,
    )
    return {
        **split,
        "train_day_count": int(len(train)),
        "test_day_count": int(len(test)),
        "train_baseline_metrics": train_baseline,
        "test_baseline_metrics": test_baseline,
        "evaluated_gate_count": len(gate_rows),
        "selected_gate_count": sum(1 for item in gate_rows if item["selected_by_train"]),
        "test_pass_count": sum(1 for item in gate_rows if item["test_pass"]),
        "top_gates": gate_rows[:12],
        "all_gates": gate_rows,
    }


def _aggregate_rolling_splits(split_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for split in split_reports:
        for gate in split["all_gates"]:
            grouped[gate["gate_key"]].append(gate)

    summaries: list[dict[str, Any]] = []
    for key, gates in grouped.items():
        selected = [gate for gate in gates if gate["selected_by_train"]]
        testable = [gate for gate in selected if gate["test_active_metrics"]["day_count"] > 0]
        passed = [gate for gate in selected if gate["test_pass"]]
        test_lifts = [
            float(gate["test_cost_adjusted_spread_lift_vs_baseline"])
            for gate in testable
            if gate.get("test_cost_adjusted_spread_lift_vs_baseline") is not None
        ]
        train_lifts = [
            float(gate["train_cost_adjusted_spread_lift_vs_baseline"])
            for gate in selected
            if gate.get("train_cost_adjusted_spread_lift_vs_baseline") is not None
        ]
        test_ics = [
            float(gate["test_active_metrics"]["mean_rank_ic"])
            for gate in testable
            if gate["test_active_metrics"].get("mean_rank_ic") is not None
        ]
        active_days = [int(gate["test_active_metrics"]["day_count"]) for gate in testable]
        template = gates[0]
        summaries.append(
            {
                "gate_key": key,
                "feature": template["feature"],
                "direction": template["direction"],
                "quantile": template["quantile"],
                "evaluated_split_count": len(gates),
                "selected_split_count": len(selected),
                "testable_selected_split_count": len(testable),
                "test_pass_count": len(passed),
                "test_pass_ratio_selected": round(len(passed) / len(selected), 6) if selected else 0.0,
                "mean_train_lift": _mean_or_none(train_lifts),
                "mean_test_lift": _mean_or_none(test_lifts),
                "min_test_lift": round(float(min(test_lifts)), 6) if test_lifts else None,
                "mean_test_active_ic": _mean_or_none(test_ics),
                "total_test_active_days": int(sum(active_days)),
                "min_test_active_days": int(min(active_days)) if active_days else 0,
                "all_selected_test_lifts_positive": bool(test_lifts and all(value > 0 for value in test_lifts)),
            }
        )

    summaries.sort(
        key=lambda item: (
            item["test_pass_count"],
            item["all_selected_test_lifts_positive"],
            item["mean_test_lift"] is not None,
            item["mean_test_lift"] or -999.0,
            item["total_test_active_days"],
            item["mean_test_active_ic"] or -999.0,
        ),
        reverse=True,
    )
    return summaries


def build_v21_rolling_activation_search_report(
    expression: str = V18_CENTER_EXPRESSION,
    *,
    path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    recent_quarter_window_count: int = 4,
    recent_warmup_days: int = DEFAULT_RECENT_WARMUP_DAYS,
    horizon_days: int = 1,
    execution_lag_days: int = 1,
    top_bottom_quantile: float = 0.2,
    cost_bps: float = 10.0,
    min_train_active_day_count: int = 12,
    min_test_active_day_count: int = 5,
) -> dict[str, Any]:
    daily, evaluation_start_date, evaluation_end_date, loaded_panel_rows, tradability_masks = _activation_daily_dataset(
        expression,
        path=path,
        recent_quarter_window_count=recent_quarter_window_count,
        recent_warmup_days=recent_warmup_days,
        horizon_days=horizon_days,
        execution_lag_days=execution_lag_days,
        top_bottom_quantile=top_bottom_quantile,
    )
    windows = sorted(str(value) for value in daily["window"].dropna().unique())
    split_reports = [
        _evaluate_rolling_split(
            daily,
            split,
            cost_bps=cost_bps,
            min_train_active_day_count=min_train_active_day_count,
            min_test_active_day_count=min_test_active_day_count,
        )
        for split in _split_specs(windows)
    ]
    gate_summaries = _aggregate_rolling_splits(split_reports)
    baseline = _metrics(daily, cost_bps=cost_bps)
    return {
        "run_id": "phase2-search-core-v21-rolling-activation-search",
        "created_at": utc_now_iso(),
        "search_core_version": SEARCH_CORE_V20_VERSION,
        "expression": expression,
        "dataset_path": str(path),
        "screening_mode": f"recent_{recent_quarter_window_count}_quarter_rolling_activation_search",
        "recent_quarter_window_count": recent_quarter_window_count,
        "recent_warmup_days": recent_warmup_days,
        "evaluation_start_date": evaluation_start_date.date().isoformat(),
        "evaluation_end_date": evaluation_end_date.date().isoformat(),
        "windows": windows,
        "horizon_days": horizon_days,
        "execution_lag_days": execution_lag_days,
        "execution_policy": "signal_t_execute_t_plus_1_exit_t_plus_2_close_to_close",
        "top_bottom_quantile": top_bottom_quantile,
        "cost_bps": cost_bps,
        "loaded_panel_rows": loaded_panel_rows,
        "daily_observation_count": int(len(daily)),
        "tradability_filter_available": bool(tradability_masks["available"]),
        "tradability_limit_up_source": tradability_masks["limit_up_source"],
        "tradability_limit_down_source": tradability_masks["limit_down_source"],
        "baseline_metrics": baseline,
        "split_count": len(split_reports),
        "split_reports": split_reports,
        "gate_summary_count": len(gate_summaries),
        "top_gate_summaries": gate_summaries[:20],
        "all_gate_summaries": gate_summaries,
        "real_edge_claim_allowed": False,
        "gate_role": "rolling_activation_search_hypothesis_not_production_rule",
    }


def write_v21_rolling_activation_search_report(
    output_path: Path | str,
    expression: str = V18_CENTER_EXPRESSION,
    **kwargs: Any,
) -> dict[str, Any]:
    report = build_v21_rolling_activation_search_report(expression, **kwargs)
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
