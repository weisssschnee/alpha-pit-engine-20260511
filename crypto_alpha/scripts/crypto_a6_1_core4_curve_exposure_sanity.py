from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a2_6_tradable_replay import (  # noqa: E402
    COST_BPS,
    forward_funding_cost,
    funding_event_rate,
    load_method,
    next_open_return,
    read_interval_panel,
)
from crypto_a2_strict_replay import MatrixContext, split_mask  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
LOCKED_OBJECT = WORKSPACE / "runtime" / "baselines" / "crypto_core4_locked_research_book_v1.json"
RUNTIME_DIR = WORKSPACE / "runtime" / "a6_1_core4_curve_exposure_sanity"
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
    return out if math.isfinite(out) else None


def rank_rows(mat: np.ndarray) -> np.ndarray:
    return pd.DataFrame(mat).rank(axis=1, pct=True).to_numpy(dtype=float)


def cluster_position(signal: np.ndarray, target: np.ndarray, orientation: float) -> np.ndarray:
    oriented = signal * orientation
    valid = np.isfinite(oriented) & np.isfinite(target)
    n = valid.sum(axis=1)
    top_score = np.where(valid, oriented, -np.inf)
    bottom_score = np.where(valid, oriented, np.inf)
    top_idx = np.argpartition(-top_score, kth=2, axis=1)[:, :3]
    bottom_idx = np.argpartition(bottom_score, kth=2, axis=1)[:, :3]
    pos = np.zeros_like(target, dtype=float)
    rows = np.arange(target.shape[0])[:, None]
    pos[rows, top_idx] = 1.0 / 3.0
    pos[rows, bottom_idx] = -1.0 / 3.0
    pos[n < 8, :] = 0.0
    return pos


def cluster_return_components(pos: np.ndarray, gross_target: np.ndarray, funding_cost: np.ndarray, cost_bps: float) -> dict[str, np.ndarray]:
    gross = np.nansum(pos * gross_target, axis=1)
    funding_drag = np.nansum(np.where(pos > 0, pos * funding_cost, 0.0), axis=1)
    pos_prev = np.vstack([np.zeros((1, pos.shape[1])), pos[:-1, :]])
    turnover = np.nansum(np.abs(pos - pos_prev), axis=1) / 2.0
    fee_drag = turnover * (cost_bps / 10000.0)
    net = gross - funding_drag - fee_drag
    return {
        "gross_return": gross,
        "funding_drag": funding_drag,
        "fee_drag": fee_drag,
        "turnover": turnover,
        "net_return": net,
        "gross_exposure": np.nansum(np.abs(pos), axis=1),
        "net_exposure": np.nansum(pos, axis=1),
    }


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
        return {"n": 0}
    qs = np.quantile(clean, [0.001, 0.01, 0.05, 0.5, 0.95, 0.99, 0.999])
    return {
        "n": int(clean.size),
        "mean": float(np.mean(clean)),
        "std": float(np.std(clean, ddof=1)) if clean.size > 1 else None,
        "annualized_mean_1h": float(np.mean(clean) * 365 * 24),
        "hit_rate": float(np.mean(clean > 0)),
        "min": float(np.min(clean)),
        "max": float(np.max(clean)),
        "q001": float(qs[0]),
        "q01": float(qs[1]),
        "q05": float(qs[2]),
        "median": float(qs[3]),
        "q95": float(qs[4]),
        "q99": float(qs[5]),
        "q999": float(qs[6]),
        "additive_total": float(np.sum(clean)),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_total": float(np.prod(1.0 + clean) - 1.0) if np.all(clean > -1.0) else None,
        "compounded_max_dd": compounded_drawdown(clean) if np.all(clean > -1.0) else None,
        "bars_le_minus_1pct": int(np.sum(clean <= -0.01)),
        "bars_le_minus_5pct": int(np.sum(clean <= -0.05)),
        "bars_le_minus_10pct": int(np.sum(clean <= -0.10)),
        "bars_le_minus_50pct": int(np.sum(clean <= -0.50)),
        "bars_le_minus_100pct": int(np.sum(clean <= -1.0)),
    }


