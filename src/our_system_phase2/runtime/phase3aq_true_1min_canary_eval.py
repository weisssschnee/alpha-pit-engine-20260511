"""Evaluate Phase3AQ sanitized formulas on a true 1min canary panel.

This is a minute-level smoke/replay, not a promotion proof. Labels are future
1min-bar returns computed from `trade_time` rows by code.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_validation import evaluate_panel_expression


REPO = Path(__file__).resolve().parents[3]
DEFAULT_PANEL = Path(
    "runtime/phase3aq_true_1min_formula_adapter_20260610/canary/"
    "phase3aq_true_1min_formula_canary.parquet"
)
DEFAULT_PACK_ROOT = Path("runtime/phase3aq_formula_packs_sanitized_20260610")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3aq_true_1min_canary_eval_20260610")
DEFAULT_HORIZONS = (1, 5, 15, 30)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_rows(pack_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack_name, lane in (
        ("phase3aq_direct_1min_formula_pack.json", "direct_1min"),
        ("phase3aq_opening_window_1min_formula_pack.json", "opening_window_1min"),
    ):
        payload = _read_json(pack_root / pack_name)
        for row in payload.get("candidate_rows") or []:
            out = dict(row)
            out["phase3aq_eval_lane"] = lane
            rows.append(out)
    return rows


def _future_returns(frame: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    close = pd.to_numeric(frame["close"], errors="coerce")
    grouped = close.groupby(frame["code"], sort=False)
    labels = pd.DataFrame(index=frame.index)
    for horizon in horizons:
        labels[f"fwd_ret_{horizon}m"] = grouped.shift(-horizon) / close.replace(0, np.nan) - 1.0
    return labels


def _rank_by_time(values: pd.Series, dates: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").groupby(dates, sort=False).rank(pct=True)


def _mean_ic_from_ranks(
    signal_rank: pd.Series,
    label_rank: pd.Series,
    time_codes: np.ndarray,
    *,
    group_count: int,
    min_obs: int,
) -> dict[str, Any]:
    x = pd.to_numeric(signal_rank, errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(label_rank, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & (time_codes >= 0)
    if not np.any(valid):
        return {"ic_mean": None, "ic_std": None, "ic_t": None, "ic_count": 0}
    codes = time_codes[valid]
    xv = x[valid]
    yv = y[valid]
    n = np.bincount(codes, minlength=group_count).astype(float)
    sx = np.bincount(codes, weights=xv, minlength=group_count)
    sy = np.bincount(codes, weights=yv, minlength=group_count)
    sxy = np.bincount(codes, weights=xv * yv, minlength=group_count)
    sx2 = np.bincount(codes, weights=xv * xv, minlength=group_count)
    sy2 = np.bincount(codes, weights=yv * yv, minlength=group_count)
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy - (sx * sy / n)
        var_x = sx2 - (sx * sx / n)
        var_y = sy2 - (sy * sy / n)
        corr = cov / np.sqrt(var_x * var_y)
    valid_corr = (n >= min_obs) & np.isfinite(corr)
    arr = corr[valid_corr].astype(float)
    if len(arr) == 0:
        return {"ic_mean": None, "ic_std": None, "ic_t": None, "ic_count": 0}
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    return {
        "ic_mean": float(arr.mean()),
        "ic_std": std,
        "ic_t": None if std == 0.0 else float(arr.mean() / (std / np.sqrt(len(arr)))),
        "ic_count": int(len(arr)),
    }


def _top_bottom_spread_from_rank(
    signal_rank: pd.Series,
    label: pd.Series,
    time_codes: np.ndarray,
    *,
    group_count: int,
    min_obs: int,
) -> dict[str, Any]:
    rank = pd.to_numeric(signal_rank, errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(label, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(rank) & np.isfinite(y) & (time_codes >= 0)
    if not np.any(valid):
        return {"spread_mean": None, "spread_t": None, "spread_count": 0, "spread_hit_rate": None}
    codes = time_codes[valid]
    rankv = rank[valid]
    yv = y[valid]
    counts = np.bincount(codes, minlength=group_count).astype(float)
    top_mask = rankv >= 0.8
    bottom_mask = rankv <= 0.2
    top_n = np.bincount(codes[top_mask], minlength=group_count).astype(float)
    bot_n = np.bincount(codes[bottom_mask], minlength=group_count).astype(float)
    top_sum = np.bincount(codes[top_mask], weights=yv[top_mask], minlength=group_count)
    bot_sum = np.bincount(codes[bottom_mask], weights=yv[bottom_mask], minlength=group_count)
    with np.errstate(invalid="ignore", divide="ignore"):
        spreads = (top_sum / top_n) - (bot_sum / bot_n)
    valid_spread = (counts >= min_obs) & (top_n > 0) & (bot_n > 0) & np.isfinite(spreads)
    arr = spreads[valid_spread].astype(float)
    if len(arr) == 0:
        return {"spread_mean": None, "spread_t": None, "spread_count": 0, "spread_hit_rate": None}
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    return {
        "spread_mean": float(arr.mean()),
        "spread_t": None if std == 0.0 else float(arr.mean() / (std / np.sqrt(len(arr)))),
        "spread_count": int(len(arr)),
        "spread_hit_rate": float(np.mean(arr > 0.0)),
    }


def evaluate(
    *,
    panel_path: Path,
    pack_root: Path,
    output_root: Path,
    horizons: tuple[int, ...],
    min_obs_per_time: int,
    sample_trade_times: int | None,
) -> dict[str, Any]:
    panel_path = _resolve(panel_path)
    pack_root = _resolve(pack_root)
    output_root = _resolve(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(pack_root)
    frame = pd.read_parquet(panel_path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame = frame.dropna(subset=["date", "trade_time", "code", "close"]).sort_values(["code", "trade_time"]).reset_index(drop=True)
    original_trade_time_count = int(frame["trade_time"].nunique())
    if sample_trade_times is not None and sample_trade_times > 0 and original_trade_time_count > sample_trade_times:
        unique_times = pd.Series(frame["trade_time"].dropna().unique()).sort_values(ignore_index=True)
        positions = np.linspace(0, len(unique_times) - 1, sample_trade_times).round().astype(int)
        sampled_times = set(pd.to_datetime(unique_times.iloc[positions]).tolist())
        frame = frame[frame["trade_time"].isin(sampled_times)].copy().reset_index(drop=True)
    labels = _future_returns(frame, horizons)
    time_codes, unique_times = pd.factorize(frame["date"], sort=False)
    group_count = int(len(unique_times))
    label_ranks = {
        horizon: _rank_by_time(labels[f"fwd_ret_{horizon}m"], frame["date"])
        for horizon in horizons
    }

    result_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        expression = str(row.get("expression") or "")
        try:
            signal = pd.to_numeric(evaluate_panel_expression(frame, expression), errors="coerce")
        except Exception as exc:
            errors.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "expression": expression,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
            continue
        base = {
            "rank": index,
            "candidate_id": row.get("candidate_id") or "",
            "lane": row.get("phase3aq_eval_lane") or "",
            "factor_lane": row.get("factor_lane") or "",
            "source_lane": row.get("source_lane") or "",
            "search_memory_key": row.get("search_memory_key") or "",
            "expression": expression,
            "signal_nonnull": int(signal.notna().sum()),
            "signal_unique": int(signal.nunique(dropna=True)),
        }
        signal_rank = _rank_by_time(signal, frame["date"])
        for horizon in horizons:
            label = labels[f"fwd_ret_{horizon}m"]
            ic = _mean_ic_from_ranks(
                signal_rank,
                label_ranks[horizon],
                time_codes,
                group_count=group_count,
                min_obs=min_obs_per_time,
            )
            spread = _top_bottom_spread_from_rank(
                signal_rank,
                label,
                time_codes,
                group_count=group_count,
                min_obs=min_obs_per_time,
            )
            out = dict(base)
            out["horizon_min"] = horizon
            out.update(ic)
            out.update(spread)
            result_rows.append(out)

    result_rows.sort(
        key=lambda item: (
            -999.0 if item.get("ic_mean") is None else -float(item["ic_mean"]),
            -int(item.get("ic_count") or 0),
        )
    )
    _write_csv(output_root / "phase3aq_true_1min_canary_eval_rows.csv", result_rows)
    _write_csv(output_root / "phase3aq_true_1min_canary_eval_errors.csv", errors)
    top_by_horizon: dict[str, list[dict[str, Any]]] = {}
    for horizon in horizons:
        subset = [row for row in result_rows if int(row["horizon_min"]) == horizon and row.get("ic_mean") is not None]
        subset.sort(key=lambda item: float(item["ic_mean"]), reverse=True)
        top_by_horizon[str(horizon)] = subset[:20]
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AQ_TRUE_1MIN_CANARY_EVAL_COMPLETE",
        "panel_path": str(panel_path),
        "pack_root": str(pack_root),
        "output_root": str(output_root),
        "panel_rows": int(len(frame)),
        "code_count": int(frame["code"].nunique()),
        "trade_time_count": int(frame["trade_time"].nunique()),
        "original_trade_time_count": original_trade_time_count,
        "sample_trade_times": sample_trade_times,
        "candidate_count": len(rows),
        "evaluated_candidate_count": len(rows) - len(errors),
        "error_count": len(errors),
        "horizons_min": list(horizons),
        "min_obs_per_time": min_obs_per_time,
        "top_by_horizon": top_by_horizon,
        "notes": [
            "This is a true trade_time 1min canary eval, not daily replay.",
            "Small-code canary IC is pipeline evidence only; not promotion proof.",
            "If sample_trade_times is set, this is a sampled-time canary eval, not full-minute evaluation.",
            "All source data fields not in the 97-pack remain preserved for sidecar/event lanes.",
        ],
    }
    _write_json(output_root / "phase3aq_true_1min_canary_eval_summary.json", summary)
    lines = [
        "# Phase3AQ True 1min Canary Eval",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Scope",
        "",
        f"- panel rows: `{summary['panel_rows']}`",
        f"- codes: `{summary['code_count']}`",
        f"- trade_time_count: `{summary['trade_time_count']}`",
        f"- candidates: `{summary['candidate_count']}`",
        f"- errors: `{summary['error_count']}`",
        "",
        "## Top IC By Horizon",
        "",
    ]
    for horizon in horizons:
        lines.append(f"### {horizon}m")
        for item in top_by_horizon[str(horizon)][:5]:
            lines.append(
                f"- `{item['candidate_id']}` ic={item['ic_mean']:.6g} spread={item['spread_mean']:.6g} expr=`{item['expression']}`"
            )
        lines.append("")
    (output_root / "PHASE3AQ_TRUE_1MIN_CANARY_EVAL_20260610.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=4)
    parser.add_argument(
        "--sample-trade-times",
        type=int,
        default=2400,
        help="Evaluate all formulas on an evenly sampled set of trade_time cross-sections. Use 0 for full panel.",
    )
    args = parser.parse_args()
    horizons = tuple(int(item.strip()) for item in args.horizons.split(",") if item.strip())
    summary = evaluate(
        panel_path=args.panel,
        pack_root=args.pack_root,
        output_root=args.output_root,
        horizons=horizons,
        min_obs_per_time=args.min_obs_per_time,
        sample_trade_times=None if args.sample_trade_times == 0 else args.sample_trade_times,
    )
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "panel_rows": summary["panel_rows"],
                "candidate_count": summary["candidate_count"],
                "evaluated_candidate_count": summary["evaluated_candidate_count"],
                "error_count": summary["error_count"],
                "output_root": summary["output_root"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
