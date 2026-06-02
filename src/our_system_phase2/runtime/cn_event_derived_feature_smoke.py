from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.event_derived_features import (
    attach_event_derived_features,
    event_derived_feature_contract,
    event_derived_feature_coverage_report,
)


DATA_ROOT = Path("G:/Project_V7_Rotation/data/cn_public_enrichment")
LOCAL_MINUTE_DAILY_ROOT = DATA_ROOT / "cn_local_minute_daily_silver_v1_20260531"
UPLIMIT_ROOT = DATA_ROOT / "cn_zzshare_uplimit_history_silver_v1_20260531"
DEFAULT_OUTPUT = Path("reports/cn_event_derived_feature_smoke_20260531")
DEFAULT_FEATURE_PATH = Path("runtime/derived_features/cn_event_daily_features_v1_20260531.parquet")


def _truthy_limit(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip().lower()
    return 1.0 if text in {"1", "1.0", "true", "yes", "y", "是", "涨停"} else 0.0


def _next_trade_date_map(dates: pd.Series) -> dict[pd.Timestamp, pd.Timestamp | None]:
    ordered = sorted(pd.to_datetime(dates, errors="coerce").dropna().unique())
    return {
        pd.Timestamp(date): (pd.Timestamp(ordered[index + 1]) if index + 1 < len(ordered) else None)
        for index, date in enumerate(ordered)
    }


def _load_daily_panel(path: Path) -> pd.DataFrame:
    columns = [
        "date",
        "code",
        "name",
        "industry",
        "open_hfq",
        "high_hfq",
        "low_hfq",
        "close_hfq",
        "pre_close_hfq",
        "volume_shares",
        "amount_yuan",
        "turnover_ratio",
        "pct_chg",
        "amplitude_pct",
        "is_st",
        "volume_ratio",
        "is_limit_up",
        "float_shares",
        "market_cap_yuan",
        "float_market_cap_yuan",
    ]
    frame = pd.read_parquet(path, columns=columns)
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"], errors="coerce"),
            "code": frame["code"].astype(str).str.zfill(6),
            "name": frame["name"],
            "industry": frame["industry"],
            "open": pd.to_numeric(frame["open_hfq"], errors="coerce"),
            "high": pd.to_numeric(frame["high_hfq"], errors="coerce"),
            "low": pd.to_numeric(frame["low_hfq"], errors="coerce"),
            "close": pd.to_numeric(frame["close_hfq"], errors="coerce"),
            "pre_close": pd.to_numeric(frame["pre_close_hfq"], errors="coerce"),
            "volume": pd.to_numeric(frame["volume_shares"], errors="coerce"),
            "amount": pd.to_numeric(frame["amount_yuan"], errors="coerce"),
            "turnover_ratio": pd.to_numeric(frame["turnover_ratio"], errors="coerce"),
            "pct_chg": pd.to_numeric(frame["pct_chg"], errors="coerce"),
            "amplitude_pct": pd.to_numeric(frame["amplitude_pct"], errors="coerce"),
            "is_st": frame["is_st"],
            "volume_ratio": pd.to_numeric(frame["volume_ratio"], errors="coerce"),
            "is_limit_up": frame["is_limit_up"].map(_truthy_limit).astype(float),
            "float_shares": pd.to_numeric(frame["float_shares"], errors="coerce"),
            "market_cap_yuan": pd.to_numeric(frame["market_cap_yuan"], errors="coerce"),
            "float_market_cap_yuan": pd.to_numeric(frame["float_market_cap_yuan"], errors="coerce"),
        }
    )
    return panel.sort_values(["code", "date"]).reset_index(drop=True)


