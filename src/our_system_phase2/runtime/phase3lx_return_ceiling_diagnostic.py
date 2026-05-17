"""Return-ceiling diagnostics for frozen Phase3L cluster variants.

All outputs are diagnostic. The oracle combo remains excluded from formal proof
and production selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_DAILY_RETURNS = Path("reports/phase3n_long_history_locked_validation_20260517/phase3n_daily_returns.csv")
DEFAULT_OUTPUT_ROOT = Path("reports/phase3lx_return_ceiling_diagnostic_20260517")
RECENT_START = "2025-07-01"
RECENT_END = "2026-05-08"
WF_START = "2025-07-01"
WF_END = "2026-05-08"

VARIANTS = {
    "X0_official_6": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_002", "cluster_004"],
    "X1_research_9": [
        "cluster_001",
        "cluster_005",
        "cluster_008",
        "cluster_006",
        "cluster_009",
        "cluster_003",
        "cluster_002",
        "cluster_007",
        "cluster_004",
    ],
    "X2_official_6_plus_003": [
        "cluster_001",
        "cluster_005",
        "cluster_006",
        "cluster_009",
        "cluster_002",
        "cluster_004",
        "cluster_003",
    ],
    "X3_official_6_minus_002": ["cluster_001", "cluster_005", "cluster_006", "cluster_009", "cluster_004"],
    "X4_official_6_plus_003_minus_002": [
        "cluster_001",
        "cluster_005",
        "cluster_006",
        "cluster_009",
        "cluster_004",
        "cluster_003",
    ],
    "X5_oracle_005_003_004_diagnostic": ["cluster_005", "cluster_003", "cluster_004"],
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> float | None:
    value = _safe_float(value)
    return round(value, digits) if value is not None else None


def _max_drawdown(values: pd.Series) -> float | None:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None
    curve = (1.0 + clean).cumprod()
    return float((curve / curve.cummax() - 1.0).min())


def _metrics(values: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "days": 0,
            "mean_daily": None,
            "ann_simple": None,
            "ann_compound": None,
            "sharpe": None,
            "sortino": None,
            "hit_rate": None,
            "max_drawdown": None,
            "total_return": None,
        }
    mean = float(clean.mean())
    std = float(clean.std(ddof=0))
    downside = clean[clean < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    return {
        "days": int(clean.shape[0]),
        "mean_daily": _round(mean, 8),
        "ann_simple": _round(mean * 252.0),
        "ann_compound": _round((1.0 + mean) ** 252 - 1.0 if mean > -1.0 else None),
        "sharpe": _round(mean / std * math.sqrt(252.0) if std > 1e-12 else None),
        "sortino": _round(mean / downside_std * math.sqrt(252.0) if downside_std > 1e-12 else None),
        "hit_rate": _round((clean > 0.0).mean()),
        "max_drawdown": _round(_max_drawdown(clean), 8),
        "total_return": _round(float((1.0 + clean).prod() - 1.0)),
    }


def _equal_variant_returns(frame: pd.DataFrame, clusters: list[str]) -> pd.Series:
    return frame[clusters].mean(axis=1, skipna=True)


def _walk_forward_returns(
    frame: pd.DataFrame,
    clusters: list[str],
    *,
    lookback: int,
    rebalance: int,
    max_weight: float,
    shrink: float,
) -> tuple[pd.Series, pd.DataFrame]:
    returns = frame[clusters].copy()
    out = pd.Series(index=returns.index, dtype=float)
    weight_rows: list[dict[str, Any]] = []
    if len(returns) <= lookback:
        return out.dropna(), pd.DataFrame(weight_rows)
    weights = pd.Series(1.0 / len(clusters), index=clusters)
    for pos in range(lookback, len(returns)):
        if (pos - lookback) % rebalance == 0:
            hist = returns.iloc[pos - lookback : pos]
            scores = hist.mean() / hist.std(ddof=0).replace(0.0, np.nan)
            scores = scores.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
            if float(scores.sum()) <= 1e-12:
                raw = pd.Series(1.0 / len(clusters), index=clusters)
            else:
                raw = scores / scores.sum()
            raw = raw.clip(upper=max_weight)
            raw = raw / raw.sum() if float(raw.sum()) > 1e-12 else pd.Series(1.0 / len(clusters), index=clusters)
            equal = pd.Series(1.0 / len(clusters), index=clusters)
            weights = shrink * equal + (1.0 - shrink) * raw
            weights = weights / weights.sum()
            weight_rows.append(
                {
                    "date": frame.index[pos].date().isoformat(),
                    "lookback": lookback,
                    "rebalance": rebalance,
                    "max_weight": max_weight,
                    "shrink_to_equal": shrink,
                    "max_weight_realized": _round(weights.max()),
                    "weights": json.dumps({cluster: _round(weights[cluster]) for cluster in clusters}, sort_keys=True),
                }
            )
        out.iloc[pos] = float((returns.iloc[pos] * weights).sum())
    return out.dropna(), pd.DataFrame(weight_rows)


def run(*, daily_returns_path: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(daily_returns_path, parse_dates=["date"]).sort_values("date").set_index("date")
    recent = frame[(frame.index >= RECENT_START) & (frame.index <= RECENT_END)]
    variant_rows: list[dict[str, Any]] = []
    wf_rows: list[dict[str, Any]] = []
    weight_rows_all: list[dict[str, Any]] = []

    for variant, clusters in VARIANTS.items():
        series = _equal_variant_returns(recent, clusters)
        row = {
            "variant": variant,
            "clusters": "|".join(clusters),
            "cluster_count": len(clusters),
            "diagnostic_only": variant.startswith("X5"),
        }
        row.update(_metrics(series))
        variant_rows.append(row)

    wf_frame = frame[(frame.index >= WF_START) & (frame.index <= WF_END)]
    for variant, clusters in VARIANTS.items():
        if variant.startswith("X5"):
            continue
        for lookback in [60, 90, 120]:
            if len(wf_frame) <= lookback + 5:
                continue
            series, weights = _walk_forward_returns(
                wf_frame,
                clusters,
                lookback=lookback,
                rebalance=20,
                max_weight=0.30,
                shrink=0.50,
            )
            row = {
                "variant": variant,
                "clusters": "|".join(clusters),
                "lookback": lookback,
                "rebalance": 20,
                "max_weight": 0.30,
                "shrink_to_equal": 0.50,
            }
            row.update(_metrics(series))
            wf_rows.append(row)
            if not weights.empty:
                weights = weights.copy()
                weights["variant"] = variant
                weight_rows_all.extend(weights.to_dict(orient="records"))

    _write_csv(output_root / "phase3lx_cluster_variant_metrics.csv", variant_rows)
    _write_csv(output_root / "phase3lx_walk_forward_weighting_metrics.csv", wf_rows)
    _write_csv(output_root / "phase3lx_walk_forward_weights.csv", weight_rows_all)

    best_variant = max(variant_rows, key=lambda row: _safe_float(row.get("ann_compound")) or -999.0)
    best_wf = max(wf_rows, key=lambda row: _safe_float(row.get("ann_compound")) or -999.0) if wf_rows else None
    summary = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3lx_return_ceiling_diagnostic",
        "decision": "PASS_RETURN_CEILING_DIAGNOSTIC_COMPLETED",
        "scope": "diagnostic_cluster_variants_and_walk_forward_weights_no_formal_promotion",
        "recent_window": [RECENT_START, RECENT_END],
        "daily_returns_path": str(daily_returns_path),
        "best_equal_weight_variant": best_variant,
        "best_walk_forward_variant": best_wf,
        "not_allowed_as_formal_proof": ["X5_oracle_005_003_004_diagnostic"],
        "outputs": {
            "variant_metrics_csv": str(output_root / "phase3lx_cluster_variant_metrics.csv"),
            "walk_forward_metrics_csv": str(output_root / "phase3lx_walk_forward_weighting_metrics.csv"),
            "walk_forward_weights_csv": str(output_root / "phase3lx_walk_forward_weights.csv"),
            "summary_json": str(output_root / "phase3lx_return_ceiling_diagnostic.json"),
            "summary_md": str(output_root / "PHASE3LX_RETURN_CEILING_DIAGNOSTIC_2026-05-17.md"),
        },
    }
    _write_json(output_root / "phase3lx_return_ceiling_diagnostic.json", summary)

    md = [
        "# Phase3LX Return Ceiling Diagnostic",
        "",
        "- decision: `PASS_RETURN_CEILING_DIAGNOSTIC_COMPLETED`",
        f"- window: `{RECENT_START}` to `{RECENT_END}`",
        "- oracle combo remains diagnostic only.",
        "",
        "## Equal-Weight Variants",
        "",
        "| variant | clusters | ann | sharpe | sortino | max dd | total return | diagnostic only |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(variant_rows, key=lambda item: _safe_float(item.get("ann_compound")) or -999.0, reverse=True):
        md.append(
            f"| {row['variant']} | {row['cluster_count']} | {row.get('ann_compound')} | {row.get('sharpe')} | {row.get('sortino')} | {row.get('max_drawdown')} | {row.get('total_return')} | {row.get('diagnostic_only')} |"
        )
    md.extend(
        [
            "",
            "## Walk-Forward Weighting",
            "",
            "| variant | lookback | ann | sharpe | sortino | max dd | total return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(wf_rows, key=lambda item: _safe_float(item.get("ann_compound")) or -999.0, reverse=True):
        md.append(
            f"| {row['variant']} | {row['lookback']} | {row.get('ann_compound')} | {row.get('sharpe')} | {row.get('sortino')} | {row.get('max_drawdown')} | {row.get('total_return')} |"
        )
    md.extend(
        [
            "",
            "## Boundaries",
            "",
            "- X5 is a theoretical ceiling reference and cannot be promoted.",
            "- Walk-forward weights use only past returns in the lookback window, with 30% max cluster weight and 50% shrinkage to equal weight.",
            "- This is still daily proxy evidence, not execution proof.",
            "",
        ]
    )
    (output_root / "PHASE3LX_RETURN_CEILING_DIAGNOSTIC_2026-05-17.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-returns", type=Path, default=DEFAULT_DAILY_RETURNS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(daily_returns_path=args.daily_returns, output_root=args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
