from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A6_1_BOOK = WORKSPACE / "runtime" / "a6_1_core4_curve_exposure_sanity" / "crypto_a6_1_core4_book_returns_20260519.csv"
LOCKED_OBJECT = WORKSPACE / "runtime" / "baselines" / "crypto_core4_locked_research_book_v1.json"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_2_core4_risk_scaling"
REPORT_DIR = WORKSPACE / "reports"

SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
}

HOURS_PER_YEAR = 365 * 24
ROLLING_VOL_BARS = 20 * 24
MIN_VOL_BARS = 5 * 24
TARGET_HOURLY_VOL = 0.005
GROSS_CAP_R1 = 1.0
GROSS_CAP_R3 = 0.5
COST_BPS = {
    "zero_0bp": 0.0,
    "normal_5bp": 5.0,
    "stress_10bp": 10.0,
    "severe_20bp": 20.0,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def additive_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    pnl = np.cumsum(clean)
    peak = np.maximum.accumulate(pnl)
    return float(np.min(pnl - peak))


def compounded_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0 or np.any(clean <= -1.0):
        return None
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0))


def stats(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"n": 0}
    downside = clean[clean < 0]
    std = float(np.std(clean, ddof=1)) if clean.size > 1 else None
    downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else None
    mean = float(np.mean(clean))
    return {
        "n": int(clean.size),
        "mean": mean,
        "annualized_mean": float(mean * HOURS_PER_YEAR),
        "std": std,
        "sharpe_proxy": None if not std else float(mean / std * math.sqrt(HOURS_PER_YEAR)),
        "sortino_proxy": None if not downside_std else float(mean / downside_std * math.sqrt(HOURS_PER_YEAR)),
        "hit_rate": float(np.mean(clean > 0)),
        "additive_total": float(np.sum(clean)),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_total": float(np.prod(1.0 + clean) - 1.0) if np.all(clean > -1.0) else None,
        "compounded_max_dd": compounded_drawdown(clean),
        "min": float(np.min(clean)),
        "q01": float(np.quantile(clean, 0.01)),
        "q05": float(np.quantile(clean, 0.05)),
        "median": float(np.quantile(clean, 0.50)),
        "q95": float(np.quantile(clean, 0.95)),
        "q99": float(np.quantile(clean, 0.99)),
        "bars_le_minus_1pct": int(np.sum(clean <= -0.01)),
        "bars_le_minus_5pct": int(np.sum(clean <= -0.05)),
        "bars_le_minus_10pct": int(np.sum(clean <= -0.10)),
    }


