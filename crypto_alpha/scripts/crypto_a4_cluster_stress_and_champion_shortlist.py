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

from crypto_a2_strict_replay import MatrixContext, row_corr, split_mask  # noqa: E402
from crypto_a2_6_tradable_replay import (  # noqa: E402
    COST_BPS,
    PURGE_EMBARGO_BARS,
    forward_funding_cost,
    funding_event_rate,
    load_candidates,
    load_method,
    net_long_short,
    next_open_return,
    purged_split_mask,
    read_interval_panel,
    summary_with_ann,
)


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A2_6_CSV = WORKSPACE / "runtime" / "a2_6_tradable_replay" / "crypto_a2_6_tradable_replay_20260519.csv"
RUNTIME_DIR = WORKSPACE / "runtime" / "a4_cluster_stress"
REPORT_DIR = WORKSPACE / "reports"

RECENT_START = pd.Timestamp("2025-07-01T00:00:00Z")
RECENT_END = pd.Timestamp("2026-04-30T23:59:59Z")
CLUSTER_CORR_THRESHOLD = 0.85
MAX_TIMESTAMPS_PER_INTERVAL = 20000
REGIME_FEATURES = ["realized_vol_24", "quote_asset_volume", "mark_index_ratio", "latest_known_funding_rate"]


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


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    clean = vec.astype(float, copy=True)
    finite = np.isfinite(clean)
    if finite.sum() < 100:
        return np.full_like(clean, np.nan, dtype=float)
    mean = np.nanmean(clean)
    std = np.nanstd(clean)
    if not std or np.isnan(std):
        return np.full_like(clean, np.nan, dtype=float)
    clean = (clean - mean) / std
    clean[~finite] = np.nan
    return clean


def corr_vectors(a: np.ndarray, b: np.ndarray) -> float:
    valid = np.isfinite(a) & np.isfinite(b)
    if valid.sum() < 100:
        return np.nan
    return float(np.corrcoef(a[valid], b[valid])[0, 1])


def load_a1_by_id() -> dict[str, dict[str, Any]]:
    return {c["candidate_id"]: c for c in load_candidates()}


def choose_sample_indices(index: pd.DatetimeIndex) -> np.ndarray:
    recent = np.asarray((index >= RECENT_START) & (index <= RECENT_END))
    recent_idx = np.flatnonzero(recent)
    if recent_idx.size <= MAX_TIMESTAMPS_PER_INTERVAL:
        return recent_idx
    step = int(np.ceil(recent_idx.size / MAX_TIMESTAMPS_PER_INTERVAL))
    return recent_idx[::step]


def score_proxy(row: pd.Series) -> float:
    return float(
        (row.get("validation_2025H1_net_normal_5bp_annualized", 0) or 0) * 0.25
        + (row.get("recent_oos_2025H2_2026_net_normal_5bp_annualized", 0) or 0) * 0.35
        + np.tanh((row.get("recent_oos_2025H2_2026_net_normal_5bp_sharpe_proxy", 0) or 0) / 3.0) * 0.20
        + np.tanh((row.get("marginal_vs_low_order_best", 0) or 0) / 0.25) * 0.20
    )


def signal_vectors_for_interval(method: dict[str, Any], keep: pd.DataFrame, a1: dict[str, dict[str, Any]], interval: str) -> dict[str, np.ndarray]:
    subset = keep[keep["interval"] == interval].copy()
    if subset.empty:
        return {}
    features = sorted({f for cid in subset["candidate_id"] for f in a1[cid]["source_features"]})
    index, _, matrices = read_interval_panel(method, interval, features)
    sample_idx = choose_sample_indices(index)
    ctx = MatrixContext(matrices)
    vectors: dict[str, np.ndarray] = {}
    for _, row in subset.iterrows():
        sig = ctx.eval(row["expression"]) * float(row["train_orientation"])
        vectors[row["candidate_id"]] = normalize_vector(sig[sample_idx, :].reshape(-1))
    return vectors


