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
    load_candidates,
    load_method,
    net_long_short,
    next_open_return,
    read_interval_panel,
    summary_with_ann,
)
from crypto_a2_strict_replay import MatrixContext, long_short, split_mask, summarize_vector  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A2_6_CSV = WORKSPACE / "runtime" / "a2_6_tradable_replay" / "crypto_a2_6_tradable_replay_20260519.csv"
A4_CHAMPIONS = WORKSPACE / "runtime" / "a4_cluster_stress" / "crypto_a4_champion_shortlist_20260519.csv"
RUNTIME_DIR = WORKSPACE / "runtime" / "a5_champion_deep_audit"
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


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return clean_float(obj)
    return obj


def load_a1_by_id() -> dict[str, dict[str, Any]]:
    return {c["candidate_id"]: c for c in load_candidates()}


def masked_symbols_target(target: np.ndarray, symbols: list[str], excluded: set[str]) -> np.ndarray:
    out = target.copy()
    for i, symbol in enumerate(symbols):
        if symbol in excluded:
            out[:, i] = np.nan
    return out


def ann_from_vec(values: np.ndarray, interval: str, horizon: int) -> float | None:
    return summary_with_ann(values, interval, horizon)["annualized"]


def max_drawdown_proxy(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(np.nanmin(dd))


def return_stats(values: np.ndarray, interval: str, horizon: int) -> dict[str, Any]:
    s = summary_with_ann(values, interval, horizon)
    clean = values[np.isfinite(values)]
    if clean.size:
        downside = clean[clean < 0]
        downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else None
        sortino = None if not downside_std or s["mean"] is None else float(s["mean"] / downside_std * math.sqrt((365 * 24) / horizon if interval == "1h" else (365 * 24 * 12) / horizon))
    else:
        downside_std = None
        sortino = None
    return {
        "n": s["n"],
        "annualized": s["annualized"],
        "sharpe_proxy": s["sharpe_proxy"],
        "sortino_proxy": sortino,
        "hit_rate": s["hit_rate"],
        "max_drawdown_proxy": max_drawdown_proxy(values),
    }


def eval_candidate_series(
    *,
    signal: np.ndarray,
    target: np.ndarray,
    orientation: float,
    cost_bps: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    net, gross, turnover = net_long_short(signal, target, orientation, cost_bps)
    return net, gross, turnover


def monthly_table(index: pd.DatetimeIndex, values: np.ndarray, interval: str, horizon: int, mask: np.ndarray) -> pd.DataFrame:
    dates = index[mask]
    vals = values[mask]
    df = pd.DataFrame({"timestamp": dates, "value": vals})
    df = df[np.isfinite(df["value"])]
    if df.empty:
        return pd.DataFrame(columns=["month", "n", "mean", "annualized", "hit_rate"])
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")
    rows = []
    for month, part in df.groupby("month"):
        arr = part["value"].to_numpy(dtype=float)
        s = summarize_vector(arr)
        rows.append(
            {
                "month": month,
                "n": s["n"],
                "mean": s["mean"],
                "annualized": ann_from_vec(arr, interval, horizon),
                "hit_rate": s["positive_rate"],
            }
        )
    return pd.DataFrame(rows)


def stress_one_interval(
    *,
    method: dict[str, Any],
    interval: str,
    champions: pd.DataFrame,
    a1: dict[str, dict[str, Any]],
    a2_6: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, pd.Series]]:
    cids = champions["representative_candidate_id"].tolist()
    feature_set = {f for cid in cids for f in a1[cid]["source_features"]}
    index, symbols, matrices = read_interval_panel(method, interval, sorted(feature_set))
    ctx = MatrixContext(matrices)
    event_rate = funding_event_rate(matrices)
    a2_by_id = a2_6.set_index("candidate_id")
    cluster_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    loo_rows: list[dict[str, Any]] = []
    net_series_by_cluster: dict[str, pd.Series] = {}

    masks = {name: split_mask(index, start, end) for name, (start, end) in SPLITS.items()}
    recent_mask = masks["recent_oos_2025H2_2026"]

    for _, champ in champions.iterrows():
        cid = champ["representative_candidate_id"]
        rep = a2_by_id.loc[cid]
        horizon = int(rep["horizon"])
        expression = rep["expression"]
        signal = ctx.eval(expression)
        target_no_funding = next_open_return(matrices["open"], horizon)
        target = target_no_funding - forward_funding_cost(event_rate, horizon)
        orientation = float(rep["train_orientation"])
        net5, gross, turnover = eval_candidate_series(signal=signal, target=target, orientation=orientation, cost_bps=COST_BPS["normal_5bp"])
        net10, _, _ = eval_candidate_series(signal=signal, target=target, orientation=orientation, cost_bps=COST_BPS["stress_2x_10bp"])
        net25, _, _ = eval_candidate_series(signal=signal, target=target, orientation=orientation, cost_bps=COST_BPS["stress_5x_25bp"])
        net5_no_funding_fee, _, _ = eval_candidate_series(signal=signal, target=target_no_funding, orientation=orientation, cost_bps=COST_BPS["normal_5bp"])
        net_series_by_cluster[champ["cluster_id"]] = pd.Series(net5, index=index, name=champ["cluster_id"])

        row: dict[str, Any] = {
            "cluster_id": champ["cluster_id"],
            "grade": champ["grade"],
            "interval": interval,
            "horizon": horizon,
            "motif_family": champ["motif_family"],
            "expression": expression,
            "member_count": int(champ["member_count"]),
            "candidate_id": cid,
            "orientation": orientation,
            "turnover_recent_mean": clean_float(np.nanmean(turnover[recent_mask])),
            "funding_fee_impact_recent_ann": None,
        }
        fee_adj = ann_from_vec(net5[recent_mask], interval, horizon)
        no_fee = ann_from_vec(net5_no_funding_fee[recent_mask], interval, horizon)
        if fee_adj is not None and no_fee is not None:
            row["funding_fee_impact_recent_ann"] = float(fee_adj - no_fee)
        for split_name, mask in masks.items():
            for name, series in {
                "gross": gross,
                "net_5bp": net5,
                "net_10bp": net10,
                "net_25bp": net25,
            }.items():
                stats = return_stats(series[mask], interval, horizon)
                for k, v in stats.items():
                    row[f"{split_name}_{name}_{k}"] = v
        mt = monthly_table(index, net5, interval, horizon, recent_mask)
        if not mt.empty:
            row["recent_months"] = int(len(mt))
            row["recent_positive_months"] = int((mt["annualized"] > 0).sum())
            row["recent_positive_month_rate"] = float((mt["annualized"] > 0).mean())
            row["recent_worst_month_ann"] = clean_float(mt["annualized"].min())
            for _, mrow in mt.iterrows():
                month_rows.append(
                    {
                        "cluster_id": champ["cluster_id"],
                        "month": mrow["month"],
                        "n": int(mrow["n"]),
                        "net_5bp_annualized": mrow["annualized"],
                        "hit_rate": mrow["hit_rate"],
                    }
                )
        else:
            row["recent_months"] = 0
            row["recent_positive_months"] = 0
            row["recent_positive_month_rate"] = None
            row["recent_worst_month_ann"] = None

        loo_values = []
        for symbol in symbols:
            loo_target = masked_symbols_target(target, symbols, {symbol})
            loo_net, _, _ = eval_candidate_series(signal=signal, target=loo_target, orientation=orientation, cost_bps=COST_BPS["normal_5bp"])
            ann = ann_from_vec(loo_net[recent_mask], interval, horizon)
            loo_values.append(ann)
            loo_rows.append(
                {
                    "cluster_id": champ["cluster_id"],
                    "excluded_symbol": symbol,
                    "recent_net_5bp_annualized": ann,
                }
            )
        finite_loo = [v for v in loo_values if v is not None and math.isfinite(float(v))]
        row["symbol_loo_min_recent_ann"] = min(finite_loo) if finite_loo else None
        row["symbol_loo_pass_count"] = int(sum(v > 0 for v in finite_loo))
        row["symbol_loo_pass_rate"] = float(sum(v > 0 for v in finite_loo) / len(finite_loo)) if finite_loo else None
        cluster_rows.append(row)

    return cluster_rows, month_rows, loo_rows, net_series_by_cluster


def book_stats(series_by_cluster: dict[str, pd.Series], cluster_ids: list[str], split_name: str, start: str, end: str, grade_name: str) -> dict[str, Any]:
    if not cluster_ids:
        return {}
    df = pd.concat([series_by_cluster[cid] for cid in cluster_ids], axis=1)
    mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
    part = df.loc[mask]
    book = part.mean(axis=1, skipna=True).to_numpy(dtype=float)
    interval = "1h"
    horizon = 1
    # Book returns are already per-bar realized series; annualization uses 1h bar clock.
    stats = return_stats(book, interval, horizon)
    corr = part.corr()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack()
    return {
        "book_name": grade_name,
        "split": split_name,
        "cluster_count": len(cluster_ids),
        "clusters": "|".join(cluster_ids),
        "annualized": stats["annualized"],
        "sharpe_proxy": stats["sharpe_proxy"],
        "sortino_proxy": stats["sortino_proxy"],
        "hit_rate": stats["hit_rate"],
        "max_drawdown_proxy": stats["max_drawdown_proxy"],
        "mean_pairwise_corr": clean_float(upper.mean()) if len(upper) else None,
        "max_pairwise_corr": clean_float(upper.max()) if len(upper) else None,
    }


def assign_final_decision(row: pd.Series) -> str:
    if row["grade"] == "Grade_A":
        if row["recent_oos_2025H2_2026_net_10bp_annualized"] > 0 and row["symbol_loo_pass_rate"] >= 0.9 and row["recent_positive_month_rate"] >= 0.7:
            return "Core"
        return "Support"
    if row["grade"] == "Grade_B":
        if row["recent_oos_2025H2_2026_net_10bp_annualized"] > 0 and row["symbol_loo_pass_rate"] >= 0.8:
            return "Support"
        return "Watch"
    return "Reject"


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    a1 = load_a1_by_id()
    champions = pd.read_csv(A4_CHAMPIONS)
    a2_6 = pd.read_csv(A2_6_CSV)

    cluster_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    loo_rows: list[dict[str, Any]] = []
    all_series: dict[str, pd.Series] = {}
    for interval, part in champions.groupby("interval"):
        c_rows, m_rows, l_rows, series = stress_one_interval(
            method=method,
            interval=interval,
            champions=part.copy(),
            a1=a1,
            a2_6=a2_6,
        )
        cluster_rows.extend(c_rows)
        month_rows.extend(m_rows)
        loo_rows.extend(l_rows)
        all_series.update(series)

    cards = pd.DataFrame(cluster_rows)
    if not cards.empty:
        cards["final_role"] = cards.apply(assign_final_decision, axis=1)
        cards = cards.sort_values(["final_role", "recent_oos_2025H2_2026_net_5bp_annualized"], ascending=[True, False])
    months = pd.DataFrame(month_rows)
    loo = pd.DataFrame(loo_rows)

    book_rows: list[dict[str, Any]] = []
    grade_a_ids = cards.loc[cards["grade"] == "Grade_A", "cluster_id"].tolist()
    champion_ids = cards.loc[cards["grade"].isin(["Grade_A", "Grade_B"]), "cluster_id"].tolist()
    core_ids = cards.loc[cards["final_role"] == "Core", "cluster_id"].tolist()
    for split_name, (start, end) in SPLITS.items():
        for name, ids in {
            "Grade_A_equal_weight": grade_a_ids,
            "A4_champion_equal_weight": champion_ids,
            "Core_equal_weight": core_ids,
        }.items():
            row = book_stats(all_series, ids, split_name, start, end, name)
            if row:
                book_rows.append(row)
    books = pd.DataFrame(book_rows)

    cards_path = RUNTIME_DIR / "crypto_a5_alpha_cards_20260519.csv"
    months_path = RUNTIME_DIR / "crypto_a5_monthly_stability_20260519.csv"
    loo_path = RUNTIME_DIR / "crypto_a5_symbol_leave_one_out_20260519.csv"
    books_path = RUNTIME_DIR / "crypto_a5_book_proxy_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a5_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A5_CHAMPION_DEEP_AUDIT_20260519.md"
    cards.to_csv(cards_path, index=False)
    months.to_csv(months_path, index=False)
    loo.to_csv(loo_path, index=False)
    books.to_csv(books_path, index=False)

    counts = {
        "input_champions": int(len(champions)),
        "final_role_counts": cards["final_role"].value_counts().to_dict() if not cards.empty else {},
        "grade_counts": cards["grade"].value_counts().to_dict() if not cards.empty else {},
        "book_rows": int(len(books)),
    }
    decision = "PASS_A5_DAILY_RESEARCH_PROOF_PACK" if counts["final_role_counts"].get("Core", 0) >= 3 else "HOLD_A5_INSUFFICIENT_CORE"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "inputs": {"a4_champions": str(A4_CHAMPIONS), "a2_6_csv": str(A2_6_CSV)},
        "outputs": {
            "alpha_cards": str(cards_path),
            "monthly_stability": str(months_path),
            "symbol_leave_one_out": str(loo_path),
            "book_proxy": str(books_path),
            "report": str(report_path),
        },
        "counts": counts,
        "boundaries": [
            "daily/1h research proof only",
            "not production ready",
            "static core12 universe remains unresolved",
            "real exchange slippage/capacity not modeled",
        ],
    }
    manifest_path.write_text(json.dumps(json_safe(manifest), indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Crypto A5 Champion Deep Audit",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- input champions: `{len(champions)}`",
        f"- final role counts: `{counts['final_role_counts']}`",
        "",
        "## Alpha Cards",
        "",
        "| role | grade | cluster | interval | horizon | motif | recent net 5bp | recent net 10bp | month pass | symbol LOO pass | funding fee impact | expression |",
        "|---|---|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in cards.iterrows():
        lines.append(
            f"| `{row['final_role']}` | `{row['grade']}` | `{row['cluster_id']}` | `{row['interval']}` | {int(row['horizon'])} | "
            f"`{row['motif_family']}` | {row['recent_oos_2025H2_2026_net_5bp_annualized']:.4f} | "
            f"{row['recent_oos_2025H2_2026_net_10bp_annualized']:.4f} | "
            f"{row['recent_positive_month_rate']:.3f} | {row['symbol_loo_pass_rate']:.3f} | "
            f"{row['funding_fee_impact_recent_ann']:.4f} | `{row['expression']}` |"
        )
    lines += [
        "",
        "## Book Proxy",
        "",
        "| book | split | clusters | annualized | sharpe | sortino | max DD | mean corr | max corr |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in books.iterrows():
        lines.append(
            f"| `{row['book_name']}` | `{row['split']}` | {int(row['cluster_count'])} | "
            f"{row['annualized']:.4f} | {row['sharpe_proxy']:.3f} | "
            f"{row['sortino_proxy'] if pd.notna(row['sortino_proxy']) else 0:.3f} | "
            f"{row['max_drawdown_proxy'] if pd.notna(row['max_drawdown_proxy']) else 0:.4f} | "
            f"{row['mean_pairwise_corr'] if pd.notna(row['mean_pairwise_corr']) else 0:.3f} | "
            f"{row['max_pairwise_corr'] if pd.notna(row['max_pairwise_corr']) else 0:.3f} |"
        )
    lines += [
        "",
        "## Decision Boundary",
        "",
        "- This is a research proof pack after next-bar proxy execution, 5bp/10bp cost stress, funding fee adjustment, placebo, ablation, month stability, and symbol leave-one-out.",
        "- It is not production proof: no order book slippage, no live forward, no time-varying universe beyond static core12.",
        "- Next valid step is locked forward/shadow or exchange-execution calibration, not broader formula search.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A5_CARDS=" + str(cards_path))
    print("A5_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
