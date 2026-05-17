"""Append-only locked forward/shadow export for the Phase3L candidate book.

This exports signals, aggregate long/short shadow positions, and a book
snapshot for the frozen 6-cluster Phase3L candidate book. It does not rebalance
weights by observed outcomes and does not run new search.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)


DEFAULT_CANDIDATE_BOOK = Path("reports/phase3l_o_daily_proof_freeze_pack_20260517/phase3l_candidate_book_6_clusters.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3l_o_locked_forward_shadow")
TOP_BOTTOM_QUANTILE = 0.02


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
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


def _write_json(path: Path, payload: Any, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"append_only_output_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _selection_rows(
    *,
    cluster_id: str,
    source_lane: str,
    expression: str,
    date_frame: pd.DataFrame,
    signal: pd.Series,
) -> list[dict[str, Any]]:
    work = date_frame[["date", "code"]].copy()
    work["signal"] = pd.to_numeric(signal.loc[date_frame.index], errors="coerce")
    work = work.dropna(subset=["signal"])
    if work.empty or work["signal"].nunique(dropna=True) < 2:
        return []
    count = max(1, int(math.ceil(len(work) * TOP_BOTTOM_QUANTILE)))
    ranked = work.sort_values(["signal", "code"], ascending=[False, True]).copy()
    top = ranked.head(count).copy()
    bottom = ranked.tail(count).copy()
    top["side"] = "long"
    bottom["side"] = "short"
    selected = pd.concat([top, bottom], ignore_index=True)
    selected["cluster_id"] = cluster_id
    selected["source_lane"] = source_lane
    selected["expression"] = expression
    selected["rank_in_side"] = selected.groupby("side").cumcount() + 1
    return selected.to_dict("records")


def run(
    *,
    candidate_book: Path,
    dataset_path: Path,
    output_root: Path,
    signal_date: str | None,
    recent_quarter_window_count: int,
    warmup_days: int,
    force: bool,
) -> dict[str, Any]:
    candidates = _read_csv(candidate_book)
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    available_dates = sorted(pd.to_datetime(signal_frame["date"], errors="coerce").dropna().unique())
    if not available_dates:
        raise ValueError("no_available_signal_dates")
    if signal_date:
        target_date = pd.Timestamp(signal_date)
        if target_date not in set(available_dates):
            raise ValueError(f"signal_date_not_available:{signal_date}")
    else:
        target_date = pd.Timestamp(available_dates[-1])
    date_key = target_date.strftime("%Y%m%d")
    date_frame = signal_frame[pd.to_datetime(signal_frame["date"], errors="coerce") == target_date].copy()
    expression_cache: dict[str, pd.Series] = {}
    signal_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row in candidates:
        cluster_id = str(row.get("cluster_id") or row.get("global_signal_cluster_id") or "")
        expression = str(row.get("representative_expression") or row.get("expression") or "")
        if not cluster_id or not expression:
            continue
        try:
            signal = evaluate_panel_expression(
                signal_frame,
                expression,
                cache=expression_cache,
                field_lags=signal_clock_report["field_lags"],
            )
            signal_rows.extend(
                _selection_rows(
                    cluster_id=cluster_id,
                    source_lane=str(row.get("source_lane") or ""),
                    expression=expression,
                    date_frame=date_frame,
                    signal=signal,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "cluster_id": cluster_id,
                    "expression": expression,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )

    cluster_count = max(1, len(candidates))
    position_accumulator: dict[str, dict[str, Any]] = {}
    for row in signal_rows:
        cluster_selected = [item for item in signal_rows if item["cluster_id"] == row["cluster_id"] and item["side"] == row["side"]]
        side_count = max(1, len(cluster_selected))
        sign = 1.0 if row["side"] == "long" else -1.0
        weight = sign * (1.0 / cluster_count) * (0.5 / side_count)
        code = str(row["code"])
        bucket = position_accumulator.setdefault(
            code,
            {
                "date": target_date.date().isoformat(),
                "code": code,
                "target_weight": 0.0,
                "long_cluster_count": 0,
                "short_cluster_count": 0,
                "cluster_ids": [],
            },
        )
        bucket["target_weight"] += weight
        if row["side"] == "long":
            bucket["long_cluster_count"] += 1
        else:
            bucket["short_cluster_count"] += 1
        bucket["cluster_ids"].append(str(row["cluster_id"]))

    position_rows = []
    for item in position_accumulator.values():
        out = dict(item)
        out["target_weight"] = round(float(out["target_weight"]), 10)
        out["cluster_ids"] = "|".join(sorted(set(out["cluster_ids"])))
        position_rows.append(out)
    position_rows.sort(key=lambda item: (abs(float(item["target_weight"])), item["code"]), reverse=True)

    signal_path = output_root / "daily_signals" / f"{date_key}.csv"
    position_path = output_root / "daily_positions" / f"{date_key}.csv"
    snapshot_path = output_root / "daily_book_snapshot" / f"{date_key}.json"
    _write_csv(signal_path, signal_rows, force=force)
    _write_csv(position_path, position_rows, force=force)
    snapshot = {
        "created_at": _now(),
        "experiment_id": "20260517_phase3l_p_locked_forward_export",
        "scope": "append_only_shadow_export_no_execution",
        "signal_date": target_date.date().isoformat(),
        "date_key": date_key,
        "dataset_path": str(dataset_path),
        "candidate_book": str(candidate_book),
        "candidate_book_sha256": _sha256(candidate_book),
        "signal_clock": SIGNAL_CLOCK_AFTER_OPEN,
        "top_bottom_quantile": TOP_BOTTOM_QUANTILE,
        "cluster_count": len(candidates),
        "signal_row_count": len(signal_rows),
        "position_count": len(position_rows),
        "gross_long_weight": round(float(sum(max(0.0, float(row["target_weight"])) for row in position_rows)), 8),
        "gross_short_weight": round(float(sum(max(0.0, -float(row["target_weight"])) for row in position_rows)), 8),
        "net_weight": round(float(sum(float(row["target_weight"]) for row in position_rows)), 8),
        "errors": errors,
        "append_only_policy": "do_not_overwrite_existing_daily_outputs_without_force",
        "outputs": {
            "daily_signals": str(signal_path),
            "daily_positions": str(position_path),
            "daily_book_snapshot": str(snapshot_path),
        },
        "not_confirmed": [
            "execution_fill",
            "minute_slippage",
            "capacity",
            "live_or_paper_survival",
        ],
    }
    _write_json(snapshot_path, snapshot, force=force)
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-book", type=Path, default=DEFAULT_CANDIDATE_BOOK)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--signal-date", default=None)
    parser.add_argument("--recent-quarter-window-count", type=int, default=1)
    parser.add_argument("--warmup-days", type=int, default=90)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = run(
        candidate_book=args.candidate_book,
        dataset_path=args.dataset_path,
        output_root=args.output_root,
        signal_date=args.signal_date,
        recent_quarter_window_count=args.recent_quarter_window_count,
        warmup_days=args.warmup_days,
        force=bool(args.force),
    )
    print(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not snapshot["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