def greedy_cluster(keep: pd.DataFrame, vectors: dict[str, np.ndarray]) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = keep.copy()
    ranked["score_proxy"] = ranked.apply(score_proxy, axis=1)
    ranked = ranked.sort_values("score_proxy", ascending=False)
    clusters: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    for _, row in ranked.iterrows():
        cid = row["candidate_id"]
        vec = vectors[cid]
        best_cluster: dict[str, Any] | None = None
        best_corr = -2.0
        for cluster in clusters:
            corr = corr_vectors(vec, vectors[cluster["representative_candidate_id"]])
            if np.isfinite(corr) and corr > best_corr:
                best_corr = corr
                best_cluster = cluster
        if best_cluster is None or best_corr < CLUSTER_CORR_THRESHOLD:
            cluster_id = f"crypto_a4_{row['interval']}_{len(clusters) + 1:03d}"
            best_cluster = {
                "cluster_id": cluster_id,
                "interval": row["interval"],
                "representative_candidate_id": cid,
                "representative_expression": row["expression"],
                "representative_motif": row["motif_family"],
                "representative_horizon": int(row["horizon"]),
                "representative_score_proxy": float(row["score_proxy"]),
                "member_count": 0,
            }
            clusters.append(best_cluster)
            best_corr = 1.0
        best_cluster["member_count"] += 1
        assignments.append(
            {
                "candidate_id": cid,
                "cluster_id": best_cluster["cluster_id"],
                "corr_to_representative": best_corr,
                "interval": row["interval"],
                "horizon": int(row["horizon"]),
                "motif_family": row["motif_family"],
                "expression": row["expression"],
                "score_proxy": float(row["score_proxy"]),
            }
        )
    return pd.DataFrame(clusters), pd.DataFrame(assignments)


def position_masks(signal: np.ndarray, target: np.ndarray, orientation: float) -> np.ndarray:
    oriented = signal * orientation
    valid = np.isfinite(oriented) & np.isfinite(target)
    n = valid.sum(axis=1)
    top_score = np.where(valid, oriented, -np.inf)
    bottom_score = np.where(valid, oriented, np.inf)
    top_idx = np.argpartition(-top_score, kth=2, axis=1)[:, :3]
    bottom_idx = np.argpartition(bottom_score, kth=2, axis=1)[:, :3]
    mask = np.zeros_like(valid, dtype=np.int8)
    rows = np.arange(valid.shape[0])[:, None]
    mask[rows, top_idx] = 1
    mask[rows, bottom_idx] = -1
    mask[n < 8, :] = 0
    return mask


def selected_symbol_concentration(signal: np.ndarray, target: np.ndarray, orientation: float, mask: np.ndarray, symbols: list[str]) -> tuple[float | None, str | None]:
    pos = position_masks(signal[mask], target[mask], orientation)
    counts = np.abs(pos).sum(axis=0).astype(float)
    total = counts.sum()
    if total <= 0:
        return None, None
    idx = int(np.argmax(counts))
    return float(counts[idx] / total), symbols[idx]


def regime_bucket_masks(matrices: dict[str, np.ndarray], date_mask: np.ndarray) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    specs = {
        "vol": "realized_vol_24",
        "liquidity": "quote_asset_volume",
        "basis_abs": "mark_index_ratio",
        "funding_abs": "latest_known_funding_rate",
    }
    for prefix, feature in specs.items():
        if feature not in matrices:
            continue
        mat = matrices[feature]
        values = np.nanmedian(np.abs(mat) if prefix in {"basis_abs", "funding_abs"} else mat, axis=1)
        local = values[date_mask]
        if np.isfinite(local).sum() < 100:
            continue
        median = float(np.nanmedian(local))
        high = date_mask & (values >= median)
        low = date_mask & (values < median)
        out[f"{prefix}_high"] = high
        out[f"{prefix}_low"] = low
    return out


def masked_symbols_target(target: np.ndarray, symbols: list[str], excluded: set[str]) -> np.ndarray:
    out = target.copy()
    for i, symbol in enumerate(symbols):
        if symbol in excluded:
            out[:, i] = np.nan
    return out


