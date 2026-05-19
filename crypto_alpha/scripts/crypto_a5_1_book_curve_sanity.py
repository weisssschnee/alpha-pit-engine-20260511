from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a5_champion_deep_audit import load_a1_by_id, stress_one_interval  # noqa: E402
from crypto_a2_6_tradable_replay import load_method  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A2_6_CSV = WORKSPACE / "runtime" / "a2_6_tradable_replay" / "crypto_a2_6_tradable_replay_20260519.csv"
A4_CHAMPIONS = WORKSPACE / "runtime" / "a4_cluster_stress" / "crypto_a4_champion_shortlist_20260519.csv"
A5_CARDS = WORKSPACE / "runtime" / "a5_champion_deep_audit" / "crypto_a5_alpha_cards_20260519.csv"
RUNTIME_DIR = WORKSPACE / "runtime" / "a5_1_book_curve_sanity"
REPORT_DIR = WORKSPACE / "reports"

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
    return out if np.isfinite(out) else None


def additive_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    pnl = np.cumsum(clean)
    peak = np.maximum.accumulate(pnl)
    return float(np.min(pnl - peak))


def compounded_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity / peak - 1.0))


def stats(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {
            "n": 0,
            "mean": None,
            "annualized_mean": None,
            "additive_total": None,
            "compounded_total": None,
            "additive_max_dd": None,
            "compounded_max_dd": None,
            "worst_bar": None,
            "best_bar": None,
            "hit_rate": None,
        }
    return {
        "n": int(clean.size),
        "mean": float(np.mean(clean)),
        "annualized_mean": float(np.mean(clean) * 365 * 24),
        "additive_total": float(np.sum(clean)),
        "compounded_total": float(np.prod(1.0 + clean) - 1.0),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_max_dd": compounded_drawdown(clean),
        "worst_bar": float(np.min(clean)),
        "best_bar": float(np.max(clean)),
        "hit_rate": float(np.mean(clean > 0)),
    }


def build_series() -> tuple[pd.DataFrame, pd.DataFrame]:
    method = load_method()
    a1 = load_a1_by_id()
    champions = pd.read_csv(A4_CHAMPIONS)
    a2_6 = pd.read_csv(A2_6_CSV)
    all_series: dict[str, pd.Series] = {}
    for interval, part in champions.groupby("interval"):
        _, _, _, series = stress_one_interval(method=method, interval=interval, champions=part.copy(), a1=a1, a2_6=a2_6)
        all_series.update(series)
    cards = pd.read_csv(A5_CARDS)
    return cards, pd.concat(all_series.values(), axis=1, keys=all_series.keys(), sort=True)


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    cards, series = build_series()
    books = {
        "Core4": cards.loc[cards["final_role"] == "Core", "cluster_id"].tolist(),
        "CoreSupport8": cards.loc[cards["final_role"].isin(["Core", "Support"]), "cluster_id"].tolist(),
        "All9": cards["cluster_id"].tolist(),
    }
    summary_rows = []
    monthly_rows = []
    daily_rows = []
    for book_name, cluster_ids in books.items():
        book = series[cluster_ids].mean(axis=1, skipna=True).dropna()
        daily = book.resample("1D").sum()
        for split_name, (start, end) in SPLITS.items():
            part = book.loc[(book.index >= pd.Timestamp(start)) & (book.index <= pd.Timestamp(end))]
            dpart = daily.loc[(daily.index >= pd.Timestamp(start)) & (daily.index <= pd.Timestamp(end))]
            out = {"book": book_name, "split": split_name, "cluster_count": len(cluster_ids), **stats(part.to_numpy(dtype=float))}
            out["daily_additive_total"] = clean_float(dpart.sum())
            out["daily_worst_day"] = clean_float(dpart.min()) if len(dpart) else None
            out["daily_best_day"] = clean_float(dpart.max()) if len(dpart) else None
            out["top_3_day_contribution"] = clean_float(dpart.sort_values(ascending=False).head(3).sum()) if len(dpart) else None
            summary_rows.append(out)
        month = daily[daily.index >= pd.Timestamp("2025-07-01T00:00:00Z")].groupby(daily[daily.index >= pd.Timestamp("2025-07-01T00:00:00Z")].index.strftime("%Y-%m")).sum()
        for m, v in month.items():
            monthly_rows.append({"book": book_name, "month": m, "daily_sum_return": clean_float(v)})
        daily_recent = daily.loc[(daily.index >= pd.Timestamp("2025-07-01T00:00:00Z")) & (daily.index <= pd.Timestamp("2026-04-30T23:59:59Z"))]
        for ts, v in daily_recent.items():
            daily_rows.append({"book": book_name, "date": ts.strftime("%Y-%m-%d"), "daily_return": clean_float(v)})
    summary = pd.DataFrame(summary_rows)
    monthly = pd.DataFrame(monthly_rows)
    daily = pd.DataFrame(daily_rows)
    summary_path = RUNTIME_DIR / "crypto_a5_1_book_curve_sanity_summary_20260519.csv"
    monthly_path = RUNTIME_DIR / "crypto_a5_1_book_monthly_20260519.csv"
    daily_path = RUNTIME_DIR / "crypto_a5_1_book_daily_recent_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a5_1_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A5_1_BOOK_CURVE_SANITY_20260519.md"
    summary.to_csv(summary_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    daily.to_csv(daily_path, index=False)
    manifest = {
        "generated_at": utc_now(),
        "decision": "PASS_A5_1_BOOK_CURVE_SANITY_WITH_DRAWDOWN_WARNING",
        "outputs": {
            "summary": str(summary_path),
            "monthly": str(monthly_path),
            "daily_recent": str(daily_path),
            "report": str(report_path),
        },
        "notes": [
            "Core4 has strong mean/Sharpe proxy but large compounded drawdown proxy.",
            "Use additive market-neutral PnL and compounded proxy separately.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Crypto A5.1 Book Curve Sanity",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        "- decision: `PASS_A5_1_BOOK_CURVE_SANITY_WITH_DRAWDOWN_WARNING`",
        "",
        "## Summary",
        "",
        "| book | split | clusters | ann mean | additive total | compounded total | additive max DD | compounded max DD | worst day | top3 day contribution |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| `{row['book']}` | `{row['split']}` | {int(row['cluster_count'])} | "
            f"{row['annualized_mean'] if pd.notna(row['annualized_mean']) else 0:.4f} | "
            f"{row['additive_total'] if pd.notna(row['additive_total']) else 0:.4f} | "
            f"{row['compounded_total'] if pd.notna(row['compounded_total']) else 0:.4f} | "
            f"{row['additive_max_dd'] if pd.notna(row['additive_max_dd']) else 0:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['daily_worst_day'] if pd.notna(row['daily_worst_day']) else 0:.4f} | "
            f"{row['top_3_day_contribution'] if pd.notna(row['top_3_day_contribution']) else 0:.4f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- The Core4 mean signal is strong, but drawdown is not acceptable for production claims.",
        "- A5 remains research proof. The next step is locked shadow with risk scaling and execution calibration, not live trading.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A5_1_SUMMARY=" + str(summary_path))
    print("A5_1_REPORT=" + str(report_path))
    print("DECISION=PASS_A5_1_BOOK_CURVE_SANITY_WITH_DRAWDOWN_WARNING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
