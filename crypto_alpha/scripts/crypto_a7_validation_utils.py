from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from crypto_a2_6_tradable_replay import (  # noqa: E402
    forward_funding_cost,
    funding_event_rate,
    load_method,
    next_open_return,
    read_interval_panel,
)
from crypto_a2_strict_replay import MatrixContext, split_args  # noqa: E402


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
REPORT_DIR = WORKSPACE / "reports"
RUNTIME_DIR = WORKSPACE / "runtime"
LOCKED_CORE4 = WORKSPACE / "runtime" / "baselines" / "crypto_core4_locked_research_book_v1.json"
METHOD_FILE = WORKSPACE / "config" / "crypto_alphafactory_method_v1.json"

HOURS_PER_YEAR = 365 * 24
CORE4_FEATURES = [
    "ret_12",
    "latest_known_funding_rate",
    "mark_index_ratio",
    "mark_minus_index",
    "funding_rate_persistence_3",
    "hl_range",
]
SPLITS = {
    "train_2024": ("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"),
    "validation_2025H1": ("2025-01-01T00:00:00Z", "2025-06-30T23:59:59Z"),
    "recent_oos_2025H2_2026Apr": ("2025-07-01T00:00:00Z", "2026-04-30T23:59:59Z"),
    "fresh_forward_2026May": ("2026-05-01T00:00:00Z", None),
}
PURGE_EMBARGO_BARS = 24
COST_BPS = {"normal_5bp": 5.0, "stress_10bp": 10.0, "severe_20bp": 20.0}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    cluster_id: str
    expression: str
    horizon: int
    family: str


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def stable_hash(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    read = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            if max_bytes is not None and read + len(chunk) > max_bytes:
                chunk = chunk[: max_bytes - read]
            h.update(chunk)
            read += len(chunk)
            if max_bytes is not None and read >= max_bytes:
                break
    return h.hexdigest()


def load_core4_specs() -> list[CandidateSpec]:
    obj = json.loads(LOCKED_CORE4.read_text(encoding="utf-8"))
    return [
        CandidateSpec(
            candidate_id=c["candidate_id"],
            cluster_id=c["cluster_id"],
            expression=c["representative_expression"],
            horizon=int(c["horizon"]),
            family=c["motif_family"],
        )
        for c in obj["clusters"]
    ]


def extract_features(expr: str) -> list[str]:
    return [f for f in CORE4_FEATURES if f in expr]


def row_rank(mat: np.ndarray) -> np.ndarray:
    return pd.DataFrame(mat).rank(axis=1, pct=True).to_numpy(dtype=float)


def row_ic(signal: np.ndarray, target: np.ndarray) -> np.ndarray:
    s = row_rank(signal)
    t = row_rank(target)
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
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (n * sxy - sx * sy) / den
    out[(n < 8) | ~np.isfinite(out)] = np.nan
    return out


def split_mask(index: pd.DatetimeIndex, split_name: str, purge_embargo_bars: int = PURGE_EMBARGO_BARS) -> np.ndarray:
    start, end = SPLITS[split_name]
    base = np.asarray(index >= pd.Timestamp(start))
    if end is not None:
        base &= np.asarray(index <= pd.Timestamp(end))
    pos = np.where(base)[0]
    if purge_embargo_bars <= 0 or pos.size == 0:
        return base
    keep = base.copy()
    head = pos[: min(purge_embargo_bars, pos.size)]
    tail = pos[max(0, pos.size - purge_embargo_bars) :]
    keep[head] = False
    keep[tail] = False
    return keep


def load_core4_context(extra_features: list[str] | None = None) -> tuple[pd.DatetimeIndex, list[str], dict[str, np.ndarray], MatrixContext]:
    method = load_method()
    features = sorted(set(CORE4_FEATURES + (extra_features or [])))
    index, symbols, matrices = read_interval_panel(method, "1h", features)
    return index, symbols, matrices, MatrixContext(matrices)


def position_matrix(signal: np.ndarray, target: np.ndarray, orientation: float, symbols_to_keep: np.ndarray | None = None) -> np.ndarray:
    oriented = signal * orientation
    valid = np.isfinite(oriented) & np.isfinite(target)
    if symbols_to_keep is not None:
        valid &= symbols_to_keep[None, :]
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


def return_components(pos: np.ndarray, gross_target: np.ndarray, funding_cost: np.ndarray, cost_bps: float) -> dict[str, np.ndarray]:
    gross = np.nansum(pos * gross_target, axis=1)
    funding_drag = np.nansum(np.where(pos > 0, pos * funding_cost, 0.0), axis=1)
    prev = np.vstack([np.zeros((1, pos.shape[1])), pos[:-1, :]])
    turnover = np.nansum(np.abs(pos - prev), axis=1) / 2.0
    fee_drag = turnover * (cost_bps / 10000.0)
    net = gross - funding_drag - fee_drag
    return {
        "gross_return": gross,
        "funding_drag": funding_drag,
        "turnover": turnover,
        "fee_drag": fee_drag,
        "net_return": net,
        "gross_exposure": np.nansum(np.abs(pos), axis=1),
        "net_exposure": np.nansum(pos, axis=1),
    }


def orient_signal(index: pd.DatetimeIndex, signal: np.ndarray, target: np.ndarray) -> tuple[float, float | None]:
    mask = split_mask(index, "train_2024")
    ic = row_ic(signal[mask], target[mask])
    mean_ic = clean_float(np.nanmean(ic))
    return (1.0 if mean_ic is None or mean_ic >= 0 else -1.0), mean_ic


def eval_expression(
    *,
    index: pd.DatetimeIndex,
    matrices: dict[str, np.ndarray],
    ctx: MatrixContext,
    expression: str,
    horizon: int,
    cost_bps: float,
    forced_signal: np.ndarray | None = None,
    forced_orientation: float | None = None,
    symbols_to_keep: np.ndarray | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    signal = forced_signal if forced_signal is not None else ctx.eval(expression)
    gross_target = next_open_return(matrices["open"], horizon)
    funding_cost = forward_funding_cost(funding_event_rate(matrices), horizon)
    target = gross_target - funding_cost
    orientation, train_ic_mean = orient_signal(index, signal, target)
    if forced_orientation is not None:
        orientation = forced_orientation
    pos = position_matrix(signal, target, orientation, symbols_to_keep=symbols_to_keep)
    comp = return_components(pos, gross_target, funding_cost, cost_bps)
    frame = pd.DataFrame({"timestamp": index, **comp})
    meta = {"orientation": orientation, "train_ic_mean": train_ic_mean, "horizon": horizon}
    return frame, meta


def evaluate_core4_book(
    *,
    index: pd.DatetimeIndex,
    matrices: dict[str, np.ndarray],
    ctx: MatrixContext,
    specs: list[CandidateSpec],
    cost_bps: float,
    symbols_to_keep: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    meta_rows = []
    for spec in specs:
        frame, meta = eval_expression(
            index=index,
            matrices=matrices,
            ctx=ctx,
            expression=spec.expression,
            horizon=spec.horizon,
            cost_bps=cost_bps,
            symbols_to_keep=symbols_to_keep,
        )
        frame["cluster_id"] = spec.cluster_id
        frames.append(frame)
        meta_rows.append({"cluster_id": spec.cluster_id, "expression": spec.expression, **meta})
    components = pd.concat(frames, ignore_index=True)
    book = pd.DataFrame({"timestamp": index})
    for col in ["gross_return", "funding_drag", "turnover", "fee_drag", "net_return", "gross_exposure", "net_exposure"]:
        p = components.pivot(index="timestamp", columns="cluster_id", values=col)
        book[col] = p.mean(axis=1, skipna=True).to_numpy(dtype=float)
    book = book.rename(columns={"net_return": "book_net_return"})
    return book, pd.DataFrame(meta_rows)


def additive_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return None
    pnl = np.cumsum(clean)
    peak = np.maximum.accumulate(pnl)
    return clean_float(np.min(pnl - peak))


def compounded_drawdown(values: np.ndarray) -> float | None:
    clean = values[np.isfinite(values)]
    if clean.size == 0 or np.any(clean <= -1.0):
        return None
    equity = np.cumprod(1.0 + clean)
    peak = np.maximum.accumulate(equity)
    return clean_float(np.min(equity / peak - 1.0))


def summarize_returns(values: np.ndarray) -> dict[str, Any]:
    clean = values[np.isfinite(values)]
    if clean.size == 0:
        return {"n": 0}
    mean = float(np.mean(clean))
    std = float(np.std(clean, ddof=1)) if clean.size > 1 else None
    downside = clean[clean < 0]
    downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else None
    return {
        "n": int(clean.size),
        "mean_hour": mean,
        "annualized_mean": mean * HOURS_PER_YEAR,
        "std_hour": std,
        "sharpe_proxy": None if not std else mean / std * math.sqrt(HOURS_PER_YEAR),
        "sortino_proxy": None if not downside_std else mean / downside_std * math.sqrt(HOURS_PER_YEAR),
        "hit_rate": float(np.mean(clean > 0)),
        "additive_total": float(np.sum(clean)),
        "additive_max_dd": additive_drawdown(clean),
        "compounded_total": clean_float(np.prod(1.0 + clean) - 1.0) if np.all(clean > -1.0) else None,
        "compounded_max_dd": compounded_drawdown(clean),
        "min_hour": float(np.min(clean)),
        "q01": float(np.quantile(clean, 0.01)),
        "q05": float(np.quantile(clean, 0.05)),
        "median": float(np.quantile(clean, 0.50)),
        "q95": float(np.quantile(clean, 0.95)),
    }


def summarize_by_split(frame: pd.DataFrame, value_col: str, prefix: dict[str, Any] | None = None) -> pd.DataFrame:
    ts = pd.to_datetime(frame["timestamp"], utc=True)
    rows = []
    for split_name in SPLITS:
        mask = split_mask(pd.DatetimeIndex(ts), split_name)
        st = summarize_returns(frame.loc[mask, value_col].to_numpy(dtype=float))
        row = dict(prefix or {})
        row["split"] = split_name
        row.update(st)
        if "turnover" in frame.columns:
            row["mean_turnover"] = clean_float(frame.loc[mask, "turnover"].mean())
        if "gross_exposure" in frame.columns:
            row["mean_gross_exposure"] = clean_float(frame.loc[mask, "gross_exposure"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def monthly_pass_rate(frame: pd.DataFrame, value_col: str, split_name: str) -> dict[str, Any]:
    ts = pd.to_datetime(frame["timestamp"], utc=True)
    mask = split_mask(pd.DatetimeIndex(ts), split_name)
    part = pd.DataFrame({"timestamp": ts[mask], "value": frame.loc[mask, value_col].to_numpy(dtype=float)})
    part = part[np.isfinite(part["value"])]
    if part.empty:
        return {"month_count": 0, "positive_month_count": 0, "positive_month_rate": None, "worst_month_sum": None}
    monthly = part.groupby(part["timestamp"].dt.strftime("%Y-%m"))["value"].sum()
    return {
        "month_count": int(len(monthly)),
        "positive_month_count": int((monthly > 0).sum()),
        "positive_month_rate": float((monthly > 0).mean()),
        "worst_month_sum": clean_float(monthly.min()),
    }


def expression_components(expr: str) -> list[str]:
    expr = expr.strip()
    if expr.startswith("Mul(") and expr.endswith(")"):
        return split_args(expr[4:-1])
    return [expr]