def stress_representatives(method: dict[str, Any], clusters: pd.DataFrame, keep: pd.DataFrame, a1: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    keep_by_id = keep.set_index("candidate_id")
    for interval, part in clusters.groupby("interval"):
        cids = part["representative_candidate_id"].tolist()
        features = sorted(
            set(REGIME_FEATURES)
            | {f for cid in cids for f in a1[cid]["source_features"]}
        )
        index, symbols, matrices = read_interval_panel(method, interval, features)
        ctx = MatrixContext(matrices)
        event_rate = funding_event_rate(matrices)
        recent_mask = split_mask(index, "2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z")
        regime_masks = regime_bucket_masks(matrices, recent_mask)

        for _, cluster in part.iterrows():
            rep = keep_by_id.loc[cluster["representative_candidate_id"]]
            horizon = int(rep["horizon"])
            signal = ctx.eval(rep["expression"])
            target = next_open_return(matrices["open"], horizon) - forward_funding_cost(event_rate, horizon)
            orientation = float(rep["train_orientation"])
            alt_target = masked_symbols_target(target, symbols, {"BTCUSDT", "ETHUSDT"})
            alt_net, _, _ = net_long_short(signal[recent_mask], alt_target[recent_mask], orientation, COST_BPS["normal_5bp"])
            alt_summary = summary_with_ann(alt_net, interval, horizon)
            symbol_share, top_symbol = selected_symbol_concentration(signal, target, orientation, recent_mask, symbols)
            out = {
                "cluster_id": cluster["cluster_id"],
                "interval": interval,
                "member_count": int(cluster["member_count"]),
                "representative_candidate_id": rep.name,
                "horizon": horizon,
                "motif_family": rep["motif_family"],
                "expression": rep["expression"],
                "validation_net_5bp_ann": rep["validation_2025H1_net_normal_5bp_annualized"],
                "recent_net_5bp_ann": rep["recent_oos_2025H2_2026_net_normal_5bp_annualized"],
                "validation_net_10bp_ann": rep["validation_2025H1_net_stress_2x_10bp_annualized"],
                "recent_net_10bp_ann": rep["recent_oos_2025H2_2026_net_stress_2x_10bp_annualized"],
                "recent_net_25bp_ann": rep["recent_oos_2025H2_2026_net_stress_5x_25bp_annualized"],
                "recent_turnover": rep["recent_oos_2025H2_2026_turnover_mean"],
                "recent_mean_ic": rep["recent_oos_2025H2_2026_mean_ic"],
                "baseline_ablation_pass": bool(rep["baseline_ablation_pass"]),
                "marginal_vs_low_order_best": rep["marginal_vs_low_order_best"],
                "placebo_gate_pass": bool(rep["placebo_gate_pass"]),
                "alt_only_recent_net_5bp_ann": alt_summary["annualized"],
                "max_symbol_share": symbol_share,
                "top_symbol": top_symbol,
            }
            for name, m in regime_masks.items():
                net, _, _ = net_long_short(signal[m], target[m], orientation, COST_BPS["normal_5bp"])
                out[f"{name}_recent_net_5bp_ann"] = summary_with_ann(net, interval, horizon)["annualized"]
            rows.append(out)
    return pd.DataFrame(rows)


def grade_cluster(row: pd.Series) -> tuple[str, str]:
    normal_ok = row["validation_net_5bp_ann"] > 0 and row["recent_net_5bp_ann"] > 0
    stress_ok = row["validation_net_10bp_ann"] > 0 and row["recent_net_10bp_ann"] > 0
    concentration_ok = pd.isna(row["max_symbol_share"]) or row["max_symbol_share"] <= 0.20
    turnover_ok = row["recent_turnover"] <= 0.60
    ablation_ok = bool(row["baseline_ablation_pass"])
    placebo_ok = bool(row["placebo_gate_pass"])
    if normal_ok and stress_ok and concentration_ok and turnover_ok and ablation_ok and placebo_ok and row["recent_net_5bp_ann"] >= 0.30:
        return "Grade_A", "passes normal/stress cost, placebo, ablation, turnover, symbol concentration"
    if normal_ok and concentration_ok and turnover_ok and ablation_ok and placebo_ok and row["recent_net_5bp_ann"] >= 0.15:
        return "Grade_B", "passes normal cost but has weaker stress or magnitude"
    return "Reject", "fails cost/stress/magnitude/concentration gate"


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    a1 = load_a1_by_id()
    a2_6 = pd.read_csv(A2_6_CSV)
    keep = a2_6[a2_6["decision"] == "KEEP_A2_6_TRADABLE_CANDIDATE"].copy()

    clusters_all: list[pd.DataFrame] = []
    assignments_all: list[pd.DataFrame] = []
    for interval in sorted(keep["interval"].unique()):
        vectors = signal_vectors_for_interval(method, keep, a1, interval)
        interval_keep = keep[keep["interval"] == interval].copy()
        clusters, assignments = greedy_cluster(interval_keep, vectors)
        clusters_all.append(clusters)
        assignments_all.append(assignments)
    clusters_df = pd.concat(clusters_all, ignore_index=True) if clusters_all else pd.DataFrame()
    assignments_df = pd.concat(assignments_all, ignore_index=True) if assignments_all else pd.DataFrame()
    stress_df = stress_representatives(method, clusters_df, keep, a1) if not clusters_df.empty else pd.DataFrame()
    if not stress_df.empty:
        grades = stress_df.apply(grade_cluster, axis=1, result_type="expand")
        stress_df["grade"] = grades[0]
        stress_df["grade_reason"] = grades[1]
        stress_df = stress_df.sort_values(["grade", "recent_net_5bp_ann"], ascending=[True, False])

    clusters_path = RUNTIME_DIR / "crypto_a4_signal_clusters_20260519.csv"
    assignments_path = RUNTIME_DIR / "crypto_a4_candidate_cluster_assignments_20260519.csv"
    stress_path = RUNTIME_DIR / "crypto_a4_cluster_stress_20260519.csv"
    champion_path = RUNTIME_DIR / "crypto_a4_champion_shortlist_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a4_manifest_20260519.json"
    report_path = REPORT_DIR / "CRYPTO_A4_CLUSTER_STRESS_AND_CHAMPION_SHORTLIST_20260519.md"
    clusters_df.to_csv(clusters_path, index=False)
    assignments_df.to_csv(assignments_path, index=False)
    stress_df.to_csv(stress_path, index=False)
    champions = stress_df[stress_df["grade"].isin(["Grade_A", "Grade_B"])].copy()
    champions.to_csv(champion_path, index=False)

    counts = {
        "input_a2_6_keep_candidates": int(len(keep)),
        "signal_clusters": int(len(clusters_df)),
        "grade_counts": stress_df["grade"].value_counts().to_dict() if not stress_df.empty else {},
        "clusters_by_interval": stress_df["interval"].value_counts().to_dict() if not stress_df.empty else {},
        "champion_count": int(len(champions)),
    }
    decision = "PASS_A4_CHAMPION_SHORTLIST_WITH_LIMITS" if len(champions) >= 5 else "HOLD_A4_INSUFFICIENT_CHAMPIONS"
    manifest = {
        "generated_at": utc_now(),
        "decision": decision,
        "inputs": {"a2_6_csv": str(A2_6_CSV)},
        "outputs": {
            "clusters": str(clusters_path),
            "assignments": str(assignments_path),
            "stress": str(stress_path),
            "champions": str(champion_path),
            "report": str(report_path),
        },
        "parameters": {
            "cluster_corr_threshold": CLUSTER_CORR_THRESHOLD,
            "normal_cost_bps": COST_BPS["normal_5bp"],
            "stress_cost_bps": COST_BPS["stress_2x_10bp"],
            "grade_a_requires": "normal+10bp cost pass, placebo, ablation, turnover<=0.60, max symbol share<=0.20, recent net>=0.30",
        },
        "counts": counts,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Crypto A4 Cluster Stress And Champion Shortlist",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        f"- decision: `{decision}`",
        f"- input A2.6 keep candidates: `{len(keep)}`",
        f"- signal clusters: `{counts['signal_clusters']}`",
        f"- grade counts: `{counts['grade_counts']}`",
        f"- champion shortlist count: `{counts['champion_count']}`",
        "",
        "## Interpretation",
        "",
        "A4 is run only on A2.6 tradable candidates. The broad A2/A3 proxy pool is intentionally excluded from champion grading.",
        "",
        "## Champion Shortlist",
        "",
        "| grade | cluster | interval | members | horizon | motif | recent net 5bp | recent net 10bp | turnover | max symbol share | expression |",
        "|---|---|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    if champions.empty:
        lines.append("| n/a |  |  |  |  |  |  |  |  |  |  |")
    else:
        for _, row in champions.sort_values(["grade", "recent_net_5bp_ann"], ascending=[True, False]).iterrows():
            max_share = "" if pd.isna(row["max_symbol_share"]) else f"{row['max_symbol_share']:.3f}"
            lines.append(
                f"| `{row['grade']}` | `{row['cluster_id']}` | `{row['interval']}` | {int(row['member_count'])} | "
                f"{int(row['horizon'])} | `{row['motif_family']}` | {row['recent_net_5bp_ann']:.4f} | "
                f"{row['recent_net_10bp_ann']:.4f} | {row['recent_turnover']:.4f} | {max_share} | `{row['expression']}` |"
            )
    lines += [
        "",
        "## Boundary",
        "",
        "- Grade A/B here means daily/1h research champion candidate after tradable proxy replay; it is not production alpha proof.",
        "- Static core12 universe and real exchange slippage/capacity remain unresolved.",
        "- If champions are dominated by funding motifs, the next stage should stress funding semantics and fee timing before expanding search.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A4_STRESS=" + str(stress_path))
    print("A4_REPORT=" + str(report_path))
    print("DECISION=" + decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
