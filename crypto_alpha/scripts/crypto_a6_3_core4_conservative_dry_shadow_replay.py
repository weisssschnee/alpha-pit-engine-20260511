from __future__ import annotations

import hashlib
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
LOCKED_CORE4 = WORKSPACE / "runtime" / "baselines" / "crypto_core4_locked_research_book_v1.json"
BASELINE_DIR = WORKSPACE / "runtime" / "baselines"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_3_core4_conservative_dry_shadow"
REPORT_DIR = WORKSPACE / "reports"

GROSS_CAP = 0.20
HOURS_PER_YEAR = 365 * 24
SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
}
COST_BPS = {"normal_5bp": 5.0, "stress_10bp": 10.0, "severe_20bp": 20.0}


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


def stable_hash(obj: dict[str, Any]) -> str:
    filtered = {k: v for k, v in obj.items() if k not in {"created_at", "object_hash"}}
    payload = json.dumps(filtered, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    downside = clean[clean < 0]
    downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else None
    return {
        "n": int(clean.size),
        "annualized_mean": float(mean * HOURS_PER_YEAR),
        "sharpe_proxy": None if not std else float(mean / std * math.sqrt(HOURS_PER_YEAR)),
        "sortino_proxy": None if not downside_std else float(mean / downside_std * math.sqrt(HOURS_PER_YEAR)),
        "hit_rate": float(np.mean(clean > 0)),
        "additive_total": float(np.sum(clean)),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_total": float(np.prod(1.0 + clean) - 1.0) if np.all(clean > -1.0) else None,
        "compounded_max_dd": compounded_drawdown(clean),
        "min_hour": float(np.min(clean)),
        "q01": float(np.quantile(clean, 0.01)),
        "q05": float(np.quantile(clean, 0.05)),
    }


def split_mask(ts: pd.Series, start: str, end: str) -> pd.Series:
    return (ts >= pd.Timestamp(start)) & (ts <= pd.Timestamp(end))


def monthly_stats(ts: pd.Series, values: pd.Series, start: str, end: str) -> tuple[pd.Series, int, int, float | None]:
    part = pd.DataFrame({"timestamp": ts, "value": values})
    part = part[(part["timestamp"] >= pd.Timestamp(start)) & (part["timestamp"] <= pd.Timestamp(end))]
    part = part[np.isfinite(part["value"])]
    if part.empty:
        return pd.Series(dtype=float), 0, 0, None
    monthly = part.groupby(part["timestamp"].dt.strftime("%Y-%m"))["value"].sum()
    pass_count = int((monthly > 0).sum())
    return monthly, int(len(monthly)), pass_count, float(pass_count / len(monthly))


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    book = pd.read_csv(A6_1_BOOK)
    book["timestamp"] = pd.to_datetime(book["timestamp"], utc=True)
    multiplier = (GROSS_CAP / book["gross_exposure"].replace(0, np.nan)).clip(lower=0.0, upper=1.0).fillna(0.0)
    panel = pd.DataFrame({"timestamp": book["timestamp"], "multiplier": multiplier})
    panel["gross_exposure"] = book["gross_exposure"] * multiplier
    panel["turnover"] = book["turnover"] * multiplier
    panel["funding_drag"] = book["funding_drag"] * multiplier
    for name, bps in COST_BPS.items():
        panel[f"{name}_net_return"] = multiplier * (
            book["gross_return"] - book["funding_drag"] - book["turnover"] * (bps / 10000.0)
        )
    summary_rows = []
    monthly_rows = []
    for cost_name in COST_BPS:
        col = f"{cost_name}_net_return"
        for split_name, (start, end) in SPLITS.items():
            mask = split_mask(panel["timestamp"], start, end)
            st = stats(panel.loc[mask, col].to_numpy(dtype=float))
            monthly, n_months, pass_count, pass_rate = monthly_stats(panel["timestamp"], panel[col], start, end)
            summary_rows.append(
                {
                    "cost_tier": cost_name,
                    "split": split_name,
                    **st,
                    "month_count": n_months,
                    "positive_month_count": pass_count,
                    "positive_month_rate": pass_rate,
                    "mean_multiplier": clean_float(panel.loc[mask, "multiplier"].mean()),
                    "mean_gross_exposure": clean_float(panel.loc[mask, "gross_exposure"].mean()),
                    "mean_turnover": clean_float(panel.loc[mask, "turnover"].mean()),
                }
            )
            for month, value in monthly.items():
                monthly_rows.append({"cost_tier": cost_name, "split": split_name, "month": month, "month_return_sum": clean_float(value)})
    return panel, pd.DataFrame(summary_rows), pd.DataFrame(monthly_rows)


def main() -> int:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    core4 = json.loads(LOCKED_CORE4.read_text(encoding="utf-8"))
    panel, summary, monthly = build_panel()
    recent10 = summary[(summary["split"] == "recent_oos_2025H2_2026") & (summary["cost_tier"] == "stress_10bp")].iloc[0]
    validation10 = summary[(summary["split"] == "validation_2025H1") & (summary["cost_tier"] == "stress_10bp")].iloc[0]
    decision = "PASS_A6_3_CONSERVATIVE_DRY_SHADOW_REPLAY_WITH_WARNINGS"
    warnings = []
    if validation10["positive_month_rate"] < 0.7:
        warnings.append("validation_month_pass_rate_below_70pct")
    if recent10["compounded_max_dd"] <= -0.30:
        warnings.append("recent_compounded_dd_not_below_30pct")
        decision = "HOLD_A6_3_DRY_SHADOW_RISK_GATE"
    if recent10["annualized_mean"] <= 0:
        warnings.append("recent_10bp_not_positive")
        decision = "HOLD_A6_3_DRY_SHADOW_RISK_GATE"

    shadow_obj = {
        "object_id": "crypto_core4_conservative_dry_shadow_v0",
        "status": "dry_shadow_candidate_not_live",
        "created_at": utc_now(),
        "parent_object_id": core4["object_id"],
        "parent_object_hash": core4["object_hash"],
        "gross_cap": GROSS_CAP,
        "risk_budget_source": "A6 diagnostic risk budget; requires explicit human approval before any forward shadow activation",
        "book_rule": {
            "clusters": [c["cluster_id"] for c in core4["clusters"]],
            "cluster_weighting": "equal_weight",
            "gross_cap": GROSS_CAP,
            "execution_assumption": "next 1h bar open proxy",
        },
        "not_confirmed": [
            "live_ready",
            "exchange_orders",
            "real_slippage",
            "real_capacity",
            "production_risk",
        ],
    }
    shadow_obj["object_hash"] = stable_hash(shadow_obj)

    panel_path = RUNTIME_DIR / "crypto_a6_3_core4_conservative_dry_shadow_panel_20260519.csv"
    summary_path = RUNTIME_DIR / "crypto_a6_3_core4_conservative_dry_shadow_summary_20260519.csv"
    monthly_path = RUNTIME_DIR / "crypto_a6_3_core4_conservative_dry_shadow_monthly_20260519.csv"
    object_path = BASELINE_DIR / "crypto_core4_conservative_dry_shadow_v0.json"
    manifest_path = RUNTIME_DIR / "crypto_a6_3_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A6_3_CORE4_CONSERVATIVE_DRY_SHADOW_REPLAY_20260519.md"
    panel.to_csv(panel_path, index=False)
    summary.to_csv(summary_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    object_path.write_text(json.dumps(shadow_obj, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "generated_at": shadow_obj["created_at"],
        "decision": decision,
        "warnings": warnings,
        "dry_shadow_object": str(object_path),
        "dry_shadow_object_hash": shadow_obj["object_hash"],
        "outputs": {
            "panel": str(panel_path),
            "summary": str(summary_path),
            "monthly": str(monthly_path),
            "report": str(report_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    display = summary[summary["cost_tier"].isin(["stress_10bp", "severe_20bp"])].copy()
    lines = [
        "# Crypto A6.3 Core4 Conservative Dry Shadow Replay",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- dry_shadow_object_hash: `{shadow_obj['object_hash']}`",
        f"- gross_cap: `{GROSS_CAP}`",
        f"- warnings: `{warnings}`",
        "",
        "## Summary",
        "",
        "| split | cost | ann mean | compounded max DD | additive max DD | month pass | sharpe | min hour |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in display.iterrows():
        lines.append(
            f"| `{row['split']}` | `{row['cost_tier']}` | {row['annualized_mean']:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | "
            f"{row['additive_max_dd'] if pd.notna(row['additive_max_dd']) else 0:.4f} | "
            f"{row['positive_month_rate'] if pd.notna(row['positive_month_rate']) else 0:.3f} | "
            f"{row['sharpe_proxy'] if pd.notna(row['sharpe_proxy']) else 0:.3f} | {row['min_hour']:.4f} |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- This is a dry-shadow replay only. It does not place orders and does not authorize live trading.",
        "- The gross cap is a conservative risk budget candidate, not alpha optimization.",
        "- Validation month pass is weak; forward shadow requires append-only observation before any deployment discussion.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_3_SUMMARY=" + str(summary_path))
    print("A6_3_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    print("DRY_SHADOW_OBJECT=" + str(object_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
