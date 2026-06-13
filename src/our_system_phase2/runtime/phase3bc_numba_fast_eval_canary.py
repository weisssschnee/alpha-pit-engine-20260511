"""Phase3BC numba fast-evaluator canary for true 1min validation hot paths.

This module does not replace Phase3AS. It benchmarks and parity-checks the
lowest-risk kernels needed before a numba backend can be allowed into large
true-1min searches.
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

try:
    from numba import njit
except Exception:  # pragma: no cover - reported at runtime
    njit = None


REPO = Path(__file__).resolve().parents[3]
DEFAULT_PANEL = Path(
    "runtime/phase3au_full_true1min_sharded_20260611/"
    "shard_00/phase3aq_wide_true1min/canary/phase3aq_true_1min_formula_canary.parquet"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bc_numba_fast_eval_canary_20260613")
DEFAULT_REPORT_ROOT = Path("reports/phase3bc_numba_fast_eval_canary_20260613")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ["numpy", "pandas", "pyarrow", "numba", "bottleneck", "numexpr", "polars", "joblib", "sklearn"]:
        try:
            module = importlib.import_module(name)
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:
            versions[name] = f"MISSING ({type(exc).__name__})"
    return versions


if njit is not None:

    @njit(cache=True)
    def _rank_pct_grouped_numba(values: np.ndarray, group_codes: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            size = end - start
            valid_index = np.empty(size, dtype=np.int64)
            valid_value = np.empty(size, dtype=np.float64)
            count = 0
            for pos in range(start, end):
                idx = order[pos]
                value = values[idx]
                if not np.isnan(value) and group_codes[idx] >= 0:
                    valid_index[count] = idx
                    valid_value[count] = value
                    count += 1
            if count == 0:
                continue
            sort_order = np.argsort(valid_value[:count])
            tie_start = 0
            while tie_start < count:
                tie_end = tie_start + 1
                current = valid_value[sort_order[tie_start]]
                while tie_end < count and valid_value[sort_order[tie_end]] == current:
                    tie_end += 1
                avg_rank = ((tie_start + 1) + tie_end) / 2.0
                pct_rank = avg_rank / count
                for tie_pos in range(tie_start, tie_end):
                    out[valid_index[sort_order[tie_pos]]] = pct_rank
                tie_start = tie_end
        return out


    @njit(cache=True)
    def _zscore_grouped_numba(values: np.ndarray, group_codes: np.ndarray, group_count: int) -> np.ndarray:
        counts = np.zeros(group_count, dtype=np.float64)
        sums = np.zeros(group_count, dtype=np.float64)
        sums2 = np.zeros(group_count, dtype=np.float64)
        for idx in range(values.shape[0]):
            code = group_codes[idx]
            value = values[idx]
            if code >= 0 and not np.isnan(value):
                counts[code] += 1.0
                sums[code] += value
                sums2[code] += value * value

        means = np.empty(group_count, dtype=np.float64)
        stds = np.empty(group_count, dtype=np.float64)
        means[:] = np.nan
        stds[:] = np.nan
        for code in range(group_count):
            n = counts[code]
            if n <= 1.0:
                continue
            mean = sums[code] / n
            var = (sums2[code] - (sums[code] * sums[code] / n)) / (n - 1.0)
            if var <= 0.0:
                continue
            means[code] = mean
            stds[code] = np.sqrt(var)

        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for idx in range(values.shape[0]):
            code = group_codes[idx]
            value = values[idx]
            if code >= 0 and not np.isnan(value):
                std = stds[code]
                if not np.isnan(std) and std != 0.0:
                    out[idx] = (value - means[code]) / std
        return out


def _group_order(codes: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(codes, kind="mergesort")
    sorted_codes = codes[order]
    valid = sorted_codes >= 0
    order = order[valid]
    sorted_codes = sorted_codes[valid]
    if len(sorted_codes) == 0:
        return order, np.array([], dtype=np.int64), np.array([], dtype=np.int64)
    boundaries = np.flatnonzero(np.diff(sorted_codes) != 0) + 1
    starts = np.r_[0, boundaries].astype(np.int64)
    ends = np.r_[boundaries, len(sorted_codes)].astype(np.int64)
    return order.astype(np.int64), starts, ends


def _read_panel(panel_path: Path, max_rows: int | None) -> pd.DataFrame:
    parquet = pq.ParquetFile(panel_path)
    columns = [col for col in ["code", "trade_time", "close", "amount", "vwap"] if col in parquet.schema_arrow.names]
    if {"code", "trade_time", "close"} - set(columns):
        raise RuntimeError(f"panel missing required columns: {sorted({'code', 'trade_time', 'close'} - set(columns))}")
    frame = pd.read_parquet(panel_path, columns=columns)
    if max_rows is not None and max_rows > 0 and len(frame) > max_rows:
        # Use an evenly spaced sample across the full true-1min shard. Taking
        # head() would cover only the earliest codes because the shard is
        # sorted by code/trade_time, which is not a cross-section canary.
        take = np.linspace(0, len(frame) - 1, max_rows).round().astype(np.int64)
        take = np.unique(take)
        frame = frame.iloc[take].copy()
    frame["code"] = frame["code"].astype(str)
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if "amount" in frame.columns:
        value_col = "amount"
    elif "vwap" in frame.columns:
        value_col = "vwap"
    else:
        value_col = "close"
    frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
    frame = frame.dropna(subset=["code", "trade_time", "close"]).reset_index(drop=True)
    return frame, value_col


def _benchmark_once(frame: pd.DataFrame, value_col: str, *, compile_only: bool = False) -> dict[str, Any]:
    values = pd.to_numeric(frame[value_col], errors="coerce").to_numpy(dtype=np.float64)
    group_codes, groups = pd.factorize(frame["trade_time"], sort=False)
    group_codes = group_codes.astype(np.int64)
    group_count = int(len(groups))
    order, starts, ends = _group_order(group_codes)

    t0 = time.perf_counter()
    pandas_rank = pd.Series(values).groupby(frame["trade_time"], sort=False).rank(pct=True).to_numpy(dtype=np.float64)
    pandas_rank_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    pandas_mean = pd.Series(values).groupby(frame["trade_time"], sort=False).transform("mean")
    pandas_std = pd.Series(values).groupby(frame["trade_time"], sort=False).transform("std").replace(0, np.nan)
    pandas_z = ((pd.Series(values) - pandas_mean) / pandas_std).to_numpy(dtype=np.float64)
    pandas_z_seconds = time.perf_counter() - t0

    if njit is None:
        return {
            "numba_available": False,
            "pandas_rank_seconds": pandas_rank_seconds,
            "pandas_zscore_seconds": pandas_z_seconds,
        }

    t0 = time.perf_counter()
    numba_rank = _rank_pct_grouped_numba(values, group_codes, order, starts, ends)
    numba_rank_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    numba_z = _zscore_grouped_numba(values, group_codes, group_count)
    numba_z_seconds = time.perf_counter() - t0

    valid_rank = np.isfinite(pandas_rank) | np.isfinite(numba_rank)
    valid_z = np.isfinite(pandas_z) | np.isfinite(numba_z)
    rank_diff = np.abs(pandas_rank[valid_rank] - numba_rank[valid_rank]) if np.any(valid_rank) else np.array([0.0])
    z_diff = np.abs(pandas_z[valid_z] - numba_z[valid_z]) if np.any(valid_z) else np.array([0.0])

    return {
        "numba_available": True,
        "compile_included": compile_only,
        "row_count": int(len(frame)),
        "group_count": group_count,
        "value_col": value_col,
        "pandas_rank_seconds": pandas_rank_seconds,
        "numba_rank_seconds": numba_rank_seconds,
        "rank_speedup": None if numba_rank_seconds == 0 else pandas_rank_seconds / numba_rank_seconds,
        "rank_max_abs_diff": float(np.nanmax(rank_diff)) if len(rank_diff) else 0.0,
        "rank_mean_abs_diff": float(np.nanmean(rank_diff)) if len(rank_diff) else 0.0,
        "pandas_zscore_seconds": pandas_z_seconds,
        "numba_zscore_seconds": numba_z_seconds,
        "zscore_speedup": None if numba_z_seconds == 0 else pandas_z_seconds / numba_z_seconds,
        "zscore_max_abs_diff": float(np.nanmax(z_diff)) if len(z_diff) else 0.0,
        "zscore_mean_abs_diff": float(np.nanmean(z_diff)) if len(z_diff) else 0.0,
    }


def run_canary(*, panel: Path, output_root: Path, report_root: Path, max_rows: int | None) -> dict[str, Any]:
    panel = _resolve(panel)
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    frame, value_col = _read_panel(panel, max_rows=max_rows)
    if frame.empty:
        raise RuntimeError("Phase3BC panel is empty")

    compile_run = _benchmark_once(frame, value_col, compile_only=True)
    warm_run = _benchmark_once(frame, value_col, compile_only=False)

    rank_pass = bool(warm_run.get("numba_available")) and float(warm_run.get("rank_max_abs_diff") or 0.0) <= 1e-12
    z_pass = bool(warm_run.get("numba_available")) and float(warm_run.get("zscore_max_abs_diff") or 0.0) <= 1e-9
    decision = "PASS_NUMBA_KERNEL_PARITY_CANARY" if rank_pass and z_pass else "HOLD_NUMBA_KERNEL_PARITY_FAILED"

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "phase": "Phase3BC",
        "purpose": "numba fast evaluator canary for true 1min rank/zscore hot paths",
        "panel": str(panel),
        "output_root": str(output_root),
        "report_root": str(report_root),
        "python": {
            "executable_note": "current process",
            "version": platform.python_version(),
            "platform": platform.platform(),
        },
        "package_versions": _package_versions(),
        "hot_path_scan": {
            "current_phase3as_hot_path": [
                "evaluate_panel_expression uses pandas groupby/rank/rolling operators",
                "Phase3AS _rank_by_group uses pandas groupby(...).rank(pct=True)",
                "IC/spread aggregation already uses numpy bincount",
            ],
            "numba_scope_this_canary": ["CSRank-compatible grouped pct rank", "ZScore-compatible grouped transform"],
            "not_changed": ["Phase3AS official evaluator route", "X0/R3", "candidate selection", "label alignment"],
        },
        "input": {
            "rows": int(len(frame)),
            "codes": int(frame["code"].nunique()),
            "trade_time_groups": int(frame["trade_time"].nunique()),
            "value_col": value_col,
            "max_rows": max_rows,
        },
        "compile_run": compile_run,
        "warm_run": warm_run,
        "parity": {
            "rank_pass": rank_pass,
            "rank_tolerance": 1e-12,
            "zscore_pass": z_pass,
            "zscore_tolerance": 1e-9,
        },
        "launch_contract": {
            "may_replace_phase3as": False,
            "required_before_large_search": [
                "extend numba backend to rolling Mean/Delta/Mom",
                "candidate-expression parity on same expression set",
                "same panel and same horizons before/after metric diff",
            ],
            "safe_worker_limit_before_backend": "prefer 1-2 heavy pandas workers per machine",
            "safe_worker_limit_after_backend": "not decided until expression parity benchmark",
        },
    }
    _write_json(output_root / "phase3bc_numba_fast_eval_canary_summary.json", summary)

    md = [
        "# Phase3BC Numba Fast Evaluator Canary",
        "",
        f"- decision: `{decision}`",
        f"- panel: `{panel}`",
        f"- rows: `{len(frame)}`",
        f"- codes: `{frame['code'].nunique()}`",
        f"- trade_time groups: `{frame['trade_time'].nunique()}`",
        f"- value column: `{value_col}`",
        "",
        "## Package Matrix",
        "",
        *[f"- `{name}`: `{version}`" for name, version in summary["package_versions"].items()],
        "",
        "## Warm Benchmark",
        "",
        f"- pandas rank seconds: `{warm_run.get('pandas_rank_seconds')}`",
        f"- numba rank seconds: `{warm_run.get('numba_rank_seconds')}`",
        f"- rank speedup: `{warm_run.get('rank_speedup')}`",
        f"- rank max abs diff: `{warm_run.get('rank_max_abs_diff')}`",
        f"- pandas zscore seconds: `{warm_run.get('pandas_zscore_seconds')}`",
        f"- numba zscore seconds: `{warm_run.get('numba_zscore_seconds')}`",
        f"- zscore speedup: `{warm_run.get('zscore_speedup')}`",
        f"- zscore max abs diff: `{warm_run.get('zscore_max_abs_diff')}`",
        "",
        "## Audit Reading",
        "",
        "The current true 1min evaluator is pandas-heavy in expression evaluation and grouped rank/zscore. "
        "This canary validates the first low-risk numba kernels only. It does not change Phase3AS behavior.",
        "",
        "Next allowed step: add rolling `Mean/Delta/Mom` kernels and run expression-level parity on a fixed candidate pack.",
        "",
    ]
    report_path = report_root / "PHASE3BC_NUMBA_FAST_EVAL_CANARY_20260613.md"
    report_path.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase3BC numba fast evaluator canary.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--max-rows", type=int, default=500_000)
    args = parser.parse_args(argv)
    run_canary(panel=args.panel, output_root=args.output_root, report_root=args.report_root, max_rows=args.max_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