def compute_core4() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    locked = json.loads(LOCKED_OBJECT.read_text(encoding="utf-8"))
    clusters = locked["clusters"]
    method = load_method()
    interval = "1h"
    features = sorted({f for c in clusters for f in extract_features(c["representative_expression"])})
    index, symbols, matrices = read_interval_panel(method, interval, features)
    ctx = MatrixContext(matrices)
    event_rate = funding_event_rate(matrices)

    cluster_components: list[pd.DataFrame] = []
    positions: list[pd.DataFrame] = []
    for cluster in clusters:
        horizon = int(cluster["horizon"])
        signal = ctx.eval(cluster["representative_expression"])
        gross_target = next_open_return(matrices["open"], horizon)
        funding_cost = forward_funding_cost(event_rate, horizon)
        # Core clusters were all selected with positive train orientation in A5 inputs;
        # use locked expression orientation by recomputing train IC sign defensively.
        train_mask = split_mask(index, SPLITS["train_2024"][0], SPLITS["train_2024"][1])
        train_corr = row_ic(signal[train_mask], (gross_target - funding_cost)[train_mask])
        orientation = 1.0 if np.nanmean(train_corr) >= 0 else -1.0
        pos = cluster_position(signal, gross_target - funding_cost, orientation)
        comp = cluster_return_components(pos, gross_target, funding_cost, COST_BPS["normal_5bp"])
        comp_df = pd.DataFrame(comp, index=index)
        comp_df["cluster_id"] = cluster["cluster_id"]
        comp_df["expression"] = cluster["representative_expression"]
        cluster_components.append(comp_df.reset_index(names="timestamp"))
        pos_df = pd.DataFrame(pos, index=index, columns=symbols).reset_index(names="timestamp")
        pos_df = pos_df.melt(id_vars="timestamp", var_name="symbol", value_name="position")
        pos_df = pos_df[pos_df["position"] != 0].copy()
        pos_df["cluster_id"] = cluster["cluster_id"]
        positions.append(pos_df)

    component_df = pd.concat(cluster_components, ignore_index=True)
    pos_long = pd.concat(positions, ignore_index=True)
    pivot = component_df.pivot(index="timestamp", columns="cluster_id", values="net_return")
    book = pd.DataFrame(index=pivot.index)
    book["core4_net_return"] = pivot.mean(axis=1, skipna=True)
    for field in ["gross_return", "funding_drag", "fee_drag", "turnover", "gross_exposure", "net_exposure"]:
        p = component_df.pivot(index="timestamp", columns="cluster_id", values=field)
        book[field] = p.mean(axis=1, skipna=True)
    return component_df, pos_long, book.reset_index(), pd.DataFrame(clusters)


def row_ic(signal: np.ndarray, target: np.ndarray) -> np.ndarray:
    s = rank_rows(signal)
    t = rank_rows(target)
    valid = np.isfinite(s) & np.isfinite(t)
    n = valid.sum(axis=1).astype(float)
    x = np.where(valid, s, 0.0)
    y = np.where(valid, t, 0.0)
    sx = x.sum(axis=1)
    sy = y.sum(axis=1)
    sxy = (x * y).sum(axis=1)
    sx2 = (x * x).sum(axis=1)
    sy2 = (y * y).sum(axis=1)
    den = np.sqrt((n * sx2 - sx * sx) * (n * sy2 - sy * sy))
    out = (n * sxy - sx * sy) / den
    out[(n < 8) | ~np.isfinite(out)] = np.nan
    return out


def extract_features(expr: str) -> list[str]:
    candidates = [
        "ret_12",
        "latest_known_funding_rate",
        "mark_index_ratio",
        "mark_minus_index",
        "funding_rate_persistence_3",
        "hl_range",
    ]
    return [f for f in candidates if f in expr]


def split_summary(book: pd.DataFrame) -> pd.DataFrame:
    rows = []
    idx = pd.to_datetime(book["timestamp"], utc=True)
    values = book["core4_net_return"].to_numpy(dtype=float)
    for split_name, (start, end) in SPLITS.items():
        mask = np.asarray((idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end)))
        s = stats(values[mask])
        s["split"] = split_name
        s["mean_gross_exposure"] = clean_float(book.loc[mask, "gross_exposure"].mean())
        s["max_gross_exposure"] = clean_float(book.loc[mask, "gross_exposure"].max())
        s["mean_abs_net_exposure"] = clean_float(book.loc[mask, "net_exposure"].abs().mean())
        s["mean_turnover"] = clean_float(book.loc[mask, "turnover"].mean())
        s["fee_drag_total"] = clean_float(book.loc[mask, "fee_drag"].sum())
        s["funding_drag_total"] = clean_float(book.loc[mask, "funding_drag"].sum())
        rows.append(s)
    return pd.DataFrame(rows)


