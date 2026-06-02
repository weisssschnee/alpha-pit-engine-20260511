"""Canonicalize the ZZShare limit/sentiment pack into clean PIT join grains."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_PACK_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_PACK_ROOT / "canonical_v1"
DEFAULT_REPORT = Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_CANONICAL_V1_2026-06-02.md")

FEATURE_BLOCKED_PREFIXES = ("next_",)
NUMERIC_HINTS = (
    "amount",
    "auction",
    "fd_",
    "_num",
    "count",
    "ratio",
    "pct",
    "price",
    "rank",
    "value",
    "strong",
    "ztjs",
    "df_num",
    "lbgd",
    "vol",
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_string_dtype(out[column]) or out[column].dtype == object:
            out[column] = out[column].astype("string").str.strip()
            out[column] = out[column].mask(out[column].isin(["", "None", "nan", "NaN"]))
    return out


def _normalize_code(value: Any) -> str | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if "." in raw:
        code = raw.split(".")[0].zfill(6)
    else:
        code = raw.zfill(6)
    first = code[0]
    if first in {"6", "9"}:
        suffix = "SH"
    elif first in {"0", "2", "3"}:
        suffix = "SZ"
    elif first in {"4", "8"}:
        suffix = "BJ"
    else:
        suffix = "UNK"
    return f"{code}.{suffix}"


def _maybe_numeric_columns(frame: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for column in frame.columns:
        lower = column.lower()
        if any(token in lower for token in NUMERIC_HINTS):
            cols.append(column)
    return cols


def _to_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _first_nonnull(values: pd.Series) -> Any:
    nonnull = values.dropna()
    return nonnull.iloc[0] if len(nonnull) else pd.NA


def _join_unique(values: pd.Series) -> str | None:
    items = sorted({str(item) for item in values.dropna() if str(item)})
    return "|".join(items) if items else None


def _last_by_date(frame: pd.DataFrame, date_col: str) -> pd.DataFrame:
    sort_cols = [column for column in ["download_time", "request_date", "id"] if column in frame.columns]
    if sort_cols:
        frame = frame.sort_values(sort_cols)
    raw_rows = frame.groupby(date_col).size().rename("raw_rows_per_date")
    dedup = frame.drop_duplicates(subset=[date_col], keep="last").copy()
    dedup = dedup.merge(raw_rows.reset_index(), on=date_col, how="left")
    return dedup


def _canonical_uplimit(pack_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = _clean_frame(pd.read_parquet(pack_root / "silver_parquet" / "uplimit_stocks.parquet"))
    raw["date"] = pd.to_datetime(raw["date1"], errors="coerce").dt.date.astype("string")
    raw["code"] = raw["stock_code"].map(_normalize_code)
    raw["up_limit_event_time"] = raw["up_limit_time"]
    feature_cols = [column for column in raw.columns if not column.startswith(FEATURE_BLOCKED_PREFIXES)]
    feature = raw[feature_cols].copy()
    numeric_cols = [column for column in _maybe_numeric_columns(feature) if column not in {"stock_code"}]
    feature = _to_numeric(feature, numeric_cols)
    group_cols = ["date", "code"]
    agg: dict[str, Any] = {}
    for column in feature.columns:
        if column in group_cols:
            continue
        if column in {"plate_code", "up_limit_desc"}:
            agg[column] = _join_unique
        elif column == "up_limit_time" or column == "up_limit_event_time":
            agg[column] = "min"
        elif pd.api.types.is_numeric_dtype(feature[column]):
            agg[column] = "max"
        else:
            agg[column] = _first_nonnull
    canonical = feature.groupby(group_cols, as_index=False).agg(agg)
    canonical["raw_rows_per_code_date"] = feature.groupby(group_cols).size().to_numpy()
    canonical["source_dataset"] = "uplimit_stocks"
    labels = raw[["date", "code", *[col for col in raw.columns if col.startswith(FEATURE_BLOCKED_PREFIXES)]]].drop_duplicates()
    return canonical, {
        "raw_rows": int(len(raw)),
        "canonical_rows": int(len(canonical)),
        "date_count": int(canonical["date"].nunique()),
        "code_count": int(canonical["code"].nunique()),
        "max_raw_rows_per_code_date": int(canonical["raw_rows_per_code_date"].max()),
        "feature_future_label_columns_excluded": [col for col in raw.columns if col.startswith(FEATURE_BLOCKED_PREFIXES)],
        "future_label_audit_rows": int(len(labels)),
    }


def _canonical_open_sentiment(pack_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = _clean_frame(pd.read_parquet(pack_root / "silver_parquet" / "open_sentiment_data.parquet"))
    raw["date"] = pd.to_datetime(raw["date1"], errors="coerce").dt.date.astype("string")
    daily = _last_by_date(raw, "date")
    daily = _to_numeric(daily, _maybe_numeric_columns(daily))
    daily["source_dataset"] = "open_sentiment_data"
    return daily, {
        "raw_rows": int(len(raw)),
        "canonical_rows": int(len(daily)),
        "date_count": int(daily["date"].nunique()),
        "max_raw_rows_per_date": int(daily["raw_rows_per_date"].max()),
    }


def _canonical_hot_day(pack_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = _clean_frame(pd.read_parquet(pack_root / "silver_parquet" / "sentiment_hot_day.parquet"))
    raw["date"] = pd.to_datetime(raw["Day"], errors="coerce").dt.date.astype("string")
    daily = _last_by_date(raw, "date")
    daily = _to_numeric(daily, _maybe_numeric_columns(daily))
    daily["source_dataset"] = "sentiment_hot_day"
    return daily, {
        "raw_rows": int(len(raw)),
        "canonical_rows": int(len(daily)),
        "date_count": int(daily["date"].nunique()),
        "max_raw_rows_per_date": int(daily["raw_rows_per_date"].max()),
    }


def _canonical_ths_hot(pack_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = _clean_frame(pd.read_parquet(pack_root / "silver_parquet" / "ths_hot_top.parquet"))
    raw["date"] = pd.to_datetime(raw["collect_date"], errors="coerce").dt.date.astype("string")
    raw["code"] = raw["symbol_code"].map(_normalize_code)
    raw = _to_numeric(raw, _maybe_numeric_columns(raw))
    sort_cols = [column for column in ["download_time", "request_date", "rank"] if column in raw.columns]
    if sort_cols:
        raw = raw.sort_values(sort_cols)
    canonical = raw.drop_duplicates(subset=["date", "code"], keep="last").copy()
    canonical["source_dataset"] = "ths_hot_top"
    return canonical, {
        "raw_rows": int(len(raw)),
        "canonical_rows": int(len(canonical)),
        "date_count": int(canonical["date"].nunique()),
        "code_count": int(canonical["code"].nunique()),
        "max_raw_rows_per_code_date": int(raw.groupby(["date", "code"]).size().max()),
    }


def canonicalize(*, pack_root: Path, output_root: Path, report_path: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    tables: list[tuple[str, pd.DataFrame, dict[str, Any]]] = []
    for name, builder in [
        ("uplimit_stock_event_day", _canonical_uplimit),
        ("open_sentiment_daily", _canonical_open_sentiment),
        ("sentiment_hot_daily", _canonical_hot_day),
        ("ths_hot_stock_day", _canonical_ths_hot),
    ]:
        frame, metrics = builder(pack_root)
        out_path = output_root / f"{name}.parquet"
        frame.to_parquet(out_path, index=False)
        metrics["output"] = str(out_path)
        tables.append((name, frame, metrics))

    summary = {
        "decision": "PASS_ZZSHARE_CANONICAL_V1_WITH_GRAIN_FIXES",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pack_root": str(pack_root),
        "output_root": str(output_root),
        "tables": {name: metrics for name, _, metrics in tables},
        "pit_policy": {
            "uplimit_stock_event_day": "stock-date event table; minute use only after up_limit_time, otherwise T+1",
            "open_sentiment_daily": "T+1 lagged market context",
            "sentiment_hot_daily": "T+1 lagged market context",
            "ths_hot_stock_day": "T+1 lagged stock hot-rank context",
            "future_labels": "next_* excluded from feature table",
        },
    }
    _write_json(output_root / "canonicalization_report.json", summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown(summary), encoding="utf-8")
    return summary


def _markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# CN ZZShare Limit/Sentiment Canonical V1",
        "",
        f"decision: `{summary['decision']}`",
        "",
        "## Tables",
        "",
    ]
    for name, metrics in summary["tables"].items():
        lines.append(
            f"- `{name}`: raw_rows=`{metrics['raw_rows']}`, canonical_rows=`{metrics['canonical_rows']}`, output=`{metrics['output']}`"
        )
    lines.extend(
        [
            "",
            "## Grain Fixes",
            "",
            "- `open_sentiment_data` and `sentiment_hot_day` are compressed to one canonical row per date.",
            "- `uplimit_stocks` is compressed to stock-date event rows; repeated plate/theme rows are retained as joined lists.",
            "- `next_*` fields are excluded from the feature table and remain labels/audit only.",
            "- All market sentiment and hot-rank outputs are T+1 context until observable timestamps are proven.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    summary = canonicalize(pack_root=args.pack_root, output_root=args.output_root, report_path=args.report)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
