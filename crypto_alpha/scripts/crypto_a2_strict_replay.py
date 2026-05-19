from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
METHOD_PATH = WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"
A1_JSONL = WORKSPACE / "runtime" / "a1_generator_dry_run" / "crypto_a1_candidates_20260519.jsonl"
RUNTIME_DIR = WORKSPACE / "runtime" / "a2_strict_replay"
REPORT_DIR = WORKSPACE / "reports"

SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
}

ANNUALIZATION = {
    "5m": {1: 365 * 24 * 12, 3: (365 * 24 * 12) / 3, 6: (365 * 24 * 12) / 6, 12: (365 * 24 * 12) / 12},
    "1h": {1: 365 * 24, 3: (365 * 24) / 3, 6: (365 * 24) / 6, 12: (365 * 24) / 12},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_method() -> dict[str, Any]:
    return json.loads(METHOD_PATH.read_text(encoding="utf-8"))


def load_candidates() -> list[dict[str, Any]]:
    out = []
    with A1_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def split_args(arg: str) -> list[str]:
    args: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(arg):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(arg[start:i].strip())
            start = i + 1
    args.append(arg[start:].strip())
    return args


def row_rank(mat: np.ndarray) -> np.ndarray:
    df = pd.DataFrame(mat)
    return df.rank(axis=1, pct=True).to_numpy(dtype=float)


def row_zscore(mat: np.ndarray) -> np.ndarray:
    mean = np.nanmean(mat, axis=1, keepdims=True)
    std = np.nanstd(mat, axis=1, keepdims=True)
    std[std == 0] = np.nan
    return (mat - mean) / std


class MatrixContext:
    def __init__(self, matrices: dict[str, np.ndarray]):
        self.matrices = matrices
        self.rank_cache: dict[str, np.ndarray] = {}
        self.z_cache: dict[str, np.ndarray] = {}
        self.expr_cache: dict[str, np.ndarray] = {}

    def eval(self, expr: str) -> np.ndarray:
        expr = expr.strip()
        if expr in self.expr_cache:
            return self.expr_cache[expr]
        if expr.startswith("Rank(") and expr.endswith(")"):
            inner = expr[5:-1].strip()
            if inner not in self.rank_cache:
                self.rank_cache[inner] = row_rank(self.matrices[inner])
            out = self.rank_cache[inner]
        elif expr.startswith("ZScore(") and expr.endswith(")"):
            inner = expr[7:-1].strip()
            if inner not in self.z_cache:
                self.z_cache[inner] = row_zscore(self.matrices[inner])
            out = self.z_cache[inner]
        elif expr.startswith("Mul(") and expr.endswith(")"):
            a, b = split_args(expr[4:-1])
            out = self.eval(a) * self.eval(b)
        else:
            out = self.matrices[expr]
        self.expr_cache[expr] = out
        return out


def row_corr(signal: np.ndarray, target: np.ndarray) -> np.ndarray:
    s_rank = row_rank(signal)
    y_rank = row_rank(target)
    valid = np.isfinite(s_rank) & np.isfinite(y_rank)
    n = valid.sum(axis=1).astype(float)
    x = np.where(valid, s_rank, 0.0)
    y = np.where(valid, y_rank, 0.0)
    sx = x.sum(axis=1)
    sy = y.sum(axis=1)
    sxy = (x * y).sum(axis=1)
    sx2 = (x * x).sum(axis=1)
    sy2 = (y * y).sum(axis=1)
    numerator = n * sxy - sx * sy
    denominator = np.sqrt((n * sx2 - sx * sx) * (n * sy2 - sy * sy))
    out = numerator / denominator
    out[(n < 8) | ~np.isfinite(out)] = np.nan
    return out


def long_short(signal: np.ndarray, target: np.ndarray, orientation: float) -> tuple[np.ndarray, np.ndarray]:
    oriented = signal * orientation
    valid = np.isfinite(oriented) & np.isfinite(target)
    n = valid.sum(axis=1)
    top_score = np.where(valid, oriented, -np.inf)
    bottom_score = np.where(valid, oriented, np.inf)
    top_idx = np.argpartition(-top_score, kth=2, axis=1)[:, :3]
    bottom_idx = np.argpartition(bottom_score, kth=2, axis=1)[:, :3]
    y_top = np.take_along_axis(target, top_idx, axis=1)
    y_bottom = np.take_along_axis(target, bottom_idx, axis=1)
    ls = np.nanmean(y_top, axis=1) - np.nanmean(y_bottom, axis=1)
    ls[n < 8] = np.nan

    top_mask = np.zeros_like(valid, dtype=np.int8)
    bottom_mask = np.zeros_like(valid, dtype=np.int8)
    rows = np.arange(valid.shape[0])[:, None]
    top_mask[rows, top_idx] = 1
    bottom_mask[rows, bottom_idx] = -1
    pos_mask = top_mask + bottom_mask
    pos_mask[n < 8, :] = 0
    turnover = np.full(valid.shape[0], np.nan)
    diffs = np.abs(np.diff(pos_mask, axis=0)).sum(axis=1) / 6.0
    turnover[1:] = diffs
    return ls, turnover


def summarize_vector(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"n": 0, "mean": None, "std": None, "positive_rate": None}
    return {
        "n": int(clean.size),
        "mean": float(np.mean(clean)),
        "std": float(np.std(clean, ddof=1)) if clean.size > 1 else None,
        "positive_rate": float(np.mean(clean > 0)),
    }


def split_mask(index: pd.DatetimeIndex, start: str, end: str) -> np.ndarray:
    return np.asarray((index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end)))


