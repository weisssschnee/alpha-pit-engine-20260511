from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


DEFAULT_AGG_ROOT = Path(
    "G:/Project_V7_Rotation/data/cn_public_enrichment/"
    "cn_fundamental_akshare_batch_v1_20260531/aggregated_v1"
)
DEFAULT_DAILY_PANEL = Path("runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_augmented_v1_20260531.parquet")
DEFAULT_OUTPUT_PANEL = Path("runtime/fundamental_features/cn_fundamental_daily_pit_features_v1_20260531.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/cn_fundamental_pit_feature_panel_20260531")


BALANCE_FEATURES = {
    "TOTAL_ASSETS": "fund_total_assets",
    "TOTAL_LIABILITIES": "fund_total_liabilities",
    "TOTAL_EQUITY": "fund_total_equity",
    "TOTAL_CURRENT_ASSETS": "fund_total_current_assets",
    "TOTAL_CURRENT_LIAB": "fund_total_current_liab",
    "MONETARYFUNDS": "fund_monetary_funds",
    "INVENTORY": "fund_inventory",
    "GOODWILL": "fund_goodwill",
    "FIXED_ASSET": "fund_fixed_asset",
}
PROFIT_FEATURES = {
    "TOTAL_OPERATE_INCOME": "fund_total_operate_income",
    "OPERATE_INCOME": "fund_operate_income",
    "TOTAL_OPERATE_COST": "fund_total_operate_cost",
    "OPERATE_PROFIT": "fund_operate_profit",
    "TOTAL_PROFIT": "fund_total_profit",
    "NETPROFIT": "fund_netprofit",
    "PARENT_NETPROFIT": "fund_parent_netprofit",
    "DEDUCT_PARENT_NETPROFIT": "fund_deduct_parent_netprofit",
    "BASIC_EPS": "fund_basic_eps",
    "RESEARCH_EXPENSE": "fund_research_expense",
}
CASH_FEATURES = {
    "NETCASH_OPERATE": "fund_netcash_operate",
    "NETCASH_INVEST": "fund_netcash_invest",
    "NETCASH_FINANCE": "fund_netcash_finance",
    "END_CASH": "fund_end_cash",
    "NETPROFIT": "fund_cash_statement_netprofit",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataset_path(root: Path, name: str) -> Path:
    return root / name / f"{name}.parquet"


def _parquet_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def _code6(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().str.extract(r"(\d{6})$", expand=False).fillna(series.astype(str).str[-6:]).str.zfill(6)


def _load_daily_keys(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["date", "code"])
    frame["_row_id"] = np.arange(len(frame), dtype=np.int64)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["code"] = frame["code"].astype(str)
    frame["source_code6"] = _code6(frame["code"])
    return frame.dropna(subset=["date", "source_code6"]).sort_values(["source_code6", "date"]).reset_index(drop=True)


def _next_trade_date_map(dates: pd.Series) -> dict[pd.Timestamp, pd.Timestamp | None]:
    ordered = sorted(pd.to_datetime(dates, errors="coerce").dropna().unique())
    as_ts = [pd.Timestamp(item) for item in ordered]
    out: dict[pd.Timestamp, pd.Timestamp | None] = {}
    for date in as_ts:
        index = np.searchsorted(as_ts, date, side="right")
        out[date] = as_ts[index] if index < len(as_ts) else None
    return out


def _availability_from_notice(notice: pd.Series, trade_dates: pd.Series) -> pd.Series:
    ordered = sorted(pd.to_datetime(trade_dates, errors="coerce").dropna().unique())
    ordered_ts = [pd.Timestamp(item) for item in ordered]

    def one(value: Any) -> pd.Timestamp | pd.NaT:
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt) or dt < pd.Timestamp("1990-01-01"):
            return pd.NaT
        index = np.searchsorted(ordered_ts, pd.Timestamp(dt), side="right")
        if index >= len(ordered_ts):
            return pd.NaT
        return ordered_ts[index]

    return notice.map(one)


def _statement_features(root: Path, dataset: str, mapping: dict[str, str], trade_dates: pd.Series) -> pd.DataFrame:
    path = _dataset_path(root, dataset)
    usecols = ["source_code6", "REPORT_DATE", "NOTICE_DATE", *[col for col in mapping if col]]
    available_columns = _parquet_columns(path)
    frame = pd.read_parquet(path, columns=[col for col in usecols if col in available_columns])
    frame["source_code6"] = _code6(frame["source_code6"])
    frame["report_date"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
    frame["notice_date"] = pd.to_datetime(frame["NOTICE_DATE"], errors="coerce")
    frame["available_date"] = _availability_from_notice(frame["notice_date"], trade_dates)
    frame = frame.dropna(subset=["source_code6", "available_date"]).copy()
    rename = {old: new for old, new in mapping.items() if old in frame.columns}
    for old in rename:
        frame[old] = pd.to_numeric(frame[old], errors="coerce")
    frame = frame.rename(columns=rename)
    keep = ["source_code6", "available_date", "report_date", "notice_date", *rename.values()]
    frame = frame[keep].sort_values(["source_code6", "available_date", "report_date", "notice_date"])
    frame = frame.drop_duplicates(["source_code6", "available_date"], keep="last")
    prefix = dataset.replace("_report_em", "")
    frame = frame.rename(
        columns={
            "report_date": f"{prefix}_report_date",
            "notice_date": f"{prefix}_notice_date",
            "available_date": f"{prefix}_available_date",
        }
    )
    return frame


def _holder_features(root: Path, trade_dates: pd.Series) -> pd.DataFrame:
    main = pd.read_parquet(_dataset_path(root, "main_stock_holder_sina"))
    main["source_code6"] = _code6(main["source_code6"])
    main["notice_date"] = pd.to_datetime(main["公告日期"], errors="coerce")
    main["holder_period_date"] = pd.to_datetime(main["截至日期"], errors="coerce")
    main["available_date"] = _availability_from_notice(main["notice_date"], trade_dates)
    main["holder_pct"] = pd.to_numeric(main.get("持股比例"), errors="coerce")
    main["holder_count"] = pd.to_numeric(main.get("股东总数"), errors="coerce")
    main["avg_holding"] = pd.to_numeric(main.get("平均持股数"), errors="coerce")
    main_agg = (
        main.dropna(subset=["source_code6", "available_date"])
        .sort_values(["source_code6", "available_date", "holder_period_date"])
        .groupby(["source_code6", "available_date"], as_index=False)
        .agg(
            fund_top1_holder_pct=("holder_pct", "max"),
            fund_top10_holder_pct=("holder_pct", "sum"),
            fund_holder_count=("holder_count", "max"),
            fund_avg_holding=("avg_holding", "max"),
            holder_period_date=("holder_period_date", "max"),
            holder_notice_date=("notice_date", "max"),
        )
    )

    circ = pd.read_parquet(_dataset_path(root, "circulate_stock_holder_sina"))
    circ["source_code6"] = _code6(circ["source_code6"])
    circ["notice_date"] = pd.to_datetime(circ["公告日期"], errors="coerce")
    circ["available_date"] = _availability_from_notice(circ["notice_date"], trade_dates)
    circ["circ_pct"] = pd.to_numeric(circ.get("占流通股比例"), errors="coerce")
    circ_agg = (
        circ.dropna(subset=["source_code6", "available_date"])
        .groupby(["source_code6", "available_date"], as_index=False)
        .agg(fund_circulate_top10_holder_pct=("circ_pct", "sum"))
    )
    merged = main_agg.merge(circ_agg, on=["source_code6", "available_date"], how="outer")
    merged = merged.sort_values(["source_code6", "available_date"]).drop_duplicates(["source_code6", "available_date"], keep="last")
    return merged


def _share_change_features(root: Path, trade_dates: pd.Series) -> pd.DataFrame:
    frame = pd.read_parquet(_dataset_path(root, "share_change_cninfo"))
    frame["source_code6"] = _code6(frame["source_code6"])
    frame["notice_date"] = pd.to_datetime(frame["公告日期"], errors="coerce")
    frame["share_change_date"] = pd.to_datetime(frame["变动日期"], errors="coerce")
    frame["available_date"] = _availability_from_notice(frame["notice_date"], trade_dates)
    mapping = {
        "总股本": "fund_total_shares_cninfo",
        "已流通股份": "fund_float_shares_cninfo",
        "流通受限股份": "fund_restricted_shares_cninfo",
    }
    for col in mapping:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    keep = ["source_code6", "available_date", "share_change_date", "notice_date", *[col for col in mapping if col in frame.columns]]
    out = frame.dropna(subset=["source_code6", "available_date"])[keep].rename(columns=mapping)
    out = out.sort_values(["source_code6", "available_date", "share_change_date", "notice_date"]).drop_duplicates(
        ["source_code6", "available_date"], keep="last"
    )
    return out.rename(columns={"notice_date": "share_change_notice_date"})


def _merge_asof_by_code(daily: pd.DataFrame, event_frame: pd.DataFrame, available_col: str) -> pd.DataFrame:
    if event_frame.empty:
        return daily
    pieces: list[pd.DataFrame] = []
    feature_cols = [col for col in event_frame.columns if col not in {"source_code6", available_col}]
    for code, left in daily[["_row_id", "date", "source_code6"]].groupby("source_code6", sort=False):
        right = event_frame[event_frame["source_code6"].eq(code)].sort_values(available_col)
        base = left.sort_values("date")
        if right.empty:
            empty = base.copy()
            for col in feature_cols:
                empty[col] = pd.NA
            pieces.append(empty)
            continue
        merged = pd.merge_asof(
            base,
            right.drop(columns=["source_code6"]).sort_values(available_col),
            left_on="date",
            right_on=available_col,
            direction="backward",
        )
        pieces.append(merged)
    return pd.concat(pieces, ignore_index=True)


def _safe_div(left: pd.Series, right: pd.Series) -> pd.Series:
    return pd.to_numeric(left, errors="coerce") / pd.to_numeric(right, errors="coerce").replace(0, np.nan)


def build_panel(*, agg_root: Path, daily_panel: Path, output_panel: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_panel.parent.mkdir(parents=True, exist_ok=True)
    daily = _load_daily_keys(daily_panel)
    trade_dates = daily["date"]

    sources = [
        ("balance_sheet", _statement_features(agg_root, "balance_sheet_report_em", BALANCE_FEATURES, trade_dates), "balance_sheet_available_date"),
        ("profit_sheet", _statement_features(agg_root, "profit_sheet_report_em", PROFIT_FEATURES, trade_dates), "profit_sheet_available_date"),
        ("cash_flow_sheet", _statement_features(agg_root, "cash_flow_sheet_report_em", CASH_FEATURES, trade_dates), "cash_flow_sheet_available_date"),
        ("holder", _holder_features(agg_root, trade_dates), "available_date"),
        ("share_change", _share_change_features(agg_root, trade_dates), "available_date"),
    ]
    out = daily[["_row_id", "date", "code", "source_code6"]].copy()
    coverage: dict[str, Any] = {}
    for name, event_frame, available_col in sources:
        merged = _merge_asof_by_code(daily, event_frame, available_col)
        add_cols = [col for col in merged.columns if col not in {"_row_id", "date", "source_code6"}]
        out = out.merge(merged[["_row_id", *add_cols]], on="_row_id", how="left", validate="1:1")
        feature_cols = [col for col in add_cols if col.startswith("fund_")]
        coverage[name] = {
            "event_rows": int(len(event_frame)),
            "feature_cols": feature_cols,
            "row_any_feature_coverage": round(float(out[feature_cols].notna().any(axis=1).mean()), 6) if feature_cols else 0.0,
        }

    out["fund_debt_to_assets"] = _safe_div(out.get("fund_total_liabilities"), out.get("fund_total_assets"))
    out["fund_cash_to_assets"] = _safe_div(out.get("fund_monetary_funds"), out.get("fund_total_assets"))
    out["fund_goodwill_to_assets"] = _safe_div(out.get("fund_goodwill"), out.get("fund_total_assets"))
    out["fund_inventory_to_assets"] = _safe_div(out.get("fund_inventory"), out.get("fund_total_assets"))
    out["fund_current_ratio"] = _safe_div(out.get("fund_total_current_assets"), out.get("fund_total_current_liab"))
    out["fund_netprofit_margin"] = _safe_div(out.get("fund_parent_netprofit"), out.get("fund_operate_income"))
    out["fund_ocf_to_netprofit"] = _safe_div(out.get("fund_netcash_operate"), out.get("fund_parent_netprofit"))
    out["fund_ocf_to_assets"] = _safe_div(out.get("fund_netcash_operate"), out.get("fund_total_assets"))
    out["fund_research_to_income"] = _safe_div(out.get("fund_research_expense"), out.get("fund_operate_income"))
    out["fund_float_share_ratio_cninfo"] = _safe_div(out.get("fund_float_shares_cninfo"), out.get("fund_total_shares_cninfo"))

    out = out.drop(columns=["_row_id"])
    out.to_parquet(output_panel, index=False)
    fund_cols = [col for col in out.columns if col.startswith("fund_")]
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_CN_FUNDAMENTAL_PIT_FEATURE_PANEL_BUILT",
        "output_panel": str(output_panel),
        "output_sha256": _file_sha256(output_panel),
        "source": {
            "agg_root": str(agg_root),
            "daily_panel": str(daily_panel),
        },
        "counts": {
            "rows": int(len(out)),
            "columns": int(len(out.columns)),
            "fundamental_feature_columns": int(len(fund_cols)),
            "codes": int(out["source_code6"].nunique()),
            "rows_with_any_fundamental_feature": int(out[fund_cols].notna().any(axis=1).sum()),
        },
        "date_range": {
            "min_date": str(out["date"].min().date()),
            "max_date": str(out["date"].max().date()),
        },
        "coverage": coverage,
        "feature_columns": fund_cols,
        "policy": {
            "availability": "announcement/notice date plus next trading day only",
            "not_included": "financial_analysis_indicator_sina, zygc_em, dividend_cninfo until announcement-date issues are resolved",
            "scope": "top200 fundamental controlled smoke joined onto mature daily panel",
        },
    }
    _write_json(output_dir / "cn_fundamental_pit_feature_panel.json", payload)
    _write_markdown(output_dir / "CN_FUNDAMENTAL_PIT_FEATURE_PANEL_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    counts = payload["counts"]
    lines = [
        "# CN Fundamental PIT Feature Panel",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Counts",
        "",
        f"- rows: {counts['rows']}",
        f"- columns: {counts['columns']}",
        f"- fundamental feature columns: {counts['fundamental_feature_columns']}",
        f"- rows with any fundamental feature: {counts['rows_with_any_fundamental_feature']}",
        "",
        "## Policy",
        "",
        f"- availability: {payload['policy']['availability']}",
        f"- not included: {payload['policy']['not_included']}",
        "",
        "## Output",
        "",
        f"- panel: `{payload['output_panel']}`",
        f"- sha256: `{payload['output_sha256']}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agg-root", type=Path, default=DEFAULT_AGG_ROOT)
    parser.add_argument("--daily-panel", type=Path, default=DEFAULT_DAILY_PANEL)
    parser.add_argument("--output-panel", type=Path, default=DEFAULT_OUTPUT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build_panel(
        agg_root=args.agg_root,
        daily_panel=args.daily_panel,
        output_panel=args.output_panel,
        output_dir=args.output_dir,
    )
    print(json.dumps({"decision": payload["decision"], "counts": payload["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
