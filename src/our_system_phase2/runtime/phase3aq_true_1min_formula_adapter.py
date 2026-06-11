"""Build the Phase3AQ true 1min formula adapter contract and canary panel.

The adapter deliberately keeps `trade_time` as the primary grain. For mature
formula compatibility it also writes `date = trade_time`, while `exec_date`
stores the trading day. This prevents code-date panels from masquerading as
minute-first data.
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
import pyarrow.parquet as pq


REPO = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = Path("runtime/phase3aq_true_1min_formula_adapter_20260610")
RAW_2023_2025 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2023_2025_symbol_parquet_v2"
)
RAW_2026 = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
    r"\stock_1min_2026_parquet_by_date"
)


BASE_FIELD_CONTRACT: list[dict[str, str]] = [
    {
        "field_name": "date",
        "source": "trade_time",
        "role": "cross_section_group_key",
        "true_1min_status": "required",
        "availability": "row_trade_time",
        "formula_allowed": "false_key_only",
        "notes": "Mature evaluator compatibility: date is trade_time, not trading day.",
    },
    {
        "field_name": "exec_date",
        "source": "trade_time.date",
        "role": "trading_day_key",
        "true_1min_status": "required",
        "availability": "row_trade_time",
        "formula_allowed": "false_key_only",
        "notes": "Trading day key for joining lagged context.",
    },
    {
        "field_name": "trade_time",
        "source": "raw_1min.trade_time",
        "role": "primary_timestamp",
        "true_1min_status": "required",
        "availability": "row_trade_time",
        "formula_allowed": "false_key_only",
        "notes": "Primary grain. Any minute-first claim must have this column.",
    },
    {
        "field_name": "volume",
        "source": "raw_1min.vol",
        "role": "raw_minute_alias",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Alias for raw vol. Unit is recorded as raw provider unit.",
    },
    {
        "field_name": "open",
        "source": "raw_1min.open",
        "role": "raw_minute_price",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar open.",
    },
    {
        "field_name": "high",
        "source": "raw_1min.high",
        "role": "raw_minute_price",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar high.",
    },
    {
        "field_name": "low",
        "source": "raw_1min.low",
        "role": "raw_minute_price",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar low.",
    },
    {
        "field_name": "close",
        "source": "raw_1min.close",
        "role": "raw_minute_price",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar close.",
    },
    {
        "field_name": "amount",
        "source": "raw_1min.amount",
        "role": "raw_minute_column",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar amount.",
    },
    {
        "field_name": "amount_yuan",
        "source": "raw_1min.amount",
        "role": "raw_minute_alias",
        "true_1min_status": "direct",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Explicit alias for amount when formulas expect currency flow.",
    },
    {
        "field_name": "vwap",
        "source": "raw_1min.amount/raw_1min.vol with scale inference",
        "role": "minute_bar_vwap_alias",
        "true_1min_status": "direct_with_semantic_note",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute bar VWAP, not full-day VWAP. Scale is inferred per materialization batch.",
    },
    {
        "field_name": "ret_1m",
        "source": "close / prior close by code - 1",
        "role": "minute_return",
        "true_1min_status": "direct_derived",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Use this instead of silently mapping old daily_ret.",
    },
    {
        "field_name": "intraday_ret_from_open",
        "source": "close / first open by code/exec_date - 1",
        "role": "minute_intraday_return",
        "true_1min_status": "direct_derived",
        "availability": "row_trade_time",
        "formula_allowed": "true",
        "notes": "Minute-time return since same-day open. Not an after-close field.",
    },
    {
        "field_name": "daily_ret",
        "source": "none",
        "role": "blocked_legacy_daily_semantic",
        "true_1min_status": "blocked_until_explicit_lagged_daily_context",
        "availability": "n/a",
        "formula_allowed": "false",
        "notes": "Do not alias old daily_ret to minute return. Use ret_1m or an explicit lagged daily context field.",
    },
]


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


def _schema_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    if path.is_dir():
        sample = next(iter(sorted(path.rglob("*.parquet"))), None)
        if sample is None:
            return set()
        return set(pq.ParquetFile(sample).schema_arrow.names)
    return set(pq.ParquetFile(path).schema_arrow.names)


def _select_files(files: list[Path], max_files: int, source_selection: str) -> list[Path]:
    if max_files <= 0 or len(files) <= max_files:
        return files
    if source_selection == "stride":
        positions = np.linspace(0, len(files) - 1, max_files).round().astype(int)
        return [files[int(position)] for position in positions]
    return files[:max_files]


def _shard_files(files: list[Path], shard_count: int, shard_index: int) -> list[Path]:
    if shard_count <= 1:
        return files
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(f"shard_index must be in [0, {shard_count - 1}], got {shard_index}")
    return [path for index, path in enumerate(files) if index % shard_count == shard_index]


def _source_files(
    raw_2023_2025: Path,
    raw_2026: Path,
    *,
    years: list[int],
    max_files: int,
    source_selection: str = "first",
    shard_count: int = 1,
    shard_index: int = 0,
) -> list[Path]:
    files: list[Path] = []
    for year in years:
        if year <= 2025:
            root = raw_2023_2025 / f"year={year}"
            files.extend(sorted(root.glob("code=*/part.parquet")))
        else:
            files.extend(sorted(raw_2026.glob("date=*.parquet")))
    files = _shard_files(files, shard_count=shard_count, shard_index=shard_index)
    return _select_files(files, max_files, source_selection)


def _infer_vwap(amount: pd.Series, volume: pd.Series, close: pd.Series) -> tuple[pd.Series, dict[str, Any]]:
    amount_num = pd.to_numeric(amount, errors="coerce")
    volume_num = pd.to_numeric(volume, errors="coerce")
    close_num = pd.to_numeric(close, errors="coerce")
    raw = amount_num / volume_num.replace(0, np.nan)
    scaled100 = amount_num / (volume_num.replace(0, np.nan) * 100.0)
    raw_error = (raw / close_num.replace(0, np.nan) - 1.0).abs().replace([np.inf, -np.inf], np.nan).median()
    scaled_error = (scaled100 / close_num.replace(0, np.nan) - 1.0).abs().replace([np.inf, -np.inf], np.nan).median()
    use_scale = 100.0 if pd.notna(scaled_error) and (pd.isna(raw_error) or scaled_error < raw_error) else 1.0
    vwap = amount_num / (volume_num.replace(0, np.nan) * use_scale)
    return vwap, {
        "volume_scale_used_for_vwap": use_scale,
        "median_abs_ratio_error_scale1": None if pd.isna(raw_error) else float(raw_error),
        "median_abs_ratio_error_scale100": None if pd.isna(scaled_error) else float(scaled_error),
    }


def _add_opening_window_features(frame: pd.DataFrame, windows: tuple[int, ...] = (5, 15, 30)) -> pd.DataFrame:
    frame = frame.sort_values(["code", "trade_time"]).copy()
    frame["_bar_index"] = frame.groupby(["code", "exec_date"], sort=False).cumcount() + 1
    grouped = frame.groupby(["code", "exec_date"], sort=False)
    for window in windows:
        prefix = f"m1_first{window}"
        first = grouped.head(window)
        agg = first.groupby(["code", "exec_date"], sort=False).agg(
            **{
                f"{prefix}_bars": ("close", "count"),
                f"{prefix}_vol": ("volume", "sum"),
                f"{prefix}_amount": ("amount", "sum"),
                f"{prefix}_high": ("high", "max"),
                f"{prefix}_low": ("low", "min"),
                f"{prefix}_last_close": ("close", "last"),
                "_open_for_window": ("open", "first"),
            }
        )
        agg[f"{prefix}_vwap"], _ = _infer_vwap(agg[f"{prefix}_amount"], agg[f"{prefix}_vol"], agg[f"{prefix}_last_close"])
        agg[f"{prefix}_vwap_return_vs_open"] = agg[f"{prefix}_vwap"] / agg["_open_for_window"].replace(0, np.nan) - 1.0
        agg[f"{prefix}_last_return_vs_open"] = agg[f"{prefix}_last_close"] / agg["_open_for_window"].replace(0, np.nan) - 1.0
        agg[f"{prefix}_range"] = agg[f"{prefix}_high"] / agg[f"{prefix}_low"].replace(0, np.nan) - 1.0
        agg = agg.drop(columns=["_open_for_window"]).reset_index()
        frame = frame.merge(agg, on=["code", "exec_date"], how="left")
        feature_cols = [col for col in agg.columns if col not in {"code", "exec_date"}]
        mask_unavailable = frame["_bar_index"] < window
        frame.loc[mask_unavailable, feature_cols] = np.nan
    return frame.drop(columns=["_bar_index"])


def _normalize_raw_minute(files: list[Path]) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    read_rows = 0
    for path in files:
        part = pd.read_parquet(path)
        read_rows += len(part)
        required = {"code", "trade_time", "open", "high", "low", "close", "vol", "amount"}
        missing = required.difference(part.columns)
        if missing:
            continue
        keep = [col for col in ["code", "trade_time", "date", "open", "high", "low", "close", "vol", "amount", "pct_chg", "pre_close"] if col in part.columns]
        frames.append(part[keep])
    if not frames:
        return pd.DataFrame(), {"read_rows": read_rows, "kept_rows": 0}
    frame = pd.concat(frames, ignore_index=True)
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame = frame.dropna(subset=["code", "trade_time", "close"]).copy()
    frame["code"] = frame["code"].astype(str)
    frame["exec_date"] = frame["trade_time"].dt.date.astype(str)
    frame["date"] = frame["trade_time"]
    frame["signal_time"] = frame["trade_time"]
    frame["volume"] = pd.to_numeric(frame["vol"], errors="coerce")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    frame["amount_yuan"] = frame["amount"]
    for col in ["open", "high", "low", "close"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["vwap"], vwap_report = _infer_vwap(frame["amount"], frame["volume"], frame["close"])
    frame = frame.sort_values(["code", "trade_time"]).reset_index(drop=True)
    frame["ret_1m"] = frame.groupby("code", sort=False)["close"].pct_change()
    if "pre_close" in frame.columns:
        first_mask = frame.groupby(["code", "exec_date"], sort=False).cumcount() == 0
        pre_close = pd.to_numeric(frame["pre_close"], errors="coerce")
        frame.loc[first_mask, "ret_1m"] = frame.loc[first_mask, "close"] / pre_close.loc[first_mask].replace(0, np.nan) - 1.0
    frame["intraday_ret_from_open"] = frame["close"] / frame.groupby(["code", "exec_date"], sort=False)["open"].transform("first").replace(0, np.nan) - 1.0
    frame["dataset_route_id"] = "phase3aq_true_1min_trade_time_v1"
    frame["label_horizon"] = "not_materialized_adapter_contract_only"
    frame = _add_opening_window_features(frame)
    report = {
        "read_rows": read_rows,
        "kept_rows": int(len(frame)),
        "code_count": int(frame["code"].nunique()),
        "trade_time_count": int(frame["trade_time"].nunique()),
        **vwap_report,
    }
    return frame, report


def _field_contract() -> list[dict[str, str]]:
    rows = list(BASE_FIELD_CONTRACT)
    for window in (5, 15, 30):
        available = f"after_first_{window}_minute"
        for suffix, role in (
            ("bars", "opening_window_count"),
            ("vol", "opening_window_volume"),
            ("amount", "opening_window_amount"),
            ("high", "opening_window_price"),
            ("low", "opening_window_price"),
            ("last_close", "opening_window_price"),
            ("vwap", "opening_window_vwap"),
            ("vwap_return_vs_open", "opening_window_return"),
            ("last_return_vs_open", "opening_window_return"),
            ("range", "opening_window_range"),
        ):
            rows.append(
                {
                    "field_name": f"m1_first{window}_{suffix}",
                    "source": f"raw_1min first {window} rows by code/exec_date",
                    "role": role,
                    "true_1min_status": "recomputed_on_trade_time_backbone",
                    "availability": available,
                    "formula_allowed": "true_after_availability",
                    "notes": "Opening-window feature. Not a separate data frequency.",
                }
            )
    return rows


def build_adapter(
    *,
    output_root: Path,
    raw_2023_2025: Path,
    raw_2026: Path,
    years: list[int],
    max_files: int,
    materialize_canary: bool,
    source_selection: str = "first",
    shard_count: int = 1,
    shard_index: int = 0,
) -> dict[str, Any]:
    output_root = _resolve(output_root)
    raw_2023_2025 = _resolve(raw_2023_2025)
    raw_2026 = _resolve(raw_2026)
    output_root.mkdir(parents=True, exist_ok=True)

    raw_schema_2025 = _schema_names(raw_2023_2025 / "year=2025")
    raw_schema_2026 = _schema_names(raw_2026)
    contract_rows = _field_contract()
    rewrite_rules = {
        "safe_aliases": {
            "$vol": "$volume",
            "$amount": "$amount",
            "$amount_yuan": "$amount_yuan",
            "$close": "$close",
            "$open": "$open",
            "$high": "$high",
            "$low": "$low",
            "$vwap": "$vwap",
        },
        "blocked_legacy_aliases": {
            "$daily_ret": "blocked: use $ret_1m for minute return or explicit lagged daily context",
            "$return_1d": "blocked until explicit lagged daily context is materialized",
            "$final_float_market_cap": "requires lagged context sidecar mapping",
            "$final_total_market_cap": "requires lagged context sidecar mapping",
            "$float_share": "requires lagged context sidecar mapping",
        },
        "opening_window_policy": "m1_firstN_* fields are features with availability guards, not data segmentation.",
    }
    _write_csv(output_root / "phase3aq_true_1min_field_contract.csv", contract_rows)
    _write_json(output_root / "phase3aq_formula_rewrite_rules.json", rewrite_rules)

    canary_report: dict[str, Any] = {"materialized": False}
    if materialize_canary:
        files = _source_files(
            raw_2023_2025,
            raw_2026,
            years=years,
            max_files=max_files,
            source_selection=source_selection,
            shard_count=shard_count,
            shard_index=shard_index,
        )
        panel, panel_report = _normalize_raw_minute(files)
        canary_report = {
            "materialized": True,
            "source_selection": source_selection,
            "shard_count": shard_count,
            "shard_index": shard_index,
            "source_file_count": len(files),
            "source_files": [str(path) for path in files[:20]],
            **panel_report,
        }
        if not panel.empty:
            out_panel = output_root / "canary" / "phase3aq_true_1min_formula_canary.parquet"
            out_panel.parent.mkdir(parents=True, exist_ok=True)
            panel.to_parquet(out_panel, index=False)
            canary_report["panel_path"] = str(out_panel)
            canary_report["columns"] = list(panel.columns)
            canary_report["has_trade_time"] = "trade_time" in panel.columns
            canary_report["date_equals_trade_time"] = bool((pd.to_datetime(panel["date"]) == pd.to_datetime(panel["trade_time"])).all())

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PHASE3AQ_TRUE_1MIN_FORMULA_ADAPTER_READY_FOR_CANARY_SEARCH_PREP",
        "output_root": str(output_root),
        "raw_sources": {
            "stock_1min_2023_2025_symbol_parquet_v2": str(raw_2023_2025),
            "stock_1min_2026_parquet_by_date": str(raw_2026),
        },
        "raw_schema_checks": {
            "schema_2025_has_trade_time": "trade_time" in raw_schema_2025,
            "schema_2026_has_trade_time": "trade_time" in raw_schema_2026,
            "schema_2025_columns": sorted(raw_schema_2025),
            "schema_2026_columns": sorted(raw_schema_2026),
        },
        "field_contract_path": str(output_root / "phase3aq_true_1min_field_contract.csv"),
        "rewrite_rules_path": str(output_root / "phase3aq_formula_rewrite_rules.json"),
        "canary": canary_report,
        "hard_rules": [
            "minute_first requires trade_time",
            "date is trade_time for mature formula cross-sectional grouping",
            "exec_date is the trading-day join key",
            "firstN fields are opening-window features, not 5/15/30min data segmentation",
            "daily_ret is blocked until explicit lagged daily context exists",
        ],
    }
    _write_json(output_root / "phase3aq_true_1min_formula_adapter_report.json", summary)
    lines = [
        "# Phase3AQ True 1min Formula Adapter",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Contract",
        "",
        "- `trade_time` is the primary grain.",
        "- `date` is set to `trade_time` only for mature evaluator compatibility.",
        "- `exec_date` stores the trading day for lagged context joins.",
        "- `first5/first15/first30` are opening-window fields, not data segmentation.",
        "- `daily_ret` is blocked until an explicit lagged daily context field is materialized.",
        "",
        "## Outputs",
        "",
        f"- field contract: `{summary['field_contract_path']}`",
        f"- rewrite rules: `{summary['rewrite_rules_path']}`",
    ]
    if canary_report.get("materialized"):
        lines.append(f"- canary panel: `{canary_report.get('panel_path', '')}`")
    (output_root / "PHASE3AQ_TRUE_1MIN_FORMULA_ADAPTER_20260610.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--raw-2023-2025", type=Path, default=RAW_2023_2025)
    parser.add_argument("--raw-2026", type=Path, default=RAW_2026)
    parser.add_argument("--years", default="2025,2026")
    parser.add_argument("--max-files", type=int, default=12)
    parser.add_argument("--source-selection", choices=["first", "stride"], default="first")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--materialize-canary", action="store_true")
    args = parser.parse_args()
    years = [int(item.strip()) for item in args.years.split(",") if item.strip()]
    summary = build_adapter(
        output_root=args.output_root,
        raw_2023_2025=args.raw_2023_2025,
        raw_2026=args.raw_2026,
        years=years,
        max_files=args.max_files,
        materialize_canary=args.materialize_canary,
        source_selection=args.source_selection,
        shard_count=args.shard_count,
        shard_index=args.shard_index,
    )
    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "field_contract_path": summary["field_contract_path"],
                "rewrite_rules_path": summary["rewrite_rules_path"],
                "canary": summary["canary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
