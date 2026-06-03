"""Field-level utility map for the integrated CN panel.

This is a broad no-formula scan. It evaluates raw panel fields as direct
cross-sectional signals under the same after-open/PIT clock family used by the
mature chain. The goal is to identify useful field axes for later repair/search,
not to promote any single field as an alpha.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.runtime.cn_underutilized_field_book_marginal_audit import DEFAULT_R3_GATE_LEDGER, _load_frame
from our_system_phase2.runtime.phase3ab_candidate_deep_validation import (
    OOS_2026_END,
    OOS_2026_START,
    SIGNAL_CLOCK_AFTER_OPEN,
    TRAIN_2025H2_END,
    TRAIN_2025H2_START,
    _metrics,
    _round,
)
from our_system_phase2.services.artifact_schema import write_json_artifact
from our_system_phase2.services.real_market_validation import _forward_return, _signal_evaluation_frame


VERSION = "cn-integrated-field-utility-map-v1-2026-06-03"
DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\data\company_phase2_panels\phase2_stock_tdx_official_20250806_to_20260410_cn_integrated_v2_all_fields_local.parquet")
DEFAULT_OUTPUT_ROOT = Path("reports/cn_integrated_field_utility_map_v1_20260603")

IDENTIFIER_COLUMNS = {
    "date",
    "code",
    "symbol",
    "join_code",
    "market",
    "sector",
    "sector_code",
    "sector_source",
    "sector_confidence",
    "instrument_type",
    "name",
}
LABEL_FORBIDDEN_PREFIXES = ("label_", "return_")
LABEL_FORBIDDEN_COLUMNS = {
    "daily_ret",
    "forward_return",
    "rt_change_pct",
    "pct_chg",
    "change",
    "R3_liquidity_low",
}
CONTROL_ONLY_COLUMNS = {
    "susp",
    "is_st",
    "is_limit_up",
    "is_limit_down",
    "market_cap_conflict_gt5pct",
    "is_capital_applicable",
}


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


def _field_family(field: str) -> str:
    name = field.lower()
    if name.startswith("m1_"):
        if "amount" in name or "vol" in name:
            return "minute_flow_liquidity"
        if "vwap" in name:
            return "minute_vwap_pressure"
        if "range" in name or "high" in name or "low" in name:
            return "minute_range_price_state"
        if "return" in name:
            return "minute_return_pressure"
        return "minute_other"
    if name.startswith("ctx_rzrq_"):
        return "rzrq_flow_leverage"
    if name.startswith("ctx_fund_"):
        return "fundamental_quality_risk"
    if name.startswith("ctx_holder_"):
        return "holder_structure"
    if name.startswith("ctx_mkt_updown_"):
        return "market_breadth_regime"
    if "market_cap" in name or "float_share" in name or "total_share" in name:
        return "capacity_size"
    if name in {"amount", "volume", "vwap"}:
        return "daily_flow_liquidity"
    if name in {"open", "high", "low", "close", "overnight"}:
        return "price_state"
    if "limit" in name:
        return "limit_tradability_or_event"
    return "other_numeric"


def _allowed_numeric_fields(frame: pd.DataFrame) -> list[str]:
    fields: list[str] = []
    for column in frame.columns:
        if column in IDENTIFIER_COLUMNS:
            continue
        if column in CONTROL_ONLY_COLUMNS:
            continue
        lower = column.lower()
        if column in LABEL_FORBIDDEN_COLUMNS or any(lower.startswith(prefix) for prefix in LABEL_FORBIDDEN_PREFIXES):
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().sum() < 100:
            continue
        if values.nunique(dropna=True) < 3:
            continue
        fields.append(column)
    return fields


def _load_r3(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    date_col = "date"
    active_col = "r3_liquidity_low_active" if "r3_liquidity_low_active" in frame.columns else "R3_liquidity_low"
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    active = frame[active_col].astype(str).str.lower().isin({"1", "1.0", "true", "yes", "y"})
    return pd.Series(active.to_numpy(), index=frame[date_col], name="R3_liquidity_low").sort_index()


def _safe_ratio(numerator: float | int, denominator: float | int) -> float | None:
    denominator = float(denominator)
    if denominator <= 0:
        return None
    return round(float(numerator) / denominator, 6)


def _signal_for_field(frame: pd.DataFrame, field: str, field_lags: dict[str, int]) -> pd.Series:
    values = pd.to_numeric(frame[field], errors="coerce")
    lag = int(field_lags.get(field, 0))
    if field in {"is_limit_up", "is_limit_down", "susp"}:
        lag = max(lag, 1)
    if lag > 0:
        values = values.groupby(frame["code"], sort=False).shift(lag)
    return values


def _bucket_labels_by_date(frame: pd.DataFrame, column: str, prefix: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(f"{prefix}_unknown", index=frame.index, dtype=object)
    values = pd.to_numeric(frame[column], errors="coerce")

    def label_day(day: pd.Series) -> pd.Series:
        out = pd.Series(f"{prefix}_unknown", index=day.index, dtype=object)
        clean = day.dropna()
        if clean.nunique(dropna=True) < 3:
            return out
        q1 = clean.quantile(1 / 3)
        q2 = clean.quantile(2 / 3)
        out.loc[day <= q1] = f"{prefix}_low"
        out.loc[(day > q1) & (day <= q2)] = f"{prefix}_mid"
        out.loc[day > q2] = f"{prefix}_high"
        return out

    return values.groupby(frame["date"], sort=False, group_keys=False).apply(label_day)


def _rank_ic(day: pd.DataFrame) -> float | None:
    if len(day) < 20 or day["signal"].nunique(dropna=True) < 3 or day["forward_return"].nunique(dropna=True) < 3:
        return None
    value = day["signal"].rank().corr(day["forward_return"].rank())
    return float(value) if pd.notna(value) else None


def _day_spread(day: pd.DataFrame, quantile: float) -> tuple[float | None, float | None, float | None, int]:
    clean = day.dropna(subset=["signal", "forward_return"])
    if len(clean) < 20 or clean["signal"].nunique(dropna=True) < 3:
        return None, None, None, 0
    side_count = max(1, int(math.ceil(len(clean) * quantile)))
    ordered = clean.sort_values(["signal", "code"], ascending=[False, True])
    top = ordered.head(side_count)
    bottom = ordered.tail(side_count)
    top_ret = pd.to_numeric(top["forward_return"], errors="coerce").mean()
    bottom_ret = pd.to_numeric(bottom["forward_return"], errors="coerce").mean()
    if pd.isna(top_ret) or pd.isna(bottom_ret):
        return None, None, None, side_count
    return float(top_ret - bottom_ret), float(top_ret), float(bottom_ret), side_count


def _turnover_by_date(work: pd.DataFrame, quantile: float) -> pd.Series:
    rows: list[tuple[pd.Timestamp, float | None]] = []
    prev_top: set[str] | None = None
    prev_bottom: set[str] | None = None
    for date, day in work.groupby("date", sort=True):
        clean = day.dropna(subset=["signal"])
        if len(clean) < 20 or clean["signal"].nunique(dropna=True) < 3:
            rows.append((date, None))
            continue
        side_count = max(1, int(math.ceil(len(clean) * quantile)))
        ordered = clean.sort_values(["signal", "code"], ascending=[False, True])
        top = set(ordered.head(side_count)["code"].astype(str))
        bottom = set(ordered.tail(side_count)["code"].astype(str))
        if prev_top is None or prev_bottom is None:
            turn = None
        else:
            top_turn = 1.0 - (len(top & prev_top) / max(1, len(top)))
            bottom_turn = 1.0 - (len(bottom & prev_bottom) / max(1, len(bottom)))
            turn = (top_turn + bottom_turn) / 2.0
        prev_top = top
        prev_bottom = bottom
        rows.append((date, turn))
    return pd.Series({date: turn for date, turn in rows}, name="average_one_way_turnover")


def _summarize_daily(daily: pd.DataFrame, mask: pd.Series, prefix: str, cost_bps: float) -> dict[str, Any]:
    use = daily.loc[mask.reindex(daily.index).fillna(False).to_numpy()].copy()
    if use.empty:
        return {
            f"{prefix}_days": 0,
            f"{prefix}_mean_ic": None,
            f"{prefix}_ic_positive_rate": None,
            f"{prefix}_ls_ann": None,
            f"{prefix}_ls_sortino": None,
            f"{prefix}_ls_net10_ann": None,
            f"{prefix}_ls_net10_sortino": None,
        }
    spread = pd.to_numeric(use["long_short_return"], errors="coerce")
    turnover = pd.to_numeric(use["average_one_way_turnover"], errors="coerce").fillna(0.0)
    net = spread - turnover * (float(cost_bps) / 10_000.0)
    ic = pd.to_numeric(use["rank_ic"], errors="coerce")
    metrics = _metrics(spread.dropna())
    net_metrics = _metrics(net.dropna())
    return {
        f"{prefix}_days": int(use.shape[0]),
        f"{prefix}_mean_ic": _round(ic.mean()),
        f"{prefix}_median_ic": _round(ic.median()),
        f"{prefix}_ic_positive_rate": _round((ic > 0).mean()) if ic.notna().any() else None,
        f"{prefix}_mean_spread": _round(spread.mean()),
        f"{prefix}_median_turnover": _round(turnover.replace(0, np.nan).median()),
        f"{prefix}_p90_turnover": _round(turnover.replace(0, np.nan).quantile(0.90)),
        f"{prefix}_ls_ann": metrics.get("ann_compound"),
        f"{prefix}_ls_sortino": metrics.get("sortino"),
        f"{prefix}_ls_maxdd": metrics.get("max_drawdown"),
        f"{prefix}_ls_top3_share": metrics.get("top3_day_share"),
        f"{prefix}_ls_net10_ann": net_metrics.get("ann_compound"),
        f"{prefix}_ls_net10_sortino": net_metrics.get("sortino"),
        f"{prefix}_ls_net10_maxdd": net_metrics.get("max_drawdown"),
    }


def _daily_stats(work: pd.DataFrame, quantile: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    turnover = _turnover_by_date(work, quantile)
    for date, day in work.groupby("date", sort=True):
        spread, top_ret, bottom_ret, side_count = _day_spread(day, quantile)
        rows.append(
            {
                "date": date,
                "rank_ic": _rank_ic(day),
                "long_short_return": spread,
                "top_return": top_ret,
                "bottom_return": bottom_ret,
                "side_count": side_count,
                "average_one_way_turnover": turnover.get(date),
            }
        )
    return pd.DataFrame(rows).set_index("date").sort_index()


def _fast_daily_ic(work: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date, day in work.groupby("date", sort=True):
        rows.append({"date": date, "rank_ic": _rank_ic(day)})
    return pd.DataFrame(rows).set_index("date").sort_index()


def _direction(row: dict[str, Any]) -> str:
    value = row.get("oos_2026_mean_ic")
    if value is None or pd.isna(value):
        value = row.get("oos_2026_ls_net10_ann")
    if value is None or pd.isna(value):
        return "unknown"
    return "positive" if float(value) >= 0 else "negative"


def _field_decision(row: dict[str, Any]) -> str:
    oos_ann = row.get("oos_2026_ls_net10_ann")
    train_ann = row.get("train_2025h2_ls_net10_ann")
    r3_ann = row.get("oos_2026_r3_on_ls_net10_ann")
    nonr3_ann = row.get("oos_2026_r3_off_ls_net10_ann")
    cov = row.get("coverage_ratio") or 0.0
    if cov < 0.05:
        return "HOLD_TOO_SPARSE_FOR_FIELD_ALPHA"
    if oos_ann is not None and train_ann is not None and float(oos_ann) > 0.20 and float(train_ann) > 0:
        return "CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH"
    if r3_ann is not None and float(r3_ann) > 0.20:
        return "R3_CONDITIONAL_DIAGNOSTIC_AXIS"
    if nonr3_ann is not None and float(nonr3_ann) > 0.20:
        return "NON_R3_DIAGNOSTIC_AXIS"
    return "HOLD_FIELD_UTILITY_WEAK_OR_UNSTABLE"


def _fast_field_decision(row: dict[str, Any]) -> str:
    cov = row.get("coverage_ratio") or 0.0
    if cov < 0.05:
        return "HOLD_TOO_SPARSE_FOR_FIELD_ALPHA"
    oos_ic = row.get("oos_2026_mean_ic")
    train_ic = row.get("train_2025h2_mean_ic")
    r3_ic = row.get("oos_2026_r3_on_mean_ic")
    nonr3_ic = row.get("oos_2026_r3_off_mean_ic")
    if oos_ic is not None and train_ic is not None and abs(float(oos_ic)) >= 0.015 and float(oos_ic) * float(train_ic) > 0:
        return "FAST_CANDIDATE_AXIS_FOR_DEEP_SCAN"
    if r3_ic is not None and abs(float(r3_ic)) >= 0.02:
        return "FAST_R3_DIAGNOSTIC_AXIS"
    if nonr3_ic is not None and abs(float(nonr3_ic)) >= 0.02:
        return "FAST_NON_R3_DIAGNOSTIC_AXIS"
    return "HOLD_FIELD_UTILITY_WEAK_OR_UNSTABLE"


def _fast_score(row: dict[str, Any]) -> float:
    oos = abs(float(row.get("oos_2026_mean_ic") or 0.0))
    train = abs(float(row.get("train_2025h2_mean_ic") or 0.0))
    r3 = abs(float(row.get("oos_2026_r3_on_mean_ic") or 0.0))
    nonr3 = abs(float(row.get("oos_2026_r3_off_mean_ic") or 0.0))
    cov = float(row.get("coverage_ratio") or 0.0)
    return (0.45 * oos + 0.25 * train + 0.15 * r3 + 0.15 * nonr3) * min(1.0, cov * 2.0)


def _round_nested(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (float, np.floating)):
            out[key] = _round(float(value), 8)
        else:
            out[key] = value
    return out


def _top_group_rows(field: str, family: str, daily_by_bucket: dict[str, pd.DataFrame], cost_bps: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_name, daily in daily_by_bucket.items():
        mask = pd.Series(True, index=daily.index)
        summary = _summarize_daily(daily, mask, "group", cost_bps)
        rows.append(_round_nested({"field": field, "field_family": family, "group": group_name, **summary}))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--r3-gate-ledger-path", type=Path, default=DEFAULT_R3_GATE_LEDGER)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--cost-bps", type=float, default=10.0)
    parser.add_argument("--min-coverage", type=float, default=0.01)
    parser.add_argument("--max-fields", type=int, default=0)
    parser.add_argument("--deep-top-n", type=int, default=40)
    args = parser.parse_args()

    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    frame = _load_frame(args.dataset_path)
    frame = frame.sort_values(["code", "date"]).reset_index(drop=True)
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    r3 = _load_r3(args.r3_gate_ledger_path)
    frame["R3_liquidity_low"] = frame["date"].map(r3).fillna(False).astype(bool)
    frame["forward_return"] = _forward_return(frame, 1, execution_lag_days=1)
    frame["size_bucket"] = _bucket_labels_by_date(frame, "final_float_market_cap", "size")
    frame["liquidity_bucket"] = _bucket_labels_by_date(frame, "amount", "liquidity")

    all_fields = _allowed_numeric_fields(frame)
    if args.max_fields > 0:
        all_fields = all_fields[: int(args.max_fields)]

    fast_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    total_rows = int(frame.shape[0])
    for idx, field in enumerate(all_fields, start=1):
        try:
            signal = _signal_for_field(signal_frame, field, signal_clock_report["field_lags"])
            work = frame[["date", "code", "forward_return", "R3_liquidity_low"]].copy()
            work["signal"] = signal
            work = work.dropna(subset=["signal", "forward_return"])
            coverage = _safe_ratio(work.shape[0], total_rows) or 0.0
            family = _field_family(field)
            base = {
                "field": field,
                "field_family": family,
                "coverage_ratio": coverage,
                "usable_rows": int(work.shape[0]),
                "usable_dates": int(work["date"].nunique()) if not work.empty else 0,
                "unique_values": int(pd.to_numeric(work["signal"], errors="coerce").nunique(dropna=True)) if not work.empty else 0,
                "lag_days": int(signal_clock_report["field_lags"].get(field, 0)),
            }
            if coverage < float(args.min_coverage):
                fast_rows.append(
                    _round_nested(
                        {
                            **base,
                            "fast_score": 0.0,
                            "decision": "HOLD_TOO_SPARSE_FOR_FIELD_ALPHA",
                        }
                    )
                )
                continue
            daily = _fast_daily_ic(work)
            masks = {
                "train_2025h2": (daily.index >= TRAIN_2025H2_START) & (daily.index <= TRAIN_2025H2_END),
                "oos_2026": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END),
                "oos_2026_r3_on": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END) & pd.Series([bool(r3.get(item, False)) for item in daily.index], index=daily.index),
                "oos_2026_r3_off": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END) & ~pd.Series([bool(r3.get(item, False)) for item in daily.index], index=daily.index),
            }
            for window, mask in masks.items():
                use = daily.loc[pd.Series(mask, index=daily.index).fillna(False).to_numpy()]
                ic = pd.to_numeric(use["rank_ic"], errors="coerce")
                fast_summary = {
                    f"{window}_days": int(use.shape[0]),
                    f"{window}_mean_ic": _round(ic.mean()),
                    f"{window}_median_ic": _round(ic.median()),
                    f"{window}_ic_positive_rate": _round((ic > 0).mean()) if ic.notna().any() else None,
                }
                window_rows.append(_round_nested({**base, "window": window, **fast_summary, "scan_stage": "fast_ic"}))
                base.update(fast_summary)
            base["preferred_direction"] = _direction(base)
            base["decision"] = _fast_field_decision(base)
            base["fast_score"] = _round(_fast_score(base), 8)
            fast_rows.append(_round_nested(base))
        except Exception as exc:  # noqa: BLE001 - field utility scan must continue.
            error_rows.append({"field": field, "error": f"{type(exc).__name__}:{str(exc)[:500]}"})
        if idx % 25 == 0:
            print(json.dumps({"status": "fast_progress", "fields_done": idx, "fields_total": len(all_fields)}, ensure_ascii=False))

    deep_fields = [
        str(row["field"])
        for row in sorted(fast_rows, key=lambda row: -float(row.get("fast_score") or 0.0))[: max(0, int(args.deep_top_n))]
        if float(row.get("fast_score") or 0.0) > 0
    ]
    fast_by_field = {str(row.get("field")): row for row in fast_rows}
    for idx, field in enumerate(deep_fields, start=1):
        try:
            signal = _signal_for_field(signal_frame, field, signal_clock_report["field_lags"])
            work = frame[["date", "code", "forward_return", "R3_liquidity_low", "sector", "size_bucket", "liquidity_bucket"]].copy()
            work["signal"] = signal
            work = work.dropna(subset=["signal", "forward_return"])
            daily = _daily_stats(work, float(args.top_bottom_quantile))
            masks = {
                "train_2025h2": (daily.index >= TRAIN_2025H2_START) & (daily.index <= TRAIN_2025H2_END),
                "oos_2026": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END),
                "oos_2026_r3_on": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END) & pd.Series([bool(r3.get(item, False)) for item in daily.index], index=daily.index),
                "oos_2026_r3_off": (daily.index >= OOS_2026_START) & (daily.index <= OOS_2026_END) & ~pd.Series([bool(r3.get(item, False)) for item in daily.index], index=daily.index),
            }
            family = _field_family(field)
            base = dict(fast_by_field.get(field, {}))
            base.update({"scan_stage": "deep_top_bottom"})
            for window, mask in masks.items():
                summary = _summarize_daily(daily, pd.Series(mask, index=daily.index), window, float(args.cost_bps))
                window_rows.append(_round_nested({**base, "window": window, **summary, "scan_stage": "deep_top_bottom"}))
                base.update(summary)
            base["preferred_direction"] = _direction(base)
            base["decision"] = _field_decision(base)
            summary_rows.append(_round_nested(base))
            if base["decision"] != "HOLD_FIELD_UTILITY_WEAK_OR_UNSTABLE":
                for group_col in ("size_bucket", "liquidity_bucket"):
                    for group_name, group_work in work.groupby(group_col, sort=True):
                        if str(group_name).endswith("_unknown") or group_work["date"].nunique() < 10:
                            continue
                        group_daily = _daily_stats(group_work, float(args.top_bottom_quantile))
                        group_rows.extend(_top_group_rows(field, family, {f"{group_col}:{group_name}": group_daily}, float(args.cost_bps)))
        except Exception as exc:  # noqa: BLE001 - deep field scan must continue.
            error_rows.append({"field": field, "stage": "deep", "error": f"{type(exc).__name__}:{str(exc)[:500]}"})
        if idx % 10 == 0:
            print(json.dumps({"status": "deep_progress", "fields_done": idx, "fields_total": len(deep_fields)}, ensure_ascii=False))

    deep_set = set(deep_fields)
    for row in fast_rows:
        if str(row.get("field")) not in deep_set:
            summary_rows.append(row)

    summary_rows.sort(
        key=lambda row: (
            0 if str(row.get("decision", "")).startswith("CANDIDATE") else 1,
            -abs(float(row.get("oos_2026_mean_ic") or 0.0)),
            -(float(row.get("oos_2026_ls_net10_ann") or -999.0)),
        )
    )
    candidate_rows = [row for row in summary_rows if row.get("decision") == "CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH"]
    diagnostic_rows = [row for row in summary_rows if row.get("decision") in {"R3_CONDITIONAL_DIAGNOSTIC_AXIS", "NON_R3_DIAGNOSTIC_AXIS"}]
    family_rows: list[dict[str, Any]] = []
    for family, rows in pd.DataFrame(summary_rows).groupby("field_family", sort=True):
        family_rows.append(
            {
                "field_family": family,
                "field_count": int(rows.shape[0]),
                "candidate_count": int((rows["decision"] == "CANDIDATE_FIELD_AXIS_FOR_REPAIR_SEARCH").sum()),
                "diagnostic_count": int(rows["decision"].isin(["R3_CONDITIONAL_DIAGNOSTIC_AXIS", "NON_R3_DIAGNOSTIC_AXIS"]).sum()),
                "median_coverage": _round(pd.to_numeric(rows["coverage_ratio"], errors="coerce").median()),
                "best_oos_net10_ann": _round(pd.to_numeric(rows.get("oos_2026_ls_net10_ann"), errors="coerce").max()),
                "best_oos_mean_ic_abs": _round(pd.to_numeric(rows.get("oos_2026_mean_ic"), errors="coerce").abs().max()),
            }
        )

    _write_csv(output_root / "field_utility_by_field.csv", summary_rows)
    _write_csv(output_root / "field_utility_by_window.csv", window_rows)
    _write_csv(output_root / "field_utility_by_group.csv", group_rows)
    _write_csv(output_root / "field_utility_by_family.csv", family_rows)
    _write_csv(output_root / "field_utility_errors.csv", error_rows)
    _write_csv(output_root / "field_utility_candidate_axes.csv", candidate_rows)
    _write_csv(output_root / "field_utility_diagnostic_axes.csv", diagnostic_rows)

    decision = (
        "PASS_FIELD_UTILITY_MAP_FOUND_CANDIDATE_AXES"
        if candidate_rows
        else "PASS_FIELD_UTILITY_MAP_NO_DIRECT_FIELD_PROMOTION"
    )
    report = {
        "version": VERSION,
        "decision": decision,
        "scope": "no_formula_no_search_field_level_direct_utility_map",
        "dataset_path": str(args.dataset_path),
        "r3_gate_ledger_path": str(args.r3_gate_ledger_path),
        "output_root": str(output_root),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "field_lag_policy": signal_clock_report.get("field_lag_policy"),
        "top_bottom_quantile": float(args.top_bottom_quantile),
        "cost_bps": float(args.cost_bps),
        "row_count": total_rows,
        "field_count_scanned": len(all_fields),
        "candidate_axis_count": len(candidate_rows),
        "diagnostic_axis_count": len(diagnostic_rows),
        "error_count": len(error_rows),
        "top_candidate_axes": candidate_rows[:20],
        "top_diagnostic_axes": diagnostic_rows[:20],
        "family_summary": family_rows,
        "promotion_policy": "no field is promoted without formula repair/search and locked OOS replay",
        "interpretation_warnings": [
            "raw_price_or_minute_high_fields_are_axis_hints_not_standalone_alpha",
            "price_level_axes_require_normalization_size_residualization_or_formula_repair_before_replay",
            "r3_conditional_axes_require_locked_gate_replay_before_shadow_use",
        ],
    }
    write_json_artifact(output_root / "field_utility_map.json", report)

    lines = [
        "# CN Integrated Field Utility Map v1",
        "",
        f"decision: `{decision}`",
        "",
        "## Counts",
        "",
        f"- row_count: `{total_rows}`",
        f"- field_count_scanned: `{len(all_fields)}`",
        f"- candidate_axis_count: `{len(candidate_rows)}`",
        f"- diagnostic_axis_count: `{len(diagnostic_rows)}`",
        f"- error_count: `{len(error_rows)}`",
        "",
        "## Top Candidate Axes",
        "",
        "| field | family | direction | oos net10 ann | oos IC | train net10 ann | R3 ann | non-R3 ann | decision |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in candidate_rows[:30]:
        lines.append(
            "| {field} | {family} | {direction} | {oos} | {ic} | {train} | {r3} | {nonr3} | {decision} |".format(
                field=row.get("field"),
                family=row.get("field_family"),
                direction=row.get("preferred_direction"),
                oos=row.get("oos_2026_ls_net10_ann"),
                ic=row.get("oos_2026_mean_ic"),
                train=row.get("train_2025h2_ls_net10_ann"),
                r3=row.get("oos_2026_r3_on_ls_net10_ann"),
                nonr3=row.get("oos_2026_r3_off_ls_net10_ann"),
                decision=row.get("decision"),
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This is a field-level utility map. It does not promote any field, formula, or book. Positive axes should feed repair/search lanes, then pass mature replay and X0 marginal audits.",
            "",
            "Raw price-level axes such as `open` and raw minute high/VWAP fields are not standalone alpha claims. They are transformation seeds and must be normalized, size/residual controlled, or repaired into formulas before any replay or promotion decision.",
            "",
            "R3-conditional axes are diagnostic until replayed through a locked gate and frozen selection path.",
        ]
    )
    (output_root / "CN_INTEGRATED_FIELD_UTILITY_MAP_V1_2026-06-03.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
