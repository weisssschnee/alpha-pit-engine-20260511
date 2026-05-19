"""Build a narrow R3 liquidity-threshold sensitivity audit.

This is a paper hygiene audit. It does not change the locked X0/R3 object,
alpha formulas, cluster membership, or official threshold.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.market_regime_state import build_pit_market_regime_state_frame


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "paper" / "phase3o_automl_2026" / "generated"

DEFAULT_DATASET = ROOT.parent / "scripts" / "data" / "phase3n_stock_tdx_official_20200101_to_20260508_maxopt.parquet"
DEFAULT_DAILY_RETURNS = ROOT / "reports" / "phase3n_long_history_locked_validation_20260517" / "phase3n_daily_returns.csv"

TRAIN_START = "2025-07-01"
TRAIN_END = "2025-12-31"
OOS_START = "2026-01-01"
OOS_END = "2026-05-08"
BOOK = "candidate_book_6"
QUANTILES = [0.25, 0.30, 1 / 3, 0.35, 0.40]
RANDOM_DRAWS = 1000
RANDOM_SEED = 20260519


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return round(out, digits) if math.isfinite(out) else None


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {"days": 0, "ann_compound": None, "sharpe": None, "max_drawdown": None, "total_return": None}
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    return {
        "days": int(clean.shape[0]),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _random_p95(returns: pd.Series, window_mask: pd.Series, active_count: int) -> float | None:
    idx = np.flatnonzero(window_mask.to_numpy())
    if active_count <= 0 or len(idx) <= 0:
        return None
    active_count = min(active_count, len(idx))
    rng = np.random.default_rng(RANDOM_SEED)
    ret_np = returns.to_numpy(dtype=float)
    vals: list[float] = []
    for _ in range(RANDOM_DRAWS):
        selected = rng.choice(idx, size=active_count, replace=False)
        gated = np.zeros(len(ret_np), dtype=float)
        gated[selected] = ret_np[selected]
        ann = _metrics(pd.Series(gated[idx])).get("ann_compound")
        if ann is not None:
            vals.append(float(ann))
    return float(np.quantile(vals, 0.95)) if vals else None


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(DEFAULT_DATASET, columns=["date", "code", "close", "amount", "rt_change_pct"])
    regime = build_pit_market_regime_state_frame(panel)
    daily = pd.read_csv(DEFAULT_DAILY_RETURNS, parse_dates=["date"])
    merged = daily.merge(regime, on="date", how="left").sort_values("date").reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")

    train_mask = (merged["date"] >= TRAIN_START) & (merged["date"] <= TRAIN_END)
    oos_mask = (merged["date"] >= OOS_START) & (merged["date"] <= OOS_END)
    returns = pd.to_numeric(merged[BOOK], errors="coerce").fillna(0.0)
    liquidity = pd.to_numeric(merged["liquidity_ratio_lag1"], errors="coerce")
    train_values = liquidity[train_mask & liquidity.notna()]

    rows: list[dict[str, Any]] = []
    for q in QUANTILES:
        threshold = float(train_values.quantile(q))
        gate = liquidity <= threshold
        active = oos_mask & gate.fillna(False)
        gated_returns = returns.where(active, 0.0)
        full = _metrics(gated_returns[oos_mask])
        active_metrics = _metrics(returns[active])
        random_p95 = _random_p95(returns, oos_mask, int(active.sum()))
        true_ann = full.get("ann_compound")
        placebo_pass = true_ann is not None and random_p95 is not None and float(true_ann) > random_p95
        rows.append(
            {
                "threshold_label": "q33" if abs(q - 1 / 3) < 1e-9 else f"q{int(round(q * 100))}",
                "train_quantile": _round(q, 6),
                "threshold": _round(threshold, 10),
                "active_days": int(active.sum()),
                "calendar_days": int(oos_mask.sum()),
                "active_ratio": _round(active.sum() / oos_mask.sum() if int(oos_mask.sum()) else None),
                "full_ann_compound": full.get("ann_compound"),
                "sharpe": full.get("sharpe"),
                "max_drawdown": full.get("max_drawdown"),
                "total_return": full.get("total_return"),
                "active_ann_compound": active_metrics.get("ann_compound"),
                "random_active_days_p95_ann": _round(random_p95),
                "placebo_decision": "PASS_TRUE_GT_RANDOM_P95" if placebo_pass else "HOLD_NOT_GT_RANDOM_P95",
            }
        )

    csv_path = OUT / "r3_sensitivity_audit.csv"
    json_path = OUT / "r3_sensitivity_audit.json"
    md_path = OUT / "R3_SENSITIVITY_AUDIT.md"
    _write_csv(csv_path, rows)
    summary = {
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "experiment_id": "20260519_r3_liquidity_threshold_sensitivity",
        "decision": "PASS_R3_NEARBY_THRESHOLD_SENSITIVITY_DIAGNOSTIC",
        "scope": "paper_hygiene_no_search_no_gate_change",
        "train_window": [TRAIN_START, TRAIN_END],
        "oos_window": [OOS_START, OOS_END],
        "book": BOOK,
        "random_draws": RANDOM_DRAWS,
        "random_seed": RANDOM_SEED,
        "outputs": {
            "csv": str(csv_path.relative_to(ROOT)),
            "json": str(json_path.relative_to(ROOT)),
            "md": str(md_path.relative_to(ROOT)),
        },
        "rows": rows,
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md = [
        "# R3 Liquidity Threshold Sensitivity Audit",
        "",
        "- scope: paper hygiene diagnostic; locked R3 is unchanged.",
        f"- train window: `{TRAIN_START}` to `{TRAIN_END}`",
        f"- OOS window: `{OOS_START}` to `{OOS_END}`",
        f"- random active-day placebo draws: `{RANDOM_DRAWS}`",
        "",
        "| threshold | active ratio | full ann | sharpe | max DD | random p95 | placebo decision |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        md.append(
            f"| {row['threshold_label']} | {row['active_ratio']} | {row['full_ann_compound']} | {row['sharpe']} | {row['max_drawdown']} | {row['random_active_days_p95_ann']} | {row['placebo_decision']} |"
        )
    md.extend(
        [
            "",
            "## Boundary",
            "",
            "This table checks nearby threshold robustness. It is not permission to retune R3; the official gate remains `R3_liquidity_low_v1`.",
            "",
        ]
    )
    md_path.write_text("\n".join(md), encoding="utf-8")
    return summary


def main() -> int:
    print(json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
