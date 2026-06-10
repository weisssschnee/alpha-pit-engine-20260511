"""Build a PIT-safe non-1min context panel for the CN minute feature system.

This panel does not create minute-row labels. It only materializes lagged or
announcement-safe context fields that can be joined to the 1-minute code-date
feature panel:

- RZRQ daily flow/liquidity fields: previous available trading day only.
- Fundamental statements: NOTICE_DATE + next trading day.
- Holder-count disclosures: HOLD_NOTICE_DATE + next trading day.
- Billboard disclosures: next trading day, diagnostic-only.
- Market up/down distribution: previous available trading day only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment")
DEFAULT_MINUTE_PANEL = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full_retry1")
DEFAULT_OUTPUT_ROOT = Path("runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602")
DEFAULT_REPORT_ROOT = Path("reports/cn_nonminute_pit_context_panel_v1_20260602")

RZRQ_DAILY = DATA_ROOT / "cn_public_rzrq_daily_silver_v1_20260530" / "rzrq_margin_xsection_daily.parquet"
UPDOWN_DISTRIBUTION = (
    DATA_ROOT
    / "cn_zzshare_uplimit_history_silver_v1_20260531"
    / "updown_distribution"
    / "updown_distribution.parquet"
)
HOLDER_DETAIL = (
    DATA_ROOT
    / "cn_public_xsection_no_kline_silver_v1_20260530"
    / "holder_num_detail"
    / "holder_num_detail.parquet"
)
BILLBOARD_DETAILS = (
    DATA_ROOT
    / "cn_public_xsection_no_kline_silver_v1_20260530"
    / "billboard_details"
    / "billboard_details.parquet"
)
FUND_ROOT = DATA_ROOT / "cn_fundamental_akshare_batch_v1_20260531" / "aggregated_v1"


RZRQ_FIELDS = [
    "RZYE",
    "RZRQYE",
    "RQYE",
    "RZMRE",
    "RZCHE",
    "RZJME",
    "RQMCL",
    "RQCHL",
    "RQJMG",
    "RZYEZB",
    "RZMRE3D",
    "RZMRE5D",
    "RZMRE10D",
    "RZCHE3D",
    "RZCHE5D",
    "RZCHE10D",
    "RZJME3D",
    "RZJME5D",
    "RZJME10D",
    "RQMCL3D",
    "RQMCL5D",
    "RQMCL10D",
    "RQCHL3D",
    "RQCHL5D",
    "RQCHL10D",
    "RQJMG3D",
    "RQJMG5D",
    "RQJMG10D",
    "FIN_BALANCE_GR",
    "SPJ",
    "ZDF",
]

BALANCE_FIELDS = [
    "TOTAL_ASSETS",
    "TOTAL_LIABILITIES",
    "TOTAL_EQUITY",
    "TOTAL_CURRENT_ASSETS",
    "TOTAL_CURRENT_LIAB",
    "TOTAL_NONCURRENT_ASSETS",
    "TOTAL_NONCURRENT_LIAB",
    "MONETARYFUNDS",
    "INVENTORY",
    "GOODWILL",
    "FIXED_ASSET",
    "INTANGIBLE_ASSET",
    "ACCOUNTS_RECE",
    "ACCOUNTS_PAYABLE",
]
PROFIT_FIELDS = [
    "TOTAL_OPERATE_INCOME",
    "OPERATE_INCOME",
    "TOTAL_OPERATE_COST",
    "OPERATE_COST",
    "RESEARCH_EXPENSE",
    "SALE_EXPENSE",
    "MANAGE_EXPENSE",
    "FINANCE_EXPENSE",
    "OPERATE_PROFIT",
    "TOTAL_PROFIT",
    "NETPROFIT",
    "PARENT_NETPROFIT",
    "DEDUCT_PARENT_NETPROFIT",
    "BASIC_EPS",
]
CASH_FIELDS = [
    "TOTAL_OPERATE_INFLOW",
    "TOTAL_OPERATE_OUTFLOW",
    "NETCASH_OPERATE",
    "NETCASH_INVEST",
    "NETCASH_FINANCE",
    "END_CCE",
    "NETPROFIT",
]
HOLDER_FIELDS = [
    "HOLDER_NUM",
    "PRE_HOLDER_NUM",
    "HOLDER_NUM_CHANGE",
    "HOLDER_NUM_RATIO",
    "INTERVAL_CHRATE",
    "AVG_MARKET_CAP",
    "AVG_HOLD_NUM",
    "TOTAL_MARKET_CAP",
    "TOTAL_A_SHARES",
    "CHANGE_SHARES",
    "CLOSE_PRICE",
]
BILLBOARD_SUM_FIELDS = [
    "BILLBOARD_DEAL_AMT",
    "BILLBOARD_SELL_AMT",
    "BILLBOARD_BUY_AMT",
    "BILLBOARD_NET_AMT",
    "ACCUM_AMOUNT",
    "SUM_BUY_AMT",
    "SUM_SELL_AMT",
    "NET_BS_AMT",
]
BILLBOARD_MEAN_FIELDS = [
    "DEAL_AMOUNT_RATIO",
    "FREE_MARKET_CAP",
    "CHANGE_RATE",
    "TURNOVERRATE",
    "DEAL_NET_RATIO",
    "BUY_RATIO",
    "SELL_RATIO",
]
UPDOWN_FIELDS = [
    "ZT",
    "DT",
    "SJZT",
    "SJDT",
    "STZT",
    "STDT",
    "SZJS",
    "XDJS",
    "q_zrcs",
    "q_zrtj",
    "qscln",
    "s_zrcs",
    "s_zrtj",
    "szln",
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


def _append_jsonl(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _schema(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(pq.ParquetFile(path).schema_arrow.names)


def _read_columns(path: Path, wanted: list[str]) -> pd.DataFrame:
    cols = [col for col in wanted if col in _schema(path)]
    if not cols:
        return pd.DataFrame()
    return pd.read_parquet(path, columns=cols)


def _normalize_cn_code(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw or raw == "NAN":
        return ""
    if "." in raw:
        left, right = raw.split(".", 1)
        digits = "".join(ch for ch in left if ch.isdigit())
        suffix = "".join(ch for ch in right if ch.isalpha())
        return f"{digits.zfill(6)}.{suffix}" if digits and suffix else raw
    prefix = raw[:2]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        return ""
    digits = digits[-6:]
    if prefix == "SH":
        return f"{digits}.SH"
    if prefix == "SZ":
        return f"{digits}.SZ"
    if prefix == "BJ":
        return f"{digits}.BJ"
    if digits.startswith(("60", "68", "90", "51", "52", "56", "58", "11", "13")):
        return f"{digits}.SH"
    if digits.startswith(("00", "30", "15", "16", "18", "39", "12", "10")):
        return f"{digits}.SZ"
    if digits.startswith(("43", "83", "87", "88", "92")):
        return f"{digits}.BJ"
    return digits


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def _next_trading_day(source_dates: pd.Series, trade_dates: pd.Series) -> pd.Series:
    calendar = pd.to_datetime(pd.Series(trade_dates.dropna().unique()), errors="coerce").dropna().sort_values()
    values = calendar.to_numpy(dtype="datetime64[ns]")
    src = pd.to_datetime(source_dates, errors="coerce").to_numpy(dtype="datetime64[ns]")
    idx = np.searchsorted(values, src, side="right")
    out = np.full(len(source_dates), np.datetime64("NaT"), dtype="datetime64[ns]")
    valid = idx < len(values)
    out[valid] = values[idx[valid]]
    return pd.Series(pd.to_datetime(out), index=source_dates.index)


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    return (num / den.where(den.abs() > 1e-12)).replace([math.inf, -math.inf], pd.NA)


def _minute_panel_files(minute_panel: Path) -> list[Path]:
    if minute_panel.is_dir():
        return sorted(minute_panel.rglob("*.parquet"))
    return [minute_panel] if minute_panel.exists() else []


def _year_from_path(path: Path) -> int | None:
    for part in path.parts:
        if part.startswith("year="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _load_base_keys(path: Path) -> pd.DataFrame:
    cols = [col for col in ["exec_date", "code"] if col in _schema(path)]
    frame = pd.read_parquet(path, columns=cols)
    frame = frame.rename(columns={"exec_date": "date"})
    frame["date"] = _to_date(frame["date"])
    frame["code"] = frame["code"].map(_normalize_cn_code)
    frame = frame[frame["date"].notna() & (frame["code"] != "")]
    return frame[["date", "code"]].drop_duplicates()


def _prepare_code_daily(
    frame: pd.DataFrame,
    *,
    code_col: str,
    date_col: str,
    trade_dates: pd.Series,
    prefix: str,
    value_fields: list[str],
    source_name: str,
) -> pd.DataFrame:
    if frame.empty or code_col not in frame.columns or date_col not in frame.columns:
        return pd.DataFrame(columns=["code", "available_date"])
    cols = [code_col, date_col, *[col for col in value_fields if col in frame.columns]]
    out = frame[cols].copy()
    out["code"] = out[code_col].map(_normalize_cn_code)
    out["source_date"] = _to_date(out[date_col])
    out["available_date"] = _next_trading_day(out["source_date"], trade_dates)
    out = out[out["code"].ne("") & out["source_date"].notna() & out["available_date"].notna()]
    value_cols = [col for col in value_fields if col in out.columns]
    for col in value_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    rename = {col: f"{prefix}{col.lower()}" for col in value_cols}
    out = out.rename(columns=rename)
    keep = ["code", "available_date", *rename.values()]
    out = out[keep].sort_values(["code", "available_date"])
    out = out.groupby(["code", "available_date"], as_index=False).last()
    out[f"meta_{source_name}_available_date"] = out["available_date"]
    return out.sort_values(["available_date", "code"])


def _prepare_fundamental(
    path: Path,
    *,
    prefix: str,
    value_fields: list[str],
    trade_dates: pd.Series,
    source_name: str,
) -> pd.DataFrame:
    wanted = ["SECUCODE", "source_code6", "NOTICE_DATE", "REPORT_DATE", *value_fields]
    frame = _read_columns(path, wanted)
    if frame.empty:
        return pd.DataFrame(columns=["code", "available_date"])
    code_col = "SECUCODE" if "SECUCODE" in frame.columns else "source_code6"
    frame["code"] = frame[code_col].map(_normalize_cn_code)
    frame["notice_date"] = _to_date(frame["NOTICE_DATE"])
    frame["report_date"] = _to_date(frame["REPORT_DATE"]) if "REPORT_DATE" in frame.columns else pd.NaT
    frame["available_date"] = _next_trading_day(frame["notice_date"], trade_dates)
    frame = frame[frame["code"].ne("") & frame["available_date"].notna()]
    selected = [col for col in value_fields if col in frame.columns]
    for col in selected:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if prefix == "ctx_fund_bs_":
        if {"TOTAL_LIABILITIES", "TOTAL_ASSETS"}.issubset(frame.columns):
            frame["debt_to_assets"] = _safe_div(frame["TOTAL_LIABILITIES"], frame["TOTAL_ASSETS"])
        if {"MONETARYFUNDS", "TOTAL_ASSETS"}.issubset(frame.columns):
            frame["cash_to_assets"] = _safe_div(frame["MONETARYFUNDS"], frame["TOTAL_ASSETS"])
        if {"GOODWILL", "TOTAL_ASSETS"}.issubset(frame.columns):
            frame["goodwill_to_assets"] = _safe_div(frame["GOODWILL"], frame["TOTAL_ASSETS"])
        if {"INVENTORY", "TOTAL_ASSETS"}.issubset(frame.columns):
            frame["inventory_to_assets"] = _safe_div(frame["INVENTORY"], frame["TOTAL_ASSETS"])
    if prefix == "ctx_fund_ps_":
        if {"NETPROFIT", "TOTAL_OPERATE_INCOME"}.issubset(frame.columns):
            frame["netprofit_margin"] = _safe_div(frame["NETPROFIT"], frame["TOTAL_OPERATE_INCOME"])
        if {"OPERATE_PROFIT", "TOTAL_OPERATE_INCOME"}.issubset(frame.columns):
            frame["operate_profit_margin"] = _safe_div(frame["OPERATE_PROFIT"], frame["TOTAL_OPERATE_INCOME"])
        if {"RESEARCH_EXPENSE", "TOTAL_OPERATE_INCOME"}.issubset(frame.columns):
            frame["research_to_income"] = _safe_div(frame["RESEARCH_EXPENSE"], frame["TOTAL_OPERATE_INCOME"])
    if prefix == "ctx_fund_cf_":
        if {"NETCASH_OPERATE", "NETPROFIT"}.issubset(frame.columns):
            frame["operate_cash_to_netprofit"] = _safe_div(frame["NETCASH_OPERATE"], frame["NETPROFIT"])

    derived = [col for col in frame.columns if col in {"debt_to_assets", "cash_to_assets", "goodwill_to_assets", "inventory_to_assets", "netprofit_margin", "operate_profit_margin", "research_to_income", "operate_cash_to_netprofit"}]
    value_cols = selected + derived
    rename = {col: f"{prefix}{col.lower()}" for col in value_cols}
    frame = frame.rename(columns=rename)
    keep = ["code", "available_date", *rename.values()]
    out = frame[keep].sort_values(["code", "available_date"])
    out = out.groupby(["code", "available_date"], as_index=False).last()
    out[f"meta_{source_name}_available_date"] = out["available_date"]
    return out.sort_values(["available_date", "code"])


def _prepare_billboard(trade_dates: pd.Series) -> pd.DataFrame:
    wanted = ["SECURITY_CODE", "SECUCODE", "TRADE_DATE", *BILLBOARD_SUM_FIELDS, *BILLBOARD_MEAN_FIELDS]
    frame = _read_columns(BILLBOARD_DETAILS, wanted)
    if frame.empty:
        return pd.DataFrame(columns=["code", "available_date"])
    code_col = "SECUCODE" if "SECUCODE" in frame.columns else "SECURITY_CODE"
    frame["code"] = frame[code_col].map(_normalize_cn_code)
    frame["source_date"] = _to_date(frame["TRADE_DATE"])
    frame["available_date"] = _next_trading_day(frame["source_date"], trade_dates)
    frame = frame[frame["code"].ne("") & frame["available_date"].notna()]
    for col in [*BILLBOARD_SUM_FIELDS, *BILLBOARD_MEAN_FIELDS]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    agg: dict[str, str] = {col: "sum" for col in BILLBOARD_SUM_FIELDS if col in frame.columns}
    agg.update({col: "mean" for col in BILLBOARD_MEAN_FIELDS if col in frame.columns})
    agg["source_date"] = "count"
    out = frame.groupby(["code", "available_date"], as_index=False).agg(agg)
    out = out.rename(columns={"source_date": "ctx_billboard_event_count"})
    for col in list(out.columns):
        if col in {"code", "available_date", "ctx_billboard_event_count"}:
            continue
        out = out.rename(columns={col: f"ctx_billboard_{col.lower()}"})
    out["meta_billboard_available_date"] = out["available_date"]
    return out.sort_values(["available_date", "code"])


def _prepare_updown(trade_dates: pd.Series) -> pd.DataFrame:
    frame = _read_columns(UPDOWN_DISTRIBUTION, ["date", *UPDOWN_FIELDS])
    if frame.empty:
        return pd.DataFrame(columns=["available_date"])
    frame["source_date"] = _to_date(frame["date"])
    frame["available_date"] = _next_trading_day(frame["source_date"], trade_dates)
    frame = frame[frame["available_date"].notna()]
    value_cols = [col for col in UPDOWN_FIELDS if col in frame.columns]
    for col in value_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    rename = {col: f"ctx_mkt_updown_{col.lower()}" for col in value_cols}
    out = frame.rename(columns=rename)[["available_date", *rename.values()]]
    if {"ctx_mkt_updown_zt", "ctx_mkt_updown_dt"}.issubset(out.columns):
        out["ctx_mkt_updown_zt_dt_ratio"] = _safe_div(out["ctx_mkt_updown_zt"], out["ctx_mkt_updown_dt"])
    out = out.groupby("available_date", as_index=False).last()
    out["meta_updown_available_date"] = out["available_date"]
    return out.sort_values("available_date")


def _merge_code_asof(base: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return base
    left = base.sort_values(["date", "code"]).reset_index(drop=True)
    right = events.sort_values(["available_date", "code"]).reset_index(drop=True)
    return pd.merge_asof(
        left,
        right,
        left_on="date",
        right_on="available_date",
        by="code",
        direction="backward",
        allow_exact_matches=True,
    ).drop(columns=["available_date"], errors="ignore")


def _merge_market_asof(base: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return base
    left = base.sort_values("date").reset_index(drop=True)
    right = events.sort_values("available_date").reset_index(drop=True)
    return pd.merge_asof(
        left,
        right,
        left_on="date",
        right_on="available_date",
        direction="backward",
        allow_exact_matches=True,
    ).drop(columns=["available_date"], errors="ignore")


def _coverage_rows(frame: pd.DataFrame, *, year: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for prefix, family in [
        ("ctx_rzrq_", "rzrq_daily"),
        ("ctx_fund_bs_", "fundamental_balance"),
        ("ctx_fund_ps_", "fundamental_profit"),
        ("ctx_fund_cf_", "fundamental_cashflow"),
        ("ctx_holder_", "holder_count"),
        ("ctx_billboard_", "billboard_diagnostic"),
        ("ctx_mkt_updown_", "market_updown"),
    ]:
        cols = [col for col in frame.columns if col.startswith(prefix)]
        if not cols:
            rows.append({"year": year, "family": family, "columns": 0, "mean_nonnull_rate": 0.0, "max_nonnull_rate": 0.0})
            continue
        rates = frame[cols].notna().mean(numeric_only=False)
        rows.append(
            {
                "year": year,
                "family": family,
                "columns": len(cols),
                "mean_nonnull_rate": float(rates.mean()),
                "max_nonnull_rate": float(rates.max()),
            }
        )
    return rows


def _contract_rows(columns: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for col in columns:
        if col in {"date", "code", "year"}:
            role = "key"
            family = "key"
            allowed = "false_key_only"
            rule = "not a feature"
        elif col.startswith("meta_"):
            role = "metadata"
            family = "availability_metadata"
            allowed = "false_metadata_only"
            rule = "audit only; not selector input"
        elif col.startswith("ctx_billboard_"):
            role = "diagnostic_context"
            family = "billboard_disclosure"
            allowed = "diagnostic_until_disclosure_timestamp_contract"
            rule = "next trading day after trade-date disclosure proxy"
        elif col.startswith("ctx_fund_") or col.startswith("ctx_holder_"):
            role = "pit_context"
            family = "announcement_pit"
            allowed = "true_after_notice_date"
            rule = "NOTICE/HOLD_NOTICE date plus next trading day"
        elif col.startswith("ctx_rzrq_") or col.startswith("ctx_mkt_updown_"):
            role = "lagged_context"
            family = "lagged_daily"
            allowed = "true_lagged_only"
            rule = "source date plus next trading day"
        else:
            role = "unknown"
            family = "unknown"
            allowed = "false_until_review"
            rule = "manual review required"
        rows.append(
            {
                "field_name": col,
                "field_family": family,
                "field_role": role,
                "selector_allowed": allowed,
                "pit_rule": rule,
            }
        )
    return rows


def run(
    *,
    minute_panel: Path,
    output_root: Path,
    report_root: Path,
    years: list[int] | None,
    progress_path: Path | None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    files = _minute_panel_files(minute_panel)
    if years:
        wanted = set(years)
        files = [path for path in files if _year_from_path(path) in wanted]
    if not files:
        raise FileNotFoundError(f"no minute panel parquet files found under {minute_panel}")

    all_base_keys = []
    file_years: dict[Path, int] = {}
    for path in files:
        year = _year_from_path(path)
        if year is None:
            sample = _load_base_keys(path)
            year = int(sample["date"].dt.year.mode().iloc[0])
            all_base_keys.append(sample)
        else:
            sample = _load_base_keys(path)
            all_base_keys.append(sample)
        file_years[path] = year
    base_all = pd.concat(all_base_keys, ignore_index=True).drop_duplicates()
    trade_dates = base_all["date"].drop_duplicates().sort_values()
    _append_jsonl(progress_path, {"event": "base_keys_loaded", "rows": int(base_all.shape[0]), "trade_dates": int(trade_dates.shape[0])})

    rzrq = _prepare_code_daily(
        _read_columns(RZRQ_DAILY, ["DATE", "SECUCODE", "SCODE", *RZRQ_FIELDS]),
        code_col="SECUCODE",
        date_col="DATE",
        trade_dates=trade_dates,
        prefix="ctx_rzrq_",
        value_fields=RZRQ_FIELDS,
        source_name="rzrq",
    )
    fund_bs = _prepare_fundamental(
        FUND_ROOT / "balance_sheet_report_em" / "balance_sheet_report_em.parquet",
        prefix="ctx_fund_bs_",
        value_fields=BALANCE_FIELDS,
        trade_dates=trade_dates,
        source_name="fund_bs",
    )
    fund_ps = _prepare_fundamental(
        FUND_ROOT / "profit_sheet_report_em" / "profit_sheet_report_em.parquet",
        prefix="ctx_fund_ps_",
        value_fields=PROFIT_FIELDS,
        trade_dates=trade_dates,
        source_name="fund_ps",
    )
    fund_cf = _prepare_fundamental(
        FUND_ROOT / "cash_flow_sheet_report_em" / "cash_flow_sheet_report_em.parquet",
        prefix="ctx_fund_cf_",
        value_fields=CASH_FIELDS,
        trade_dates=trade_dates,
        source_name="fund_cf",
    )
    holder = _prepare_code_daily(
        _read_columns(HOLDER_DETAIL, ["SECUCODE", "SECURITY_CODE", "HOLD_NOTICE_DATE", *HOLDER_FIELDS]),
        code_col="SECUCODE",
        date_col="HOLD_NOTICE_DATE",
        trade_dates=trade_dates,
        prefix="ctx_holder_",
        value_fields=HOLDER_FIELDS,
        source_name="holder",
    )
    billboard = _prepare_billboard(trade_dates)
    updown = _prepare_updown(trade_dates)
    source_sizes = {
        "rzrq_rows": int(rzrq.shape[0]),
        "fund_bs_rows": int(fund_bs.shape[0]),
        "fund_ps_rows": int(fund_ps.shape[0]),
        "fund_cf_rows": int(fund_cf.shape[0]),
        "holder_rows": int(holder.shape[0]),
        "billboard_rows": int(billboard.shape[0]),
        "updown_rows": int(updown.shape[0]),
    }
    _append_jsonl(progress_path, {"event": "sources_prepared", **source_sizes})

    coverage: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    all_columns: set[str] = {"date", "code", "year"}
    for year in sorted(set(file_years.values())):
        year_base_parts = [_load_base_keys(path) for path, file_year in file_years.items() if file_year == year]
        base = pd.concat(year_base_parts, ignore_index=True).drop_duplicates()
        base["year"] = year
        _append_jsonl(progress_path, {"event": "year_start", "year": year, "base_rows": int(base.shape[0])})

        frame = base
        for source_name, source_frame in [
            ("rzrq", rzrq),
            ("fund_bs", fund_bs),
            ("fund_ps", fund_ps),
            ("fund_cf", fund_cf),
            ("holder", holder),
            ("billboard", billboard),
        ]:
            frame = _merge_code_asof(frame, source_frame)
            _append_jsonl(progress_path, {"event": "source_merged", "year": year, "source": source_name, "columns": int(frame.shape[1])})
        frame = _merge_market_asof(frame, updown)
        frame = frame.sort_values(["date", "code"]).reset_index(drop=True)
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        for col in [col for col in frame.columns if col.startswith("meta_")]:
            frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.strftime("%Y-%m-%d")

        out_path = output_root / f"year={year}" / "part.parquet"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(out_path, index=False)
        all_columns.update(frame.columns)
        coverage.extend(_coverage_rows(frame, year=year))
        year_rows.append({"year": year, "rows": int(frame.shape[0]), "columns": int(frame.shape[1]), "path": str(out_path)})
        _append_jsonl(progress_path, {"event": "year_written", "year": year, "rows": int(frame.shape[0]), "columns": int(frame.shape[1]), "path": str(out_path)})

    field_contract = _contract_rows(sorted(all_columns))
    _write_csv(output_root / "field_contract.csv", field_contract)
    _write_csv(output_root / "coverage_by_family_year.csv", coverage)
    _write_csv(output_root / "year_outputs.csv", year_rows)

    status_counts = pd.DataFrame(field_contract)["selector_allowed"].value_counts(dropna=False).to_dict()
    summary = {
        "decision": "PASS_NONMINUTE_PIT_CONTEXT_PANEL_V1",
        "minute_panel": str(minute_panel),
        "output_root": str(output_root),
        "report_root": str(report_root),
        "years": sorted(set(file_years.values())),
        "total_rows": int(sum(row["rows"] for row in year_rows)),
        "year_outputs": year_rows,
        "source_sizes": source_sizes,
        "field_count": len(field_contract),
        "selector_allowed_counts": {str(key): int(value) for key, value in status_counts.items()},
        "coverage_csv": str(output_root / "coverage_by_family_year.csv"),
        "field_contract_csv": str(output_root / "field_contract.csv"),
        "year_outputs_csv": str(output_root / "year_outputs.csv"),
        "pit_boundary": {
            "rzrq": "source DATE plus next trading day",
            "fundamentals": "NOTICE_DATE plus next trading day",
            "holder": "HOLD_NOTICE_DATE plus next trading day",
            "billboard": "TRADE_DATE plus next trading day, diagnostic only",
            "updown_distribution": "source date plus next trading day",
        },
    }
    write_json_artifact(report_root / "cn_nonminute_pit_context_panel_v1.json", summary)
    lines = [
        "# CN Non-1min PIT Context Panel v1 - 2026-06-02",
        "",
        f"decision: `{summary['decision']}`",
        f"total_rows: `{summary['total_rows']}`",
        f"field_count: `{summary['field_count']}`",
        "",
        "## Output",
        "",
        f"- panel_root: `{output_root}`",
        f"- field_contract: `{summary['field_contract_csv']}`",
        f"- coverage: `{summary['coverage_csv']}`",
        "",
        "## Boundary",
        "",
        "- RZRQ and market distribution are lagged to the next trading day.",
        "- Fundamentals and holder fields are available only after notice date plus next trading day.",
        "- Billboard fields are diagnostic-only until a stronger disclosure timestamp contract is proven.",
        "- Metadata columns are audit-only and cannot enter selector scoring.",
        "",
        "## Year Outputs",
        "",
    ]
    for row in year_rows:
        lines.append(f"- `{row['year']}`: rows `{row['rows']}`, columns `{row['columns']}`")
    (report_root / "CN_NONMINUTE_PIT_CONTEXT_PANEL_V1_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minute-panel", type=Path, default=DEFAULT_MINUTE_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--years", default="", help="Optional comma-separated year list, for example 2026 or 2024,2025.")
    parser.add_argument("--progress-path", type=Path, default=None)
    args = parser.parse_args()
    years = [int(item.strip()) for item in args.years.split(",") if item.strip()] if args.years else None
    summary = run(
        minute_panel=args.minute_panel,
        output_root=args.output_root,
        report_root=args.report_root,
        years=years,
        progress_path=args.progress_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(summary["decision"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
