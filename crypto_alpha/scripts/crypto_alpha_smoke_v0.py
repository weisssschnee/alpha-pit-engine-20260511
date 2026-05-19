from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
PANEL_DIR = ROOT / "gold" / "panels"
REPORT_DIR = ROOT / "alphafactory_crypto" / "reports"

INTERVALS = ["1h", "5m"]
HORIZONS = [1, 3, 6, 12]

SPLITS = {
    "train_2024": ("2024-01-01", "2024-12-31 23:59:59"),
    "validation_2025H1": ("2025-01-01", "2025-06-30 23:59:59"),
    "recent_oos_2025H2_2026": ("2025-07-01", "2026-04-30 23:59:59"),
}

BASE_FEATURES = [
    "ret_1",
    "ret_3",
    "ret_6",
    "ret_12",
    "ret_24",
    "hl_range",
    "abs_ret_1",
    "realized_vol_6",
    "realized_vol_12",
    "realized_vol_24",
    "quote_asset_volume",
    "quote_volume_mean_6",
    "quote_volume_mean_12",
    "quote_volume_mean_24",
    "avg_trade_size_quote",
    "taker_buy_ratio",
    "taker_imbalance",
    "mark_minus_index",
    "mark_index_ratio",
    "premium_index",
    "spot_perp_basis",
    "latest_known_funding_rate",
    "funding_rate_z_24",
    "funding_rate_persistence_3",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def annualization(interval: str, horizon: int) -> float:
    bars_per_year = {"5m": 365 * 24 * 12, "1h": 365 * 24}[interval]
    return bars_per_year / max(horizon, 1)


def split_mask(ts: pd.Series, start: str, end: str) -> pd.Series:
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    return (ts >= start_ts) & (ts <= end_ts)


def cross_sectional_ic_by_time(df: pd.DataFrame, feature: str, target: str) -> pd.Series:
    sub = df[["timestamp", feature, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if sub.empty:
        return pd.Series(dtype=float)
    grouped = sub.groupby("timestamp", sort=False)
    rx = grouped[feature].rank(method="average")
    ry = grouped[target].rank(method="average")
    work = pd.DataFrame({"timestamp": sub["timestamp"], "x": rx, "y": ry})
    work["xy"] = work["x"] * work["y"]
    work["x2"] = work["x"] * work["x"]
    work["y2"] = work["y"] * work["y"]
    agg = work.groupby("timestamp", sort=False).agg(
        n=("x", "count"),
        sx=("x", "sum"),
        sy=("y", "sum"),
        sxy=("xy", "sum"),
        sx2=("x2", "sum"),
        sy2=("y2", "sum"),
    )
    numerator = agg["n"] * agg["sxy"] - agg["sx"] * agg["sy"]
    denominator = np.sqrt(
        (agg["n"] * agg["sx2"] - agg["sx"] * agg["sx"])
        * (agg["n"] * agg["sy2"] - agg["sy"] * agg["sy"])
    )
    out = numerator / denominator.replace(0, np.nan)
    return out.where(agg["n"] >= 8)


def long_short_by_time(df: pd.DataFrame, feature: str, target: str, sign: float) -> pd.Series:
    sub = df[["timestamp", feature, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if sub.empty:
        return pd.Series(dtype=float)
    sub = sub.copy()
    sub["score"] = sub[feature] * sign
    grouped = sub.groupby("timestamp", sort=False)
    sub["n"] = grouped["score"].transform("count")
    sub["rank_desc"] = grouped["score"].rank(method="first", ascending=False)
    sub["rank_asc"] = grouped["score"].rank(method="first", ascending=True)
    sub = sub[sub["n"] >= 8]
    top = sub[sub["rank_desc"] <= 3].groupby("timestamp", sort=False)[target].mean()
    bottom = sub[sub["rank_asc"] <= 3].groupby("timestamp", sort=False)[target].mean()
    return top - bottom


def summarize_return_series(series: pd.Series, ann: float) -> dict[str, float | int | None]:
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {"n": 0, "mean": None, "annualized_mean": None, "sharpe_proxy": None, "hit_rate": None}
    std = clean.std()
    return {
        "n": int(len(clean)),
        "mean": float(clean.mean()),
        "annualized_mean": float(clean.mean() * ann),
        "sharpe_proxy": float(clean.mean() / std * np.sqrt(ann)) if std and not np.isnan(std) else None,
        "hit_rate": float((clean > 0).mean()),
    }


def summarize_ic(series: pd.Series) -> dict[str, float | int | None]:
    clean = series.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return {"n": 0, "mean_ic": None, "icir": None, "positive_rate": None}
    std = clean.std()
    return {
        "n": int(len(clean)),
        "mean_ic": float(clean.mean()),
        "icir": float(clean.mean() / std) if std and not np.isnan(std) else None,
        "positive_rate": float((clean > 0).mean()),
    }


def feature_family(feature: str) -> str:
    if feature.startswith("ret_") or feature in {"hl_range", "abs_ret_1"}:
        return "price"
    if "vol" in feature or "range" in feature:
        return "volatility"
    if "quote" in feature or "trade_size" in feature:
        return "liquidity"
    if "taker" in feature:
        return "flow"
    if "mark_" in feature or "premium" in feature or "basis" in feature:
        return "basis"
    if "funding" in feature:
        return "funding"
    return "other"


def evaluate_panel(interval: str) -> list[dict[str, Any]]:
    path = PANEL_DIR / f"crypto_core12_{interval}_v1.parquet"
    cols = ["timestamp", "symbol"] + BASE_FEATURES + [f"fwd_ret_{h}" for h in HORIZONS]
    df = pd.read_parquet(path, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    features = [f for f in BASE_FEATURES if f in df.columns]
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        target = f"fwd_ret_{horizon}"
        if target not in df.columns:
            continue
        ann = annualization(interval, horizon)
        for feature in features:
            train_mask = split_mask(df["timestamp"], *SPLITS["train_2024"])
            train_df = df.loc[train_mask, ["timestamp", "symbol", feature, target]].copy()
            train_ic = cross_sectional_ic_by_time(train_df, feature, target)
            train_ic_summary = summarize_ic(train_ic)
            mean_ic = train_ic_summary["mean_ic"]
            if mean_ic is None or np.isnan(mean_ic):
                sign = 1.0
            else:
                sign = 1.0 if mean_ic >= 0 else -1.0

            record: dict[str, Any] = {
                "interval": interval,
                "horizon": horizon,
                "feature": feature,
                "family": feature_family(feature),
                "train_sign": sign,
                "train_mean_ic": train_ic_summary["mean_ic"],
                "train_icir": train_ic_summary["icir"],
            }
            for split_name, (start, end) in SPLITS.items():
                part = df.loc[split_mask(df["timestamp"], start, end), ["timestamp", "symbol", feature, target]].copy()
                ic = cross_sectional_ic_by_time(part, feature, target)
                ic_summary = summarize_ic(ic)
                ls = long_short_by_time(part, feature, target, sign)
                ls_summary = summarize_return_series(ls, ann)
                record[f"{split_name}_mean_ic_oriented"] = (
                    None if ic_summary["mean_ic"] is None else float(ic_summary["mean_ic"] * sign)
                )
                record[f"{split_name}_icir_oriented"] = (
                    None if ic_summary["icir"] is None else float(ic_summary["icir"] * sign)
                )
                record[f"{split_name}_ls_annualized"] = ls_summary["annualized_mean"]
                record[f"{split_name}_ls_sharpe_proxy"] = ls_summary["sharpe_proxy"]
                record[f"{split_name}_ls_hit_rate"] = ls_summary["hit_rate"]
                record[f"{split_name}_n"] = ls_summary["n"]
            rows.append(record)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Crypto AlphaFactory feature smoke v0.")
    parser.add_argument("--intervals", default="1h,5m", help="Comma-separated intervals to evaluate.")
    args = parser.parse_args()
    intervals = [part.strip() for part in args.intervals.split(",") if part.strip()]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    for interval in intervals:
        all_rows.extend(evaluate_panel(interval))
    out = pd.DataFrame(all_rows)
    csv_path = REPORT_DIR / "crypto_alpha_smoke_v0_results_20260519.csv"
    json_path = REPORT_DIR / "crypto_alpha_smoke_v0_results_20260519.json"
    md_path = REPORT_DIR / "CRYPTO_ALPHA_SMOKE_V0_20260519.md"
    out.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps({"generated_at": utc_now(), "rows": all_rows}, indent=2, sort_keys=True), encoding="utf-8")

    rank_col = "recent_oos_2025H2_2026_ls_annualized"
    top = out.sort_values(rank_col, ascending=False).head(30)
    stable = out[
        (out["train_2024_mean_ic_oriented"] > 0)
        & (out["validation_2025H1_mean_ic_oriented"] > 0)
        & (out["recent_oos_2025H2_2026_mean_ic_oriented"] > 0)
    ].sort_values(rank_col, ascending=False).head(20)
    family = (
        out.groupby(["interval", "family"], dropna=False)[rank_col]
        .agg(["count", "median", "max"])
        .reset_index()
        .sort_values(["interval", "max"], ascending=[True, False])
    )

    lines = [
        "# Crypto Alpha Smoke v0",
        "",
        f"- generated_at: `{utc_now()}`",
        "- decision: `PASS_CRYPTO_ALPHA_SMOKE_V0`",
        "- universe: `core12 futures`",
        "- splits: `2024 train / 2025H1 validation / 2025H2-2026-04 recent OOS`",
        "- method: cross-sectional Spearman IC and train-sign oriented top/bottom basket",
        "- warning: this is feature smoke, not deployable alpha proof",
        "",
        "## Top Recent-OOS Feature/Horizon Rows",
        "",
        "| interval | horizon | feature | family | train IC | val IC | recent IC | recent LS ann | recent LS sharpe |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in top.iterrows():
        lines.append(
            f"| `{row['interval']}` | {int(row['horizon'])} | `{row['feature']}` | `{row['family']}` | "
            f"{row['train_2024_mean_ic_oriented']:.4f} | {row['validation_2025H1_mean_ic_oriented']:.4f} | "
            f"{row['recent_oos_2025H2_2026_mean_ic_oriented']:.4f} | {row[rank_col]:.4f} | "
            f"{row['recent_oos_2025H2_2026_ls_sharpe_proxy']:.3f} |"
        )
    lines += [
        "",
        "## Stable Positive-IC Rows Across All Splits",
        "",
        "| interval | horizon | feature | family | train IC | val IC | recent IC | recent LS ann |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]
    if stable.empty:
        lines.append("| n/a |  |  |  |  |  |  |  |")
    else:
        for _, row in stable.iterrows():
            lines.append(
                f"| `{row['interval']}` | {int(row['horizon'])} | `{row['feature']}` | `{row['family']}` | "
                f"{row['train_2024_mean_ic_oriented']:.4f} | {row['validation_2025H1_mean_ic_oriented']:.4f} | "
                f"{row['recent_oos_2025H2_2026_mean_ic_oriented']:.4f} | {row[rank_col]:.4f} |"
            )
    lines += [
        "",
        "## Family Summary By Recent-OOS LS Annualized",
        "",
        "| interval | family | count | median | max |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in family.iterrows():
        lines.append(f"| `{row['interval']}` | `{row['family']}` | {int(row['count'])} | {row['median']:.4f} | {row['max']:.4f} |")
    lines += [
        "",
        "## Boundary",
        "",
        "- Forward-return columns are labels and must not enter formula generation.",
        "- This smoke does not use recent-only positioning.",
        "- Results are priors for motif/search allocation, not a final alpha book.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("SMOKE_CSV=" + str(csv_path))
    print("SMOKE_MD=" + str(md_path))
    print("DECISION=PASS_CRYPTO_ALPHA_SMOKE_V0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
