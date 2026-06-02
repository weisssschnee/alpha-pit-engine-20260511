from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DATA_ROOT = Path("G:/Project_V7_Rotation/data/cn_public_enrichment")
LOCAL_MINUTE_DAILY_ROOT = DATA_ROOT / "cn_local_minute_daily_silver_v1_20260531"
UPLIMIT_ROOT = DATA_ROOT / "cn_zzshare_uplimit_history_silver_v1_20260531"
RZRQ_ROOT = DATA_ROOT / "cn_public_rzrq_daily_silver_v1_20260530"
XSECTION_ROOT = DATA_ROOT / "cn_public_xsection_no_kline_silver_v1_20260530"
DEFAULT_OUTPUT = Path("reports/cn_controlled_data_smoke_20260531")
DEFAULT_FIELD_REGISTRY = Path("runtime/field_registry/cn_alpha_field_registry_v1_20260531.json")


@dataclass(frozen=True, slots=True)
class TableSpec:
    table_id: str
    path: Path
    date_column: str | None
    code_column: str | None
    key_columns: tuple[str, ...]
    source_role: str
    lag_policy: str
    pit_policy: str
    notes: str


TABLES = [
    TableSpec(
        "hfq_daily_2026",
        LOCAL_MINUTE_DAILY_ROOT / "hfq_daily_2026/hfq_daily_2026.parquet",
        "date",
        "code",
        ("date", "code"),
        "daily_price_state_value",
        "available_next_trading_day_conservative",
        "daily_vendor_snapshot; do not use same-day close fields for after-open decisions",
        "2026 daily hfq price/state/value panel.",
    ),
    TableSpec(
        "stock_1min_2026_manifest",
        LOCAL_MINUTE_DAILY_ROOT / "stock_1min_2026_manifest.csv",
        "date",
        None,
        ("date",),
        "minute_manifest",
        "intraday_observable_after_bar_close; daily alpha aggregation must lag unless intraday strategy",
        "manifest_level",
        "Manifest for 2026 1min parquet partitions; full 1min table is not loaded by this smoke.",
    ),
    TableSpec(
        "stock_1min_2026_sample_partition",
        LOCAL_MINUTE_DAILY_ROOT / "stock_1min_2026_parquet_by_date/date=20260105.parquet",
        "date",
        "code",
        ("code", "trade_time"),
        "minute_price_sample_partition",
        "intraday_observable_after_bar_close; daily alpha aggregation must lag unless intraday strategy",
        "minute_bar_partition",
        "One partition schema/key sample only.",
    ),
    TableSpec(
        "review_uplimit_reason",
        UPLIMIT_ROOT / "review_uplimit_reason/review_uplimit_reason.parquet",
        "date1",
        "stock_code",
        ("date1", "stock_code"),
        "limit_event_close_reason",
        "available_next_trading_day_conservative unless timestamp contract proves intraday observability",
        "event_vendor_snapshot",
        "Limit-up reason and seal/order-flow proxy table.",
    ),
    TableSpec(
        "review_uplimit_reason_open",
        UPLIMIT_ROOT / "review_uplimit_reason_open/review_uplimit_reason_open.parquet",
        "date",
        "stock_code",
        ("date", "stock_code"),
        "limit_event_open_board_reason",
        "available_next_trading_day_conservative",
        "event_vendor_snapshot",
        "Open-board/reason auxiliary table.",
    ),
    TableSpec(
        "updown_distribution",
        UPLIMIT_ROOT / "updown_distribution/updown_distribution.parquet",
        "date",
        None,
        ("date",),
        "market_regime_distribution",
        "available_next_trading_day_conservative",
        "market_level_daily_summary",
        "Market up/down distribution summary.",
    ),
    TableSpec(
        "uplimit_trend",
        UPLIMIT_ROOT / "uplimit_trend/uplimit_trend.parquet",
        "date",
        None,
        ("date", "time"),
        "market_limit_trend_intraday_summary",
        "timestamped; require explicit time gating before intraday use",
        "market_level_intraday_summary",
        "Limit/open-board intraday trend summary.",
    ),
    TableSpec(
        "rzrq_margin_xsection_daily",
        RZRQ_ROOT / "rzrq_margin_xsection_daily.parquet",
        "DATE",
        "SCODE",
        ("DATE", "SCODE"),
        "margin_short_xsection_daily",
        "available_next_trading_day_conservative",
        "daily_vendor_snapshot",
        "Margin financing/securities-lending daily xsection.",
    ),
    TableSpec(
        "billboard_details",
        XSECTION_ROOT / "billboard_details/billboard_details.parquet",
        None,
        None,
        (),
        "lhb_billboard_details",
        "available_next_trading_day_conservative",
        "event_disclosure; preserve disclosure date",
        "Dragon-tiger billboard details.",
    ),
    TableSpec(
        "billboard_buy",
        XSECTION_ROOT / "billboard_buy/billboard_buy.parquet",
        None,
        None,
        (),
        "lhb_buy_departments",
        "available_next_trading_day_conservative",
        "event_disclosure; preserve disclosure date",
        "Dragon-tiger buy-side departments.",
    ),
    TableSpec(
        "billboard_sell",
        XSECTION_ROOT / "billboard_sell/billboard_sell.parquet",
        None,
        None,
        (),
        "lhb_sell_departments",
        "available_next_trading_day_conservative",
        "event_disclosure; preserve disclosure date",
        "Dragon-tiger sell-side departments.",
    ),
    TableSpec(
        "holder_num_detail",
        XSECTION_ROOT / "holder_num_detail/holder_num_detail.parquet",
        None,
        None,
        (),
        "holder_count_detail",
        "available_after_announcement_date_only",
        "pit_by_announcement_date_required; never by report/end date alone",
        "Holder count detail; requires PIT standardization before alpha use.",
    ),
    TableSpec(
        "stock_calendar",
        XSECTION_ROOT / "stock_calendar/stock_calendar.parquet",
        None,
        None,
        (),
        "company_event_calendar",
        "not_tradable_daily_state_until_standardized",
        "calendar_disclosure",
        "Company event calendar; not a daily tradable-state table until standardized.",
    ),
]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if pd.isna(value):
        return None
    return value


