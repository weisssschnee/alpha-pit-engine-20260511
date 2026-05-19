from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a2_strict_replay import MatrixContext, load_method, read_interval_panel  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
A2_CSV = WORKSPACE / "runtime" / "a2_strict_replay" / "crypto_a2_strict_replay_20260519.csv"
A1_JSONL = WORKSPACE / "runtime" / "a1_generator_dry_run" / "crypto_a1_candidates_20260519.jsonl"
RUNTIME_DIR = WORKSPACE / "runtime" / "a3_signal_cluster_registry"
REPORT_DIR = WORKSPACE / "reports"

RECENT_START = pd.Timestamp("2025-07-01T00:00:00Z")
RECENT_END = pd.Timestamp("2026-04-30T23:59:59Z")
CLUSTER_CORR_THRESHOLD = 0.85
MAX_TIMESTAMPS_PER_INTERVAL = 20000


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_a1_by_id() -> dict[str, dict[str, Any]]:
    out = {}
    with A1_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                obj = json.loads(line)
                out[obj["candidate_id"]] = obj
    return out


def score_proxy(row: pd.Series) -> float:
    return float(
        (row.get("validation_2025H1_mean_ic", 0) or 0) * 0.25
        + (row.get("recent_oos_2025H2_2026_mean_ic", 0) or 0) * 0.35
        + np.tanh((row.get("recent_oos_2025H2_2026_ls_sharpe_proxy", 0) or 0) / 3.0) * 0.25
        + np.tanh((row.get("validation_2025H1_ls_sharpe_proxy", 0) or 0) / 3.0) * 0.15
    )


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


def choose_sample_indices(index: pd.DatetimeIndex) -> np.ndarray:
    recent = np.asarray((index >= RECENT_START) & (index <= RECENT_END))
    recent_idx = np.flatnonzero(recent)
    if recent_idx.size <= MAX_TIMESTAMPS_PER_INTERVAL:
        return recent_idx
    step = int(np.ceil(recent_idx.size / MAX_TIMESTAMPS_PER_INTERVAL))
    return recent_idx[::step]


def signal_vectors_for_interval(method: dict[str, Any], keep: pd.DataFrame, a1: dict[str, dict[str, Any]], interval: str) -> dict[str, np.ndarray]:
    subset = keep[keep["interval"] == interval].copy()
    if subset.empty:
        return {}
    features = sorted({f for cid in subset["candidate_id"] for f in a1[cid]["source_features"]})
    horizons = sorted(int(h) for h in subset["horizon"].unique())
    index, _, matrices = read_interval_panel(method, interval, features, horizons)
    sample_idx = choose_sample_indices(index)
    ctx = MatrixContext(matrices)
    vectors: dict[str, np.ndarray] = {}
    for _, row in subset.iterrows():
        sig = ctx.eval(row["expression"]) * float(row["train_orientation"])
        sampled = sig[sample_idx, :].reshape(-1)
        vectors[row["candidate_id"]] = normalize_vector(sampled)
    return vectors


