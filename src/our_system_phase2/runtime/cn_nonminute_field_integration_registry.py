"""Build the authoritative CN non-1min field integration registry.

This registry is intentionally separate from the stock 1min feature panel. It
routes daily, PIT announcement, disclosure event, market event, RZRQ,
fundamental, holder, dividend, and capacity fields into system-safe use classes.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment")
DEFAULT_OUTPUT_ROOT = Path("runtime/field_registry/cn_nonminute_field_integration_registry_v1_20260602")
DEFAULT_REPORT_ROOT = Path("reports/cn_nonminute_field_integration_registry_20260602")


TABLE_ROOTS = [
    DATA_ROOT / "cn_local_minute_daily_silver_v1_20260531" / "hfq_daily_2024_2025",
    DATA_ROOT / "cn_local_minute_daily_silver_v1_20260531" / "hfq_daily_2026",
    DATA_ROOT / "cn_fundamental_akshare_batch_v1_20260531" / "aggregated_v1",
    DATA_ROOT / "cn_public_rzrq_daily_silver_v1_20260530",
    DATA_ROOT / "cn_public_rzrq_monthly_silver_v1_20260530",
    DATA_ROOT / "cn_public_xsection_no_kline_silver_v1_20260530",
    DATA_ROOT / "cn_zzshare_uplimit_history_silver_v1_20260531",
]


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


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(DATA_ROOT))
    except ValueError:
        return str(path)


def _dataset_id(path: Path) -> str:
    rel = _rel(path).replace("\\", "/")
    parts = rel.split("/")
    if "aggregated_v1" in parts:
        idx = parts.index("aggregated_v1")
        if len(parts) > idx + 1:
            return parts[idx + 1]
    if len(parts) >= 2 and parts[-1].endswith(".parquet"):
        return parts[-2] if parts[-1] in {"part.parquet"} else Path(parts[-1]).stem
    return path.stem


def _schema(path: Path) -> tuple[int, list[str]]:
    pf = pq.ParquetFile(path)
    return int(pf.metadata.num_rows), list(pf.schema_arrow.names)


def _table_route(path: Path, columns: list[str]) -> dict[str, str]:
    cols = set(columns)
    rel = _rel(path).lower().replace("\\", "/")
    dataset = _dataset_id(path).lower()

    if "hfq_daily" in rel:
        return {
            "route": "lagged_daily_context",
            "system_destination": "minute_panel_ctx_and_daily_factor_pack",
            "availability": "trade_date_plus_1_conservative",
            "selector_allowed": "true_lagged_only",
            "pit_rule": "join on signal_date = prior trading day; same-day close/state fields forbidden for intraday decisions",
        }
    if "review_uplimit_reason" in rel and "up_limit_time" in cols:
        return {
            "route": "timestamped_stock_intraday_event",
            "system_destination": "minute_event_alignment_and_event_factor_pack",
            "availability": "usable_at_or_after_up_limit_time_cutoff",
            "selector_allowed": "true_after_cutoff_only",
            "pit_rule": "same-day use before event timestamp is leakage; reason text requires separate NLP contract",
        }
    if "uplimit_trend" in rel and {"time", "uplimit_count", "open_board_count"}.issubset(cols):
        return {
            "route": "timestamped_market_intraday_event",
            "system_destination": "minute_event_alignment_and_regime_context",
            "availability": "usable_at_or_after_row_time",
            "selector_allowed": "true_after_cutoff_only",
            "pit_rule": "market event state can gate only after row time; no later cutoff fields in earlier horizons",
        }
    if "updown_distribution" in rel:
        return {
            "route": "lagged_market_regime_context",
            "system_destination": "regime_panel_and_daily_factor_pack",
            "availability": "trade_date_plus_1_conservative",
            "selector_allowed": "true_lagged_only",
            "pit_rule": "daily market summary; do not use same-day for open/morning decisions",
        }
    if "rzrq" in rel:
        return {
            "route": "lagged_daily_context",
            "system_destination": "daily_factor_pack_and_minute_ctx",
            "availability": "vendor_daily_plus_1_conservative",
            "selector_allowed": "true_lagged_only",
            "pit_rule": "same-day RZRQ forbidden; use prior available date",
        }
    if "billboard" in rel:
        return {
            "route": "event_disclosure_context",
            "system_destination": "daily_event_factor_pack_diagnostic_first",
            "availability": "after_disclosure_or_next_trading_day_conservative",
            "selector_allowed": "diagnostic_until_disclosure_timestamp_contract",
            "pit_rule": "cannot be used intraday on trade date by default",
        }
    if "holder_num" in rel:
        return {
            "route": "announcement_pit_context",
            "system_destination": "pit_feature_panel",
            "availability": "announcement_date_plus_1_conservative",
            "selector_allowed": "true_after_pit_contract",
            "pit_rule": "join by announcement/update date, not report end date alone",
        }
    if "stock_calendar" in rel:
        return {
            "route": "tradability_calendar_context",
            "system_destination": "universe_filter_and_diagnostic",
            "availability": "calendar_metadata",
            "selector_allowed": "false_universe_control_only",
            "pit_rule": "tradability/universe metadata, not alpha signal unless separately proven",
        }
    if "dividend" in dataset or "share_change" in dataset:
        return {
            "route": "announcement_pit_context",
            "system_destination": "pit_feature_panel",
            "availability": "announcement_date_plus_1_conservative",
            "selector_allowed": "true_after_pit_contract",
            "pit_rule": "corporate action dates need notice/ex-date separation",
        }
    if any(col in cols for col in ["NOTICE_DATE", "REPORT_DATE", "source_code6"]):
        return {
            "route": "announcement_pit_context",
            "system_destination": "fundamental_pit_feature_panel",
            "availability": "notice_date_plus_1_conservative",
            "selector_allowed": "true_after_notice_date",
            "pit_rule": "NOTICE_DATE governs availability; REPORT_DATE alone is not enough",
        }
    return {
        "route": "manual_contract_required",
        "system_destination": "blocked_until_registry_review",
        "availability": "unknown",
        "selector_allowed": "false_until_contract",
        "pit_rule": "manual review required",
    }


def _field_family(field: str) -> str:
    name = field.lower()
    if name in {"date", "date1", "trade_date", "report_date", "notice_date", "update_date", "time"} or "date" in name:
        return "date_key"
    if name in {"code", "scode", "stock_code", "security_code", "secucode", "source_code6"}:
        return "instrument_key"
    if any(token in name for token in ["amount", "volume", "turnover", "rzmre", "rzche", "rzjme", "rqmcl", "rqchl", "rqjmg", "rzye", "rqye"]):
        return "flow_liquidity"
    if any(token in name for token in ["market_cap", "float", "circulation", "free_market_cap", "shares", "share"]):
        return "capacity_size"
    if any(token in name for token in ["limit", "uplimit", "open_board", "zt", "dt", "fengdan", "seal"]):
        return "limit_event"
    if any(token in name for token in ["pe", "pb", "ps", "asset", "liab", "profit", "income", "cash", "debt", "goodwill", "inventory", "roe", "roa"]):
        return "fundamental"
    if any(token in name for token in ["billboard", "buy", "sell", "net", "seat", "explain"]):
        return "disclosure_event"
    if any(token in name for token in ["industry", "plate", "sector", "theme"]):
        return "industry_theme"
    if any(token in name for token in ["is_st", "susp", "calendar", "delist", "list_date", "marginable"]):
        return "tradability_universe"
    if any(token in name for token in ["open", "high", "low", "close", "pct_chg", "change", "return"]) or name.startswith("ma"):
        return "price_state"
    return "other"


def _field_role(field: str, table: dict[str, str]) -> dict[str, str]:
    family = _field_family(field)
    route = table["route"]
    selector_allowed = table["selector_allowed"]
    role = "feature_candidate"
    if family in {"date_key", "instrument_key"}:
        role = "key"
        selector_allowed = "false_key_only"
    elif family == "tradability_universe":
        role = "filter_or_diagnostic"
    elif route in {"manual_contract_required"}:
        role = "blocked"
    elif "diagnostic" in selector_allowed:
        role = "diagnostic_candidate"
    return {"field_family": family, "field_role": role, "selector_allowed": selector_allowed}


def _recommended_transforms(route: str, family: str) -> str:
    if route.startswith("timestamped") and family == "limit_event":
        return "cutoff_flags|event_age|streak_lifecycle|open_board_transition|source_lane_cap"
    if family == "flow_liquidity":
        return "lagged_level|delta_3_5_10|zscore_20|rank_xsection|ratio_to_float_mcap"
    if family == "capacity_size":
        return "lagged_level|rank_xsection|bucket|small_capacity_guard|liquidity_capacity_interaction"
    if family == "fundamental":
        return "notice_lagged_latest|quarter_delta|ttm_proxy|rank_xsection|winsorize"
    if family == "disclosure_event":
        return "event_flag|event_age|net_buy_sell_ratio|matched_control_required"
    if family == "industry_theme":
        return "group_neutralizer|group_density|theme_strength_lagged"
    if family == "price_state":
        return "lagged_momentum|mean_reversion|volatility|do_not_use_same_day_close_intraday"
    return "lagged_level|rank_xsection"


def _coverage_probe(path: Path, table_route: str, columns: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        if "uplimit_trend" in str(path) and {"date", "time", "uplimit_count"}.issubset(columns):
            frame = pd.read_parquet(path, columns=["date", "time", "uplimit_count", "open_board_count"])
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            recent = frame[frame["date"] >= pd.Timestamp("2026-01-01")]
            out.update(
                {
                    "date_min": str(frame["date"].min().date()) if frame["date"].notna().any() else "",
                    "date_max": str(frame["date"].max().date()) if frame["date"].notna().any() else "",
                    "recent_nonnull_rate": float(recent["uplimit_count"].notna().mean()) if not recent.empty else None,
                }
            )
        elif "review_uplimit_reason" in str(path) and {"date1", "up_limit_time"}.issubset(columns):
            frame = pd.read_parquet(path, columns=["date1", "up_limit_time", "stock_code"])
            frame["date1"] = pd.to_datetime(frame["date1"], errors="coerce")
            recent = frame[frame["date1"] >= pd.Timestamp("2026-01-01")]
            out.update(
                {
                    "date_min": str(frame["date1"].min().date()) if frame["date1"].notna().any() else "",
                    "date_max": str(frame["date1"].max().date()) if frame["date1"].notna().any() else "",
                    "recent_nonnull_rate": float(recent["up_limit_time"].notna().mean()) if not recent.empty else None,
                    "recent_rows": int(recent.shape[0]),
                }
            )
        elif "hfq_daily" in str(path) and {"date", "code"}.issubset(columns):
            frame = pd.read_parquet(path, columns=[col for col in ["date", "code", "amount_yuan", "volume_ratio", "turnover_ratio"] if col in columns])
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            out.update(
                {
                    "date_min": str(frame["date"].min().date()) if frame["date"].notna().any() else "",
                    "date_max": str(frame["date"].max().date()) if frame["date"].notna().any() else "",
                    "amount_nonnull_rate": float(frame["amount_yuan"].notna().mean()) if "amount_yuan" in frame else None,
                }
            )
    except Exception as exc:  # noqa: BLE001
        out["coverage_error"] = f"{type(exc).__name__}:{str(exc)[:160]}"
    return out


def _iter_parquet_tables() -> list[Path]:
    paths: list[Path] = []
    for root in TABLE_ROOTS:
        if not root.exists():
            continue
        if root.is_file() and root.suffix == ".parquet":
            paths.append(root)
        else:
            paths.extend(sorted(path for path in root.rglob("*.parquet") if path.is_file()))
    # Keep one schema row per parquet table path; do not include stock_1min roots.
    return sorted(set(paths))


def run(*, output_root: Path, report_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    table_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []

    for path in _iter_parquet_tables():
        rel = _rel(path)
        if "stock_1min" in rel.lower():
            continue
        try:
            nrows, columns = _schema(path)
            route = _table_route(path, columns)
            probe = _coverage_probe(path, route["route"], columns)
            table_id = _dataset_id(path)
            table_row = {
                "table_id": table_id,
                "path": rel,
                "rows": nrows,
                "columns": len(columns),
                **route,
                **probe,
                "key_columns": "|".join([col for col in columns if _field_family(col) in {"date_key", "instrument_key"}][:20]),
                "sample_columns": "|".join(columns[:40]),
            }
            table_rows.append(table_row)
            for col in columns:
                role = _field_role(col, route)
                field_rows.append(
                    {
                        "table_id": table_id,
                        "path": rel,
                        "field_name": col,
                        **role,
                        "route": route["route"],
                        "system_destination": route["system_destination"],
                        "availability": route["availability"],
                        "pit_rule": route["pit_rule"],
                        "recommended_transforms": _recommended_transforms(route["route"], role["field_family"]),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            error_rows.append({"path": rel, "error": f"{type(exc).__name__}:{str(exc)[:240]}"})

    _write_csv(output_root / "table_registry.csv", table_rows)
    _write_csv(output_root / "field_registry.csv", field_rows)
    _write_csv(output_root / "error_manifest.csv", error_rows)

    table_frame = pd.DataFrame(table_rows)
    field_frame = pd.DataFrame(field_rows)
    route_counts = table_frame["route"].value_counts(dropna=False).to_dict() if not table_frame.empty else {}
    field_family_counts = field_frame["field_family"].value_counts(dropna=False).to_dict() if not field_frame.empty else {}
    blocked_tables = table_frame[table_frame["selector_allowed"].astype(str).str.contains("false|diagnostic", case=False, na=False)].to_dict("records") if not table_frame.empty else []
    summary = {
        "decision": "PASS_NONMINUTE_FIELD_INTEGRATION_REGISTRY",
        "registry_id": "cn_nonminute_field_integration_registry_v1_20260602",
        "table_count": len(table_rows),
        "field_count": len(field_rows),
        "error_count": len(error_rows),
        "route_counts": route_counts,
        "field_family_counts": field_family_counts,
        "blocked_or_diagnostic_table_count": len(blocked_tables),
        "outputs": {
            "table_registry": str(output_root / "table_registry.csv"),
            "field_registry": str(output_root / "field_registry.csv"),
            "error_manifest": str(output_root / "error_manifest.csv"),
            "json": str(output_root / "cn_nonminute_field_integration_registry_v1_20260602.json"),
            "markdown": str(report_root / "CN_NONMINUTE_FIELD_INTEGRATION_REGISTRY_2026-06-02.md"),
        },
        "policy": {
            "stock_1min": "excluded; handled by cn_minute_feature_panel_v2",
            "daily_context": "signal_date/prior-date only for intraday or next-day selector",
            "announcement_pit": "NOTICE_DATE/announcement date governs availability",
            "timestamped_event": "usable only after event row time/cutoff",
            "diagnostic": "can be scanned but cannot promote without PIT contract and frozen replay",
        },
    }
    write_json_artifact(output_root / "cn_nonminute_field_integration_registry_v1_20260602.json", summary)
    lines = [
        "# CN Non-1min Field Integration Registry - 2026-06-02",
        "",
        f"decision: `{summary['decision']}`",
        f"table_count: `{summary['table_count']}`",
        f"field_count: `{summary['field_count']}`",
        f"error_count: `{summary['error_count']}`",
        f"blocked_or_diagnostic_table_count: `{summary['blocked_or_diagnostic_table_count']}`",
        "",
        "## Route Counts",
        "",
    ]
    for key, value in route_counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Integration Policy",
            "",
            "- Stock 1min fields are intentionally excluded from this registry and handled by the minute v2 panel.",
            "- Daily/HFQ/RZRQ/context fields are selector-eligible only through lagged joins.",
            "- Fundamental, holder, share-change and dividend data require announcement/PIT availability.",
            "- Billboard/disclosure rows remain diagnostic until disclosure timestamp policy is proven.",
            "- Limit event rows are valid only after the timestamp/cutoff encoded in the feature.",
        ]
    )
    (report_root / "CN_NONMINUTE_FIELD_INTEGRATION_REGISTRY_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    summary = run(output_root=args.output_root, report_root=args.report_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
