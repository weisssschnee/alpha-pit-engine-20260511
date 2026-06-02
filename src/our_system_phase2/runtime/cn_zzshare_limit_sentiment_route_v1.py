"""Route the ZZShare limit/sentiment pack into PIT-safe feature roles."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_PACK_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_zzshare_limit_sentiment_pack_v1_20260602"
)
DEFAULT_OUTPUT_ROOT = Path("runtime/field_registry/cn_zzshare_limit_sentiment_route_v1_20260602")
DEFAULT_REPORT = Path("reports/CN_ZZSHARE_LIMIT_SENTIMENT_ROUTE_V1_2026-06-02.md")

FUTURE_LABEL_RE = re.compile(r"^(next_|label_)")
META_FIELDS = {"dataset", "request_date", "download_time", "id", "checked", "tip", "errcode"}
DATE_FIELDS = {"date1", "Day", "collect_date", "update_time", "next_day"}
STOCK_KEY_FIELDS = {"stock_code", "symbol_code", "stock_name", "symbol_name"}

UPLIMIT_EVENT_FIELDS = {
    "up_limit_time": ("event_time", "minute_event_cutoff", "usable after this timestamp only"),
    "up_limit_keep_times": ("event_state", "minute_event_or_tplus1", "board streak state"),
    "up_limit_type": ("event_state_category", "minute_event_or_tplus1", "limit-up type category"),
    "amount": ("event_liquidity", "minute_event_or_tplus1", "event-day traded amount from vendor event row"),
    "auction_buy": ("auction_flow", "minute_event_or_tplus1", "auction buy pressure"),
    "auction_money": ("auction_flow", "minute_event_or_tplus1", "auction money pressure"),
    "auction_offer": ("auction_flow", "minute_event_or_tplus1", "auction offer pressure"),
    "auction_turnover": ("auction_flow", "minute_event_or_tplus1", "auction turnover pressure"),
    "auction_pre1max_ratio": ("auction_flow", "minute_event_or_tplus1", "auction previous max ratio"),
    "fd_close": ("seal_strength", "minute_event_or_tplus1", "close seal/order strength"),
    "fd_max": ("seal_strength", "minute_event_or_tplus1", "max seal/order strength"),
    "market_c": ("event_market_context", "minute_event_or_tplus1", "vendor event market context"),
    "market_c_c": ("event_market_context", "minute_event_or_tplus1", "vendor event market context"),
    "plate_code": ("industry_theme_key", "diagnostic_context", "theme/plate grouping key"),
    "up_limit_desc": ("event_text", "diagnostic_context", "vendor limit-up description text; parse before selector use"),
}

OPEN_SENTIMENT_FIELDS = {
    "uplimit_num": ("market_limit_breadth", "lagged_daily_context", "market limit-up count"),
    "uplimit_n_num": ("market_limit_breadth", "lagged_daily_context", "non-first limit-up count"),
    "downlimit_num": ("market_limit_breadth", "lagged_daily_context", "market down-limit count"),
    "up_num": ("market_breadth", "lagged_daily_context", "up stock count"),
    "down_num": ("market_breadth", "lagged_daily_context", "down stock count"),
    "zb_num": ("market_limit_structure", "lagged_daily_context", "open-board count"),
    "lb_2_num": ("board_ladder", "lagged_daily_context", "2-board count"),
    "lb_3_num": ("board_ladder", "lagged_daily_context", "3-board count"),
    "second_lb_num": ("board_ladder", "lagged_daily_context", "second-board count"),
    "max_lb_num": ("board_ladder", "lagged_daily_context", "max board height"),
    "lb_h_num": ("board_ladder", "lagged_daily_context", "high-board/limit-streak height count"),
    "max_lb_stocks": ("board_identity_list", "diagnostic_context", "max-streak stock list; expand before selector use"),
    "mian_num": ("loss_effect", "lagged_daily_context", "loss-effect count"),
    "tiandi_num": ("loss_effect", "lagged_daily_context", "sky-to-floor count"),
    "ditian_num": ("reversal_effect", "lagged_daily_context", "floor-to-sky count"),
    "damian_num": ("loss_effect", "lagged_daily_context", "large loss-effect count"),
    "gt5_num": ("market_breadth", "lagged_daily_context", "greater-than-5pct count"),
    "lt5_num": ("market_breadth", "lagged_daily_context", "less-than-minus-5pct count"),
    "fb_num": ("market_limit_structure", "lagged_daily_context", "failed-board count"),
    "bigleg_num": ("loss_effect", "lagged_daily_context", "large intraday reversal count"),
}

HOT_DAY_FIELDS = {
    "df_num": ("sentiment_hot_state", "lagged_daily_context", "daily loss-effect/hot state proxy"),
    "lbgd": ("sentiment_hot_state", "lagged_daily_context", "board ladder height proxy"),
    "strong": ("sentiment_strength", "lagged_daily_context", "daily sentiment strength"),
    "ztjs": ("sentiment_limit_count", "lagged_daily_context", "hot limit-up count"),
    "ttag": ("sentiment_state_raw", "diagnostic_context", "vendor tag raw field"),
}

THS_HOT_FIELDS = {
    "rank": ("stock_hot_rank", "lagged_daily_stock_context", "THS hot rank"),
    "rank_diff": ("stock_hot_rank_change", "lagged_daily_stock_context", "THS hot rank delta"),
    "circulation_value": ("stock_hot_capacity", "lagged_daily_stock_context", "hot-stock circulation value"),
    "last_pct": ("stock_hot_return_state", "lagged_daily_stock_context", "close-derived return state, T+1 only"),
    "last_price": ("stock_hot_price_state", "lagged_daily_stock_context", "close-derived price state, T+1 only"),
}


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
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_dataset(pack_root: Path, dataset: str) -> pd.DataFrame:
    path = pack_root / "silver_parquet" / f"{dataset}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def _route_field(dataset: str, field: str) -> dict[str, str]:
    if FUTURE_LABEL_RE.search(field) or field in {"next_open_yi", "next_gt9_offer_v", "next_gt9_time", "next_gt9_turnover"}:
        return {
            "route": "blocked_future_label",
            "pit_rule": "forbidden_as_selector_input",
            "feature_family": "future_label",
            "meaning": "future/next-session outcome field",
            "allowed_use": "label/audit only",
        }
    if field in META_FIELDS:
        return {
            "route": "metadata",
            "pit_rule": "not_alpha_feature",
            "feature_family": "metadata",
            "meaning": "download/source metadata",
            "allowed_use": "audit only",
        }
    if field in DATE_FIELDS or field in STOCK_KEY_FIELDS:
        return {
            "route": "key_or_timestamp",
            "pit_rule": "join_key_or_time_contract",
            "feature_family": "key",
            "meaning": "join/time key",
            "allowed_use": "join key only",
        }
    if dataset == "uplimit_stocks" and field in UPLIMIT_EVENT_FIELDS:
        family, route, meaning = UPLIMIT_EVENT_FIELDS[field]
        pit_rule = "timestamped_intraday_event_after_up_limit_time" if route == "minute_event_cutoff" else "event_row_available_after_up_limit_time_or_T_plus_1_daily"
        return {"route": route, "pit_rule": pit_rule, "feature_family": family, "meaning": meaning, "allowed_use": route}
    if dataset == "open_sentiment_data" and field in OPEN_SENTIMENT_FIELDS:
        family, route, meaning = OPEN_SENTIMENT_FIELDS[field]
        return {"route": route, "pit_rule": "T_plus_1_lagged_daily_context", "feature_family": family, "meaning": meaning, "allowed_use": route}
    if dataset == "sentiment_hot_day" and field in HOT_DAY_FIELDS:
        family, route, meaning = HOT_DAY_FIELDS[field]
        return {"route": route, "pit_rule": "T_plus_1_lagged_daily_context", "feature_family": family, "meaning": meaning, "allowed_use": route}
    if dataset == "ths_hot_top" and field in THS_HOT_FIELDS:
        family, route, meaning = THS_HOT_FIELDS[field]
        return {"route": route, "pit_rule": "T_plus_1_lagged_daily_stock_context", "feature_family": family, "meaning": meaning, "allowed_use": route}
    return {
        "route": "manual_review",
        "pit_rule": "not_eligible_until_contract_written",
        "feature_family": "unknown",
        "meaning": "",
        "allowed_use": "blocked_pending_review",
    }


def _date_range(frame: pd.DataFrame, column: str) -> tuple[str, str]:
    dates = pd.to_datetime(frame[column], errors="coerce").dropna()
    if dates.empty:
        return "", ""
    return str(dates.min().date()), str(dates.max().date())


def _coverage(pack_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in ["uplimit_stocks", "open_sentiment_data", "sentiment_hot_day", "ths_hot_top"]:
        frame = _read_dataset(pack_root, dataset)
        date_col = {"uplimit_stocks": "date1", "open_sentiment_data": "date1", "sentiment_hot_day": "Day", "ths_hot_top": "collect_date"}[dataset]
        start, end = _date_range(frame, date_col)
        row = {
            "dataset": dataset,
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "date_col": date_col,
            "date_min": start,
            "date_max": end,
        }
        if dataset == "uplimit_stocks":
            row["stock_count"] = int(frame["stock_code"].astype(str).nunique()) if "stock_code" in frame else 0
            row["up_limit_time_nonnull_rate"] = float(frame["up_limit_time"].notna().mean()) if "up_limit_time" in frame else 0.0
            row["future_label_field_count"] = sum(1 for col in frame.columns if _route_field(dataset, col)["route"] == "blocked_future_label")
        if dataset == "ths_hot_top":
            row["stock_count"] = int(frame["symbol_code"].astype(str).nunique()) if "symbol_code" in frame else 0
        rows.append(row)
    return rows


def _field_routes(pack_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dataset in ["uplimit_stocks", "open_sentiment_data", "sentiment_hot_day", "ths_hot_top"]:
        path = pack_root / "silver_parquet" / f"{dataset}.parquet"
        schema = pq.ParquetFile(path).schema_arrow
        for field in schema.names:
            route = _route_field(dataset, field)
            rows.append(
                {
                    "dataset": dataset,
                    "field": field,
                    "dtype": str(schema.field(field).type),
                    **route,
                }
            )
    return rows


def _candidate_transforms(route_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in route_rows:
        route = row["route"]
        if route in {"metadata", "key_or_timestamp", "blocked_future_label", "manual_review"}:
            continue
        field = row["field"]
        dataset = row["dataset"]
        prefix = "evt_zls" if dataset == "uplimit_stocks" else "ctx_zls"
        if route == "minute_event_cutoff":
            out.append(
                {
                    "candidate_field": f"{prefix}_{field}",
                    "dataset": dataset,
                    "source_field": field,
                    "candidate_role": "minute_event_cutoff_key",
                    "transform": "parse HH:MM event time; usable only when event_time <= decision_time",
                    "pit_rule": row["pit_rule"],
                    "priority": "high",
                }
            )
            continue
        if route == "diagnostic_context":
            out.append(
                {
                    "candidate_field": f"{prefix}_{field}_diagnostic",
                    "dataset": dataset,
                    "source_field": field,
                    "candidate_role": route,
                    "transform": "diagnostic_parse_or_expand_before_selector",
                    "pit_rule": row["pit_rule"],
                    "priority": "diagnostic",
                }
            )
            continue
        base_name = f"{prefix}_{field}_lag1" if "daily" in route else f"{prefix}_{field}"
        transforms = ["raw_numeric"]
        if route not in {"event_state_category", "diagnostic_context"}:
            transforms.extend(["cross_sectional_rank", "zscore", "rolling_3d", "rolling_5d"])
        for transform in transforms:
            out.append(
                {
                    "candidate_field": f"{base_name}_{transform}" if transform != "raw_numeric" else base_name,
                    "dataset": dataset,
                    "source_field": field,
                    "candidate_role": route,
                    "transform": transform,
                    "pit_rule": row["pit_rule"],
                    "priority": _priority(dataset, route, field),
                }
            )
    return out


def _priority(dataset: str, route: str, field: str) -> str:
    if dataset == "uplimit_stocks" and field in {"up_limit_time", "up_limit_keep_times", "fd_close", "fd_max", "auction_turnover", "auction_money"}:
        return "high"
    if dataset == "open_sentiment_data" and field in {"uplimit_num", "downlimit_num", "zb_num", "lb_2_num", "lb_3_num", "max_lb_num", "lb_h_num"}:
        return "high"
    if dataset == "sentiment_hot_day" and field in {"strong", "ztjs", "df_num", "lbgd"}:
        return "high"
    if dataset == "ths_hot_top" and field in {"rank", "rank_diff", "circulation_value"}:
        return "medium"
    if route == "diagnostic_context":
        return "diagnostic"
    return "medium"


def run(*, pack_root: Path, output_root: Path, report_path: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    coverage_rows = _coverage(pack_root)
    route_rows = _field_routes(pack_root)
    transform_rows = _candidate_transforms(route_rows)
    route_counts = Counter(row["route"] for row in route_rows)
    priority_counts = Counter(row["priority"] for row in transform_rows)
    blocked_future = [row for row in route_rows if row["route"] == "blocked_future_label"]
    manual = [row for row in route_rows if row["route"] == "manual_review"]

    _write_csv(output_root / "field_route.csv", route_rows)
    _write_csv(output_root / "candidate_transform_plan.csv", transform_rows)
    _write_csv(output_root / "coverage.csv", coverage_rows)
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_ZZSHARE_LIMIT_SENTIMENT_ROUTE_V1",
        "pack_root": str(pack_root),
        "dataset_count": len(coverage_rows),
        "field_count": len(route_rows),
        "candidate_transform_count": len(transform_rows),
        "route_counts": dict(sorted(route_counts.items())),
        "candidate_priority_counts": dict(sorted(priority_counts.items())),
        "blocked_future_label_fields": blocked_future,
        "manual_review_fields": manual,
        "coverage": coverage_rows,
        "policy": {
            "uplimit_stocks": "minute event context after up_limit_time; T+1 daily event context also allowed",
            "open_sentiment_data": "T+1 lagged daily market context only",
            "sentiment_hot_day": "T+1 lagged daily sentiment context only",
            "ths_hot_top": "T+1 lagged daily stock hot-rank context only",
            "blocked": "next_* and label-like fields are labels/audit only",
        },
        "outputs": {
            "field_route_csv": str(output_root / "field_route.csv"),
            "candidate_transform_plan_csv": str(output_root / "candidate_transform_plan.csv"),
            "coverage_csv": str(output_root / "coverage.csv"),
            "summary_json": str(output_root / "cn_zzshare_limit_sentiment_route_v1.json"),
            "markdown": str(report_path),
        },
        "schema_version": "cn-zzshare-limit-sentiment-route-v1",
    }
    _write_json(output_root / "cn_zzshare_limit_sentiment_route_v1.json", summary)
    _write_markdown(report_path, summary)
    return summary


def _write_markdown(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CN ZZShare Limit/Sentiment Route V1",
        "",
        f"- decision: `{summary['decision']}`",
        f"- field_count: `{summary['field_count']}`",
        f"- candidate_transform_count: `{summary['candidate_transform_count']}`",
        "",
        "## Route Counts",
    ]
    for key, value in summary["route_counts"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Coverage"])
    for row in summary["coverage"]:
        extra = ""
        if "stock_count" in row:
            extra = f", stock_count=`{row['stock_count']}`"
        lines.append(f"- {row['dataset']}: rows=`{row['rows']}`, date=`{row['date_min']}..{row['date_max']}`{extra}")
    lines.extend(
        [
            "",
            "## PIT Boundary",
            "",
            "- `uplimit_stocks.up_limit_time` is a timestamped event key. It is usable only after the event timestamp for minute decisions.",
            "- `open_sentiment_data`, `sentiment_hot_day`, and `ths_hot_top` are T+1 lagged context until observable intraday timestamp is proven.",
            "- `next_*` fields are blocked as future labels and must not enter selector/replay expressions.",
            "",
            "## Next Action",
            "",
            "Build a dedicated ZZShare event/context candidate pack v1 from `candidate_transform_plan.csv`, then run selector-only before replay.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    summary = run(pack_root=args.pack_root, output_root=args.output_root, report_path=args.report_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
