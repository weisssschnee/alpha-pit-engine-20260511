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


    @njit(cache=True)
    def _rolling_mean_grouped_numba(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            rolling_sum = 0.0
            valid_count = 0
            for pos in range(start, end):
                idx = order[pos]
                value = values[idx]
                if not np.isnan(value):
                    rolling_sum += value
                    valid_count += 1
                old_pos = pos - window
                if old_pos >= start:
                    old_idx = order[old_pos]
                    old_value = values[old_idx]
                    if not np.isnan(old_value):
                        rolling_sum -= old_value
                        valid_count -= 1
                if (pos - start + 1) >= window and valid_count >= window:
                    out[idx] = rolling_sum / window
        return out


    @njit(cache=True)
    def _delta_grouped_numba(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            for pos in range(start + window, end):
                idx = order[pos]
                lag_idx = order[pos - window]
                out[idx] = values[idx] - values[lag_idx]
        return out


    @njit(cache=True)
    def _mom_grouped_numba(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            for pos in range(start + window, end):
                idx = order[pos]
                lag_idx = order[pos - window]
                current = values[idx]
                lagged = values[lag_idx]
                if np.isnan(current) or np.isnan(lagged):
                    out[idx] = np.nan
                elif lagged == 0.0:
                    if current == 0.0:
                        out[idx] = np.nan
                    elif current > 0.0:
                        out[idx] = np.inf
                    else:
                        out[idx] = -np.inf
                else:
                    out[idx] = current / lagged - 1.0
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


def _diff_stats(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    both_nan = np.isnan(left) & np.isnan(right)
    both_pos_inf = np.isposinf(left) & np.isposinf(right)
    both_neg_inf = np.isneginf(left) & np.isneginf(right)
    comparable = ~(both_nan | both_pos_inf | both_neg_inf)
    mismatch = comparable & ((np.isnan(left) != np.isnan(right)) | (np.isposinf(left) != np.isposinf(right)) | (np.isneginf(left) != np.isneginf(right)))
    finite = comparable & np.isfinite(left) & np.isfinite(right)
    diffs = np.abs(left[finite] - right[finite]) if np.any(finite) else np.array([0.0])
    return {
        "max_abs_diff": float(np.nanmax(diffs)) if len(diffs) else 0.0,
        "mean_abs_diff": float(np.nanmean(diffs)) if len(diffs) else 0.0,
        "nonfinite_mismatch_count": int(np.sum(mismatch)),
        "finite_compare_count": int(np.sum(finite)),
    }


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
    code_codes, code_groups = pd.factorize(frame["code"], sort=False)
    code_codes = code_codes.astype(np.int64)
    code_order, code_starts, code_ends = _group_order(code_codes)
    rolling_window = 30

    t0 = time.perf_counter()
    pandas_rank = pd.Series(values).groupby(frame["trade_time"], sort=False).rank(pct=True).to_numpy(dtype=np.float64)
    pandas_rank_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    pandas_mean = pd.Series(values).groupby(frame["trade_time"], sort=False).transform("mean")
    pandas_std = pd.Series(values).groupby(frame["trade_time"], sort=False).transform("std").replace(0, np.nan)
    pandas_z = ((pd.Series(values) - pandas_mean) / pandas_std).to_numpy(dtype=np.float64)
    pandas_z_seconds = time.perf_counter() - t0

    value_series = pd.Series(values)
    value_by_code = value_series.groupby(frame["code"], sort=False)
    t0 = time.perf_counter()
    pandas_mean_code = value_by_code.transform(lambda item: item.rolling(rolling_window, min_periods=rolling_window).mean()).to_numpy(dtype=np.float64)
    pandas_mean_code_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    pandas_delta_code = (value_series - value_by_code.shift(rolling_window)).to_numpy(dtype=np.float64)
    pandas_delta_code_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    pandas_mom_code = (value_series / value_by_code.shift(rolling_window) - 1.0).to_numpy(dtype=np.float64)
    pandas_mom_code_seconds = time.perf_counter() - t0

    if njit is None:
        return {
            "numba_available": False,
            "pandas_rank_seconds": pandas_rank_seconds,
            "pandas_zscore_seconds": pandas_z_seconds,
            "pandas_rolling_mean_seconds": pandas_mean_code_seconds,
            "pandas_delta_seconds": pandas_delta_code_seconds,
            "pandas_mom_seconds": pandas_mom_code_seconds,
        }

    t0 = time.perf_counter()
    numba_rank = _rank_pct_grouped_numba(values, group_codes, order, starts, ends)
    numba_rank_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    numba_z = _zscore_grouped_numba(values, group_codes, group_count)
    numba_z_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    numba_mean_code = _rolling_mean_grouped_numba(values, code_order, code_starts, code_ends, rolling_window)
    numba_mean_code_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    numba_delta_code = _delta_grouped_numba(values, code_order, code_starts, code_ends, rolling_window)
    numba_delta_code_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    numba_mom_code = _mom_grouped_numba(values, code_order, code_starts, code_ends, rolling_window)
    numba_mom_code_seconds = time.perf_counter() - t0

    rank_diff = _diff_stats(pandas_rank, numba_rank)
    z_diff = _diff_stats(pandas_z, numba_z)
    mean_diff = _diff_stats(pandas_mean_code, numba_mean_code)
    delta_diff = _diff_stats(pandas_delta_code, numba_delta_code)
    mom_diff = _diff_stats(pandas_mom_code, numba_mom_code)

    return {
        "numba_available": True,
        "compile_included": compile_only,
        "row_count": int(len(frame)),
        "group_count": group_count,
        "code_group_count": int(len(code_groups)),
        "rolling_window": rolling_window,
        "value_col": value_col,
        "pandas_rank_seconds": pandas_rank_seconds,
        "numba_rank_seconds": numba_rank_seconds,
        "rank_speedup": None if numba_rank_seconds == 0 else pandas_rank_seconds / numba_rank_seconds,
        "rank_max_abs_diff": rank_diff["max_abs_diff"],
        "rank_mean_abs_diff": rank_diff["mean_abs_diff"],
        "rank_nonfinite_mismatch_count": rank_diff["nonfinite_mismatch_count"],
        "pandas_zscore_seconds": pandas_z_seconds,
        "numba_zscore_seconds": numba_z_seconds,
        "zscore_speedup": None if numba_z_seconds == 0 else pandas_z_seconds / numba_z_seconds,
        "zscore_max_abs_diff": z_diff["max_abs_diff"],
        "zscore_mean_abs_diff": z_diff["mean_abs_diff"],
        "zscore_nonfinite_mismatch_count": z_diff["nonfinite_mismatch_count"],
        "pandas_rolling_mean_seconds": pandas_mean_code_seconds,
        "numba_rolling_mean_seconds": numba_mean_code_seconds,
        "rolling_mean_speedup": None if numba_mean_code_seconds == 0 else pandas_mean_code_seconds / numba_mean_code_seconds,
        "rolling_mean_max_abs_diff": mean_diff["max_abs_diff"],
        "rolling_mean_mean_abs_diff": mean_diff["mean_abs_diff"],
        "rolling_mean_nonfinite_mismatch_count": mean_diff["nonfinite_mismatch_count"],
        "pandas_delta_seconds": pandas_delta_code_seconds,
        "numba_delta_seconds": numba_delta_code_seconds,
        "delta_speedup": None if numba_delta_code_seconds == 0 else pandas_delta_code_seconds / numba_delta_code_seconds,
        "delta_max_abs_diff": delta_diff["max_abs_diff"],
        "delta_mean_abs_diff": delta_diff["mean_abs_diff"],
        "delta_nonfinite_mismatch_count": delta_diff["nonfinite_mismatch_count"],
        "pandas_mom_seconds": pandas_mom_code_seconds,
        "numba_mom_seconds": numba_mom_code_seconds,
        "mom_speedup": None if numba_mom_code_seconds == 0 else pandas_mom_code_seconds / numba_mom_code_seconds,
        "mom_max_abs_diff": mom_diff["max_abs_diff"],
        "mom_mean_abs_diff": mom_diff["mean_abs_diff"],
        "mom_nonfinite_mismatch_count": mom_diff["nonfinite_mismatch_count"],
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

    rank_pass = (
        bool(warm_run.get("numba_available"))
        and float(warm_run.get("rank_max_abs_diff") or 0.0) <= 1e-12
        and int(warm_run.get("rank_nonfinite_mismatch_count") or 0) == 0
    )
    z_pass = (
        bool(warm_run.get("numba_available"))
        and float(warm_run.get("zscore_max_abs_diff") or 0.0) <= 1e-9
        and int(warm_run.get("zscore_nonfinite_mismatch_count") or 0) == 0
    )
    rolling_mean_pass = (
        bool(warm_run.get("numba_available"))
        and float(warm_run.get("rolling_mean_max_abs_diff") or 0.0) <= 1e-9
        and int(warm_run.get("rolling_mean_nonfinite_mismatch_count") or 0) == 0
    )
    delta_pass = (
        bool(warm_run.get("numba_available"))
        and float(warm_run.get("delta_max_abs_diff") or 0.0) <= 1e-12
        and int(warm_run.get("delta_nonfinite_mismatch_count") or 0) == 0
    )
    mom_pass = (
        bool(warm_run.get("numba_available"))
        and float(warm_run.get("mom_max_abs_diff") or 0.0) <= 1e-12
        and int(warm_run.get("mom_nonfinite_mismatch_count") or 0) == 0
    )
    decision = (
        "PASS_NUMBA_KERNEL_PARITY_CANARY"
        if rank_pass and z_pass and rolling_mean_pass and delta_pass and mom_pass
        else "HOLD_NUMBA_KERNEL_PARITY_FAILED"
    )

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
            "numba_scope_this_canary": [
                "CSRank-compatible grouped pct rank",
                "ZScore-compatible grouped transform",
                "Mean-compatible rolling mean by code",
                "Delta-compatible shift difference by code",
                "Mom-compatible pct-change by code",
            ],
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
            "rolling_mean_pass": rolling_mean_pass,
            "rolling_mean_tolerance": 1e-9,
            "delta_pass": delta_pass,
            "delta_tolerance": 1e-12,
            "mom_pass": mom_pass,
            "mom_tolerance": 1e-12,
        },
        "launch_contract": {
            "may_replace_phase3as": False,
            "required_before_large_search": [
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
        f"- pandas rolling mean seconds: `{warm_run.get('pandas_rolling_mean_seconds')}`",
        f"- numba rolling mean seconds: `{warm_run.get('numba_rolling_mean_seconds')}`",
        f"- rolling mean speedup: `{warm_run.get('rolling_mean_speedup')}`",
        f"- rolling mean max abs diff: `{warm_run.get('rolling_mean_max_abs_diff')}`",
        f"- pandas delta seconds: `{warm_run.get('pandas_delta_seconds')}`",
        f"- numba delta seconds: `{warm_run.get('numba_delta_seconds')}`",
        f"- delta speedup: `{warm_run.get('delta_speedup')}`",
        f"- delta max abs diff: `{warm_run.get('delta_max_abs_diff')}`",
        f"- pandas mom seconds: `{warm_run.get('pandas_mom_seconds')}`",
        f"- numba mom seconds: `{warm_run.get('numba_mom_seconds')}`",
        f"- mom speedup: `{warm_run.get('mom_speedup')}`",
        f"- mom max abs diff: `{warm_run.get('mom_max_abs_diff')}`",
        "",
        "## Audit Reading",
        "",
        "The current true 1min evaluator is pandas-heavy in expression evaluation and grouped rank/zscore/rolling operators. "
        "This canary validates low-risk numba kernels for the most common grouped and rolling operators. It does not change Phase3AS behavior.",
        "",
        "Next allowed step: run expression-level parity on a fixed candidate pack, then wire the numba backend behind an explicit evaluator flag.",
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
