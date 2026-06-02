"""Build a multi-year CN 1min feature panel from validated minute parquet v2.

This is a code-date panel, not a raw minute-row table. It reads:

- 2023-2025 stock_1min_2023_2025_symbol_parquet_v2, symbol parquet layout.
- 2026 stock_1min_2026_parquet_by_date, date parquet layout.
- Lagged daily context from HFQ daily and the augmented mature daily panel.

Leakage boundary:

- `m1_first*` fields are observable after their cutoff.
- `ctx_*` fields are joined from the previous trading day only.
- `label_*` fields are evaluation labels and forbidden as selector inputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531")
DEFAULT_SYMBOL_MINUTE_ROOT = DATA_ROOT / "stock_1min_2023_2025_symbol_parquet_v2"
DEFAULT_2026_MINUTE_ROOT = DATA_ROOT / "stock_1min_2026_parquet_by_date"
DEFAULT_HFQ_2024_2025 = DATA_ROOT / "hfq_daily_2024_2025"
DEFAULT_HFQ_2026 = DATA_ROOT / "hfq_daily_2026" / "hfq_daily_2026.parquet"
DEFAULT_AUGMENTED_DAILY = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_OUTPUT = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602")
DEFAULT_CONTEXT_CACHE = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_daily_context_cache")

KEY_COLUMNS = ["exec_date", "signal_date", "code"]
LABEL_PREFIX = "label_"
NUMERIC_COLUMNS = ["open", "high", "low", "close", "vol", "amount", "pct_chg", "pre_close"]
HFQ_CONTEXT_COLUMNS = [
    "date",
    "code",
    "industry",
    "amount_yuan",
    "volume_shares",
    "turnover_ratio",
    "pct_chg",
    "amplitude_pct",
    "is_st",
    "volume_ratio",
    "is_limit_up",
    "total_shares",
    "float_shares",
    "market_cap_yuan",
    "float_market_cap_yuan",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "ma120",
    "ma250",
    "is_marginable",
]
MATURE_FIXED_CONTEXT = [
    "date",
    "code",
    "amount",
    "volume",
    "turnover_ratio",
    "turnover_ratio_real",
    "pct_chg",
    "amplitude_pct",
    "volume_ratio",
    "is_limit_up",
    "is_limit_down",
    "susp",
    "is_st",
    "float_market_cap",
    "final_float_market_cap",
    "market_cap",
    "final_total_market_cap",
]


def _normalize_cn_code(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return raw
    if "." in raw:
        left, right = raw.split(".", 1)
        digits = "".join(ch for ch in left if ch.isdigit())
        suffix = "".join(ch for ch in right if ch.isalpha())
        return f"{digits.zfill(6)}.{suffix}" if digits and suffix else raw
    prefix = raw[:2]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        return raw
    digits = digits[-6:]
    if prefix == "SH":
        return f"{digits}.SH"
    if prefix == "SZ":
        return f"{digits}.SZ"
    if prefix == "BJ":
        return f"{digits}.BJ"
    if digits.startswith(("60", "68", "90", "51", "52", "56", "58")):
        return f"{digits}.SH"
    if digits.startswith(("00", "30", "15", "16", "18", "39")):
        return f"{digits}.SZ"
    if digits.startswith(("43", "83", "87", "88", "92")):
        return f"{digits}.BJ"
    return raw


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    den = pd.to_numeric(den, errors="coerce")
    out = pd.to_numeric(num, errors="coerce") / den.where(den.abs() > 1e-12)
    return out.replace([math.inf, -math.inf], pd.NA)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _append_jsonl(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_parquet_available(path: Path, wanted: list[str]) -> pd.DataFrame:
    columns = [col for col in wanted if col in pq.ParquetFile(path).schema_arrow.names]
    return pd.read_parquet(path, columns=columns)


def _ctx_columns_from_mature(columns: list[str]) -> list[str]:
    limit_cols = [
        col
        for col in columns
        if col.startswith("limit_up")
        or col.startswith("break_board")
        or col in {"high_board_rank", "is_market_high_board", "actual_circulation_value"}
    ]
    fund_cols = [col for col in columns if col.startswith("fund_")]
    selected = MATURE_FIXED_CONTEXT + limit_cols + fund_cols
    out: list[str] = []
    for col in selected:
        if col in columns and col not in out:
            out.append(col)
    return out


def _load_context_frames(hfq_2024_2025: Path, hfq_2026: Path, augmented_daily: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if hfq_2024_2025.exists():
        for path in sorted(hfq_2024_2025.rglob("*.parquet")):
            frame = _read_parquet_available(path, HFQ_CONTEXT_COLUMNS)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
            frame["code"] = frame["code"].map(_normalize_cn_code)
            frame = frame.rename(columns={col: f"ctx_hfq_{col}" for col in frame.columns if col not in {"date", "code"}})
            frames.append(frame)
    if hfq_2026.exists():
        frame = _read_parquet_available(hfq_2026, HFQ_CONTEXT_COLUMNS)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["code"] = frame["code"].map(_normalize_cn_code)
        frame = frame.rename(columns={col: f"ctx_hfq_{col}" for col in frame.columns if col not in {"date", "code"}})
        frames.append(frame)
    if augmented_daily.exists():
        columns = pq.ParquetFile(augmented_daily).schema_arrow.names
        selected = _ctx_columns_from_mature(columns)
        frame = pd.read_parquet(augmented_daily, columns=selected)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["code"] = frame["code"].map(_normalize_cn_code)
        frame = frame.rename(columns={col: f"ctx_aug_{col}" for col in frame.columns if col not in {"date", "code"}})
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["signal_date", "code"])
    context = frames[0]
    for frame in frames[1:]:
        context = context.merge(frame, on=["date", "code"], how="outer")
    context = context.rename(columns={"date": "signal_date"})
    return context.drop_duplicates(["signal_date", "code"])


def _write_context_cache(context: pd.DataFrame, cache_root: Path) -> dict[str, Any]:
    cache_root.mkdir(parents=True, exist_ok=True)
    rows = []
    if not context.empty:
        context = context.copy()
        context["_signal_year"] = pd.to_datetime(context["signal_date"], errors="coerce").dt.year
        for year, part in context.dropna(subset=["_signal_year"]).groupby("_signal_year", sort=True):
            year_int = int(year)
            out_path = cache_root / f"year={year_int}" / "part.parquet"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            part.drop(columns=["_signal_year"]).to_parquet(out_path, index=False)
            rows.append({"year": year_int, "rows": int(part.shape[0]), "path": str(out_path)})
    manifest = {
        "decision": "PASS_CONTEXT_CACHE_BUILT",
        "cache_root": str(cache_root),
        "total_rows": int(context.shape[0]) if not context.empty else 0,
        "years": rows,
    }
    write_json_artifact(cache_root / "_READY.json", manifest)
    return manifest


def _load_context_cache(
    *,
    cache_root: Path,
    hfq_2024_2025: Path,
    hfq_2026: Path,
    augmented_daily: Path,
    years: list[int],
    rebuild: bool,
) -> pd.DataFrame:
    ready = cache_root / "_READY.json"
    if rebuild or not ready.exists():
        context = _load_context_frames(hfq_2024_2025, hfq_2026, augmented_daily)
        _write_context_cache(context, cache_root)
    frames = []
    for year in sorted(set(years)):
        part = cache_root / f"year={year}" / "part.parquet"
        if part.exists():
            frames.append(pd.read_parquet(part))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["signal_date", "code"])


def _vwap_by_group(frame: pd.DataFrame, n: int, prefix: str) -> pd.DataFrame:
    head = frame.groupby("date", sort=False).head(n).copy()
    head["_px_vol"] = pd.to_numeric(head["close"], errors="coerce") * pd.to_numeric(head["vol"], errors="coerce").fillna(0)
    grouped = head.groupby("date", sort=False)
    out = grouped.agg(
        **{
            f"{prefix}_bars": ("trade_time", "count"),
            f"{prefix}_px_vol": ("_px_vol", "sum"),
            f"{prefix}_vol": ("vol", "sum"),
            f"{prefix}_amount": ("amount", "sum"),
            f"{prefix}_high": ("high", "max"),
            f"{prefix}_low": ("low", "min"),
            f"{prefix}_last_close": ("close", "last"),
        }
    )
    out[f"{prefix}_vwap"] = _safe_div(out[f"{prefix}_px_vol"], out[f"{prefix}_vol"])
    return out.drop(columns=[f"{prefix}_px_vol"])


def _features_from_minute_frame(frame: pd.DataFrame, code_hint: str | None = None) -> pd.DataFrame:
    frame = frame.copy()
    frame["code"] = frame["code"].map(_normalize_cn_code)
    if code_hint:
        frame["code"] = code_hint
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    if "date" not in frame.columns:
        frame["date"] = frame["trade_time"].dt.strftime("%Y%m%d")
    frame["date"] = pd.to_datetime(frame["date"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "pre_close" not in frame.columns:
        frame["pre_close"] = pd.NA
    frame = frame.dropna(subset=["trade_time", "date"]).sort_values(["date", "trade_time"])
    grouped = frame.groupby("date", sort=False)
    base = grouped.agg(
        m1_open=("open", "first"),
        m1_pre_close=("pre_close", "first"),
        m1_day_close=("close", "last"),
        m1_day_high=("high", "max"),
        m1_day_low=("low", "min"),
        m1_amount_day=("amount", "sum"),
        m1_vol_day=("vol", "sum"),
        m1_bars_day=("trade_time", "count"),
        m1_pct_chg_first=("pct_chg", "first") if "pct_chg" in frame.columns else ("close", "size"),
    ).reset_index()
    if base["m1_pre_close"].isna().all() and "pct_chg" in frame.columns:
        denom = 1.0 + pd.to_numeric(base["m1_pct_chg_first"], errors="coerce") / 100.0
        base["m1_pre_close"] = pd.to_numeric(base["m1_open"], errors="coerce") / denom.where(denom.abs() > 1e-12)
    if base["m1_pre_close"].isna().any():
        base["m1_pre_close"] = base["m1_pre_close"].fillna(pd.to_numeric(base["m1_day_close"], errors="coerce").shift(1))
    base.insert(0, "code", frame["code"].dropna().iloc[0] if not frame.empty else code_hint)
    for n, prefix in [(5, "m1_first5"), (15, "m1_first15"), (30, "m1_first30")]:
        base = base.merge(_vwap_by_group(frame, n, prefix), left_on="date", right_index=True, how="left")
    base["m1_open_gap_vs_preclose"] = _safe_div(base["m1_open"], base["m1_pre_close"]) - 1.0
    for prefix in ("m1_first5", "m1_first15", "m1_first30"):
        base[f"{prefix}_vwap_return_vs_open"] = _safe_div(base[f"{prefix}_vwap"], base["m1_open"]) - 1.0
        base[f"{prefix}_last_return_vs_open"] = _safe_div(base[f"{prefix}_last_close"], base["m1_open"]) - 1.0
        base[f"{prefix}_range"] = _safe_div(base[f"{prefix}_high"], base[f"{prefix}_low"]) - 1.0
        base[f"label_{prefix}_vwap_to_close"] = _safe_div(base["m1_day_close"], base[f"{prefix}_vwap"]) - 1.0
    base["label_open_to_close"] = _safe_div(base["m1_day_close"], base["m1_open"]) - 1.0
    base["label_day_range"] = _safe_div(base["m1_day_high"], base["m1_day_low"]) - 1.0
    base = base.rename(columns={"date": "exec_date"})
    return base


def _vwap_by_code(frame: pd.DataFrame, n: int, prefix: str) -> pd.DataFrame:
    head = frame.groupby("code", sort=False).head(n).copy()
    head["_px_vol"] = pd.to_numeric(head["close"], errors="coerce") * pd.to_numeric(head["vol"], errors="coerce").fillna(0)
    grouped = head.groupby("code", sort=False)
    out = grouped.agg(
        **{
            f"{prefix}_bars": ("trade_time", "count"),
            f"{prefix}_px_vol": ("_px_vol", "sum"),
            f"{prefix}_vol": ("vol", "sum"),
            f"{prefix}_amount": ("amount", "sum"),
            f"{prefix}_high": ("high", "max"),
            f"{prefix}_low": ("low", "min"),
            f"{prefix}_last_close": ("close", "last"),
        }
    )
    out[f"{prefix}_vwap"] = _safe_div(out[f"{prefix}_px_vol"], out[f"{prefix}_vol"])
    return out.drop(columns=[f"{prefix}_px_vol"])


def _features_from_single_date_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["code"] = frame["code"].map(_normalize_cn_code)
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    if "date" not in frame.columns:
        frame["date"] = frame["trade_time"].dt.strftime("%Y-%m-%d")
    frame["date"] = pd.to_datetime(frame["date"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "pre_close" not in frame.columns:
        frame["pre_close"] = pd.NA
    frame = frame.dropna(subset=["code", "trade_time", "date"]).sort_values(["code", "trade_time"])
    grouped = frame.groupby("code", sort=False)
    base = grouped.agg(
        exec_date=("date", "first"),
        m1_open=("open", "first"),
        m1_pre_close=("pre_close", "first"),
        m1_day_close=("close", "last"),
        m1_day_high=("high", "max"),
        m1_day_low=("low", "min"),
        m1_amount_day=("amount", "sum"),
        m1_vol_day=("vol", "sum"),
        m1_bars_day=("trade_time", "count"),
        m1_pct_chg_first=("pct_chg", "first") if "pct_chg" in frame.columns else ("close", "size"),
    ).reset_index()
    if base["m1_pre_close"].isna().all() and "pct_chg" in frame.columns:
        denom = 1.0 + pd.to_numeric(base["m1_pct_chg_first"], errors="coerce") / 100.0
        base["m1_pre_close"] = pd.to_numeric(base["m1_open"], errors="coerce") / denom.where(denom.abs() > 1e-12)
    for n, prefix in [(5, "m1_first5"), (15, "m1_first15"), (30, "m1_first30")]:
        base = base.merge(_vwap_by_code(frame, n, prefix), left_on="code", right_index=True, how="left")
    base["m1_open_gap_vs_preclose"] = _safe_div(base["m1_open"], base["m1_pre_close"]) - 1.0
    for prefix in ("m1_first5", "m1_first15", "m1_first30"):
        base[f"{prefix}_vwap_return_vs_open"] = _safe_div(base[f"{prefix}_vwap"], base["m1_open"]) - 1.0
        base[f"{prefix}_last_return_vs_open"] = _safe_div(base[f"{prefix}_last_close"], base["m1_open"]) - 1.0
        base[f"{prefix}_range"] = _safe_div(base[f"{prefix}_high"], base[f"{prefix}_low"]) - 1.0
        base[f"label_{prefix}_vwap_to_close"] = _safe_div(base["m1_day_close"], base[f"{prefix}_vwap"]) - 1.0
    base["label_open_to_close"] = _safe_div(base["m1_day_close"], base["m1_open"]) - 1.0
    base["label_day_range"] = _safe_div(base["m1_day_high"], base["m1_day_low"]) - 1.0
    return base


def _symbol_files(symbol_root: Path, year: int, shard_index: int, shard_count: int, limit_symbols: int) -> list[Path]:
    files = sorted((symbol_root / f"year={year}").glob("code=*/part.parquet"))
    if shard_count > 1:
        files = [path for i, path in enumerate(files) if i % shard_count == shard_index]
    return files[:limit_symbols] if limit_symbols > 0 else files


def _date_files(date_root: Path, start_date: str, end_date: str, limit_days: int) -> list[Path]:
    files = sorted(date_root.glob("date=*.parquet"))
    out = []
    for path in files:
        date = path.stem.replace("date=", "")
        if start_date <= date <= end_date:
            out.append(path)
    return out[:limit_days] if limit_days > 0 else out


def _build_symbol_year(
    symbol_root: Path,
    year: int,
    shard_index: int,
    shard_count: int,
    limit_symbols: int,
    progress_path: Path | None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[pd.DataFrame] = []
    manifest: list[dict[str, Any]] = []
    files = _symbol_files(symbol_root, year, shard_index, shard_count, limit_symbols)
    started = time.time()
    _append_jsonl(progress_path, {"event": "symbol_year_start", "year": year, "files": len(files), "shard_index": shard_index, "shard_count": shard_count})
    for i, path in enumerate(files, start=1):
        try:
            code = path.parent.name.replace("code=", "")
            frame = pd.read_parquet(path)
            features = _features_from_minute_frame(frame, code_hint=code)
            rows.append(features)
            manifest.append({"year": year, "path": str(path), "status": "ok", "feature_rows": int(features.shape[0]), "source_rows": int(frame.shape[0]), "index": i, "total": len(files)})
        except Exception as exc:  # noqa: BLE001
            manifest.append({"year": year, "path": str(path), "status": "error", "error": f"{type(exc).__name__}:{str(exc)[:240]}", "index": i, "total": len(files)})
        if i % 100 == 0 or i == len(files):
            _append_jsonl(
                progress_path,
                {
                    "event": "symbol_year_progress",
                    "year": year,
                    "index": i,
                    "total": len(files),
                    "ok": sum(1 for row in manifest if row.get("status") == "ok"),
                    "errors": sum(1 for row in manifest if row.get("status") != "ok"),
                    "elapsed_sec": round(time.time() - started, 3),
                },
            )
    if not rows:
        return pd.DataFrame(), manifest
    return pd.concat(rows, ignore_index=True), manifest


def _build_2026_by_date(
    date_root: Path,
    start_date: str,
    end_date: str,
    limit_days: int,
    progress_path: Path | None,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[pd.DataFrame] = []
    manifest: list[dict[str, Any]] = []
    files = _date_files(date_root, start_date, end_date, limit_days)
    started = time.time()
    _append_jsonl(progress_path, {"event": "date_year_start", "year": 2026, "files": len(files), "start_date": start_date, "end_date": end_date})
    for i, path in enumerate(files, start=1):
        try:
            frame = pd.read_parquet(path)
            features = _features_from_single_date_frame(frame)
            rows.append(features)
            manifest.append({"year": 2026, "path": str(path), "status": "ok", "feature_rows": int(features.shape[0]), "source_rows": int(frame.shape[0]), "index": i, "total": len(files)})
        except Exception as exc:  # noqa: BLE001
            manifest.append({"year": 2026, "path": str(path), "status": "error", "error": f"{type(exc).__name__}:{str(exc)[:240]}", "index": i, "total": len(files)})
        if i % 5 == 0 or i == len(files):
            _append_jsonl(
                progress_path,
                {
                    "event": "date_year_progress",
                    "year": 2026,
                    "index": i,
                    "total": len(files),
                    "ok": sum(1 for row in manifest if row.get("status") == "ok"),
                    "errors": sum(1 for row in manifest if row.get("status") != "ok"),
                    "elapsed_sec": round(time.time() - started, 3),
                },
            )
    if not rows:
        return pd.DataFrame(), manifest
    return pd.concat(rows, ignore_index=True), manifest


def _attach_context(features: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features
    features = features.copy()
    trade_dates = sorted(pd.to_datetime(features["exec_date"], errors="coerce").dropna().dt.strftime("%Y-%m-%d").unique())
    prior = {trade_dates[i]: trade_dates[i - 1] for i in range(1, len(trade_dates))}
    features["signal_date"] = features["exec_date"].map(prior)
    features = features[features["signal_date"].notna()].copy()
    if context.empty:
        return features
    return features.merge(context, on=["signal_date", "code"], how="left")


def _add_cross_features(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    amount_cols = [col for col in ["ctx_hfq_amount_yuan", "ctx_aug_amount"] if col in panel.columns]
    float_mcap_cols = [col for col in ["ctx_hfq_float_market_cap_yuan", "ctx_aug_final_float_market_cap", "ctx_aug_float_market_cap"] if col in panel.columns]
    if amount_cols:
        den = panel[amount_cols[0]]
        for prefix in ("m1_first5", "m1_first15", "m1_first30"):
            panel[f"{prefix}_amount_vs_ctx_amount"] = _safe_div(panel[f"{prefix}_amount"], den)
    if float_mcap_cols:
        den = panel[float_mcap_cols[0]]
        for prefix in ("m1_first5", "m1_first15", "m1_first30"):
            panel[f"{prefix}_amount_vs_ctx_float_mcap"] = _safe_div(panel[f"{prefix}_amount"], den)
    return panel


def _feature_contract(columns: list[str]) -> list[dict[str, str]]:
    out = []
    for column in columns:
        if column in KEY_COLUMNS:
            role = "key"
            earliest = "n/a"
        elif column.startswith("label_"):
            role = "evaluation_label_not_selector_input"
            earliest = "future_after_execution"
        elif column.startswith("m1_first5"):
            role = "minute_native_feature"
            earliest = "09:35"
        elif column.startswith("m1_first15"):
            role = "minute_native_feature"
            earliest = "09:45"
        elif column.startswith("m1_first30"):
            role = "minute_native_feature"
            earliest = "10:00"
        elif column in {"m1_day_close", "m1_day_high", "m1_day_low", "m1_amount_day", "m1_vol_day", "m1_bars_day", "label_open_to_close", "label_day_range"}:
            role = "day_summary_or_label_not_selector_input"
            earliest = "after_close"
        elif column.startswith("m1_"):
            role = "minute_native_feature"
            earliest = "09:30"
        elif column.startswith("ctx_"):
            role = "lagged_daily_context_feature"
            earliest = "prior_trading_day_only"
        else:
            role = "unknown_review_required"
            earliest = "review_required"
        out.append({"field_name": column, "role": role, "earliest_valid_use": earliest})
    return out


def run(
    *,
    years: list[int],
    symbol_minute_root: Path,
    minute_2026_root: Path,
    hfq_2024_2025: Path,
    hfq_2026: Path,
    augmented_daily: Path,
    output_root: Path,
    context_cache_root: Path,
    build_context_cache_only: bool,
    rebuild_context_cache: bool,
    start_date: str,
    end_date: str,
    symbol_shard_index: int,
    symbol_shard_count: int,
    limit_symbols_per_year: int,
    limit_2026_days: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    context = _load_context_cache(
        cache_root=context_cache_root,
        hfq_2024_2025=hfq_2024_2025,
        hfq_2026=hfq_2026,
        augmented_daily=augmented_daily,
        years=years,
        rebuild=rebuild_context_cache,
    )
    if build_context_cache_only:
        summary = {
            "decision": "PASS_MINUTE_FEATURE_PANEL_V2_CONTEXT_CACHE_READY",
            "context_cache_root": str(context_cache_root),
            "context_rows_loaded": int(context.shape[0]),
            "years": years,
        }
        write_json_artifact(output_root / "context_cache_ready_report.json", summary)
        return summary
    manifest_rows: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    started = time.time()
    progress_path = output_root / f"progress_shard{symbol_shard_index:02d}of{symbol_shard_count:02d}_{'_'.join(map(str, years))}.jsonl"
    _append_jsonl(progress_path, {"event": "run_start", "years": years, "context_rows": int(context.shape[0])})
    for year in years:
        if year == 2026:
            features, manifest = _build_2026_by_date(minute_2026_root, start_date, end_date, limit_2026_days, progress_path)
        else:
            features, manifest = _build_symbol_year(symbol_minute_root, year, symbol_shard_index, symbol_shard_count, limit_symbols_per_year, progress_path)
        manifest_rows.extend(manifest)
        _append_jsonl(progress_path, {"event": "feature_rows_built", "year": year, "rows": int(features.shape[0]), "manifest_rows": len(manifest)})
        panel = _attach_context(features, context)
        _append_jsonl(progress_path, {"event": "context_attached", "year": year, "rows": int(panel.shape[0]), "columns": int(panel.shape[1]) if not panel.empty else 0})
        panel = _add_cross_features(panel)
        if panel.empty:
            outputs.append({"year": year, "status": "empty"})
            continue
        year_dir = output_root / f"year={year}"
        year_dir.mkdir(parents=True, exist_ok=True)
        if year == 2026:
            out_path = year_dir / "part.parquet"
        else:
            out_path = year_dir / f"shard={symbol_shard_index:02d}-of-{symbol_shard_count:02d}.parquet"
        panel.to_parquet(out_path, index=False)
        _append_jsonl(progress_path, {"event": "panel_written", "year": year, "path": str(out_path), "rows": int(panel.shape[0]), "columns": int(panel.shape[1])})
        outputs.append(
            {
                "year": year,
                "status": "ok",
                "path": str(out_path),
                "rows": int(panel.shape[0]),
                "columns": int(panel.shape[1]),
                "exec_date_min": str(panel["exec_date"].min()),
                "exec_date_max": str(panel["exec_date"].max()),
                "symbols": int(panel["code"].nunique()),
                "context_any_match_rate": float(panel[[c for c in panel.columns if c.startswith("ctx_")]].notna().any(axis=1).mean())
                if any(c.startswith("ctx_") for c in panel.columns)
                else None,
            }
        )
    _write_csv(output_root / f"manifest_shard{symbol_shard_index:02d}of{symbol_shard_count:02d}.csv", manifest_rows)
    if outputs and outputs[0].get("path"):
        sample_cols = pq.ParquetFile(outputs[0]["path"]).schema_arrow.names
        _write_csv(output_root / "cn_minute_feature_panel_v2_contract.csv", _feature_contract(sample_cols))
    summary = {
        "decision": "PASS_MINUTE_FEATURE_PANEL_V2_SHARD_BUILT" if outputs and all(row.get("status") == "ok" for row in outputs) else "REVIEW_MINUTE_FEATURE_PANEL_V2_SHARD",
        "years": years,
        "symbol_shard_index": symbol_shard_index,
        "symbol_shard_count": symbol_shard_count,
        "limit_symbols_per_year": limit_symbols_per_year,
        "limit_2026_days": limit_2026_days,
        "output_root": str(output_root),
        "outputs": outputs,
        "manifest_rows": len(manifest_rows),
        "manifest_error_count": sum(1 for row in manifest_rows if row.get("status") != "ok"),
        "context_rows": int(context.shape[0]),
        "elapsed_sec": round(time.time() - started, 3),
        "schema_version": "cn_minute_feature_panel_v2_20260602",
        "progress": str(progress_path),
    }
    write_json_artifact(output_root / f"report_shard{symbol_shard_index:02d}of{symbol_shard_count:02d}.json", summary)
    lines = [
        "# CN Minute Feature Panel V2 Shard Report - 2026-06-02",
        "",
        f"decision: `{summary['decision']}`",
        f"years: `{','.join(map(str, years))}`",
        f"shard: `{symbol_shard_index}/{symbol_shard_count}`",
        f"manifest_error_count: `{summary['manifest_error_count']}`",
        f"context_rows: `{summary['context_rows']}`",
        f"elapsed_sec: `{summary['elapsed_sec']}`",
        "",
        "## Boundary",
        "",
        "- Outputs are code-date feature panels, not raw minute-row tables.",
        "- `ctx_*` fields are joined using `signal_date = prior exec_date` only.",
        "- `label_*` and day-summary fields are forbidden for selector input.",
    ]
    (output_root / f"CN_MINUTE_FEATURE_PANEL_V2_SHARD_REPORT_2026-06-02_shard{symbol_shard_index:02d}of{symbol_shard_count:02d}.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="2023,2024,2025,2026")
    parser.add_argument("--symbol-minute-root", type=Path, default=DEFAULT_SYMBOL_MINUTE_ROOT)
    parser.add_argument("--minute-2026-root", type=Path, default=DEFAULT_2026_MINUTE_ROOT)
    parser.add_argument("--hfq-2024-2025", type=Path, default=DEFAULT_HFQ_2024_2025)
    parser.add_argument("--hfq-2026", type=Path, default=DEFAULT_HFQ_2026)
    parser.add_argument("--augmented-daily", type=Path, default=DEFAULT_AUGMENTED_DAILY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--context-cache-root", type=Path, default=DEFAULT_CONTEXT_CACHE)
    parser.add_argument("--build-context-cache-only", action="store_true")
    parser.add_argument("--rebuild-context-cache", action="store_true")
    parser.add_argument("--start-date", default="20260105")
    parser.add_argument("--end-date", default="20260410")
    parser.add_argument("--symbol-shard-index", type=int, default=0)
    parser.add_argument("--symbol-shard-count", type=int, default=1)
    parser.add_argument("--limit-symbols-per-year", type=int, default=0)
    parser.add_argument("--limit-2026-days", type=int, default=0)
    args = parser.parse_args()
    years = [int(item.strip()) for item in args.years.split(",") if item.strip()]
    summary = run(
        years=years,
        symbol_minute_root=args.symbol_minute_root,
        minute_2026_root=args.minute_2026_root,
        hfq_2024_2025=args.hfq_2024_2025,
        hfq_2026=args.hfq_2026,
        augmented_daily=args.augmented_daily,
        output_root=args.output_root,
        context_cache_root=args.context_cache_root,
        build_context_cache_only=bool(args.build_context_cache_only),
        rebuild_context_cache=bool(args.rebuild_context_cache),
        start_date=args.start_date,
        end_date=args.end_date,
        symbol_shard_index=args.symbol_shard_index,
        symbol_shard_count=args.symbol_shard_count,
        limit_symbols_per_year=args.limit_symbols_per_year,
        limit_2026_days=args.limit_2026_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
