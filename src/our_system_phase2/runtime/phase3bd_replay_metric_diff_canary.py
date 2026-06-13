"""Phase3BD replay metric-diff canary for pandas vs numba-hybrid signals.

Phase3BC showed that strict element-level expression parity can fail because
nested CSRank expressions are sensitive to tiny floating-point differences.
This diagnostic checks the next question: whether those differences change the
actual Phase3AS replay metrics enough to block any optional backend work.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.runtime.phase3as_true_1min_sidecar_canary_eval import (
    _future_returns,
    _mean_ic_from_ranks,
    _rank_by_group,
    _top_bottom_spread_from_rank,
)
from our_system_phase2.runtime.phase3bc_expression_parity_canary import (
    DEFAULT_CANDIDATES,
    DEFAULT_PANEL,
    _build_context,
    _fast_eval,
    _load_candidates,
    _package_versions,
    _read_panel,
    _resolve,
    _write_csv,
    _write_json,
)
from our_system_phase2.services.real_market_validation import evaluate_panel_expression


DEFAULT_OUTPUT_ROOT = Path("runtime/phase3bd_replay_metric_diff_canary_20260613")
DEFAULT_REPORT_ROOT = Path("reports/phase3bd_replay_metric_diff_canary_20260613")
DEFAULT_HORIZONS = (1, 5, 15, 30)
METRIC_COLUMNS = ("ic_mean", "ic_abs_mean", "spread_mean", "spread_abs_mean", "spread_hit_rate")


def _parse_horizons(raw: str) -> tuple[int, ...]:
    out = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not out:
        raise ValueError("at least one horizon is required")
    return out


def _metric_rows(
    *,
    frame: pd.DataFrame,
    candidate_rows: list[dict[str, Any]],
    backend: str,
    horizons: tuple[int, ...],
    min_obs_per_time: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    group_codes, unique_times = pd.factorize(frame["trade_time"], sort=False)
    group_count = int(len(unique_times))
    labels = _future_returns(frame, horizons)
    label_ranks = {
        horizon: _rank_by_group(labels[f"fwd_ret_{horizon}m"], frame["trade_time"])
        for horizon in horizons
    }
    fast_context = _build_context(frame) if backend == "numba_hybrid" else None
    fast_cache: dict[str, np.ndarray] = {}
    pandas_cache: dict[str, pd.Series] = {}
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    eval_seconds = 0.0

    for index, row in enumerate(candidate_rows, start=1):
        expression = str(row.get("expression") or "")
        try:
            t0 = time.perf_counter()
            if backend == "pandas":
                signal = pd.to_numeric(
                    evaluate_panel_expression(frame, expression, cache=pandas_cache),
                    errors="coerce",
                ).reset_index(drop=True)
            elif backend == "numba_hybrid":
                if fast_context is None:
                    raise RuntimeError("missing fast context")
                signal = pd.Series(_fast_eval(expression, fast_context, fast_cache), index=frame.index)
            else:
                raise RuntimeError(f"unsupported backend: {backend}")
            eval_seconds += time.perf_counter() - t0
        except Exception as exc:
            errors.append(
                {
                    "backend": backend,
                    "candidate_id": row.get("candidate_id") or "",
                    "expression": expression,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
            continue

        signal_rank = _rank_by_group(signal, frame["trade_time"])
        base = {
            "backend": backend,
            "rank_input_order": index,
            "candidate_id": row.get("candidate_id") or "",
            "source_horizon_min": row.get("horizon_min") or "",
            "source_mean_ic_abs_mean": row.get("mean_ic_abs_mean") or "",
            "signal_nonnull": int(signal.notna().sum()),
            "signal_unique": int(signal.nunique(dropna=True)),
            "expression": expression,
        }
        for horizon in horizons:
            label = labels[f"fwd_ret_{horizon}m"]
            result = dict(base)
            result["horizon_min"] = horizon
            result.update(
                _mean_ic_from_ranks(
                    signal_rank,
                    label_ranks[horizon],
                    group_codes,
                    group_count=group_count,
                    min_obs=min_obs_per_time,
                )
            )
            result.update(
                _top_bottom_spread_from_rank(
                    signal_rank,
                    label,
                    group_codes,
                    group_count=group_count,
                    min_obs=min_obs_per_time,
                )
            )
            rows.append(result)
    return rows, {"backend": backend, "eval_seconds": eval_seconds, "errors": errors}


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except Exception:
        return None
    if not np.isfinite(out):
        return None
    return out


def _compare_rows(pandas_rows: list[dict[str, Any]], numba_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {
        (str(row.get("candidate_id") or ""), int(row.get("horizon_min") or 0)): row
        for row in numba_rows
    }
    out: list[dict[str, Any]] = []
    for prow in pandas_rows:
        key = (str(prow.get("candidate_id") or ""), int(prow.get("horizon_min") or 0))
        nrow = by_key.get(key)
        if nrow is None:
            continue
        item: dict[str, Any] = {
            "candidate_id": key[0],
            "horizon_min": key[1],
            "expression": prow.get("expression") or "",
        }
        for column in METRIC_COLUMNS:
            left = _safe_float(prow.get(column))
            right = _safe_float(nrow.get(column))
            item[f"pandas_{column}"] = left
            item[f"numba_{column}"] = right
            item[f"diff_{column}"] = None if left is None or right is None else right - left
            item[f"abs_diff_{column}"] = None if item[f"diff_{column}"] is None else abs(float(item[f"diff_{column}"]))
        item["pandas_ic_count"] = prow.get("ic_count")
        item["numba_ic_count"] = nrow.get("ic_count")
        item["pandas_spread_count"] = prow.get("spread_count")
        item["numba_spread_count"] = nrow.get("spread_count")
        out.append(item)
    return out


def _top_ids(rows: list[dict[str, Any]], horizon: int, top_n: int) -> list[str]:
    subset = [
        row for row in rows
        if int(row.get("horizon_min") or 0) == horizon and _safe_float(row.get("ic_abs_mean")) is not None
    ]
    subset.sort(key=lambda row: float(row["ic_abs_mean"]), reverse=True)
    return [str(row.get("candidate_id") or "") for row in subset[:top_n]]


def run_canary(
    *,
    panel: Path,
    candidates: Path,
    output_root: Path,
    report_root: Path,
    candidate_limit: int,
    max_rows: int | None,
    horizons: tuple[int, ...],
    min_obs_per_time: int,
    metric_tolerance: float,
    top_n: int,
) -> dict[str, Any]:
    panel = _resolve(panel)
    candidates = _resolve(candidates)
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    candidate_rows = _load_candidates(candidates, candidate_limit)
    expressions = [str(row.get("expression") or "") for row in candidate_rows]
    frame = _read_panel(panel, expressions, max_rows=max_rows)
    frame = frame.sort_values(["code", "trade_time"]).reset_index(drop=True)
    date_equals_trade_time = bool((pd.to_datetime(frame["date"]) == pd.to_datetime(frame["trade_time"])).all())

    pandas_rows, pandas_meta = _metric_rows(
        frame=frame,
        candidate_rows=candidate_rows,
        backend="pandas",
        horizons=horizons,
        min_obs_per_time=min_obs_per_time,
    )
    numba_rows, numba_meta = _metric_rows(
        frame=frame,
        candidate_rows=candidate_rows,
        backend="numba_hybrid",
        horizons=horizons,
        min_obs_per_time=min_obs_per_time,
    )
    compare_rows = _compare_rows(pandas_rows, numba_rows)
    all_abs_diffs = [
        float(value)
        for row in compare_rows
        for key, value in row.items()
        if key.startswith("abs_diff_") and value is not None
    ]
    max_metric_abs_diff = max(all_abs_diffs, default=None)
    max_abs_diff_by_metric = {
        column: max(
            (
                float(row[f"abs_diff_{column}"])
                for row in compare_rows
                if row.get(f"abs_diff_{column}") is not None
            ),
            default=None,
        )
        for column in METRIC_COLUMNS
    }

    ranking_rows: list[dict[str, Any]] = []
    ranking_pass = True
    for horizon in horizons:
        pandas_top = _top_ids(pandas_rows, horizon, top_n)
        numba_top = _top_ids(numba_rows, horizon, top_n)
        top1_same = bool(pandas_top and numba_top and pandas_top[0] == numba_top[0])
        overlap = len(set(pandas_top) & set(numba_top))
        required_overlap = min(top_n, len(pandas_top), len(numba_top))
        passed = top1_same and overlap == required_overlap
        ranking_pass = ranking_pass and passed
        ranking_rows.append(
            {
                "horizon_min": horizon,
                "top_n": top_n,
                "pandas_top": "|".join(pandas_top),
                "numba_top": "|".join(numba_top),
                "top1_same": top1_same,
                "top_overlap": overlap,
                "required_overlap": required_overlap,
                "passed": passed,
            }
        )

    metric_pass = bool(max_metric_abs_diff is not None and max_metric_abs_diff <= metric_tolerance)
    no_errors = not pandas_meta["errors"] and not numba_meta["errors"]
    decision = (
        "PASS_REPLAY_METRIC_DIFF_CANARY"
        if metric_pass and ranking_pass and no_errors
        else "HOLD_REPLAY_METRIC_DIFF_CANARY"
    )

    _write_csv(output_root / "phase3bd_pandas_metric_rows.csv", pandas_rows)
    _write_csv(output_root / "phase3bd_numba_metric_rows.csv", numba_rows)
    _write_csv(output_root / "phase3bd_metric_diff_rows.csv", compare_rows)
    _write_csv(output_root / "phase3bd_ranking_diff_rows.csv", ranking_rows)
    errors = list(pandas_meta["errors"]) + list(numba_meta["errors"])
    if errors:
        _write_csv(output_root / "phase3bd_errors.csv", errors)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase3BD",
        "decision": decision,
        "purpose": "pandas vs numba-hybrid replay metric-diff canary after Phase3BC element parity hold",
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
            "candidate_count": len(candidate_rows),
            "horizons": list(horizons),
            "max_rows": max_rows,
        },
        "timing": {
            "pandas_eval_seconds": pandas_meta["eval_seconds"],
            "numba_hybrid_eval_seconds": numba_meta["eval_seconds"],
            "eval_speedup": None if numba_meta["eval_seconds"] == 0 else pandas_meta["eval_seconds"] / numba_meta["eval_seconds"],
        },
        "metric_diff": {
            "metric_tolerance": metric_tolerance,
            "max_metric_abs_diff": max_metric_abs_diff,
            "max_abs_diff_by_metric": max_abs_diff_by_metric,
            "metric_pass": metric_pass,
            "row_count": len(compare_rows),
        },
        "ranking_diff": {
            "top_n": top_n,
            "ranking_pass": ranking_pass,
            "rows": ranking_rows,
        },
        "errors": {"count": len(errors), "rows": errors[:10]},
        "launch_contract": {
            "may_enable_numba_backend_by_default": False,
            "may_add_explicit_backend_flag": decision == "PASS_REPLAY_METRIC_DIFF_CANARY",
            "requires_default_pandas_for_proof": True,
            "official_x0_r3_changed": False,
            "search_results_changed": False,
        },
    }
    _write_json(output_root / "phase3bd_replay_metric_diff_summary.json", summary)

    md = [
        "# Phase3BD Replay Metric-Diff Canary",
        "",
        f"- decision: `{decision}`",
        f"- panel: `{panel}`",
        f"- candidates: `{candidates}`",
        f"- rows: `{len(frame)}`",
        f"- codes: `{frame['code'].nunique()}`",
        f"- date groups: `{frame['date'].nunique()}`",
        f"- trade_time groups: `{frame['trade_time'].nunique()}`",
        f"- date equals trade_time: `{date_equals_trade_time}`",
        f"- candidates: `{len(candidate_rows)}`",
        f"- horizons: `{','.join(str(item) for item in horizons)}`",
        f"- max metric abs diff: `{max_metric_abs_diff}`",
        f"- max abs diff by metric: `{max_abs_diff_by_metric}`",
        f"- metric tolerance: `{metric_tolerance}`",
        f"- ranking pass: `{ranking_pass}`",
        f"- pandas eval seconds: `{pandas_meta['eval_seconds']}`",
        f"- numba-hybrid eval seconds: `{numba_meta['eval_seconds']}`",
        f"- eval speedup: `{summary['timing']['eval_speedup']}`",
        "",
        "## Meaning",
        "",
        "This is not alpha proof and not a new search. It compares replay metrics from the existing pandas signal evaluator against the Phase3BC numba-hybrid signal evaluator on the same true-1min sidecar panel and the same Phase3BA/BB candidate expressions.",
        "",
        "Phase3BC strict element parity remains the stricter gate. Phase3BD only answers whether the observed signal-level differences materially change Phase3AS-style IC/spread metrics.",
        "",
        "## Ranking Diff",
        "",
        "| horizon | top1_same | overlap | required | pass |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for row in ranking_rows:
        md.append(
            f"| {row['horizon_min']} | `{row['top1_same']}` | {row['top_overlap']} | {row['required_overlap']} | `{row['passed']}` |"
        )
    md.extend(
        [
            "",
            "## Largest Metric Diffs",
            "",
            "| candidate_id | horizon | abs_diff_ic_abs | abs_diff_ic_mean | abs_diff_spread_abs | abs_diff_spread_mean | abs_diff_spread_hit_rate |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    sorted_compare = sorted(
        compare_rows,
        key=lambda row: max(
            float(value)
            for key, value in row.items()
            if key.startswith("abs_diff_") and value is not None
        ),
        reverse=True,
    )
    for row in sorted_compare[:20]:
        md.append(
            f"| `{row['candidate_id']}` | {row['horizon_min']} | "
            f"{row.get('abs_diff_ic_abs_mean')} | {row.get('abs_diff_ic_mean')} | "
            f"{row.get('abs_diff_spread_abs_mean')} | {row.get('abs_diff_spread_mean')} | "
            f"{row.get('abs_diff_spread_hit_rate')} |"
        )
    md.extend(
        [
            "",
            "## Launch Contract",
            "",
            "- Do not make numba the default proof evaluator.",
            "- If this canary passes, a future change may add an explicit `--evaluator-backend numba_hybrid` flag for diagnostic replay only.",
            "- X0/R3 and prior search decisions are unchanged.",
            "",
        ]
    )
    (report_root / "PHASE3BD_REPLAY_METRIC_DIFF_CANARY_20260613.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase3BD pandas vs numba-hybrid replay metric-diff canary.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--candidate-limit", type=int, default=16)
    parser.add_argument("--max-rows", type=int, default=0, help="0 means full fixed panel")
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=4)
    parser.add_argument("--metric-tolerance", type=float, default=1e-4)
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args(argv)
    run_canary(
        panel=args.panel,
        candidates=args.candidates,
        output_root=args.output_root,
        report_root=args.report_root,
        candidate_limit=args.candidate_limit,
        max_rows=None if args.max_rows <= 0 else args.max_rows,
        horizons=_parse_horizons(args.horizons),
        min_obs_per_time=args.min_obs_per_time,
        metric_tolerance=args.metric_tolerance,
        top_n=args.top_n,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
