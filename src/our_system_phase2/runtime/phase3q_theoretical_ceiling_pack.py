"""Phase3Q theoretical ceiling pack for locked daily books.

Computes formal, research, and oracle-diagnostic regime-gated daily proxy
performance. This is not a live execution report and not a production proof.
It prints the highest historical daily-proxy ceilings currently supported by
the locked data artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


DEFAULT_DATASET = Path(r"G:\Project_V7_Rotation\scripts\data\phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet")
DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3q_theoretical_ceiling_pack_20260517")
TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"

VARIANTS = {
    "X0_official_6": {
        "status": "formal_shadow",
        "clusters": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"],
    },
    "X1_research_9": {
        "status": "research_pool",
        "clusters": [
            "cluster_001",
            "cluster_005",
            "cluster_008",
            "cluster_006",
            "cluster_009",
            "cluster_003",
            "cluster_002",
            "cluster_007",
            "cluster_004",
        ],
    },
    "X2_official_6_plus_003": {
        "status": "research_diagnostic",
        "clusters": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004", "cluster_003"],
    },
    "X3_official_6_minus_002": {
        "status": "research_diagnostic",
        "clusters": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_004"],
    },
    "X4_official_6_plus_003_minus_002": {
        "status": "research_diagnostic",
        "clusters": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_004", "cluster_003"],
    },
    "X5_oracle_005_003_004": {
        "status": "oracle_diagnostic_only",
        "clusters": ["cluster_005", "cluster_003", "cluster_004"],
    },
}

AXES = {
    "trend": "trend_mean_lag1",
    "volatility": "volatility_lag1",
    "liquidity": "liquidity_ratio_lag1",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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
            "ann_simple": None,
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
        "ann_simple": _round(mean * 252.0),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
    }


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


def _prepare_frame(dataset_path: Path, daily_returns_path: Path) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    panel = pd.read_parquet(dataset_path, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
    returns = pd.read_csv(daily_returns_path, parse_dates=["date"])
    frame = returns.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    train_mask = (frame["date"] >= TRAIN_START) & (frame["date"] <= TRAIN_END)
    labels = {axis: _bucket_by_train_thresholds(frame[column], train_mask, axis) for axis, column in AXES.items()}
    gates = {
        "R0_no_gate": pd.Series(True, index=frame.index),
        "R3_liquidity_low": labels["liquidity"] == "liquidity_low",
        "R5_vol_or_trendlow_or_liqlow": (
            (labels["volatility"] == "volatility_high")
            | (labels["trend"] == "trend_low")
            | (labels["liquidity"] == "liquidity_low")
        ),
        "R6_at_least_2_of_vol_trend_liq": (
            (
                (labels["volatility"] == "volatility_high").astype(int)
                + (labels["trend"] == "trend_low").astype(int)
                + (labels["liquidity"] == "liquidity_low").astype(int)
            )
            >= 2
        ),
    }
    return frame, gates


def _variant_return(frame: pd.DataFrame, clusters: list[str]) -> pd.Series:
    return frame[clusters].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True).fillna(0.0)


def _window_mask(frame: pd.DataFrame, window: str) -> pd.Series:
    if window == "oos_2026":
        return (frame["date"] >= OOS_START) & (frame["date"] <= OOS_END)
    if window == "recent_2025h2_2026":
        return (frame["date"] >= TRAIN_START) & (frame["date"] <= OOS_END)
    if window == "all_history_2020_2026":
        return (frame["date"] >= "2020-01-01") & (frame["date"] <= OOS_END)
    raise ValueError(f"unknown_window:{window}")


def _plot_curve(curve_rows: list[dict[str, Any]], output_path: Path) -> str | None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None
    df = pd.DataFrame(curve_rows)
    if df.empty:
        return None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(12, 7))
    for label, block in df.groupby("series_label"):
        block = block.sort_values("date")
        plt.plot(pd.to_datetime(block["date"]), block["equity"], label=label)
    plt.title("Phase3Q 2026 OOS Equity Curves")
    plt.xlabel("date")
    plt.ylabel("equity")
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()
    return str(output_path)


def run(*, dataset_path: Path, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    frame, gates = _prepare_frame(dataset_path, daily_returns_path)
    metric_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    blotter_rows: list[dict[str, Any]] = []
    windows = ["oos_2026", "recent_2025h2_2026", "all_history_2020_2026"]
    for variant, meta in VARIANTS.items():
        base_return = _variant_return(frame, meta["clusters"])
        for gate_name, gate in gates.items():
            gate = gate.fillna(False).astype(bool)
            gated_return = base_return.where(gate, 0.0)
            for window in windows:
                mask = _window_mask(frame, window)
                row = {
                    "variant": variant,
                    "status": meta["status"],
                    "clusters": "|".join(meta["clusters"]),
                    "cluster_count": len(meta["clusters"]),
                    "gate": gate_name,
                    "window": window,
                    "active_days": int((mask & gate).sum()),
                    "active_day_ratio": _round((mask & gate).sum() / mask.sum() if int(mask.sum()) else None),
                }
                row.update(_metrics(gated_return[mask]))
                metric_rows.append(row)
            oos_mask = _window_mask(frame, "oos_2026")
            equity = (1.0 + gated_return[oos_mask].fillna(0.0)).cumprod()
            drawdown = equity / equity.cummax() - 1.0
            for idx, value in equity.items():
                curve_rows.append(
                    {
                        "date": frame.loc[idx, "date"].date().isoformat(),
                        "variant": variant,
                        "gate": gate_name,
                        "series_label": f"{variant}|{gate_name}",
                        "daily_return": _round(gated_return.loc[idx], 8),
                        "equity": _round(value, 8),
                        "drawdown": _round(drawdown.loc[idx], 8),
                        "gate_active": bool(gate.loc[idx]),
                    }
                )
                blotter_rows.append(
                    {
                        "date": frame.loc[idx, "date"].date().isoformat(),
                        "variant": variant,
                        "status": meta["status"],
                        "gate": gate_name,
                        "gate_active": bool(gate.loc[idx]),
                        "action": "hold_book" if bool(gate.loc[idx]) else "cash",
                        "book_return_if_ungated": _round(base_return.loc[idx], 8),
                        "gated_book_return": _round(gated_return.loc[idx], 8),
                        "equity": _round(value, 8),
                        "drawdown": _round(drawdown.loc[idx], 8),
                        "clusters": "|".join(meta["clusters"]),
                    }
                )

    _write_csv(output_root / "phase3q_theoretical_ceiling_metrics.csv", metric_rows)
    _write_csv(output_root / "phase3q_2026_equity_curves.csv", curve_rows)
    _write_csv(output_root / "phase3q_daily_proxy_blotter.csv", blotter_rows)
    oos_rows = [row for row in metric_rows if row["window"] == "oos_2026"]
    best_formal = max(
        [row for row in oos_rows if row["status"] == "formal_shadow"],
        key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0,
    )
    best_non_oracle = max(
        [row for row in oos_rows if row["status"] != "oracle_diagnostic_only"],
        key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0,
    )
    best_any = max(oos_rows, key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0)
    top_series = {
        f"{best_formal['variant']}|{best_formal['gate']}",
        f"{best_non_oracle['variant']}|{best_non_oracle['gate']}",
        f"{best_any['variant']}|{best_any['gate']}",
        "X4_official_6_plus_003_minus_002|R3_liquidity_low",
    }
    plot_rows = [row for row in curve_rows if row["series_label"] in top_series]
    plot_path = _plot_curve(plot_rows, output_root / "phase3q_2026_top_equity_curves.png")
    summary = {
        "created_at": _now(),
        "decision": "PASS_PHASE3Q_THEORETICAL_CEILING_PACK_CREATED",
        "scope": "daily_proxy_theoretical_ceiling_no_execution_no_capacity",
        "best_formal_oos_2026": best_formal,
        "best_non_oracle_oos_2026": best_non_oracle,
        "best_any_oos_2026": best_any,
        "outputs": {
            "metrics_csv": str(output_root / "phase3q_theoretical_ceiling_metrics.csv"),
            "equity_curves_csv": str(output_root / "phase3q_2026_equity_curves.csv"),
            "daily_proxy_blotter_csv": str(output_root / "phase3q_daily_proxy_blotter.csv"),
            "equity_curve_png": plot_path,
            "summary_json": str(output_root / "phase3q_theoretical_ceiling_pack.json"),
            "summary_md": str(output_root / "PHASE3Q_THEORETICAL_CEILING_PACK_2026-05-17.md"),
        },
        "not_confirmed": ["production_ready", "minute_execution", "real_slippage", "real_capacity", "live_survival"],
    }
    _write_json(output_root / "phase3q_theoretical_ceiling_pack.json", summary)
    top_oos = sorted(oos_rows, key=lambda row: _safe_float(row.get("ann_compound"), -999.0) or -999.0, reverse=True)[:12]
    md = [
        "# Phase3Q Theoretical Ceiling Pack",
        "",
        "- decision: `PASS_PHASE3Q_THEORETICAL_CEILING_PACK_CREATED`",
        "- scope: `daily_proxy_theoretical_ceiling_no_execution_no_capacity`",
        "",
        "## Key Ceilings",
        "",
        f"- best formal: `{best_formal['variant']} + {best_formal['gate']}` ann `{best_formal['ann_compound']}` sharpe `{best_formal['sharpe']}` max_dd `{best_formal['max_drawdown']}`",
        f"- best non-oracle: `{best_non_oracle['variant']} + {best_non_oracle['gate']}` ann `{best_non_oracle['ann_compound']}` sharpe `{best_non_oracle['sharpe']}` max_dd `{best_non_oracle['max_drawdown']}`",
        f"- best any/oracle-inclusive: `{best_any['variant']} + {best_any['gate']}` ann `{best_any['ann_compound']}` sharpe `{best_any['sharpe']}` max_dd `{best_any['max_drawdown']}`",
        "",
        "## Top 2026 OOS Daily Proxy Rows",
        "",
        "| variant | status | gate | ann | sharpe | max dd | total return | active ratio |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in top_oos:
        md.append(
            f"| {row['variant']} | {row['status']} | {row['gate']} | {row['ann_compound']} | {row['sharpe']} | {row['max_drawdown']} | {row['total_return']} | {row['active_day_ratio']} |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "- The daily proxy blotter is not a broker execution blotter.",
            "- Oracle diagnostic rows are theoretical ceilings only and must not be used as formal selection rules.",
            "- No minute slippage, true capacity, live survival, or fill feasibility is confirmed.",
            "",
        ]
    )
    (output_root / "PHASE3Q_THEORETICAL_CEILING_PACK_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(dataset_path=args.dataset_path, daily_returns_path=args.daily_returns, output_root=args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