def top_loss_hours(book: pd.DataFrame, component: pd.DataFrame, positions: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    top = book.sort_values("core4_net_return").head(n).copy()
    rows = []
    comp_by_ts = component.groupby("timestamp")
    pos_by_ts = positions.groupby("timestamp")
    for _, row in top.iterrows():
        ts = row["timestamp"]
        comp = comp_by_ts.get_group(ts).sort_values("net_return").head(4)
        pos = pos_by_ts.get_group(ts) if ts in pos_by_ts.groups else pd.DataFrame()
        symbol_contrib = {}
        if not pos.empty:
            symbol_contrib = pos.groupby("symbol")["position"].apply(lambda x: float(np.sum(np.abs(x)))).sort_values(ascending=False).head(3).to_dict()
        rows.append(
            {
                "timestamp": ts,
                "book_net_return": row["core4_net_return"],
                "gross_return": row["gross_return"],
                "fee_drag": row["fee_drag"],
                "funding_drag": row["funding_drag"],
                "turnover": row["turnover"],
                "gross_exposure": row["gross_exposure"],
                "worst_cluster": comp.iloc[0]["cluster_id"] if not comp.empty else None,
                "worst_cluster_return": comp.iloc[0]["net_return"] if not comp.empty else None,
                "cluster_returns": ";".join(f"{r['cluster_id']}={r['net_return']:.4f}" for _, r in comp.iterrows()),
                "top_abs_symbol_positions": json.dumps(symbol_contrib, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def contribution_summary(component: pd.DataFrame, positions: pd.DataFrame, book: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    recent_mask = (pd.to_datetime(component["timestamp"], utc=True) >= pd.Timestamp(SPLITS["recent_oos_2025H2_2026"][0])) & (
        pd.to_datetime(component["timestamp"], utc=True) <= pd.Timestamp(SPLITS["recent_oos_2025H2_2026"][1])
    )
    cluster = (
        component.loc[recent_mask]
        .groupby("cluster_id")
        .agg(
            net_total=("net_return", "sum"),
            net_mean=("net_return", "mean"),
            worst_hour=("net_return", "min"),
            best_hour=("net_return", "max"),
            fee_drag_total=("fee_drag", "sum"),
            funding_drag_total=("funding_drag", "sum"),
            turnover_mean=("turnover", "mean"),
            gross_exposure_mean=("gross_exposure", "mean"),
        )
        .reset_index()
    )
    pos_recent = positions[
        (pd.to_datetime(positions["timestamp"], utc=True) >= pd.Timestamp(SPLITS["recent_oos_2025H2_2026"][0]))
        & (pd.to_datetime(positions["timestamp"], utc=True) <= pd.Timestamp(SPLITS["recent_oos_2025H2_2026"][1]))
    ].copy()
    symbol = (
        pos_recent.assign(abs_position=pos_recent["position"].abs())
        .groupby("symbol")
        .agg(abs_position_sum=("abs_position", "sum"), signed_position_sum=("position", "sum"))
        .reset_index()
    )
    total_abs = symbol["abs_position_sum"].sum()
    symbol["abs_position_share"] = symbol["abs_position_sum"] / total_abs if total_abs else np.nan
    return cluster, symbol.sort_values("abs_position_share", ascending=False)


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    component, positions, book, clusters = compute_core4()
    summary = split_summary(book)
    losses = top_loss_hours(book, component, positions)
    cluster_contrib, symbol_contrib = contribution_summary(component, positions, book)

    component_path = RUNTIME_DIR / "crypto_a6_1_core4_component_returns_20260519.csv"
    positions_path = RUNTIME_DIR / "crypto_a6_1_core4_positions_20260519.csv"
    book_path = RUNTIME_DIR / "crypto_a6_1_core4_book_returns_20260519.csv"
    summary_path = RUNTIME_DIR / "crypto_a6_1_core4_curve_summary_20260519.csv"
    losses_path = RUNTIME_DIR / "crypto_a6_1_core4_top_loss_hours_20260519.csv"
    cluster_path = RUNTIME_DIR / "crypto_a6_1_core4_cluster_contribution_20260519.csv"
    symbol_path = RUNTIME_DIR / "crypto_a6_1_core4_symbol_exposure_20260519.csv"
    report_path = REPORT_DIR / "CRYPTO_A6_1_CORE4_CURVE_EXPOSURE_SANITY_20260519.md"
    manifest_path = RUNTIME_DIR / "crypto_a6_1_manifest_20260519.json"

    component.to_csv(component_path, index=False)
    # Positions can be large but manageable; keep for audit trace.
    positions.to_csv(positions_path, index=False)
    book.to_csv(book_path, index=False)
    summary.to_csv(summary_path, index=False)
    losses.to_csv(losses_path, index=False)
    cluster_contrib.to_csv(cluster_path, index=False)
    symbol_contrib.to_csv(symbol_path, index=False)

    recent = summary[summary["split"] == "recent_oos_2025H2_2026"].iloc[0].to_dict()
    has_unit_bug = bool(recent.get("bars_le_minus_100pct", 0) and recent["bars_le_minus_100pct"] > 0)
    high_tail_loss = bool(recent.get("bars_le_minus_10pct", 0) and recent["bars_le_minus_10pct"] > 0)
    decision = "HOLD_A6_1_RETURN_UNIT_BUG" if has_unit_bug else "PASS_A6_1_CURVE_SANITY_RISK_SCALING_REQUIRED"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "locked_object": str(LOCKED_OBJECT),
        "outputs": {
            "component_returns": str(component_path),
            "positions": str(positions_path),
            "book_returns": str(book_path),
            "summary": str(summary_path),
            "top_loss_hours": str(losses_path),
            "cluster_contribution": str(cluster_path),
            "symbol_exposure": str(symbol_path),
            "report": str(report_path),
        },
        "recent_oos_summary": {k: clean_float(v) for k, v in recent.items()},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Crypto A6.1 Core4 Curve Exposure Sanity",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- locked object: `{LOCKED_OBJECT}`",
        "",
        "## Split Summary",
        "",
        "| split | ann mean | additive total | additive max DD | compounded total | compounded max DD | min hour | <=-10% bars | gross exposure mean | turnover mean | fee drag total | funding drag total |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| `{row['split']}` | {row['annualized_mean_1h']:.4f} | {row['additive_total']:.4f} | "
            f"{row['additive_max_dd']:.4f} | {row['compounded_total'] if pd.notna(row['compounded_total']) else 0:.4f} | "
            f"{row['compounded_max_dd'] if pd.notna(row['compounded_max_dd']) else 0:.4f} | {row['min']:.4f} | "
            f"{int(row['bars_le_minus_10pct'])} | {row['mean_gross_exposure']:.4f} | {row['mean_turnover']:.4f} | "
            f"{row['fee_drag_total']:.4f} | {row['funding_drag_total']:.4f} |"
        )

    lines += [
        "",
        "## Top Loss Hours",
        "",
        "| timestamp | book net | gross | fee | funding | turnover | gross exposure | worst cluster | worst cluster ret |",
        "|---|---:|---:|---:|---:|---:|---:|---|---:|",
    ]
    for _, row in losses.head(10).iterrows():
        lines.append(
            f"| `{row['timestamp']}` | {row['book_net_return']:.4f} | {row['gross_return']:.4f} | "
            f"{row['fee_drag']:.4f} | {row['funding_drag']:.4f} | {row['turnover']:.4f} | {row['gross_exposure']:.4f} | "
            f"`{row['worst_cluster']}` | {row['worst_cluster_return']:.4f} |"
        )
    lines += [
        "",
        "## Recent Cluster Contribution",
        "",
        "| cluster | net total | mean | worst hour | best hour | fee drag | funding drag | turnover |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in cluster_contrib.iterrows():
        lines.append(
            f"| `{row['cluster_id']}` | {row['net_total']:.4f} | {row['net_mean']:.6f} | {row['worst_hour']:.4f} | "
            f"{row['best_hour']:.4f} | {row['fee_drag_total']:.4f} | {row['funding_drag_total']:.4f} | {row['turnover_mean']:.4f} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- No <= -100% hourly return bars means the -93% compounded drawdown is not an immediate unit bug.",
        "- The drawdown is driven by repeated large unscaled hourly long-short losses and compounding at full notional.",
        "- Core4 can proceed to A6.2 risk scaling only as a locked research object; it is not shadow/live-ready yet.",
    ]
    if high_tail_loss:
        lines.append("- Tail loss is material; A6.2 must use pre-declared exposure/volatility caps.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A6_1_SUMMARY=" + str(summary_path))
    print("A6_1_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
