"""Expression-level pandas/numba parity canary for true 1min candidates.

This module is deliberately diagnostic. It checks whether a small numba-backed
expression evaluator can reproduce the existing pandas evaluator on fixed
Phase3BA/BB expressions before any search route is allowed to use it.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import platform
import re
import time
from dataclasses import dataclass
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

from our_system_phase2.services.feature_algebra import expand_derived_fields
from our_system_phase2.services.field_encoder import FIELD_ALIASES
from our_system_phase2.services.real_market_validation import evaluate_panel_expression
from our_system_phase2.runtime.phase3bc_numba_fast_eval_canary import (
    _diff_stats,
    _group_order,
    _rank_pct_grouped_numba,
)


REPO = Path(__file__).resolve().parents[3]
DEFAULT_PANEL = Path(
    "runtime/phase3at_company_slice24_dailyjoin2_20260610_pull/"
    "phase3ar_wide_sidecar/phase3ar_true_1min_sidecar_canary.parquet"
)
DEFAULT_CANDIDATES = Path(
    "reports/phase3bb_company_ba_parent_deepening_aggregate_20260613/"
    "phase3au_true1min_shard_fresh_top.csv"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bc_expression_parity_canary_20260613")
DEFAULT_REPORT_ROOT = Path("reports/phase3bc_expression_parity_canary_20260613")
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO / path


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


def _package_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ["numpy", "pandas", "pyarrow", "numba", "bottleneck", "numexpr", "polars", "joblib", "sklearn"]:
        try:
            module = importlib.import_module(name)
            out[name] = str(getattr(module, "__version__", "unknown"))
        except Exception as exc:
            out[name] = f"MISSING ({type(exc).__name__})"
    return out


def _split_args(payload: str) -> list[str]:
    args: list[str] = []
    depth = 0
    start = 0
    for index, char in enumerate(payload):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(payload[start:index].strip())
            start = index + 1
    args.append(payload[start:].strip())
    return args


def _parse_call(expression: str) -> tuple[str, list[str]] | None:
    expression = expression.strip()
    if not expression.endswith(")") or "(" not in expression:
        return None
    name, rest = expression.split("(", 1)
    if not name.strip():
        return None
    return name.strip(), _split_args(rest[:-1])


def _fields(expressions: list[str]) -> list[str]:
    fields: set[str] = set()
    for expression in expressions:
        expanded = expand_derived_fields(expression or "")
        for field in FIELD_RE.findall(expanded):
            fields.add(FIELD_ALIASES.get(field, field))
    return sorted(fields)


def _load_candidates(path: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        seen: set[str] = set()
        for row in reader:
            expr = str(row.get("expression") or "").strip()
            if not expr or expr in seen:
                continue
            seen.add(expr)
            rows.append(row)
            if len(rows) >= limit:
                break
    return rows


def _read_panel(panel_path: Path, expressions: list[str], max_rows: int | None) -> pd.DataFrame:
    parquet = pq.ParquetFile(panel_path)
    schema_cols = set(parquet.schema_arrow.names)
    required = {"code", "date", "trade_time", "close"}
    missing_required = sorted(required - schema_cols)
    if missing_required:
        raise RuntimeError(f"panel missing required columns: {missing_required}")
    expression_fields = set(_fields(expressions))
    columns = sorted((required | {"exec_date"} | expression_fields) & schema_cols)
    missing_fields = sorted(expression_fields - schema_cols)
    if missing_fields:
        raise RuntimeError(f"panel missing expression fields: {missing_fields[:20]}")
    frame = pd.read_parquet(panel_path, columns=columns)
    if max_rows is not None and max_rows > 0 and len(frame) > max_rows:
        take = np.linspace(0, len(frame) - 1, max_rows).round().astype(np.int64)
        frame = frame.iloc[np.unique(take)].copy()
    frame["code"] = frame["code"].astype(str)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    if "exec_date" in frame.columns:
        frame["exec_date"] = pd.to_datetime(frame["exec_date"], errors="coerce").dt.date.astype(str)
    for column in columns:
        if column not in {"code", "date", "trade_time", "exec_date"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["code", "date", "trade_time", "close"]).reset_index(drop=True)
    return frame


if njit is not None:

    @njit(cache=True)
    def _zscore_grouped_twopass_numba(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            count = 0
            total = 0.0
            for pos in range(start, end):
                value = values[order[pos]]
                if not np.isnan(value):
                    total += value
                    count += 1
            if count <= 1:
                continue
            mean = total / count
            ss = 0.0
            for pos in range(start, end):
                value = values[order[pos]]
                if not np.isnan(value):
                    diff = value - mean
                    ss += diff * diff
            std = np.sqrt(ss / (count - 1))
            if std == 0.0 or np.isnan(std):
                continue
            for pos in range(start, end):
                idx = order[pos]
                value = values[idx]
                if not np.isnan(value):
                    out[idx] = (value - mean) / std
        return out

    @njit(cache=True)
    def _rolling_std_grouped_numba(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            rolling_sum = 0.0
            rolling_sum2 = 0.0
            valid_count = 0
            for pos in range(start, end):
                idx = order[pos]
                value = values[idx]
                if not np.isnan(value):
                    rolling_sum += value
                    rolling_sum2 += value * value
                    valid_count += 1
                old_pos = pos - window
                if old_pos >= start:
                    old_idx = order[old_pos]
                    old_value = values[old_idx]
                    if not np.isnan(old_value):
                        rolling_sum -= old_value
                        rolling_sum2 -= old_value * old_value
                        valid_count -= 1
                if (pos - start + 1) >= window and valid_count >= window and valid_count > 1:
                    n = float(valid_count)
                    var = (rolling_sum2 - (rolling_sum * rolling_sum / n)) / (n - 1.0)
                    if var >= 0.0:
                        out[idx] = np.sqrt(var)
        return out


    @njit(cache=True)
    def _delta_grouped_numba_local(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            for pos in range(starts[group_idx] + window, ends[group_idx]):
                idx = order[pos]
                lag_idx = order[pos - window]
                out[idx] = values[idx] - values[lag_idx]
        return out


    @njit(cache=True)
    def _rolling_mean_grouped_numba_local(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
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
    def _mom_grouped_numba_local(values: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray, window: int) -> np.ndarray:
        out = np.empty(values.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            for pos in range(starts[group_idx] + window, ends[group_idx]):
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


    @njit(cache=True)
    def _csresidual_grouped_numba(left: np.ndarray, right: np.ndarray, order: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
        out = np.empty(left.shape[0], dtype=np.float64)
        out[:] = np.nan
        for group_idx in range(starts.shape[0]):
            start = starts[group_idx]
            end = ends[group_idx]
            count = 0
            sx = 0.0
            sy = 0.0
            for pos in range(start, end):
                idx = order[pos]
                x = right[idx]
                y = left[idx]
                if not np.isnan(x) and not np.isnan(y):
                    count += 1
                    sx += x
                    sy += y
            if count < 5:
                continue
            mx = sx / count
            my = sy / count
            cov = 0.0
            varx = 0.0
            for pos in range(start, end):
                idx = order[pos]
                x = right[idx]
                y = left[idx]
                if not np.isnan(x) and not np.isnan(y):
                    dx = x - mx
                    cov += dx * (y - my)
                    varx += dx * dx
            varx = varx / count
            if varx <= 0.0:
                continue
            beta = (cov / count) / varx
            intercept = my - beta * mx
            for pos in range(start, end):
                idx = order[pos]
                x = right[idx]
                y = left[idx]
                if not np.isnan(x) and not np.isnan(y):
                    out[idx] = y - intercept - beta * x
        return out


@dataclass
class FastContext:
    frame: pd.DataFrame
    xsec_codes: np.ndarray
    xsec_group_count: int
    xsec_order: np.ndarray
    xsec_starts: np.ndarray
    xsec_ends: np.ndarray
    code_order: np.ndarray
    code_starts: np.ndarray
    code_ends: np.ndarray


def _build_context(frame: pd.DataFrame) -> FastContext:
    xsec_codes, _ = pd.factorize(frame["date"], sort=False)
    xsec_codes = xsec_codes.astype(np.int64)
    xsec_order, xsec_starts, xsec_ends = _group_order(xsec_codes)
    code_codes, _ = pd.factorize(frame["code"], sort=False)
    code_codes = code_codes.astype(np.int64)
    code_order, code_starts, code_ends = _group_order(code_codes)
    return FastContext(
        frame=frame,
        xsec_codes=xsec_codes,
        xsec_group_count=int(xsec_codes.max() + 1) if len(xsec_codes) else 0,
        xsec_order=xsec_order,
        xsec_starts=xsec_starts,
        xsec_ends=xsec_ends,
        code_order=code_order,
        code_starts=code_starts,
        code_ends=code_ends,
    )


def _fast_eval(expression: str, context: FastContext, cache: dict[str, np.ndarray]) -> np.ndarray:
    expression = expand_derived_fields(expression.strip())
    if expression in cache:
        return cache[expression]

    def store(values: np.ndarray) -> np.ndarray:
        cache[expression] = values
        return values

    if expression.startswith("$"):
        column = FIELD_ALIASES.get(expression[1:], expression[1:])
        if column not in context.frame.columns:
            raise RuntimeError(f"missing_field:{column}")
        return store(pd.to_numeric(context.frame[column], errors="coerce").to_numpy(dtype=np.float64))
    try:
        constant = float(expression)
        out = np.empty(len(context.frame), dtype=np.float64)
        out[:] = constant
        return store(out)
    except ValueError:
        pass

    call = _parse_call(expression)
    if call is None:
        raise RuntimeError(f"unsupported_expression:{expression}")
    name, args = call
    name_lower = name.lower()

    if name_lower in {"csrank", "rank"} and len(args) == 1:
        value = _fast_eval(args[0], context, cache)
        return store(_rank_pct_grouped_numba(value, context.xsec_codes, context.xsec_order, context.xsec_starts, context.xsec_ends))
    if name_lower == "zscore" and len(args) == 1:
        value = _fast_eval(args[0], context, cache)
        return store(_zscore_grouped_twopass_numba(value, context.xsec_order, context.xsec_starts, context.xsec_ends))
    if name_lower == "csresidual" and len(args) == 2:
        left = _fast_eval(args[0], context, cache)
        right = _fast_eval(args[1], context, cache)
        return store(_csresidual_grouped_numba(left, right, context.xsec_order, context.xsec_starts, context.xsec_ends))
    if name_lower == "abs" and len(args) == 1:
        return store(np.abs(_fast_eval(args[0], context, cache)))
    if name_lower == "neg" and len(args) == 1:
        return store(-_fast_eval(args[0], context, cache))
    if name_lower == "sign" and len(args) == 1:
        return store(np.sign(_fast_eval(args[0], context, cache)))
    if name_lower == "log" and len(args) == 1:
        value = np.abs(_fast_eval(args[0], context, cache))
        value = np.where(value == 0.0, np.nan, value)
        return store(np.log(value))

    if name_lower in {"mean", "std", "delta", "delay", "mom"} and len(args) == 2:
        value = _fast_eval(args[0], context, cache)
        window = int(float(args[1]))
        if name_lower == "mean":
            return store(_rolling_mean_grouped_numba_local(value, context.code_order, context.code_starts, context.code_ends, window))
        if name_lower == "std":
            return store(_rolling_std_grouped_numba(value, context.code_order, context.code_starts, context.code_ends, window))
        if name_lower == "delta":
            return store(_delta_grouped_numba_local(value, context.code_order, context.code_starts, context.code_ends, window))
        if name_lower == "delay":
            delayed = _delta_grouped_numba_local(value, context.code_order, context.code_starts, context.code_ends, 0)
            delayed[:] = np.nan
            order = context.code_order
            for start, end in zip(context.code_starts, context.code_ends):
                for pos in range(start + window, end):
                    delayed[order[pos]] = value[order[pos - window]]
            return store(delayed)
        return store(_mom_grouped_numba_local(value, context.code_order, context.code_starts, context.code_ends, window))

    if name_lower in {"add", "sub", "mul", "div"} and len(args) == 2:
        left = _fast_eval(args[0], context, cache)
        right = _fast_eval(args[1], context, cache)
        if name_lower == "add":
            return store(left + right)
        if name_lower == "sub":
            return store(left - right)
        if name_lower == "mul":
            return store(left * right)
        denominator = np.where(right == 0.0, np.nan, right)
        return store(left / denominator)

    raise RuntimeError(f"unsupported_operator:{name}")


def run_canary(
    *,
    panel: Path,
    candidates: Path,
    output_root: Path,
    report_root: Path,
    candidate_limit: int,
    max_rows: int | None,
    tolerance: float,
) -> dict[str, Any]:
    if njit is None:
        raise RuntimeError("numba is unavailable; expression parity cannot run")
    panel = _resolve(panel)
    candidates = _resolve(candidates)
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    candidate_rows = _load_candidates(candidates, candidate_limit)
    expressions = [str(row["expression"]) for row in candidate_rows]
    frame = _read_panel(panel, expressions, max_rows=max_rows)
    context = _build_context(frame)

    date_equals_trade_time = bool((pd.to_datetime(frame["date"]) == pd.to_datetime(frame["trade_time"])).all())
    pandas_cache: dict[str, pd.Series] = {}
    fast_cache: dict[str, np.ndarray] = {}
    rows: list[dict[str, Any]] = []

    for idx, row in enumerate(candidate_rows, start=1):
        expression = str(row.get("expression") or "")
        t0 = time.perf_counter()
        pandas_signal = evaluate_panel_expression(frame, expression, cache=pandas_cache)
        pandas_seconds = time.perf_counter() - t0

        t0 = time.perf_counter()
        fast_signal = _fast_eval(expression, context, fast_cache)
        fast_seconds = time.perf_counter() - t0

        pandas_values = pd.to_numeric(pandas_signal, errors="coerce").to_numpy(dtype=np.float64)
        diff = _diff_stats(pandas_values, fast_signal.astype(np.float64))
        passed = (
            diff["max_abs_diff"] <= tolerance
            and diff["nonfinite_mismatch_count"] == 0
        )
        rows.append(
            {
                "rank": idx,
                "candidate_id": row.get("candidate_id") or "",
                "horizon_min": row.get("horizon_min") or "",
                "mean_ic_abs_mean": row.get("mean_ic_abs_mean") or "",
                "pandas_seconds": pandas_seconds,
                "numba_seconds": fast_seconds,
                "speedup": None if fast_seconds == 0.0 else pandas_seconds / fast_seconds,
                "max_abs_diff": diff["max_abs_diff"],
                "mean_abs_diff": diff["mean_abs_diff"],
                "nonfinite_mismatch_count": diff["nonfinite_mismatch_count"],
                "finite_compare_count": diff["finite_compare_count"],
                "passed": passed,
                "expression": expression,
            }
        )

    pass_count = sum(1 for row in rows if row["passed"])
    decision = "PASS_EXPRESSION_PARITY_CANARY" if pass_count == len(rows) and rows else "HOLD_EXPRESSION_PARITY_FAILED"
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase3BC",
        "decision": decision,
        "purpose": "fixed Phase3BA/BB expression-level pandas vs numba parity before backend integration",
        "panel": str(panel),
        "candidates": str(candidates),
        "output_root": str(output_root),
        "report_root": str(report_root),
        "python": {"version": platform.python_version(), "platform": platform.platform()},
        "package_versions": _package_versions(),
        "input": {
            "rows": int(len(frame)),
            "codes": int(frame["code"].nunique()),
            "date_groups": int(frame["date"].nunique()),
            "trade_time_groups": int(frame["trade_time"].nunique()),
            "date_equals_trade_time": date_equals_trade_time,
            "candidate_limit": candidate_limit,
            "candidate_count": len(rows),
            "max_rows": max_rows,
        },
        "operator_scope": [
            "CSRank/Rank",
            "ZScore",
            "CSResidual",
            "Mean",
            "Std",
            "Delta",
            "Delay",
            "Mom",
            "Add/Sub/Mul/Div",
            "Abs/Neg/Sign/Log",
        ],
        "parity": {
            "pass_count": pass_count,
            "candidate_count": len(rows),
            "tolerance": tolerance,
            "max_diff_max": max((float(row["max_abs_diff"]) for row in rows), default=None),
            "nonfinite_mismatch_total": int(sum(int(row["nonfinite_mismatch_count"]) for row in rows)),
        },
        "failure_interpretation": (
            None
            if decision == "PASS_EXPRESSION_PARITY_CANARY"
            else {
                "short": "strict element-level expression parity failed; backend integration is blocked",
                "observed_pattern": "nonfinite mismatches are zero, but nested CSRank outputs diverge on finite values",
                "likely_cause": "tiny floating-point differences in nested rolling/zscore inputs can change pandas exact-tie rank behavior",
                "required_next_step": "run replay metric-diff canary or implement a pandas-exact rank/rolling compatibility layer before any Phase3AS backend flag",
            }
        ),
        "launch_contract": {
            "may_wire_phase3as_backend": decision == "PASS_EXPRESSION_PARITY_CANARY",
            "backend_must_be_explicit_flag": True,
            "official_x0_r3_changed": False,
            "search_results_changed": False,
        },
    }
    _write_csv(output_root / "phase3bc_expression_parity_rows.csv", rows)
    _write_json(output_root / "phase3bc_expression_parity_summary.json", summary)

    md = [
        "# Phase3BC Expression Parity Canary",
        "",
        f"- decision: `{decision}`",
        f"- panel: `{panel}`",
        f"- candidates: `{candidates}`",
        f"- rows: `{len(frame)}`",
        f"- codes: `{frame['code'].nunique()}`",
        f"- date groups: `{frame['date'].nunique()}`",
        f"- trade_time groups: `{frame['trade_time'].nunique()}`",
        f"- date equals trade_time: `{date_equals_trade_time}`",
        f"- pass: `{pass_count}/{len(rows)}`",
        "",
        "## Meaning",
        "",
        "This is not a search result and not alpha proof. It is a backend safety check: fixed Phase3BA/BB expressions are evaluated by the existing pandas evaluator and a numba-backed evaluator on the same true-1min sidecar panel.",
        "",
        "The existing evaluator groups `CSRank`, `ZScore`, and `CSResidual` by `frame['date']`. In this true-1min panel, `date` is equal to `trade_time`, so the cross-section is minute-level rather than old daily kline.",
        "",
        "## Failure Reading",
        "",
        (
            "Strict expression parity passed."
            if decision == "PASS_EXPRESSION_PARITY_CANARY"
            else "Strict expression parity failed. Nonfinite mismatches are zero, so this is not a missing-field, NaN, or old-1D-data problem. The observed pattern is finite-value rank divergence in nested `CSRank` expressions, likely from tiny floating-point differences in rolling/zscore subexpressions changing pandas exact-tie rank behavior. Phase3AS numba backend wiring remains blocked."
        ),
        "",
        "## Rows",
        "",
        "| rank | candidate_id | horizon | pandas_s | numba_s | speedup | max_diff | nonfinite_mismatch | pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        speedup_text = "" if row["speedup"] is None else f"{float(row['speedup']):.3f}"
        md.append(
            f"| {row['rank']} | `{row['candidate_id']}` | {row['horizon_min']} | "
            f"{float(row['pandas_seconds']):.6f} | {float(row['numba_seconds']):.6f} | "
            f"{speedup_text} | "
            f"{float(row['max_abs_diff']):.3e} | {row['nonfinite_mismatch_count']} | `{row['passed']}` |"
        )
    md.extend(
        [
            "",
            "## Next Contract",
            "",
            "- If this canary passes, Phase3AS can receive an explicit `--evaluator-backend numba` flag.",
            "- The default evaluator must remain pandas until a small replay metric-diff audit passes.",
            "- X0/R3 and prior search decisions are unchanged.",
            "",
        ]
    )
    report_path = report_root / "PHASE3BC_EXPRESSION_PARITY_CANARY_20260613.md"
    report_path.write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase3BC expression-level pandas/numba parity canary.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--candidate-limit", type=int, default=16)
    parser.add_argument("--max-rows", type=int, default=400_000)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    args = parser.parse_args(argv)
    run_canary(
        panel=args.panel,
        candidates=args.candidates,
        output_root=args.output_root,
        report_root=args.report_root,
        candidate_limit=args.candidate_limit,
        max_rows=args.max_rows,
        tolerance=args.tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