def read_interval_panel(method: dict[str, Any], interval: str, features: list[str], horizons: list[int]) -> tuple[pd.DatetimeIndex, list[str], dict[str, np.ndarray]]:
    path = Path(method["data_inputs"]["gold_panels"][interval])
    cols = ["timestamp", "symbol"] + sorted(set(features)) + [f"fwd_ret_{h}" for h in horizons]
    df = pd.read_parquet(path, columns=cols)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    symbols = sorted(df["symbol"].unique().tolist())
    index = pd.DatetimeIndex(sorted(df["timestamp"].unique()))
    matrices: dict[str, np.ndarray] = {}
    for col in sorted(set(features + [f"fwd_ret_{h}" for h in horizons])):
        pivot = df.pivot(index="timestamp", columns="symbol", values=col).reindex(index=index, columns=symbols)
        matrices[col] = pivot.to_numpy(dtype=float)
    return index, symbols, matrices


def evaluate_interval(method: dict[str, Any], candidates: list[dict[str, Any]], interval: str) -> list[dict[str, Any]]:
    interval_candidates = [c for c in candidates if c["interval"] == interval and c["decision"] == "A1_DRY_RUN_CANDIDATE"]
    if not interval_candidates:
        return []
    features = sorted({f for c in interval_candidates for f in c["source_features"]})
    horizons = sorted({int(c["horizon"]) for c in interval_candidates})
    index, symbols, matrices = read_interval_panel(method, interval, features, horizons)
    ctx = MatrixContext(matrices)
    masks = {name: split_mask(index, start, end) for name, (start, end) in SPLITS.items()}

    rows: list[dict[str, Any]] = []
    for i, cand in enumerate(interval_candidates, start=1):
        expr = cand["expression"]
        horizon = int(cand["horizon"])
        signal = ctx.eval(expr)
        target = matrices[f"fwd_ret_{horizon}"]
        train_ic_vec = row_corr(signal[masks["train_2024"]], target[masks["train_2024"]])
        train_ic_summary = summarize_vector(train_ic_vec)
        train_mean_ic = train_ic_summary["mean"]
        orientation = 1.0 if train_mean_ic is None or train_mean_ic >= 0 else -1.0

        result: dict[str, Any] = {
            "candidate_id": cand["candidate_id"],
            "interval": interval,
            "horizon": horizon,
            "motif_family": cand["motif_family"],
            "priority": cand["priority"],
            "expression": expr,
            "feature_families": cand["feature_families"],
            "source_features": cand["source_features"],
            "train_orientation": orientation,
            "symbols": symbols,
        }
        hard_blockers: list[str] = []
        if any(f.startswith("fwd_ret_") for f in cand["source_features"]):
            hard_blockers.append("label_feature_used")
        if any("positioning" in f for f in cand["source_features"]):
            hard_blockers.append("positioning_historical_used")

        for split_name, mask in masks.items():
            ic_vec = row_corr(signal[mask], target[mask]) * orientation
            ls_vec, turnover_vec = long_short(signal[mask], target[mask], orientation)
            ann = ANNUALIZATION[interval][horizon]
            ic_summary = summarize_vector(ic_vec)
            ls_summary = summarize_vector(ls_vec)
            turnover_summary = summarize_vector(turnover_vec)
            ls_std = ls_summary["std"]
            result[f"{split_name}_n_dates"] = ls_summary["n"]
            result[f"{split_name}_mean_ic"] = ic_summary["mean"]
            result[f"{split_name}_icir"] = (
                None
                if ic_summary["std"] in (None, 0)
                else float(ic_summary["mean"] / ic_summary["std"])
                if ic_summary["mean"] is not None
                else None
            )
            result[f"{split_name}_ic_positive_rate"] = ic_summary["positive_rate"]
            result[f"{split_name}_ls_mean"] = ls_summary["mean"]
            result[f"{split_name}_ls_annualized"] = None if ls_summary["mean"] is None else float(ls_summary["mean"] * ann)
            result[f"{split_name}_ls_sharpe_proxy"] = (
                None
                if ls_std in (None, 0) or ls_summary["mean"] is None
                else float(ls_summary["mean"] / ls_std * math.sqrt(ann))
            )
            result[f"{split_name}_ls_hit_rate"] = ls_summary["positive_rate"]
            result[f"{split_name}_turnover_mean"] = turnover_summary["mean"]

        min_dates = method["reward_policy"]["minimum_keep_conditions"]["minimum_effective_dates"][interval]
        if result["validation_2025H1_n_dates"] < min_dates or result["recent_oos_2025H2_2026_n_dates"] < min_dates:
            hard_blockers.append("insufficient_effective_dates")
        if hard_blockers:
            decision = "REJECT_LEAKAGE" if any("used" in b or "label" in b for b in hard_blockers) else "HOLD_RESEARCH"
        elif (
            (result["validation_2025H1_mean_ic"] or 0) > 0
            and (result["recent_oos_2025H2_2026_mean_ic"] or 0) > 0
            and (result["validation_2025H1_ls_annualized"] or -999) > 0
            and (result["recent_oos_2025H2_2026_ls_annualized"] or -999) > 0
        ):
            decision = "KEEP_REPLAY_CANDIDATE"
        else:
            decision = "HOLD_RESEARCH"
        result["hard_blockers"] = hard_blockers
        result["decision"] = decision
        rows.append(result)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="A2 strict replay for crypto A1 candidates.")
    parser.add_argument("--intervals", default="1h,5m", help="Comma-separated intervals.")
    args = parser.parse_args()
    intervals = [p.strip() for p in args.intervals.split(",") if p.strip()]

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    method = load_method()
    candidates = load_candidates()
    all_rows: list[dict[str, Any]] = []
    started = utc_now()
    for interval in intervals:
        all_rows.extend(evaluate_interval(method, candidates, interval))
    df = pd.DataFrame(all_rows)
    csv_path = RUNTIME_DIR / "crypto_a2_strict_replay_20260519.csv"
    json_path = RUNTIME_DIR / "crypto_a2_strict_replay_20260519.json"
    md_path = REPORT_DIR / "CRYPTO_A2_STRICT_REPLAY_20260519.md"
    df.to_csv(csv_path, index=False)

    counts = {
        "total": int(len(df)),
        "by_decision": df["decision"].value_counts().to_dict() if not df.empty else {},
        "by_interval": df.groupby(["interval", "decision"]).size().to_dict() if not df.empty else {},
        "by_motif": df.groupby(["motif_family", "decision"]).size().to_dict() if not df.empty else {},
    }
    out = {
        "started_at": started,
        "finished_at": utc_now(),
        "decision": "PASS_A2_STRICT_REPLAY",
        "counts": {k: (str(v) if isinstance(v, dict) and any(isinstance(kk, tuple) for kk in v.keys()) else v) for k, v in counts.items()},
        "csv_path": str(csv_path),
        "method_path": str(METHOD_PATH),
        "a1_jsonl": str(A1_JSONL),
    }
    json_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    keep = df[df["decision"] == "KEEP_REPLAY_CANDIDATE"].copy()
    if not keep.empty:
        keep["score_proxy"] = (
            keep["validation_2025H1_mean_ic"].fillna(0) * 0.25
            + keep["recent_oos_2025H2_2026_mean_ic"].fillna(0) * 0.35
            + np.tanh(keep["recent_oos_2025H2_2026_ls_sharpe_proxy"].fillna(0) / 3.0) * 0.25
            + np.tanh(keep["validation_2025H1_ls_sharpe_proxy"].fillna(0) / 3.0) * 0.15
        )
        keep = keep.sort_values("score_proxy", ascending=False)
    lines = [
        "# Crypto A2 Strict Replay",
        "",
        f"- started_at: `{started}`",
        f"- finished_at: `{out['finished_at']}`",
        "- decision: `PASS_A2_STRICT_REPLAY`",
        f"- candidates evaluated: `{len(df)}`",
        f"- counts by decision: `{counts['by_decision']}`",
        f"- output csv: `{csv_path}`",
        "",
        "## Top KEEP Candidates",
        "",
        "| interval | horizon | motif | expression | val IC | recent IC | val LS ann | recent LS ann | turnover recent | score proxy |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    if keep.empty:
        lines.append("| n/a |  |  |  |  |  |  |  |  |  |")
    else:
        for _, row in keep.head(40).iterrows():
            lines.append(
                f"| `{row['interval']}` | {int(row['horizon'])} | `{row['motif_family']}` | `{row['expression']}` | "
                f"{row['validation_2025H1_mean_ic']:.4f} | {row['recent_oos_2025H2_2026_mean_ic']:.4f} | "
                f"{row['validation_2025H1_ls_annualized']:.4f} | {row['recent_oos_2025H2_2026_ls_annualized']:.4f} | "
                f"{row['recent_oos_2025H2_2026_turnover_mean']:.4f} | {row['score_proxy']:.4f} |"
            )
    lines += [
        "",
        "## Decision Counts By Motif",
        "",
        "| motif | HOLD_RESEARCH | KEEP_REPLAY_CANDIDATE |",
        "|---|---:|---:|",
    ]
    motif_counts = df.groupby(["motif_family", "decision"]).size().unstack(fill_value=0) if not df.empty else pd.DataFrame()
    for motif, row in motif_counts.iterrows():
        lines.append(
            f"| `{motif}` | {int(row.get('HOLD_RESEARCH', 0))} | {int(row.get('KEEP_REPLAY_CANDIDATE', 0))} |"
        )
    lines += [
        "",
        "## Bias / Scope Notes",
        "",
        "- Candidate direction is selected only from the train window.",
        "- Validation and recent-OOS use fixed train orientation.",
        "- No recent-only positioning fields are evaluated.",
        "- `fwd_ret_*` columns are labels only.",
        "- This is strict replay for A1 candidates, not cluster-level alpha proof.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("A2_CSV=" + str(csv_path))
    print("A2_REPORT=" + str(md_path))
    print("DECISION=PASS_A2_STRICT_REPLAY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
