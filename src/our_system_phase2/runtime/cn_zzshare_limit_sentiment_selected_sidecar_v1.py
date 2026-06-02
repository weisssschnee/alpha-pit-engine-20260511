"""Build a selected-row ZZShare sidecar using canonical PIT grains."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INDEX_SIDECAR = Path("runtime/cn_integrated_pit_selected_sidecars_20260602/nonminute_selected_sidecar.parquet")
DEFAULT_CANONICAL_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602\canonical_v1"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_zzshare_limit_sentiment_selected_sidecar_v1_20260602")
DEFAULT_REPORT = Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_SELECTED_SIDECAR_V1_2026-06-02.md")

KEY_COLUMNS = ["join_code", "date"]
BLOCK_PREFIXES = ("next_",)
TEXT_COLUMNS = {
    "stock_name",
    "symbol_name",
    "up_limit_desc",
    "plate_code",
    "max_lb_stocks",
    "tip",
    "ttag",
    "source_dataset",
    "dataset",
    "download_time",
    "request_date",
}
NON_FEATURE_COLUMNS = {
    "date",
    "code",
    "join_code",
    "zzshare_lag_date",
    "Day",
    "date1",
    "collect_date",
    "id",
    "stock_code",
    "symbol_code",
}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_index(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=KEY_COLUMNS)
    frame = frame.drop_duplicates().copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    return frame.sort_values(KEY_COLUMNS).reset_index(drop=True)


def _lag_map(index: pd.DataFrame) -> pd.DataFrame:
    dates = pd.Series(sorted(index["date"].dropna().unique()), name="date")
    out = pd.DataFrame({"date": dates})
    out["zzshare_lag_date"] = out["date"].shift(1)
    return out


def _numeric_feature_columns(frame: pd.DataFrame, *, exclude: set[str]) -> list[str]:
    cols: list[str] = []
    for column in frame.columns:
        if column in exclude or column in TEXT_COLUMNS or column in NON_FEATURE_COLUMNS or column.startswith(BLOCK_PREFIXES):
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        if converted.notna().sum() > 0:
            frame[column] = converted
            cols.append(column)
    return cols


def _market_daily(index: pd.DataFrame, lag_dates: pd.DataFrame, canonical_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    left = index[KEY_COLUMNS].merge(lag_dates, on="date", how="left")
    daily_tables = [
        ("open_sentiment_daily", "ctx_zls_open"),
        ("sentiment_hot_daily", "ctx_zls_hot"),
    ]
    metrics: dict[str, Any] = {}
    out = left[KEY_COLUMNS].copy()
    for table, prefix in daily_tables:
        frame = pd.read_parquet(canonical_root / f"{table}.parquet")
        frame["zzshare_lag_date"] = pd.to_datetime(frame["date"], errors="coerce")
        features = _numeric_feature_columns(frame, exclude={"raw_rows_per_date"})
        renamed = frame[["zzshare_lag_date", *features]].rename(columns={field: f"{prefix}_{field}" for field in features})
        out = out.merge(left[["date", "zzshare_lag_date"]].drop_duplicates().merge(renamed, on="zzshare_lag_date", how="left").drop(columns=["zzshare_lag_date"]), on="date", how="left")
        cols = [f"{prefix}_{field}" for field in features]
        metrics[table] = {
            "feature_count": len(cols),
            "mean_nonnull_rate": float(out[cols].notna().mean().mean()) if cols else 0.0,
        }
    return out, metrics


def _stock_previous_day(index: pd.DataFrame, lag_dates: pd.DataFrame, canonical_root: Path, table: str, prefix: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    left = index[KEY_COLUMNS].merge(lag_dates, on="date", how="left")
    frame = pd.read_parquet(canonical_root / f"{table}.parquet")
    frame["zzshare_lag_date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["join_code"] = frame["code"].astype("string")
    features = _numeric_feature_columns(frame, exclude={"raw_rows_per_code_date"})
    right = frame[["join_code", "zzshare_lag_date", *features]].rename(columns={field: f"{prefix}_{field}" for field in features})
    out = left.merge(right, on=["join_code", "zzshare_lag_date"], how="left").drop(columns=["zzshare_lag_date"])
    cols = [f"{prefix}_{field}" for field in features]
    return out, {
        "feature_count": len(cols),
        "mean_nonnull_rate": float(out[cols].notna().mean().mean()) if cols else 0.0,
        "matched_rows": int(out[cols].notna().any(axis=1).sum()) if cols else 0,
    }


def build_sidecar(*, index_sidecar: Path, canonical_root: Path, output_root: Path, report_path: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    index = _load_index(index_sidecar)
    lag_dates = _lag_map(index)

    market, market_metrics = _market_daily(index, lag_dates, canonical_root)
    uplimit, uplimit_metrics = _stock_previous_day(index, lag_dates, canonical_root, "uplimit_stock_event_day", "evt_zls_prev")
    hot, hot_metrics = _stock_previous_day(index, lag_dates, canonical_root, "ths_hot_stock_day", "ctx_zls_ths_prev")

    sidecar = index.copy()
    for frame in [market, uplimit, hot]:
        extra_cols = [column for column in frame.columns if column not in KEY_COLUMNS]
        sidecar = sidecar.merge(frame[KEY_COLUMNS + extra_cols], on=KEY_COLUMNS, how="left")

    output_path = output_root / "zzshare_selected_sidecar.parquet"
    sidecar.to_parquet(output_path, index=False)
    feature_cols = [column for column in sidecar.columns if column not in KEY_COLUMNS]
    summary = {
        "decision": "PASS_ZZSHARE_SELECTED_SIDECAR_V1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "index_sidecar": str(index_sidecar),
        "canonical_root": str(canonical_root),
        "output": str(output_path),
        "rows": int(len(sidecar)),
        "date_min": str(sidecar["date"].min().date()),
        "date_max": str(sidecar["date"].max().date()),
        "feature_count": len(feature_cols),
        "mean_feature_nonnull_rate": float(sidecar[feature_cols].notna().mean().mean()) if feature_cols else 0.0,
        "tables": {
            "market_daily": market_metrics,
            "uplimit_stock_event_day": uplimit_metrics,
            "ths_hot_stock_day": hot_metrics,
        },
        "pit_policy": {
            "join": "selected replay row date uses previous selected trading date as zzshare_lag_date",
            "uplimit": "previous-day stock event only; no same-day up_limit_time event is used in this daily sidecar",
            "daily_context": "market sentiment and hot-rank fields are T+1 lagged",
            "future_labels": "next_* excluded upstream and absent from sidecar",
        },
    }
    _write_json(output_root / "sidecar_report.json", summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown(summary), encoding="utf-8")
    return summary


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# CN ZZShare Limit/Sentiment Selected Sidecar v1",
        "",
        f"decision: `{summary['decision']}`",
        f"rows: `{summary['rows']}`",
        f"feature_count: `{summary['feature_count']}`",
        f"mean_feature_nonnull_rate: `{summary['mean_feature_nonnull_rate']:.6f}`",
        f"date_range: `{summary['date_min']}..{summary['date_max']}`",
        "",
        "## Table Coverage",
        "",
    ]
    for table, metrics in summary["tables"].items():
        lines.append(f"- `{table}`: `{metrics}`")
    lines.extend(
        [
            "",
            "## PIT Policy",
            "",
            "- Every feature uses the previous selected trading date.",
            "- Same-day `up_limit_time` minute-event usage is not included in this daily sidecar.",
            "- `next_*` labels are absent.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-sidecar", type=Path, default=DEFAULT_INDEX_SIDECAR)
    parser.add_argument("--canonical-root", type=Path, default=DEFAULT_CANONICAL_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    summary = build_sidecar(
        index_sidecar=args.index_sidecar,
        canonical_root=args.canonical_root,
        output_root=args.output_root,
        report_path=args.report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
