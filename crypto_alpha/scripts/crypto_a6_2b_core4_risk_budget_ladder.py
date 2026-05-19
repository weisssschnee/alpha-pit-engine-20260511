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
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_2b_core4_risk_budget_ladder"
REPORT_DIR = WORKSPACE / "reports"

SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
}
HOURS_PER_YEAR = 365 * 24
COST_BPS = {"normal_5bp": 5.0, "stress_10bp": 10.0, "severe_20bp": 20.0}
GROSS_CAPS = [0.50, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15]


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


def compounded_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0 or np.any(clean <= -1.0):
        return None
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0))


def additive_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    pnl = np.cumsum(clean)
    peak = np.maximum.accumulate(pnl)
    return float(np.min(pnl - peak))


def stats(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"n": 0}
    mean = float(np.mean(clean))
    std = float(np.std(clean, ddof=1)) if clean.size > 1 else None
    return {
        "n": int(clean.size),
        "annualized_mean": float(mean * HOURS_PER_YEAR),
        "sharpe_proxy": None if not std else float(mean / std * math.sqrt(HOURS_PER_YEAR)),
        "hit_rate": float(np.mean(clean > 0)),
        "additive_total": float(np.sum(clean)),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_total": float(np.prod(1.0 + clean) - 1.0) if np.all(clean > -1.0) else None,
        "compounded_max_dd": compounded_drawdown(clean),
        "min": float(np.min(clean)),
        "q01": float(np.quantile(clean, 0.01)),
        "q05": float(np.quantile(clean, 0.05)),
    }


def split_mask(ts: pd.Series, start: str, end: str) -> pd.Series:
    return (ts >= pd.Timestamp(start)) & (ts <= pd.Timestamp(end))


def monthly_pass_rate(ts: pd.Series, values: pd.Series, start: str, end: str) -> tuple[int, int, float | None]:
    part = pd.DataFrame({"timestamp": ts, "value": values})
    part = part[(part["timestamp"] >= pd.Timestamp(start)) & (part["timestamp"] <= pd.Timestamp(end))]
    part = part[np.isfinite(part["value"])]
    if part.empty:
        return 0, 0, None
    monthly = part.groupby(part["timestamp"].dt.strftime("%Y-%m"))["value"].sum()
    passes = int((monthly > 0).sum())
    return int(len(monthly)), passes, float(passes / len(monthly))


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(A6_1_BOOK)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    rows = []
    panels = pd.DataFrame({"timestamp": df["timestamp"]})
    for cap in GROSS_CAPS:
        mult = (cap / df["gross_exposure"].replace(0, np.nan)).clip(lower=0.0, upper=1.0).fillna(0.0)
        variant = f"gross_cap_{cap:.2f}x"
        panels[f"{variant}_multiplier"] = mult
        panels[f"{variant}_gross_exposure"] = df["gross_exposure"] * mult
        for cost_name, bps in COST_BPS.items():
            net = mult * (df["gross_return"] - df["funding_drag"] - df["turnover"] * (bps / 10000.0))
            panels[f"{variant}_{cost_name}_net_return"] = net
            for split_name, (start, end) in SPLITS.items():
                mask = split_mask(df["timestamp"], start, end)
                st = stats(net[mask].to_numpy(dtype=float))
                months, pass_count, pass_rate = monthly_pass_rate(df["timestamp"], net, start, end)
                rows.append(
                    {
                        "variant": variant,
                        "gross_cap": cap,
                        "cost_tier": cost_name,
                        "split": split_name,
                        **st,
                        "month_count": months,
                        "positive_month_count": pass_count,
                        "positive_month_rate": pass_rate,
                        "mean_multiplier": clean_float(mult[mask].mean()),
                        "mean_gross_exposure": clean_float((df.loc[mask, "gross_exposure"] * mult[mask]).mean()),
                        "mean_turnover": clean_float((df.loc[mask, "turnover"] * mult[mask]).mean()),
                    }
                )
    summary = pd.DataFrame(rows)
    recent10 = summary[(summary["split"] == "recent_oos_2025H2_2026") & (summary["cost_tier"] == "stress_10bp")].copy()
    feasible = recent10[(recent10["annualized_mean"] > 0) & (recent10["compounded_max_dd"] > -0.30)].copy()
    if feasible.empty:
        decision = "HOLD_A6_2B_NO_DD_30_RISK_BUDGET"
        max_passing_cap = None
    else:
        decision = "PASS_A6_2B_DIAGNOSTIC_RISK_BUDGET_EXISTS"
        max_passing_cap = float(feasible["gross_cap"].max())

    panel_path = RUNTIME_DIR / "crypto_a6_2b_core4_risk_budget_panel_20260519.csv"
    summary_path = RUNTIME_DIR / "crypto_a6_2b_core4_risk_budget_summary_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a6_2b_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A6_2B_CORE4_RISK_BUDGET_LADDER_20260519.md"
    panels.to_csv(panel_path, index=False)
    summary.to_csv(summary_path, index=False)
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "maximum_diagnostic_gross_cap_with_positive_10bp_and_dd_lt_30pct": max_passing_cap,
        "outputs": {
            "panel": str(panel_path),
            "summary": str(summary_path),
            "report": str(report_path),
        },
        "boundary": "diagnostic only; not an official selector or optimized OOS parameter",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    display = recent10.sort_values("gross_cap", ascending=False)
    lines = [
        "# Crypto A6.2B Core4 Risk Budget Ladder",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- maximum diagnostic cap passing positive 10bp and DD < 30%: `{max_passing_cap}`",
        "- boundary: diagnostic only; this does not promote Core4 to shadow",
        "",
        "## Recent OOS 10bp Ladder",
        "",
        "| gross cap | ann mean | compounded max DD | additive max DD | month pass | mean turnover | min hour |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| {row['gross_cap']:.2f} | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['additive_max_dd'] if pd.notna(row['additive_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.4f} | {row['min']:.4f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- The official A6.2 fixed variants did not pass the shadow gate.",
        "- This ladder only quantifies the scale required to control drawdown.",
        "- Any future shadow risk budget must be specified from capital/risk tolerance, not selected from recent OOS performance.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_2B_SUMMARY=" + str(summary_path))
    print("A6_2B_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    if max_passing_cap is not None:
        print("MAX_PASSING_DIAGNOSTIC_GROSS_CAP=" + str(max_passing_cap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