def load_book() -> pd.DataFrame:
    df = pd.read_csv(A6_1_BOOK)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def compute_multipliers(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"timestamp": df["timestamp"]})
    gross = df["gross_exposure"].replace(0, np.nan)
    rolling_vol = df["core4_net_return"].rolling(ROLLING_VOL_BARS, min_periods=MIN_VOL_BARS).std().shift(1)
    vol_mult = (TARGET_HOURLY_VOL / rolling_vol).clip(lower=0.0, upper=1.0).fillna(0.0)
    r1 = (GROSS_CAP_R1 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
    r3_gross = (GROSS_CAP_R3 / gross).clip(lower=0.0, upper=1.0).fillna(0.0)
    out["R0_unscaled"] = 1.0
    out["R1_gross_1x_cap"] = r1
    out["R2_rolling_vol_target_50bp"] = vol_mult
    out["R3_vol_target_gross_0p5x_cap"] = np.minimum(vol_mult, r3_gross)
    out["rolling_vol_lagged"] = rolling_vol
    return out


def scaled_net(df: pd.DataFrame, multiplier: pd.Series, cost_bps: float) -> pd.Series:
    pre_fee = df["gross_return"] - df["funding_drag"]
    fee = df["turnover"] * (cost_bps / 10000.0)
    return multiplier * (pre_fee - fee)


def split_mask(ts: pd.Series, start: str, end: str) -> pd.Series:
    return (ts >= pd.Timestamp(start)) & (ts <= pd.Timestamp(end))


def monthly_pass_rate(ts: pd.Series, values: pd.Series, start: str, end: str) -> tuple[int, int, float | None, float | None]:
    part = pd.DataFrame({"timestamp": ts, "value": values})
    part = part[(part["timestamp"] >= pd.Timestamp(start)) & (part["timestamp"] <= pd.Timestamp(end))]
    part = part[np.isfinite(part["value"])]
    if part.empty:
        return 0, 0, None, None
    month = part.groupby(part["timestamp"].dt.strftime("%Y-%m"))["value"].sum()
    pass_count = int((month > 0).sum())
    return int(len(month)), pass_count, float(pass_count / len(month)), clean_float(month.min())


def build_scaled_panel(df: pd.DataFrame, mult: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.DataFrame({"timestamp": df["timestamp"]})
    summary_rows = []
    variants = [c for c in mult.columns if c.startswith("R")]
    for variant in variants:
        m = mult[variant]
        panel[f"{variant}_multiplier"] = m
        panel[f"{variant}_gross_exposure"] = df["gross_exposure"] * m
        panel[f"{variant}_turnover"] = df["turnover"] * m
        panel[f"{variant}_funding_drag"] = df["funding_drag"] * m
        for cost_name, bps in COST_BPS.items():
            col = f"{variant}_{cost_name}_net_return"
            panel[col] = scaled_net(df, m, bps)
            for split_name, (start, end) in SPLITS.items():
                mask = split_mask(df["timestamp"], start, end)
                st = stats(panel.loc[mask, col].to_numpy(dtype=float))
                months, mpass, mrate, worst_month = monthly_pass_rate(df["timestamp"], panel[col], start, end)
                row = {
                    "variant": variant,
                    "cost_tier": cost_name,
                    "split": split_name,
                    **st,
                    "month_count": months,
                    "positive_month_count": mpass,
                    "positive_month_rate": mrate,
                    "worst_month_sum": worst_month,
                    "mean_multiplier": clean_float(m[mask].mean()),
                    "median_multiplier": clean_float(m[mask].median()),
                    "mean_gross_exposure": clean_float((df.loc[mask, "gross_exposure"] * m[mask]).mean()),
                    "max_gross_exposure": clean_float((df.loc[mask, "gross_exposure"] * m[mask]).max()),
                    "mean_turnover": clean_float((df.loc[mask, "turnover"] * m[mask]).mean()),
                    "fee_drag_total": clean_float((df.loc[mask, "turnover"] * m[mask] * (bps / 10000.0)).sum()),
                    "funding_drag_total": clean_float((df.loc[mask, "funding_drag"] * m[mask]).sum()),
                }
                summary_rows.append(row)
    return panel, pd.DataFrame(summary_rows)


def pick_decision(summary: pd.DataFrame) -> tuple[str, str]:
    recent = summary[(summary["split"] == "recent_oos_2025H2_2026") & (summary["cost_tier"] == "stress_10bp")].copy()
    candidates = recent[
        (recent["annualized_mean"] > 0.30)
        & (recent["compounded_max_dd"] > -0.30)
        & (recent["positive_month_rate"] >= 0.70)
    ].copy()
    if candidates.empty:
        return "HOLD_A6_2_NO_RISK_SCALED_SHADOW_CANDIDATE", ""
    # Prefer the most constrained passing variant.
    priority = {
        "R3_vol_target_gross_0p5x_cap": 0,
        "R2_rolling_vol_target_50bp": 1,
        "R1_gross_1x_cap": 2,
        "R0_unscaled": 3,
    }
    candidates["priority"] = candidates["variant"].map(priority).fillna(99)
    chosen = candidates.sort_values(["priority", "annualized_mean"], ascending=[True, False]).iloc[0]
    return "PASS_A6_2_RISK_SCALED_SHADOW_CANDIDATE", str(chosen["variant"])


def top_loss_hours(panel: pd.DataFrame, variant: str, cost_tier: str, n: int = 20) -> pd.DataFrame:
    col = f"{variant}_{cost_tier}_net_return"
    return (
        panel[["timestamp", col, f"{variant}_multiplier", f"{variant}_gross_exposure", f"{variant}_turnover"]]
        .sort_values(col)
        .head(n)
        .rename(
            columns={
                col: "net_return",
                f"{variant}_multiplier": "multiplier",
                f"{variant}_gross_exposure": "gross_exposure",
                f"{variant}_turnover": "turnover",
            }
        )
    )


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_book()
    mult = compute_multipliers(df)
    panel, summary = build_scaled_panel(df, mult)
    decision, selected_variant = pick_decision(summary)

    panel_path = RUNTIME_DIR / "crypto_a6_2_core4_scaled_panel_20260519.csv"
    mult_path = RUNTIME_DIR / "crypto_a6_2_core4_multipliers_20260519.csv"
    summary_path = RUNTIME_DIR / "crypto_a6_2_core4_risk_scaling_summary_20260519.csv"
    loss_path = RUNTIME_DIR / "crypto_a6_2_core4_selected_top_loss_hours_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a6_2_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A6_2_CORE4_RISK_SCALING_20260519.md"
    panel.to_csv(panel_path, index=False)
    mult.to_csv(mult_path, index=False)
    summary.to_csv(summary_path, index=False)
    if selected_variant:
        losses = top_loss_hours(panel, selected_variant, "stress_10bp")
    else:
        losses = top_loss_hours(panel, "R3_vol_target_gross_0p5x_cap", "stress_10bp")
    losses.to_csv(loss_path, index=False)

    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "selected_variant": selected_variant or None,
        "locked_object": str(LOCKED_OBJECT),
        "parameters": {
            "rolling_vol_bars": ROLLING_VOL_BARS,
            "min_vol_bars": MIN_VOL_BARS,
            "target_hourly_vol": TARGET_HOURLY_VOL,
            "gross_cap_r1": GROSS_CAP_R1,
            "gross_cap_r3": GROSS_CAP_R3,
            "cost_bps": COST_BPS,
            "vol_estimate_lag": "shift(1), no future realized vol",
        },
        "outputs": {
            "scaled_panel": str(panel_path),
            "multipliers": str(mult_path),
            "summary": str(summary_path),
            "top_loss_hours": str(loss_path),
            "report": str(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    recent = summary[summary["split"] == "recent_oos_2025H2_2026"].copy()
    display = recent[recent["cost_tier"].isin(["normal_5bp", "stress_10bp", "severe_20bp"])].copy()
    display["variant_order"] = display["variant"].map(
        {
            "R0_unscaled": 0,
            "R1_gross_1x_cap": 1,
            "R2_rolling_vol_target_50bp": 2,
            "R3_vol_target_gross_0p5x_cap": 3,
        }
    )
    display = display.sort_values(["variant_order", "cost_tier"])

    lines = [
        "# Crypto A6.2 Core4 Risk Scaling",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- selected_variant: `{selected_variant or 'none'}`",
        "- scope: fixed Core4 only; no formula changes, no cluster changes, no OOS parameter optimization",
        "",
        "## Fixed Variants",
        "",
        "| variant | rule |",
        "|---|---|",
        "| `R0_unscaled` | multiplier = 1 |",
        "| `R1_gross_1x_cap` | multiplier = min(1, 1.0 / current gross exposure) |",
        "| `R2_rolling_vol_target_50bp` | multiplier = min(1, 0.5% hourly target / lagged rolling 20d vol) |",
        "| `R3_vol_target_gross_0p5x_cap` | R2 plus multiplier capped by 0.5 gross exposure |",
        "",
        "## Recent OOS Summary",
        "",
        "| variant | cost | ann mean | compounded max DD | additive max DD | month pass | mean multiplier | mean gross | mean turnover | min hour |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['variant']}` | `{row['cost_tier']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['additive_max_dd'] if pd.notna(row['additive_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_multiplier'] if pd.notna(row['mean_multiplier']) else 0:.3f} | "
            f"{row['mean_gross_exposure'] if pd.notna(row['mean_gross_exposure']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.3f} | {row['min']:.4f} |"
        )
    lines += [
        "",
        "## Gate",
        "",
        "- A6.2 pass requires a fixed variant with recent OOS 10bp annualized > 30%, compounded max DD better than -30%, and monthly pass rate >= 70%.",
        "- Passing A6.2 only allows A6.3 tradable book replay / execution calibration. It does not allow live trading.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_2_SUMMARY=" + str(summary_path))
    print("A6_2_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    if selected_variant:
        print("SELECTED_VARIANT=" + selected_variant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
