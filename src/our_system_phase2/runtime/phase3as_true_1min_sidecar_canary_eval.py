"""Evaluate Phase3AR sidecar candidates on the true 1min canary panel.

This is a minute cross-section canary, not a production proof. Signals are
ranked by `trade_time`, labels are future 1min-bar returns by code, and search
memory hits are tagged so repeated structures are not treated as fresh alpha.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from our_system_phase2.services.real_market_validation import evaluate_panel_expression


REPO = Path(__file__).resolve().parents[3]
DEFAULT_PANEL = Path("runtime/phase3ar_sidecar_field_adapter_20260610/phase3ar_true_1min_sidecar_canary.parquet")
DEFAULT_PACK_ROOT = Path("runtime/phase3ar_sidecar_field_adapter_20260610")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3as_true_1min_sidecar_canary_eval_20260610")
DEFAULT_REPORT_ROOT = Path("reports/phase3as_true_1min_sidecar_canary_eval_20260610")
DEFAULT_HORIZONS = (1, 5, 15, 30)
FIELD_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


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


def _stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _fields(expression: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(expression or "")))


def _load_pack(path: Path, lane: str) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("candidate_rows") if isinstance(payload, dict) else None
    out: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if isinstance(row, dict):
            item = dict(row)
            item["phase3as_eval_lane"] = lane
            out.append(item)
    return out


def _load_rows(pack_root: Path, include_diagnostic: bool) -> list[dict[str, Any]]:
    rows = []
    rows.extend(_load_pack(pack_root / "phase3ar_sidecar_context_formula_pack.json", "sidecar_context_formula"))
    rows.extend(_load_pack(pack_root / "phase3ar_event_state_cutoff_canary_pack.json", "event_state_cutoff_canary"))
    if include_diagnostic:
        rows.extend(_load_pack(pack_root / "phase3ar_diagnostic_context_only_pack.json", "diagnostic_context_only"))
    return rows


def _load_memory(memory_roots: list[Path]) -> tuple[set[str], set[str]]:
    keys: set[str] = set()
    expr_hashes: set[str] = set()
    for root in memory_roots:
        root = _resolve(root)
        paths: list[Path]
        if root.is_dir():
            paths = list(root.rglob("phase3aj_search_memory_ledger.json"))
        else:
            paths = [root]
        for path in paths:
            if not path.exists():
                continue
            data = _read_json(path)
            entries = data.get("memory_entries") if isinstance(data, dict) else data
            if not isinstance(entries, list):
                continue
            for row in entries:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("search_memory_key") or "")
                expr_hash = str(row.get("expression_hash") or "")
                if key:
                    keys.add(key)
                if expr_hash:
                    expr_hashes.add(expr_hash)
    return keys, expr_hashes


def _future_returns(frame: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    close = pd.to_numeric(frame["close"], errors="coerce")
    grouped = close.groupby(frame["code"], sort=False)
    labels = pd.DataFrame(index=frame.index)
    for horizon in horizons:
        labels[f"fwd_ret_{horizon}m"] = grouped.shift(-horizon) / close.replace(0, np.nan) - 1.0
    return labels


def _rank_by_group(values: pd.Series, group: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").groupby(group, sort=False).rank(pct=True)


def _mean_ic_from_ranks(
    signal_rank: pd.Series,
    label_rank: pd.Series,
    group_codes: np.ndarray,
    *,
    group_count: int,
    min_obs: int,
) -> dict[str, Any]:
    x = pd.to_numeric(signal_rank, errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(label_rank, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(x) & np.isfinite(y) & (group_codes >= 0)
    if not np.any(valid):
        return {"ic_mean": None, "ic_abs_mean": None, "ic_std": None, "ic_t": None, "ic_count": 0}
    codes = group_codes[valid]
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
    arr = corr[(n >= min_obs) & np.isfinite(corr)].astype(float)
    if len(arr) == 0:
        return {"ic_mean": None, "ic_abs_mean": None, "ic_std": None, "ic_t": None, "ic_count": 0}
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    mean = float(arr.mean())
    return {
        "ic_mean": mean,
        "ic_abs_mean": float(np.mean(np.abs(arr))),
        "ic_std": std,
        "ic_t": None if std == 0.0 else float(mean / (std / np.sqrt(len(arr)))),
        "ic_count": int(len(arr)),
    }


def _top_bottom_spread_from_rank(
    signal_rank: pd.Series,
    label: pd.Series,
    group_codes: np.ndarray,
    *,
    group_count: int,
    min_obs: int,
) -> dict[str, Any]:
    rank = pd.to_numeric(signal_rank, errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(label, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(rank) & np.isfinite(y) & (group_codes >= 0)
    if not np.any(valid):
        return {"spread_mean": None, "spread_abs_mean": None, "spread_t": None, "spread_count": 0, "spread_hit_rate": None}
    codes = group_codes[valid]
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
    arr = spreads[(counts >= min_obs) & (top_n > 0) & (bot_n > 0) & np.isfinite(spreads)].astype(float)
    if len(arr) == 0:
        return {"spread_mean": None, "spread_abs_mean": None, "spread_t": None, "spread_count": 0, "spread_hit_rate": None}
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    mean = float(arr.mean())
    return {
        "spread_mean": mean,
        "spread_abs_mean": float(np.mean(np.abs(arr))),
        "spread_t": None if std == 0.0 else float(mean / (std / np.sqrt(len(arr)))),
        "spread_count": int(len(arr)),
        "spread_hit_rate": float(np.mean(arr > 0.0)),
    }


def _compact_top_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id") or "",
        "lane": row.get("lane") or "",
        "horizon_min": row.get("horizon_min"),
        "ic_mean": row.get("ic_mean"),
        "ic_abs_mean": row.get("ic_abs_mean"),
        "ic_count": row.get("ic_count"),
        "spread_mean": row.get("spread_mean"),
        "spread_count": row.get("spread_count"),
        "memory_hit": row.get("memory_hit"),
        "fresh_eligible": row.get("fresh_eligible"),
        "source_lane": row.get("source_lane") or "",
        "fields": row.get("fields") or "",
        "expression_hash": row.get("expression_hash") or "",
    }


def _panel_trade_times(panel_path: Path) -> pd.Series:
    parquet = pq.ParquetFile(panel_path)
    if "trade_time" not in parquet.schema_arrow.names:
        raise RuntimeError("panel missing required column: trade_time")
    chunks: list[pd.Series] = []
    for row_group in range(parquet.num_row_groups):
        table = parquet.read_row_group(row_group, columns=["trade_time"])
        unique = pc.unique(table["trade_time"].combine_chunks()).to_pandas()
        chunks.append(pd.Series(pd.to_datetime(unique, errors="coerce")).dropna())
    if not chunks:
        return pd.Series([], dtype="datetime64[ns]")
    return pd.concat(chunks, ignore_index=True).drop_duplicates().sort_values(ignore_index=True)


def _sample_signal_and_read_times(
    trade_times: pd.Series,
    *,
    sample_trade_times: int | None,
    horizons: tuple[int, ...],
) -> tuple[set[pd.Timestamp] | None, set[pd.Timestamp] | None]:
    if sample_trade_times is None or sample_trade_times <= 0 or len(trade_times) <= sample_trade_times:
        return None, None
    positions = np.linspace(0, len(trade_times) - 1, sample_trade_times).round().astype(int)
    positions = np.unique(positions)
    signal_times = set(pd.to_datetime(trade_times.iloc[positions]).tolist())
    max_horizon = max(horizons) if horizons else 0
    read_positions = set(int(pos) for pos in positions)
    for pos in positions:
        for offset in range(1, max_horizon + 1):
            future_pos = int(pos) + offset
            if future_pos < len(trade_times):
                read_positions.add(future_pos)
    read_times = set(pd.to_datetime(trade_times.iloc[sorted(read_positions)]).tolist())
    return signal_times, read_times


def _arrow_time_values(values: set[pd.Timestamp], arrow_type: pa.DataType) -> pa.Array:
    arr = pa.array(pd.to_datetime(sorted(values)).to_numpy(dtype="datetime64[ns]"))
    if not arr.type.equals(arrow_type):
        arr = arr.cast(arrow_type)
    return arr


def _read_panel_columns(
    panel_path: Path,
    *,
    columns: list[str],
    trade_times: set[pd.Timestamp] | None,
) -> pd.DataFrame:
    if trade_times is None:
        return pd.read_parquet(panel_path, columns=columns)

    parquet = pq.ParquetFile(panel_path)
    trade_time_type = parquet.schema_arrow.field("trade_time").type
    value_set = _arrow_time_values(trade_times, trade_time_type)
    tables: list[pa.Table] = []
    for row_group in range(parquet.num_row_groups):
        table = parquet.read_row_group(row_group, columns=columns)
        mask = pc.is_in(table["trade_time"], value_set=value_set)
        filtered = table.filter(mask)
        if filtered.num_rows:
            tables.append(filtered)
    if not tables:
        return pd.DataFrame(columns=columns)
    return pa.concat_tables(tables, promote_options="default").to_pandas()


def evaluate(
    *,
    panel_path: Path,
    pack_root: Path,
    output_root: Path,
    report_root: Path,
    horizons: tuple[int, ...],
    min_obs_per_time: int,
    sample_trade_times: int | None,
    include_diagnostic: bool,
    memory_roots: list[Path],
    exclude_memory_hits: bool,
    robust_min_ic_count: int,
) -> dict[str, Any]:
    panel_path = _resolve(panel_path)
    pack_root = _resolve(pack_root)
    output_root = _resolve(output_root)
    report_root = _resolve(report_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    rows = _load_rows(pack_root, include_diagnostic=include_diagnostic)
    memory_keys, memory_expr_hashes = _load_memory(memory_roots)
    prepared_rows: list[dict[str, Any]] = []
    memory_hit_count = 0
    for row in rows:
        expression = str(row.get("expression") or "")
        expression_hash = _stable_hash(expression)
        search_memory_key = str(row.get("search_memory_key") or expression_hash)
        memory_hit = search_memory_key in memory_keys or expression_hash in memory_expr_hashes
        memory_hit_count += int(memory_hit)
        if exclude_memory_hits and memory_hit:
            continue
        out = dict(row)
        out["phase3as_expression_hash"] = expression_hash
        out["phase3as_memory_hit"] = memory_hit
        out["phase3as_fresh_eligible"] = not memory_hit
        prepared_rows.append(out)

    expression_fields: set[str] = set()
    for row in prepared_rows:
        expression_fields.update(_fields(str(row.get("expression") or "")))
    required_columns = {
        "code",
        "date",
        "exec_date",
        "trade_time",
        "open",
        "high",
        "low",
        "close",
        "vol",
        "volume",
        "amount",
        "amount_yuan",
        *expression_fields,
    }
    schema_columns = set(pq.ParquetFile(panel_path).schema_arrow.names)
    read_columns = [column for column in sorted(required_columns) if column in schema_columns]
    missing_core = {"code", "date", "trade_time", "close"} - set(read_columns)
    if missing_core:
        raise RuntimeError(f"panel missing required columns: {sorted(missing_core)}")
    all_trade_times = _panel_trade_times(panel_path)
    original_trade_time_count = int(len(all_trade_times))
    signal_trade_times, read_trade_times = _sample_signal_and_read_times(
        all_trade_times,
        sample_trade_times=sample_trade_times,
        horizons=horizons,
    )
    frame = _read_panel_columns(panel_path, columns=read_columns, trade_times=signal_trade_times)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame = frame.dropna(subset=["date", "trade_time", "code", "close"]).sort_values(["code", "trade_time"]).reset_index(drop=True)
    if signal_trade_times is None or read_trade_times is None:
        label_frame = frame
        labels = _future_returns(label_frame, horizons)
        labels_eval = labels.reset_index(drop=True)
        label_read_trade_time_count = int(label_frame["trade_time"].nunique())
    else:
        label_frame = _read_panel_columns(
            panel_path,
            columns=["code", "date", "trade_time", "close"],
            trade_times=read_trade_times,
        )
        label_frame["date"] = pd.to_datetime(label_frame["date"], errors="coerce")
        label_frame["trade_time"] = pd.to_datetime(label_frame["trade_time"], errors="coerce")
        label_frame = label_frame.dropna(subset=["date", "trade_time", "code", "close"]).sort_values(["code", "trade_time"]).reset_index(drop=True)
        labels = _future_returns(label_frame, horizons)
        label_source = label_frame[["code", "trade_time"]].copy()
        for horizon in horizons:
            label_source[f"fwd_ret_{horizon}m"] = labels[f"fwd_ret_{horizon}m"].to_numpy()
        labels_eval = frame[["code", "trade_time"]].merge(label_source, on=["code", "trade_time"], how="left")
        labels_eval = labels_eval[[f"fwd_ret_{horizon}m" for horizon in horizons]]
        label_read_trade_time_count = int(label_frame["trade_time"].nunique())
    eval_frame = frame
    if eval_frame.empty:
        raise RuntimeError("sampled panel is empty after trade_time filtering")

    group_codes, unique_times = pd.factorize(eval_frame["trade_time"], sort=False)
    group_count = int(len(unique_times))
    label_ranks = {
        horizon: _rank_by_group(labels_eval[f"fwd_ret_{horizon}m"], eval_frame["trade_time"])
        for horizon in horizons
    }

    result_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, row in enumerate(prepared_rows, start=1):
        expression = str(row.get("expression") or "")
        try:
            signal = pd.to_numeric(evaluate_panel_expression(frame, expression), errors="coerce").reset_index(drop=True)
        except Exception as exc:
            errors.append(
                {
                    "candidate_id": row.get("candidate_id") or "",
                    "lane": row.get("phase3as_eval_lane") or "",
                    "expression": expression,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
            continue
        signal_rank = _rank_by_group(signal, eval_frame["trade_time"])
        base = {
            "rank_input_order": index,
            "candidate_id": row.get("candidate_id") or "",
            "lane": row.get("phase3as_eval_lane") or "",
            "factor_lane": row.get("factor_lane") or "",
            "source_lane": row.get("source_lane") or "",
            "source_generator": row.get("source_generator") or "",
            "search_memory_key": row.get("search_memory_key") or "",
            "expression_hash": row.get("phase3as_expression_hash") or "",
            "memory_hit": bool(row.get("phase3as_memory_hit")),
            "fresh_eligible": bool(row.get("phase3as_fresh_eligible")),
            "fields": "|".join(_fields(expression)),
            "expression": expression,
            "signal_nonnull": int(signal.notna().sum()),
            "signal_unique": int(signal.nunique(dropna=True)),
        }
        for horizon in horizons:
            label = labels_eval[f"fwd_ret_{horizon}m"]
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
            result_rows.append(result)

    result_rows.sort(
        key=lambda item: (
            item.get("ic_abs_mean") is None,
            0.0 if item.get("ic_abs_mean") is None else -float(item["ic_abs_mean"]),
            -int(item.get("ic_count") or 0),
        )
    )
    _write_csv(output_root / "phase3as_true_1min_sidecar_canary_eval_rows.csv", result_rows)
    _write_csv(output_root / "phase3as_true_1min_sidecar_canary_eval_errors.csv", errors)

    top_by_horizon: dict[str, list[dict[str, Any]]] = {}
    robust_top_by_horizon: dict[str, list[dict[str, Any]]] = {}
    for horizon in horizons:
        subset = [row for row in result_rows if int(row["horizon_min"]) == horizon and row.get("ic_abs_mean") is not None]
        subset.sort(key=lambda item: float(item["ic_abs_mean"]), reverse=True)
        top_by_horizon[str(horizon)] = [_compact_top_row(row) for row in subset[:25]]
        robust_subset = [row for row in subset if int(row.get("ic_count") or 0) >= robust_min_ic_count]
        robust_top_by_horizon[str(horizon)] = [_compact_top_row(row) for row in robust_subset[:25]]

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AS_TRUE_1MIN_SIDECAR_CANARY_EVAL_COMPLETE",
        "panel_path": str(panel_path),
        "pack_root": str(pack_root),
        "output_root": str(output_root),
        "report_root": str(report_root),
        "input_candidate_count": len(rows),
        "evaluated_candidate_count": len(prepared_rows),
        "memory_hit_count": memory_hit_count,
        "exclude_memory_hits": exclude_memory_hits,
        "error_count": len(errors),
        "panel_rows": int(len(eval_frame)),
        "panel_codes": int(eval_frame["code"].nunique()),
        "panel_schema_column_count": int(len(schema_columns)),
        "panel_read_column_count": int(len(read_columns)),
        "expression_field_count": int(len(expression_fields)),
        "original_trade_time_count": original_trade_time_count,
        "signal_read_trade_time_count": int(frame["trade_time"].nunique()),
        "label_read_trade_time_count": label_read_trade_time_count,
        "read_trade_time_count": label_read_trade_time_count,
        "evaluated_trade_time_count": int(eval_frame["trade_time"].nunique()),
        "horizons_min": list(horizons),
        "lane_counts": dict(Counter(str(row.get("phase3as_eval_lane") or "") for row in prepared_rows)),
        "source_lane_counts": dict(Counter(str(row.get("source_lane") or "") for row in prepared_rows)),
        "top_by_horizon": top_by_horizon,
        "robust_min_ic_count": robust_min_ic_count,
        "robust_top_by_horizon": robust_top_by_horizon,
        "hard_rules": [
            "minute cross-section is trade_time, not date",
            "future labels are computed from true 1min rows by code",
            "sidecar daily/event fields are evaluated only after Phase3AR PIT/cutoff adapter materialization",
            "search memory hits are tagged and are not counted as fresh structures",
            "X0/R3 read-only; no promotion decision",
        ],
    }
    _write_json(output_root / "phase3as_true_1min_sidecar_canary_eval_summary.json", summary)
    _write_json(report_root / "phase3as_true_1min_sidecar_canary_eval_summary.json", summary)

    lines = [
        "# Phase3AS True 1min Sidecar Canary Eval",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Counts",
        "",
        f"- input candidates: `{summary['input_candidate_count']}`",
        f"- evaluated candidates: `{summary['evaluated_candidate_count']}`",
        f"- memory hits: `{summary['memory_hit_count']}`",
        f"- errors: `{summary['error_count']}`",
        f"- panel rows: `{summary['panel_rows']}`",
        f"- panel codes: `{summary['panel_codes']}`",
        f"- evaluated trade_time groups: `{summary['evaluated_trade_time_count']}`",
        "",
        "## Hard Rules",
        "",
        "- cross-section key is `trade_time`, not `date`.",
        "- labels are future 1min-bar returns by `code`.",
        "- Phase3AR sidecars must already be PIT/cutoff materialized.",
        "- search-memory hits are tagged, not treated as fresh alpha.",
        "- X0/R3 remains read-only.",
        "",
        "## Outputs",
        "",
        f"- rows: `{output_root / 'phase3as_true_1min_sidecar_canary_eval_rows.csv'}`",
        f"- errors: `{output_root / 'phase3as_true_1min_sidecar_canary_eval_errors.csv'}`",
        f"- summary: `{output_root / 'phase3as_true_1min_sidecar_canary_eval_summary.json'}`",
    ]
    (report_root / "PHASE3AS_TRUE_1MIN_SIDECAR_CANARY_EVAL_20260610.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Phase3AR sidecar formulas on the true 1min canary panel.")
    parser.add_argument("--panel", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--horizons", default="1,5,15,30")
    parser.add_argument("--min-obs-per-time", type=int, default=4)
    parser.add_argument("--sample-trade-times", type=int, default=2400)
    parser.add_argument("--include-diagnostic", action="store_true")
    parser.add_argument("--memory-root", action="append", type=Path, default=[Path("runtime/search_memory")])
    parser.add_argument("--exclude-memory-hits", action="store_true")
    parser.add_argument("--robust-min-ic-count", type=int, default=50)
    args = parser.parse_args()

    horizons = tuple(int(item.strip()) for item in args.horizons.split(",") if item.strip())
    evaluate(
        panel_path=args.panel,
        pack_root=args.pack_root,
        output_root=args.output_root,
        report_root=args.report_root,
        horizons=horizons or DEFAULT_HORIZONS,
        min_obs_per_time=args.min_obs_per_time,
        sample_trade_times=args.sample_trade_times,
        include_diagnostic=args.include_diagnostic,
        memory_roots=args.memory_root,
        exclude_memory_hits=args.exclude_memory_hits,
        robust_min_ic_count=args.robust_min_ic_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
