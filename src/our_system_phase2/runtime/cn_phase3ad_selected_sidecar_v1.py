"""Build selected-row sidecar for Phase3AD new-data fields.

This materializes the Phase3AD alias map onto the mature selected replay index.
It does not generate candidates, run selectors, or replay alpha performance.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_INDEX_SIDECAR = Path("runtime/cn_integrated_pit_selected_sidecars_20260602/nonminute_selected_sidecar.parquet")
DEFAULT_ALIAS_MAP = Path("reports/cn_phase3ad_new_data_factor_pack_v1_20260603/field_alias_map.csv")
DEFAULT_OUTPUT_ROOT = Path("runtime/cn_phase3ad_selected_sidecar_v1_20260603")
DEFAULT_REPORT_ROOT = Path("reports/cn_phase3ad_selected_sidecar_v1_20260603")

KEY_COLUMNS = ["join_code", "date"]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _load_index(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=KEY_COLUMNS)
    frame = frame.drop_duplicates().copy()
    frame["date"] = _to_date(frame["date"])
    frame["code6"] = frame["join_code"].astype("string").str.slice(0, 6)
    return frame.sort_values(["date", "join_code"]).reset_index(drop=True)


def _lag_dates(index: pd.DataFrame) -> pd.DataFrame:
    dates = pd.Series(sorted(index["date"].dropna().unique()), name="date")
    out = pd.DataFrame({"date": dates})
    out["lag_date"] = out["date"].shift(1)
    return out


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _dataset_aliases(aliases: list[dict[str, Any]], dataset: str) -> list[dict[str, Any]]:
    return [row for row in aliases if str(row.get("dataset") or "") == dataset]


def _source_columns(rows: list[dict[str, Any]], required: list[str]) -> list[str]:
    cols = list(required)
    for row in rows:
        raw = str(row.get("raw_field") or "")
        if raw and raw not in cols:
            cols.append(raw)
    return cols


def _effective_notice_date(frame: pd.DataFrame) -> pd.Series:
    notice = _to_date(frame["NOTICE_DATE"]) if "NOTICE_DATE" in frame.columns else pd.Series(pd.NaT, index=frame.index)
    update = _to_date(frame["UPDATE_DATE"]) if "UPDATE_DATE" in frame.columns else pd.Series(pd.NaT, index=frame.index)
    effective = pd.concat([notice, update], axis=1).max(axis=1)
    return effective + pd.Timedelta(days=1)


def _asof_by_code(left: pd.DataFrame, right: pd.DataFrame, *, value_columns: list[str]) -> pd.DataFrame:
    """Conservative grouped asof join by code6.

    A grouped loop is slower than a single merge_asof, but it avoids subtle
    sort-order mistakes and keeps this pre-search materialization gate simple.
    """

    left_work = left[["__row_id", "code6", "date"]].copy()
    right_work = right[["code6", "available_date", *value_columns]].copy()
    chunks: list[pd.DataFrame] = []
    right_groups = {str(code): group.sort_values("available_date") for code, group in right_work.groupby("code6", sort=False)}

    def _empty_values(row_ids: pd.Series) -> pd.DataFrame:
        base = pd.DataFrame({"__row_id": row_ids.to_numpy()})
        if not value_columns:
            return base
        values = pd.DataFrame(pd.NA, index=base.index, columns=value_columns)
        return pd.concat([base, values], axis=1)

    empty = _empty_values(left_work["__row_id"])
    for code, left_group in left_work.groupby("code6", sort=False):
        right_group = right_groups.get(str(code))
        if right_group is None or right_group.empty:
            chunk = _empty_values(left_group["__row_id"])
        else:
            merged = pd.merge_asof(
                left_group.sort_values("date"),
                right_group,
                left_on="date",
                right_on="available_date",
                direction="backward",
            )
            chunk = merged[["__row_id", *value_columns]]
        chunks.append(chunk)
    if not chunks:
        return empty
    return pd.concat(chunks, ignore_index=True)


def _materialize_fundamental(index: pd.DataFrame, rows: list[dict[str, Any]], dataset: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not rows:
        return index[["__row_id"]].copy(), {"feature_count": 0}
    path = Path(str(rows[0]["materialized_path"]))
    raw_to_panel = {str(row["raw_field"]): str(row["panel_field"]) for row in rows}
    columns = _source_columns(rows, ["source_code6", "REPORT_DATE", "NOTICE_DATE", "UPDATE_DATE"])
    source = pd.read_parquet(path, columns=columns)
    source["code6"] = source["source_code6"].astype("string").str.zfill(6)
    source["REPORT_DATE"] = _to_date(source["REPORT_DATE"])
    source["available_date"] = _effective_notice_date(source)
    source = source.dropna(subset=["code6", "REPORT_DATE", "available_date"])
    for raw in raw_to_panel:
        source[raw] = _numeric(source, raw)
    source = source.sort_values(["code6", "available_date", "REPORT_DATE"])
    source = source.drop_duplicates(["code6", "available_date"], keep="last")
    joined = _asof_by_code(index, source, value_columns=list(raw_to_panel))
    joined = joined.rename(columns=raw_to_panel)
    feature_cols = list(raw_to_panel.values())
    return joined[["__row_id", *feature_cols]], {
        "dataset": dataset,
        "source_path": str(path),
        "source_rows": int(len(source)),
        "feature_count": len(feature_cols),
        "pit_policy": "max(NOTICE_DATE, UPDATE_DATE) + 1 calendar day; REPORT_DATE alone is never used for availability",
    }


def _materialize_market_lag(index: pd.DataFrame, lag_dates: pd.DataFrame, rows: list[dict[str, Any]], dataset: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not rows:
        return index[["__row_id"]].copy(), {"feature_count": 0}
    path = Path(str(rows[0]["materialized_path"]))
    raw_to_panel = {str(row["raw_field"]): str(row["panel_field"]) for row in rows}
    columns = _source_columns(rows, ["date"])
    source = pd.read_parquet(path, columns=columns)
    source["lag_date"] = _to_date(source["date"])
    for raw in raw_to_panel:
        source[raw] = _numeric(source, raw)
    source = source.sort_values("lag_date").drop_duplicates(["lag_date"], keep="last")
    right = source[["lag_date", *raw_to_panel]].rename(columns=raw_to_panel)
    left = index[["__row_id", "date"]].merge(lag_dates, on="date", how="left")
    out = left.merge(right, on="lag_date", how="left").drop(columns=["date", "lag_date"])
    return out, {
        "dataset": dataset,
        "source_path": str(path),
        "source_rows": int(len(source)),
        "feature_count": len(raw_to_panel),
        "pit_policy": "previous selected trading date broadcast to all stocks",
    }


def _materialize_stock_lag(index: pd.DataFrame, lag_dates: pd.DataFrame, rows: list[dict[str, Any]], dataset: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    if not rows:
        return index[["__row_id"]].copy(), {"feature_count": 0}
    path = Path(str(rows[0]["materialized_path"]))
    raw_to_panel = {str(row["raw_field"]): str(row["panel_field"]) for row in rows}
    columns = _source_columns(rows, ["date", "code"])
    source = pd.read_parquet(path, columns=columns)
    source["lag_date"] = _to_date(source["date"])
    source["join_code"] = source["code"].astype("string")
    for raw in raw_to_panel:
        source[raw] = _numeric(source, raw)
    source = source.sort_values(["lag_date", "join_code"]).drop_duplicates(["lag_date", "join_code"], keep="last")
    right = source[["lag_date", "join_code", *raw_to_panel]].rename(columns=raw_to_panel)
    left = index[["__row_id", "join_code", "date"]].merge(lag_dates, on="date", how="left")
    out = left.merge(right, on=["lag_date", "join_code"], how="left").drop(columns=["join_code", "date", "lag_date"])
    return out, {
        "dataset": dataset,
        "source_path": str(path),
        "source_rows": int(len(source)),
        "feature_count": len(raw_to_panel),
        "pit_policy": "previous selected trading date stock-level context",
    }


def _feature_coverage(sidecar: pd.DataFrame, aliases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row_by_panel = {str(row["panel_field"]): row for row in aliases}
    rows: list[dict[str, Any]] = []
    total = len(sidecar)
    for column in [col for col in sidecar.columns if col not in KEY_COLUMNS]:
        series = sidecar[column]
        nonnull = int(series.notna().sum())
        meta = row_by_panel.get(column, {})
        rows.append(
            {
                "panel_field": column,
                "source_group": meta.get("source_group"),
                "dataset": meta.get("dataset"),
                "route": meta.get("route"),
                "field_family": meta.get("field_family"),
                "nonnull_count": nonnull,
                "nonnull_rate": round(nonnull / total, 8) if total else 0.0,
                "unique_nonnull_count": int(series.dropna().nunique()) if nonnull else 0,
            }
        )
    return rows


def build_sidecar(index_sidecar: Path, alias_map: Path, output_root: Path, report_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    aliases = _read_csv(alias_map)
    index = _load_index(index_sidecar).reset_index(drop=True)
    index["__row_id"] = range(len(index))
    lag_dates = _lag_dates(index)
    sidecar = index[["__row_id", "join_code", "date"]].copy()

    table_summaries: list[dict[str, Any]] = []
    for dataset in ["fundamental_balance_long", "fundamental_profit_long"]:
        part, summary = _materialize_fundamental(index, _dataset_aliases(aliases, dataset), dataset)
        sidecar = sidecar.merge(part, on="__row_id", how="left")
        table_summaries.append(summary)
    for dataset in ["open_sentiment_daily", "sentiment_hot_daily"]:
        part, summary = _materialize_market_lag(index, lag_dates, _dataset_aliases(aliases, dataset), dataset)
        sidecar = sidecar.merge(part, on="__row_id", how="left")
        table_summaries.append(summary)
    for dataset in ["ths_hot_stock_day", "uplimit_stock_event_day"]:
        part, summary = _materialize_stock_lag(index, lag_dates, _dataset_aliases(aliases, dataset), dataset)
        sidecar = sidecar.merge(part, on="__row_id", how="left")
        table_summaries.append(summary)

    sidecar = sidecar.drop(columns=["__row_id"])
    feature_cols = [column for column in sidecar.columns if column not in KEY_COLUMNS]
    output_path = output_root / "phase3ad_selected_sidecar.parquet"
    sidecar.to_parquet(output_path, index=False)
    coverage_rows = _feature_coverage(sidecar, aliases)
    nonnull_rates = [float(row["nonnull_rate"]) for row in coverage_rows]
    route_coverage: dict[str, dict[str, Any]] = {}
    for route in sorted({str(row.get("route") or "") for row in coverage_rows}):
        subset = [row for row in coverage_rows if str(row.get("route") or "") == route]
        rates = [float(row["nonnull_rate"]) for row in subset]
        route_coverage[route] = {
            "feature_count": len(subset),
            "nonzero_feature_count": sum(rate > 0 for rate in rates),
            "zero_nonnull_feature_count": sum(rate == 0 for rate in rates),
            "mean_nonnull_rate": sum(rates) / len(rates) if rates else 0.0,
        }
    _write_csv(report_root / "phase3ad_selected_sidecar_feature_coverage.csv", coverage_rows)
    route_counts = Counter(str(row.get("route") or "") for row in aliases)
    report = {
        "version": "cn-phase3ad-selected-sidecar-v1-2026-06-03",
        "decision": "PASS_PHASE3AD_SELECTED_SIDECAR_BUILT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "index_sidecar": str(index_sidecar),
        "alias_map": str(alias_map),
        "output_path": str(output_path),
        "rows": int(len(sidecar)),
        "date_min": str(sidecar["date"].min().date()),
        "date_max": str(sidecar["date"].max().date()),
        "feature_count": len(feature_cols),
        "alias_count": len(aliases),
        "mean_feature_nonnull_rate": float(sidecar[feature_cols].notna().mean().mean()) if feature_cols else 0.0,
        "nonzero_feature_count": sum(rate > 0 for rate in nonnull_rates),
        "zero_nonnull_feature_count": sum(rate == 0 for rate in nonnull_rates),
        "lt_1pct_nonnull_feature_count": sum(rate < 0.01 for rate in nonnull_rates),
        "lt_5pct_nonnull_feature_count": sum(rate < 0.05 for rate in nonnull_rates),
        "route_alias_counts": dict(sorted(route_counts.items())),
        "route_coverage": route_coverage,
        "tables": table_summaries,
        "pit_policy": {
            "fundamental": "max(NOTICE_DATE, UPDATE_DATE) + 1 calendar day; no REPORT_DATE-only availability",
            "uplimit_stock_event_day": "materialized as previous selected trading day for this daily sidecar",
            "sentiment_hot/open_sentiment": "previous selected trading day market context",
            "ths_hot_stock_day": "previous selected trading day stock heat context",
        },
        "scope": "selected-row sidecar materialization only; no formula evaluation, no selector, no replay",
        "next": "phase3ad_coverage_filter_then_selector_only_smoke_with_sidecar",
    }
    write_json_artifact(output_root / "sidecar_manifest.json", report)
    write_json_artifact(report_root / "phase3ad_selected_sidecar_report.json", report)
    _write_markdown(report_root / "CN_PHASE3AD_SELECTED_SIDECAR_V1_2026-06-03.md", report)
    return report


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# CN Phase3AD Selected Sidecar v1",
        "",
        f"decision: `{report['decision']}`",
        "",
        "## Counts",
        "",
        f"- rows: `{report['rows']}`",
        f"- date_range: `{report['date_min']} .. {report['date_max']}`",
        f"- feature_count: `{report['feature_count']}`",
        f"- alias_count: `{report['alias_count']}`",
        f"- mean_feature_nonnull_rate: `{report['mean_feature_nonnull_rate']:.6f}`",
        f"- nonzero_feature_count: `{report['nonzero_feature_count']}`",
        f"- zero_nonnull_feature_count: `{report['zero_nonnull_feature_count']}`",
        f"- lt_1pct_nonnull_feature_count: `{report['lt_1pct_nonnull_feature_count']}`",
        f"- lt_5pct_nonnull_feature_count: `{report['lt_5pct_nonnull_feature_count']}`",
        "",
        "## Route Alias Counts",
        "",
    ]
    for route, count in report["route_alias_counts"].items():
        lines.append(f"- `{route}`: `{count}`")
    lines.extend(["", "## Route Coverage", ""])
    for route, values in report["route_coverage"].items():
        lines.append(
            f"- `{route}`: features `{values['feature_count']}`, nonzero `{values['nonzero_feature_count']}`, "
            f"zero `{values['zero_nonnull_feature_count']}`, mean_nonnull `{values['mean_nonnull_rate']:.6f}`"
        )
    lines.extend(["", "## PIT Policy", ""])
    for key, value in report["pit_policy"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This artifact only materializes selected-row sidecar fields. It does not validate formula performance.",
            "",
            "## Output",
            "",
            f"`{report['output_path']}`",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-sidecar", type=Path, default=DEFAULT_INDEX_SIDECAR)
    parser.add_argument("--alias-map", type=Path, default=DEFAULT_ALIAS_MAP)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    report = build_sidecar(args.index_sidecar, args.alias_map, args.output_root, args.report_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
