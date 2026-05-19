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
A6_1_COMPONENT = WORKSPACE / "runtime" / "a6_1_core4_curve_exposure_sanity" / "crypto_a6_1_core4_component_returns_20260519.csv"
DRY_SHADOW_OBJECT = WORKSPACE / "runtime" / "baselines" / "crypto_core4_conservative_dry_shadow_v0.json"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_4_core4_conservative_robustness"
REPORT_DIR = WORKSPACE / "reports"

GROSS_CAP = 0.20
HOURS_PER_YEAR = 365 * 24
COST_BPS = {"stress_10bp": 10.0, "severe_20bp": 20.0}
SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
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
        "min_hour": float(np.min(clean)),
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
    pass_count = int((monthly > 0).sum())
    return int(len(monthly)), pass_count, float(pass_count / len(monthly))


def subset_panel(component: pd.DataFrame, clusters: list[str], cost_bps: float) -> pd.DataFrame:
    part = component[component["cluster_id"].isin(clusters)].copy()
    grouped = part.groupby("timestamp")
    df = grouped.agg(
        gross_return=("gross_return", "mean"),
        funding_drag=("funding_drag", "mean"),
        turnover=("turnover", "mean"),
        gross_exposure=("gross_exposure", "mean"),
    ).reset_index()
    mult = (GROSS_CAP / df["gross_exposure"].replace(0, np.nan)).clip(lower=0.0, upper=1.0).fillna(0.0)
    df["multiplier"] = mult
    df["net_return"] = mult * (df["gross_return"] - df["funding_drag"] - df["turnover"] * (cost_bps / 10000.0))
    return df


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    component = pd.read_csv(A6_1_COMPONENT)
    component["timestamp"] = pd.to_datetime(component["timestamp"], utc=True)
    clusters = sorted(component["cluster_id"].unique().tolist())
    subsets = {"Core4_full": clusters}
    for cluster in clusters:
        subsets[f"LOO_without_{cluster}"] = [c for c in clusters if c != cluster]
    rows = []
    panel_rows = []
    for subset_name, subset_clusters in subsets.items():
        for cost_name, bps in COST_BPS.items():
            panel = subset_panel(component, subset_clusters, bps)
            panel["subset"] = subset_name
            panel["cost_tier"] = cost_name
            panel_rows.append(panel)
            for split_name, (start, end) in SPLITS.items():
                mask = split_mask(panel["timestamp"], start, end)
                st = stats(panel.loc[mask, "net_return"].to_numpy(dtype=float))
                n_months, pass_count, pass_rate = monthly_pass_rate(panel["timestamp"], panel["net_return"], start, end)
                rows.append(
                    {
                        "subset": subset_name,
                        "clusters": "|".join(subset_clusters),
                        "removed_cluster": "" if subset_name == "Core4_full" else subset_name.replace("LOO_without_", ""),
                        "cluster_count": len(subset_clusters),
                        "cost_tier": cost_name,
                        "split": split_name,
                        **st,
                        "month_count": n_months,
                        "positive_month_count": pass_count,
                        "positive_month_rate": pass_rate,
                        "mean_multiplier": clean_float(panel.loc[mask, "multiplier"].mean()),
                        "mean_gross_exposure": clean_float((panel.loc[mask, "gross_exposure"] * panel.loc[mask, "multiplier"]).mean()),
                        "mean_turnover": clean_float((panel.loc[mask, "turnover"] * panel.loc[mask, "multiplier"]).mean()),
                    }
                )
    summary = pd.DataFrame(rows)
    panel_all = pd.concat(panel_rows, ignore_index=True)
    recent10 = summary[(summary["split"] == "recent_oos_2025H2_2026") & (summary["cost_tier"] == "stress_10bp")]
    loo = recent10[recent10["subset"] != "Core4_full"].copy()
    all_loo_positive = bool((loo["annualized_mean"] > 0).all())
    all_loo_dd_ok = bool((loo["compounded_max_dd"] > -0.30).all())
    full = recent10[recent10["subset"] == "Core4_full"].iloc[0]
    decision = (
        "PASS_A6_4_CONSERVATIVE_ROBUSTNESS"
        if all_loo_positive and all_loo_dd_ok and full["annualized_mean"] > 0 and full["compounded_max_dd"] > -0.30
        else "HOLD_A6_4_CLUSTER_LOO_WEAKNESS"
    )

    summary_path = RUNTIME_DIR / "crypto_a6_4_core4_conservative_robustness_summary_20260519.csv"
    panel_path = RUNTIME_DIR / "crypto_a6_4_core4_conservative_robustness_panel_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a6_4_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A6_4_CORE4_CONSERVATIVE_ROBUSTNESS_20260519.md"
    summary.to_csv(summary_path, index=False)
    panel_all.to_csv(panel_path, index=False)
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "dry_shadow_object": str(DRY_SHADOW_OBJECT),
        "gross_cap": GROSS_CAP,
        "all_recent_loo_positive_10bp": all_loo_positive,
        "all_recent_loo_dd_ok_10bp": all_loo_dd_ok,
        "outputs": {
            "summary": str(summary_path),
            "panel": str(panel_path),
            "report": str(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    display = recent10.sort_values("subset")
    lines = [
        "# Crypto A6.4 Core4 Conservative Robustness",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- gross_cap: `{GROSS_CAP}`",
        "",
        "## Recent OOS 10bp Cluster Leave-One-Out",
        "",
        "| subset | removed | ann mean | compounded max DD | month pass | mean turnover | min hour |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['subset']}` | `{row['removed_cluster']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['mean_turnover'] if pd.notna(row['mean_turnover']) else 0:.4f} | {row['min_hour']:.4f} |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- This checks whether the conservative dry-shadow result depends on a single Core4 cluster.",
        "- Passing A6.4 does not authorize live trading; it only supports append-only dry shadow observation.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_4_SUMMARY=" + str(summary_path))
    print("A6_4_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