def _parquet_schema(path: Path) -> tuple[int, list[str]]:
    parquet_file = pq.ParquetFile(path)
    return int(parquet_file.metadata.num_rows), list(parquet_file.schema_arrow.names)


def _read_key_frame(spec: TableSpec, columns: list[str]) -> pd.DataFrame:
    if spec.path.suffix.lower() == ".csv":
        return pd.read_csv(spec.path, usecols=[column for column in columns if column], low_memory=False)
    return pd.read_parquet(spec.path, columns=[column for column in columns if column])


def _parse_date_series(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    compact_mask = text.str.fullmatch(r"\d{8}", na=False)
    parsed = pd.to_datetime(series, errors="coerce")
    if compact_mask.any():
        parsed.loc[compact_mask] = pd.to_datetime(text.loc[compact_mask], format="%Y%m%d", errors="coerce")
    return parsed


def _table_summary(spec: TableSpec) -> dict[str, Any]:
    if not spec.path.exists():
        return {
            "table_id": spec.table_id,
            "path": str(spec.path),
            "exists": False,
            "decision": "MISSING",
        }

    if spec.path.suffix.lower() == ".csv":
        frame = pd.read_csv(spec.path, low_memory=False)
        rows = int(len(frame))
        columns = list(frame.columns)
    else:
        rows, columns = _parquet_schema(spec.path)

    summary: dict[str, Any] = {
        "table_id": spec.table_id,
        "path": str(spec.path),
        "exists": True,
        "rows": rows,
        "columns": columns,
        "column_count": len(columns),
        "date_column": spec.date_column,
        "code_column": spec.code_column,
        "key_columns": list(spec.key_columns),
        "source_role": spec.source_role,
        "lag_policy": spec.lag_policy,
        "pit_policy": spec.pit_policy,
        "notes": spec.notes,
    }

    inspect_columns = sorted(set([column for column in [spec.date_column, spec.code_column, *spec.key_columns] if column and column in columns]))
    if inspect_columns:
        frame = _read_key_frame(spec, inspect_columns)
        if spec.date_column and spec.date_column in frame:
            dates = _parse_date_series(frame[spec.date_column])
            summary["date_min"] = str(dates.min().date()) if dates.notna().any() else None
            summary["date_max"] = str(dates.max().date()) if dates.notna().any() else None
            summary["unique_dates"] = int(dates.nunique(dropna=True))
        if spec.code_column and spec.code_column in frame:
            summary["unique_codes"] = int(frame[spec.code_column].astype(str).nunique(dropna=True))
        if spec.key_columns and all(column in frame.columns for column in spec.key_columns):
            summary["duplicate_key_count"] = int(frame.duplicated(list(spec.key_columns)).sum())
    if spec.table_id == "stock_1min_2026_manifest":
        frame = pd.read_csv(spec.path, low_memory=False)
        summary["rows_total_from_manifest"] = int(pd.to_numeric(frame["rows"], errors="coerce").fillna(0).sum())
        summary["partitions"] = int(len(frame))
        summary["duplicate_code_time_total"] = int(pd.to_numeric(frame["duplicate_code_time"], errors="coerce").fillna(0).sum())
        summary["max_symbols_per_day"] = int(pd.to_numeric(frame["symbols"], errors="coerce").max())
    summary["decision"] = "PASS_TABLE_SMOKE"
    return summary


def _field_registry_payload(table_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    table_by_id = {summary["table_id"]: summary for summary in table_summaries if summary.get("exists")}
    for spec in TABLES:
        summary = table_by_id.get(spec.table_id)
        if not summary:
            continue
        for column in summary["columns"]:
            fields.append(
                {
                    "table_id": spec.table_id,
                    "raw_field": column,
                    "normalized_field": _normalize_field_name(spec.table_id, column),
                    "source_role": spec.source_role,
                    "lag_policy": spec.lag_policy,
                    "pit_policy": spec.pit_policy,
                    "usage_status": _usage_status(spec, column),
                }
            )
    return {
        "registry_id": "cn_alpha_field_registry_v1_20260531",
        "status": "controlled_data_field_inventory",
        "data_roots": {
            "local_minute_daily": str(LOCAL_MINUTE_DAILY_ROOT),
            "uplimit_history": str(UPLIMIT_ROOT),
            "rzrq_daily": str(RZRQ_ROOT),
            "xsection_no_kline": str(XSECTION_ROOT),
        },
        "global_policy": {
            "default_daily_event_lag": "available_next_trading_day_conservative",
            "minute_bar_policy": "intraday_observable_after_bar_close; aggregate to daily with explicit lag",
            "holder_num_detail_policy": "must be keyed by announcement date, not report/end date",
            "stock_calendar_policy": "not a daily tradable-state input until standardized",
            "promotion_policy": "field availability does not imply alpha promotion; all features require frozen selection and replay audits",
        },
        "tables": [
            {
                "table_id": spec.table_id,
                "path": str(spec.path),
                "source_role": spec.source_role,
                "lag_policy": spec.lag_policy,
                "pit_policy": spec.pit_policy,
                "notes": spec.notes,
            }
            for spec in TABLES
        ],
        "fields": fields,
    }


def _normalize_field_name(table_id: str, column: str) -> str:
    lower = column.lower()
    aliases = {
        "date1": "date",
        "stock_code": "code",
        "scode": "code",
        "date": "date",
        "trade_date": "date",
        "amount_yuan": "amount",
        "volume_shares": "volume",
        "vol": "volume",
        "up_limit_keep_times": "limit_up_keep_times",
        "fengdan_money": "seal_money",
        "fengdan_rate": "seal_rate",
        "actualcirculation_value": "actual_circulation_value",
        "turnover_ration_real": "turnover_ratio_real",
    }
    return aliases.get(lower, lower)


def _usage_status(spec: TableSpec, column: str) -> str:
    lower = column.lower()
    if spec.table_id == "stock_calendar":
        return "blocked_until_daily_state_standardized"
    if spec.table_id == "holder_num_detail":
        return "blocked_until_announcement_date_pit_verified"
    if "date" in lower or lower in {"time", "trade_time"}:
        return "key_or_time_field"
    if spec.source_role.startswith("minute"):
        return "usable_with_intraday_clock_or_lagged_daily_aggregate"
    if "limit" in lower or "feng" in lower or "board" in lower or "up_limit" in lower:
        return "usable_as_event_feature_with_conservative_lag"
    return "usable_after_field_contract_review"


def run(output_dir: Path, field_registry_path: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    field_registry_path.parent.mkdir(parents=True, exist_ok=True)

    table_summaries = [_table_summary(spec) for spec in TABLES]
    registry = _field_registry_payload(table_summaries)

    source_rows = [
        {key: value for key, value in summary.items() if key != "columns"}
        for summary in table_summaries
    ]
    field_rows = registry["fields"]
    pd.DataFrame(source_rows).to_csv(output_dir / "cn_controlled_data_sources.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(field_rows).to_csv(output_dir / "cn_controlled_field_inventory.csv", index=False, encoding="utf-8-sig")

    summary_payload = {
        "decision": "PASS_CN_CONTROLLED_DATA_SMOKE" if all(item.get("exists") for item in table_summaries) else "HOLD_CN_CONTROLLED_DATA_SMOKE",
        "table_count": len(table_summaries),
        "missing_tables": [item["table_id"] for item in table_summaries if not item.get("exists")],
        "tables": table_summaries,
        "field_registry_path": str(field_registry_path),
    }
    (output_dir / "cn_controlled_data_smoke.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    field_registry_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    (output_dir / "CN_CONTROLLED_DATA_SMOKE_2026-05-31.md").write_text(
        _render_markdown(summary_payload),
        encoding="utf-8",
    )
    return summary_payload


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CN Controlled Data Smoke",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Policy",
        "",
        "- Daily/event fields are conservatively treated as next-trading-day inputs unless an intraday timestamp contract proves otherwise.",
        "- 1min fields are observable only after the bar close; daily alpha use must explicitly aggregate and lag.",
        "- `holder_num_detail` requires announcement-date PIT handling.",
        "- `stock_calendar` is not a daily tradable-state input until standardized.",
        "",
        "## Tables",
        "",
        "| table | rows | date range | unique dates | unique codes | duplicate keys | role |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for item in payload["tables"]:
        date_range = f"{item.get('date_min')}..{item.get('date_max')}" if item.get("date_min") else ""
        lines.append(
            f"| `{item['table_id']}` | {item.get('rows', '')} | {date_range} | "
            f"{item.get('unique_dates', '')} | {item.get('unique_codes', '')} | "
            f"{item.get('duplicate_key_count', '')} | `{item.get('source_role', '')}` |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `cn_controlled_data_smoke.json`",
            "- `cn_controlled_data_sources.csv`",
            "- `cn_controlled_field_inventory.csv`",
            f"- `{payload['field_registry_path']}`",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test controlled CN data sources and emit a field registry.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--field-registry", type=Path, default=DEFAULT_FIELD_REGISTRY)
    args = parser.parse_args()
    payload = run(args.output_dir, args.field_registry)
    print(json.dumps({"decision": payload["decision"], "output_dir": str(args.output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