def greedy_cluster(keep: pd.DataFrame, vectors: dict[str, np.ndarray]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = keep.copy()
    ranked["score_proxy"] = ranked.apply(score_proxy, axis=1)
    ranked = ranked.sort_values("score_proxy", ascending=False)
    clusters: list[dict[str, Any]] = []
    assignments: list[dict[str, Any]] = []
    for _, row in ranked.iterrows():
        cid = row["candidate_id"]
        vec = vectors[cid]
        best_cluster = None
        best_corr = -2.0
        for cluster in clusters:
            corr = corr_vectors(vec, vectors[cluster["representative_candidate_id"]])
            if np.isfinite(corr) and corr > best_corr:
                best_corr = corr
                best_cluster = cluster
        if best_cluster is None or best_corr < CLUSTER_CORR_THRESHOLD:
            cluster_id = f"crypto_a3_{row['interval']}_{len(clusters) + 1:03d}"
            cluster = {
                "cluster_id": cluster_id,
                "interval": row["interval"],
                "representative_candidate_id": cid,
                "representative_expression": row["expression"],
                "representative_motif": row["motif_family"],
                "representative_horizon": int(row["horizon"]),
                "representative_score_proxy": float(row["score_proxy"]),
                "member_count": 0,
                "max_member_corr_to_rep": 1.0,
            }
            clusters.append(cluster)
            best_cluster = cluster
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
                "recent_ls_annualized": row.get("recent_oos_2025H2_2026_ls_annualized"),
                "recent_turnover": row.get("recent_oos_2025H2_2026_turnover_mean"),
            }
        )
    return clusters, assignments


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    a1 = load_a1_by_id()
    a2 = pd.read_csv(A2_CSV)
    keep = a2[a2["decision"] == "KEEP_REPLAY_CANDIDATE"].copy()

    all_clusters: list[dict[str, Any]] = []
    all_assignments: list[dict[str, Any]] = []
    for interval in sorted(keep["interval"].unique()):
        vectors = signal_vectors_for_interval(method, keep, a1, interval)
        interval_keep = keep[keep["interval"] == interval].copy()
        clusters, assignments = greedy_cluster(interval_keep, vectors)
        all_clusters.extend(clusters)
        all_assignments.extend(assignments)

    clusters_df = pd.DataFrame(all_clusters)
    assignments_df = pd.DataFrame(all_assignments)
    clusters_path = RUNTIME_DIR / "crypto_a3_signal_clusters_20260519.csv"
    assignments_path = RUNTIME_DIR / "crypto_a3_candidate_cluster_assignments_20260519.csv"
    manifest_path = RUNTIME_DIR / "crypto_a3_signal_cluster_manifest_20260519.json"
    clusters_df.to_csv(clusters_path, index=False)
    assignments_df.to_csv(assignments_path, index=False)
    counts = {
        "keep_candidates": int(len(keep)),
        "signal_clusters": int(len(clusters_df)),
        "clusters_by_interval": clusters_df["interval"].value_counts().to_dict() if not clusters_df.empty else {},
        "candidate_assignments_by_interval": assignments_df["interval"].value_counts().to_dict() if not assignments_df.empty else {},
        "representative_motif_counts": clusters_df["representative_motif"].value_counts().to_dict()
        if not clusters_df.empty
        else {},
    }
    manifest = {
        "generated_at": utc_now(),
        "decision": "PASS_A3_SIGNAL_CLUSTER_REGISTRY",
        "cluster_corr_threshold": CLUSTER_CORR_THRESHOLD,
        "recent_sample_max_timestamps": MAX_TIMESTAMPS_PER_INTERVAL,
        "counts": counts,
        "clusters_path": str(clusters_path),
        "assignments_path": str(assignments_path),
        "a2_csv": str(A2_CSV),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    top_clusters = clusters_df.sort_values("representative_score_proxy", ascending=False).head(40)
    md_path = REPORT_DIR / "CRYPTO_A3_SIGNAL_CLUSTER_REGISTRY_20260519.md"
    lines = [
        "# Crypto A3 Signal Cluster Registry",
        "",
        f"- generated_at: `{manifest['generated_at']}`",
        "- decision: `PASS_A3_SIGNAL_CLUSTER_REGISTRY`",
        f"- input KEEP candidates: `{counts['keep_candidates']}`",
        f"- signal clusters: `{counts['signal_clusters']}`",
        f"- cluster corr threshold: `{CLUSTER_CORR_THRESHOLD}`",
        f"- clusters by interval: `{counts['clusters_by_interval']}`",
        "",
        "## Top Cluster Representatives",
        "",
        "| cluster | interval | members | horizon | motif | score | expression |",
        "|---|---|---:|---:|---|---:|---|",
    ]
    for _, row in top_clusters.iterrows():
        lines.append(
            f"| `{row['cluster_id']}` | `{row['interval']}` | {int(row['member_count'])} | "
            f"{int(row['representative_horizon'])} | `{row['representative_motif']}` | "
            f"{row['representative_score_proxy']:.4f} | `{row['representative_expression']}` |"
        )
    lines += [
        "",
        "## Representative Motif Counts",
        "",
    ]
    for motif, count in sorted(counts["representative_motif_counts"].items()):
        lines.append(f"- `{motif}`: {count}")
    lines += [
        "",
        "## Boundary",
        "",
        "- A3 clusters are signal-correlation clusters over recent-OOS sampled vectors.",
        "- This prevents counting many near-duplicate replay candidates as independent alpha.",
        "- This is still not production alpha proof; next step is cluster-level holdout/stress and cost-aware book construction.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A3_CLUSTERS=" + str(clusters_path))
    print("A3_REPORT=" + str(md_path))
    print("DECISION=PASS_A3_SIGNAL_CLUSTER_REGISTRY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