def _load_limit_reason(path: Path) -> pd.DataFrame:
    columns = [
        "date1",
        "stock_code",
        "up_limit_keep_times",
        "up_limit_type",
        "up_limit_time",
        "reason",
        "fengdan_volumn",
        "fengdan_money",
        "fengdan_rate",
        "feng_circulation_rate",
        "actualcirculation_value",
        "turnover_ration_real",
        "amount",
        "plate_code",
        "plate_name",
        "plate_score",
    ]
    frame = pd.read_parquet(path, columns=columns)
    frame["date"] = pd.to_datetime(frame["date1"], errors="coerce")
    frame["code"] = frame["stock_code"].astype(str).str.zfill(6)
    numeric = [
        "up_limit_keep_times",
        "fengdan_volumn",
        "fengdan_money",
        "fengdan_rate",
        "feng_circulation_rate",
        "actualcirculation_value",
        "turnover_ration_real",
        "amount",
        "plate_score",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    grouped = frame.sort_values(["date", "code", "up_limit_time"]).groupby(["date", "code"], as_index=False)
    return grouped.agg(
        reason_record=("reason", "first"),
        limit_up_keep_times_vendor=("up_limit_keep_times", "max"),
        limit_up_type=("up_limit_type", "first"),
        limit_up_time=("up_limit_time", "first"),
        seal_volume=("fengdan_volumn", "max"),
        seal_money=("fengdan_money", "max"),
        seal_rate=("fengdan_rate", "max"),
        seal_circulation_rate=("feng_circulation_rate", "max"),
        actual_circulation_value=("actualcirculation_value", "max"),
        turnover_ratio_real=("turnover_ration_real", "max"),
        limit_reason_amount=("amount", "max"),
        plate_code=("plate_code", "first"),
        plate_name=("plate_name", "first"),
        plate_score=("plate_score", "max"),
    )


def _load_open_board(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["date", "stock_code", "reason"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["code"] = frame["stock_code"].astype(str).str.zfill(6)
    return (
        frame.groupby(["date", "code"], as_index=False)
        .agg(open_board_reason=("reason", "first"))
        .assign(open_board_record=1.0)
    )


def _add_window_counts(frame: pd.DataFrame, max_window_n: int) -> pd.DataFrame:
    result = frame.sort_values(["code", "date"]).copy()
    base_fields = {
        "close": "limit_up_close_event",
        "open": "limit_up_open_event",
        "touch": "limit_up_touch_event",
        "open_not_close": "limit_up_open_not_close",
        "touch_not_close": "limit_up_touch_not_close",
        "close_not_open": "limit_up_close_not_open",
    }
    generated: dict[str, pd.Series] = {}
    grouped = result.groupby("code", sort=False)
    for window in range(2, int(max_window_n) + 1):
        for suffix, field in base_fields.items():
            values = pd.to_numeric(result[field], errors="coerce").fillna(0.0)
            generated[f"limit_up_{suffix}_count_t{window}"] = grouped[field].transform(
                lambda item, w=window: pd.to_numeric(item, errors="coerce").fillna(0.0).rolling(w, min_periods=1).sum()
            )
        generated[f"limit_up_any_open_not_close_in_t{window}"] = generated[f"limit_up_open_not_close_count_t{window}"].gt(0.0).astype(float)
        generated[f"limit_up_any_close_not_open_in_t{window}"] = generated[f"limit_up_close_not_open_count_t{window}"].gt(0.0).astype(float)
    if generated:
        result = pd.concat([result, pd.DataFrame(generated, index=result.index)], axis=1)
    return result


def build_features(
    *,
    output_dir: Path,
    feature_path: Path,
    max_streak_n: int,
    max_window_n: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_path.parent.mkdir(parents=True, exist_ok=True)

    daily = _load_daily_panel(LOCAL_MINUTE_DAILY_ROOT / "hfq_daily_2026/hfq_daily_2026.parquet")
    enriched = attach_event_derived_features(daily, max_streak_n=max_streak_n)
    enriched = _add_window_counts(enriched, max_window_n=max_window_n)

    reason = _load_limit_reason(UPLIMIT_ROOT / "review_uplimit_reason/review_uplimit_reason.parquet")
    open_board = _load_open_board(UPLIMIT_ROOT / "review_uplimit_reason_open/review_uplimit_reason_open.parquet")
    enriched = enriched.merge(reason, on=["date", "code"], how="left")
    enriched = enriched.merge(open_board, on=["date", "code"], how="left")
    enriched["reason_record_exists"] = enriched["reason_record"].notna().astype(float)
    enriched["open_board_record"] = pd.to_numeric(enriched["open_board_record"], errors="coerce").fillna(0.0)
    enriched["close_limit_without_reason_record"] = (
        enriched["limit_up_close_event"].fillna(0.0).gt(0.0) & enriched["reason_record"].isna()
    ).astype(float)
    enriched["reason_record_without_close_limit"] = (
        enriched["reason_record"].notna() & enriched["limit_up_close_event"].fillna(0.0).le(0.0)
    ).astype(float)
    enriched["vendor_streak_minus_derived_close_streak"] = (
        pd.to_numeric(enriched["limit_up_keep_times_vendor"], errors="coerce")
        - pd.to_numeric(enriched["limit_up_streak_close"], errors="coerce")
    )

    next_map = _next_trade_date_map(enriched["date"])
    enriched["event_available_date"] = enriched["date"].map(next_map)
    enriched["event_availability_policy"] = "next_trading_day_conservative"

    selected_columns = _selected_feature_columns(enriched, max_streak_n=max_streak_n, max_window_n=max_window_n)
    feature_frame = enriched[selected_columns].copy()
    feature_frame.to_parquet(feature_path, index=False)

    coverage = event_derived_feature_coverage_report(enriched, max_streak_n=max_streak_n)
    extra = _extra_feature_report(feature_frame, max_window_n=max_window_n)
    payload = {
        "decision": "PASS_CN_EVENT_DERIVED_FEATURE_SMOKE",
        "feature_path": str(feature_path),
        "rows": int(len(feature_frame)),
        "date_min": str(feature_frame["date"].min().date()),
        "date_max": str(feature_frame["date"].max().date()),
        "code_count": int(feature_frame["code"].nunique()),
        "max_streak_n": int(max_streak_n),
        "max_window_n": int(max_window_n),
        "coverage": coverage,
        "extra": extra,
        "contract": event_derived_feature_contract(max_streak_n=max_streak_n),
    }
    (output_dir / "cn_event_derived_feature_smoke.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.DataFrame(_coverage_rows(coverage, extra)).to_csv(
        output_dir / "cn_event_derived_feature_inventory.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (output_dir / "CN_EVENT_DERIVED_FEATURE_SMOKE_2026-05-31.md").write_text(
        _render_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _selected_feature_columns(frame: pd.DataFrame, *, max_streak_n: int, max_window_n: int) -> list[str]:
    base = [
        "date",
        "event_available_date",
        "event_availability_policy",
        "code",
        "name",
        "industry",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "amount",
        "volume",
        "turnover_ratio",
        "pct_chg",
        "is_st",
        "float_shares",
        "market_cap_yuan",
        "float_market_cap_yuan",
        "limit_up_close_event",
        "limit_up_open_event",
        "limit_up_touch_event",
        "limit_up_touch_not_close",
        "limit_up_open_not_close",
        "limit_up_close_not_open",
        "limit_up_break",
        "limit_up_streak_close",
        "limit_up_streak_touch",
        "market_high_board",
        "is_market_high_board",
        "streak_gap_to_market_high",
        "high_board_rank",
        "reason_record_exists",
        "open_board_record",
        "close_limit_without_reason_record",
        "reason_record_without_close_limit",
        "vendor_streak_minus_derived_close_streak",
        "limit_up_keep_times_vendor",
        "limit_up_type",
        "limit_up_time",
        "seal_volume",
        "seal_money",
        "seal_rate",
        "seal_circulation_rate",
        "actual_circulation_value",
        "turnover_ratio_real",
        "limit_reason_amount",
        "plate_code",
        "plate_name",
        "plate_score",
        "reason_record",
        "open_board_reason",
    ]
    parametric = []
    for n in range(1, int(max_streak_n) + 1):
        parametric.extend(
            [
                f"limit_up_streak_ge_{n}",
                f"limit_up_touch_streak_ge_{n}",
                f"break_board_after_streak_ge_{n}",
            ]
        )
    for window in range(2, int(max_window_n) + 1):
        parametric.extend(
            [
                f"limit_up_close_count_t{window}",
                f"limit_up_open_count_t{window}",
                f"limit_up_touch_count_t{window}",
                f"limit_up_open_not_close_count_t{window}",
                f"limit_up_touch_not_close_count_t{window}",
                f"limit_up_close_not_open_count_t{window}",
                f"limit_up_any_open_not_close_in_t{window}",
                f"limit_up_any_close_not_open_in_t{window}",
            ]
        )
    return [column for column in [*base, *parametric] if column in frame.columns]


def _extra_feature_report(frame: pd.DataFrame, *, max_window_n: int) -> dict[str, Any]:
    fields = [
        "reason_record_exists",
        "open_board_record",
        "limit_up_open_not_close",
        "limit_up_touch_not_close",
        "limit_up_close_not_open",
        "close_limit_without_reason_record",
        "reason_record_without_close_limit",
    ]
    for window in (2, 3, 4, 5, 10):
        if window <= max_window_n:
            fields.extend(
                [
                    f"limit_up_close_count_t{window}",
                    f"limit_up_open_not_close_count_t{window}",
                    f"limit_up_close_not_open_count_t{window}",
                ]
            )
    report: dict[str, Any] = {}
    rows = len(frame)
    for field in fields:
        if field not in frame:
            report[field] = {"present": False, "positive_ratio": 0.0}
            continue
        values = pd.to_numeric(frame[field], errors="coerce").fillna(0.0)
        report[field] = {
            "present": True,
            "non_null_ratio": round(float(values.notna().mean()) if rows else 0.0, 6),
            "positive_ratio": round(float(values.gt(0.0).mean()) if rows else 0.0, 6),
            "max": round(float(values.max()) if rows else 0.0, 6),
        }
    return report


def _coverage_rows(coverage: dict[str, Any], extra: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, payload in coverage["coverage"].items():
        rows.append(
            {
                "field": field,
                "source": "event_derived_feature_contract",
                "present": payload.get("present", False),
                "non_null_ratio": payload.get("non_null_ratio", 0.0),
                "positive_ratio": payload.get("positive_ratio", 0.0),
                "max": "",
            }
        )
    for field, payload in extra.items():
        rows.append(
            {
                "field": field,
                "source": "cn_event_panel_extra",
                "present": payload.get("present", False),
                "non_null_ratio": payload.get("non_null_ratio", 0.0),
                "positive_ratio": payload.get("positive_ratio", 0.0),
                "max": payload.get("max", ""),
            }
        )
    return rows


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CN Event Derived Feature Smoke",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Output",
        "",
        f"- feature_path: `{payload['feature_path']}`",
        f"- rows: `{payload['rows']}`",
        f"- date_range: `{payload['date_min']}..{payload['date_max']}`",
        f"- code_count: `{payload['code_count']}`",
        "",
        "## Critical Distinctions",
        "",
        "- `limit_up_open_not_close`: opened at limit proxy but did not close limit.",
        "- `limit_up_touch_not_close`: touched limit intraday but did not close limit.",
        "- `limit_up_close_not_open`: closed limit but was not locked at open.",
        "- `limit_up_*_count_tN`: rolling N-session event counts generated for N=2..max_window_n, not hard-coded to 2/3/4.",
        "- All close/touch/reason fields are marked next-trading-day conservative for daily selection.",
        "",
        "## Selected Coverage",
        "",
        "| field | positive_ratio | max |",
        "| --- | ---: | ---: |",
    ]
    for field, report in payload["extra"].items():
        lines.append(f"| `{field}` | {report.get('positive_ratio', 0.0)} | {report.get('max', '')} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a controlled CN event-derived daily feature smoke panel.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--feature-path", type=Path, default=DEFAULT_FEATURE_PATH)
    parser.add_argument("--max-streak-n", type=int, default=10)
    parser.add_argument("--max-window-n", type=int, default=10)
    args = parser.parse_args()
    payload = build_features(
        output_dir=args.output_dir,
        feature_path=args.feature_path,
        max_streak_n=args.max_streak_n,
        max_window_n=args.max_window_n,
    )
    print(json.dumps({"decision": payload["decision"], "feature_path": payload["feature_path"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
