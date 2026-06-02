"""Build a 1-minute-native feature panel with lagged daily context.

The output is a research panel for intraday/minute work. It keeps:

- `m1_*` features observable from early minute bars,
- `ctx_*` features joined from the previous daily/enrichment row,
- `label_*` execution/evaluation labels that must not enter selectors.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_MINUTE_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
)
DEFAULT_DAILY_PANEL = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_OUTPUT = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v1_20260601")


def _round(value: Any, digits: int = 8) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _normalize_cn_code(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return raw
    if "." in raw:
        left, right = raw.split(".", 1)
        digits = "".join(ch for ch in left if ch.isdigit())
        suffix = "".join(ch for ch in right if ch.isalpha())
        return f"{digits.zfill(6)}.{suffix}" if digits and suffix else raw
    prefix = raw[:2]
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 6:
        return raw
    digits = digits[-6:]
    if prefix == "SH":
        return f"{digits}.SH"
    if prefix == "SZ":
        return f"{digits}.SZ"
    if prefix == "BJ":
        return f"{digits}.BJ"
    if digits.startswith(("60", "68", "90", "51", "52", "56", "58")):
        return f"{digits}.SH"
    if digits.startswith(("00", "30", "15", "16", "18", "39")):
        return f"{digits}.SZ"
    if digits.startswith(("43", "83", "87", "88", "92")):
        return f"{digits}.BJ"
    return raw


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def _manifest_rows(path: Path, start: str, end: str, limit: int) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    for row in rows:
        date = str(row.get("date") or "")
        if start <= date <= end and Path(str(row.get("silver_file") or "")).exists():
            out.append(row)
    out.sort(key=lambda row: str(row.get("date") or ""))
    return out[:limit] if limit > 0 else out


def _context_columns(daily_columns: list[str]) -> list[str]:
    fixed = [
        "amount",
        "volume",
        "turnover_ratio",
        "turnover_ratio_real",
        "pct_chg",
        "amplitude_pct",
        "volume_ratio",
        "is_limit_up",
        "is_limit_down",
        "susp",
        "is_st",
        "float_market_cap",
        "final_float_market_cap",
        "market_cap",
        "final_total_market_cap",
    ]
    limit_cols = [
        col
        for col in daily_columns
        if col.startswith("limit_up_streak")
        or col in {"limit_up_break", "limit_up_touch_event", "limit_up_touch_not_close", "limit_up_open_not_close"}
        or col.startswith("limit_up_close_count_t")
        or col.startswith("limit_up_touch_not_close_count_t")
        or col.startswith("limit_up_open_not_close_count_t")
    ]
    fund_cols = [col for col in daily_columns if col.startswith("fund_")]
    selected = ["date", "code"] + [col for col in fixed + limit_cols + fund_cols if col in daily_columns]
    out: list[str] = []
    for col in selected:
        if col not in out:
            out.append(col)
    return out


def _load_daily_context(path: Path) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.Timestamp]]:
    all_columns = pq.ParquetFile(path).schema_arrow.names
    columns = _context_columns(all_columns)
    daily = pd.read_parquet(path, columns=columns)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily["_code_norm"] = daily["code"].map(_normalize_cn_code)
    rename = {col: f"ctx_{col}" for col in daily.columns if col not in {"date", "code", "_code_norm"}}
    daily = daily.rename(columns=rename)
    trade_dates = sorted(pd.to_datetime(daily["date"], errors="coerce").dropna().unique())
    prior_by_date = {pd.Timestamp(trade_dates[i]).normalize(): pd.Timestamp(trade_dates[i - 1]).normalize() for i in range(1, len(trade_dates))}
    return daily, prior_by_date


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    den = pd.to_numeric(den, errors="coerce")
    out = pd.to_numeric(num, errors="coerce") / den.where(den.abs() > 1e-12)
    return out.replace([math.inf, -math.inf], pd.NA)


def _vwap_features(part: pd.DataFrame, prefix: str) -> pd.DataFrame:
    vol = pd.to_numeric(part["vol"], errors="coerce").fillna(0.0)
    close = pd.to_numeric(part["close"], errors="coerce")
    amount = pd.to_numeric(part["amount"], errors="coerce").fillna(0.0)
    grouped = part.assign(_px_vol=close * vol, _vol=vol, _amount=amount).groupby("code", sort=False)
    agg = grouped.agg(
        **{
            f"{prefix}_bars": ("trade_time", "count"),
            f"{prefix}_px_vol": ("_px_vol", "sum"),
            f"{prefix}_vol": ("_vol", "sum"),
            f"{prefix}_amount": ("_amount", "sum"),
            f"{prefix}_high": ("high", "max"),
            f"{prefix}_low": ("low", "min"),
            f"{prefix}_last_close": ("close", "last"),
        }
    )
    agg[f"{prefix}_vwap"] = _safe_div(agg[f"{prefix}_px_vol"], agg[f"{prefix}_vol"])
    agg = agg.drop(columns=[f"{prefix}_px_vol"])
    return agg


def _minute_features(path: Path) -> pd.DataFrame:
    cols = ["code", "trade_time", "open", "high", "low", "close", "vol", "amount", "pre_close"]
    frame = pd.read_parquet(path, columns=cols)
    frame["code"] = frame["code"].astype(str).str.strip().str.upper()
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame = frame.sort_values(["code", "trade_time"])
    base = (
        frame.groupby("code", sort=False)
        .agg(
            m1_open=("open", "first"),
            m1_pre_close=("pre_close", "first"),
            m1_day_close=("close", "last"),
            m1_day_high=("high", "max"),
            m1_day_low=("low", "min"),
            m1_amount_day=("amount", "sum"),
            m1_vol_day=("vol", "sum"),
        )
        .reset_index()
    )
    for column in [col for col in base.columns if col != "code"]:
        base[column] = pd.to_numeric(base[column], errors="coerce")
    first5 = _vwap_features(frame.groupby("code", sort=False).head(5), "m1_first5")
    first15 = _vwap_features(frame.groupby("code", sort=False).head(15), "m1_first15")
    first30 = _vwap_features(frame.groupby("code", sort=False).head(30), "m1_first30")
    out = base.merge(first5, left_on="code", right_index=True, how="left")
    out = out.merge(first15, left_on="code", right_index=True, how="left")
    out = out.merge(first30, left_on="code", right_index=True, how="left")
    out["m1_open_gap_vs_preclose"] = _safe_div(out["m1_open"], out["m1_pre_close"]) - 1.0
    for prefix in ("m1_first5", "m1_first15", "m1_first30"):
        out[f"{prefix}_vwap_return_vs_open"] = _safe_div(out[f"{prefix}_vwap"], out["m1_open"]) - 1.0
        out[f"{prefix}_last_return_vs_open"] = _safe_div(out[f"{prefix}_last_close"], out["m1_open"]) - 1.0
        out[f"{prefix}_range"] = _safe_div(out[f"{prefix}_high"], out[f"{prefix}_low"]) - 1.0
        out[f"label_{prefix}_vwap_to_close"] = _safe_div(out["m1_day_close"], out[f"{prefix}_vwap"]) - 1.0
    out["label_open_to_close"] = _safe_div(out["m1_day_close"], out["m1_open"]) - 1.0
    out["label_day_range"] = _safe_div(out["m1_day_high"], out["m1_day_low"]) - 1.0
    return out


def run(
    *,
    minute_root: Path,
    daily_panel_path: Path,
    output_root: Path,
    start_date: str,
    end_date: str,
    limit_days: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = _manifest_rows(minute_root / "stock_1min_2026_manifest.csv", start_date.replace("-", ""), end_date.replace("-", ""), limit_days)
    daily, prior_by_date = _load_daily_context(daily_panel_path)
    daily_by_date = {pd.Timestamp(date).normalize(): group for date, group in daily.groupby("date", sort=False)}
    rows: list[pd.DataFrame] = []
    manifest_rows: list[dict[str, Any]] = []
    for item in manifest:
        exec_date = pd.Timestamp(str(item["date"])).normalize()
        signal_date = prior_by_date.get(exec_date)
        if signal_date is None:
            continue
        minute = _minute_features(Path(str(item["silver_file"])))
        context = daily_by_date.get(signal_date)
        if context is None:
            continue
        context = context.drop(columns=["date", "code"]).copy()
        merged = minute.merge(context, left_on="code", right_on="_code_norm", how="left").drop(columns=["_code_norm"])
        merged.insert(0, "exec_date", exec_date.date().isoformat())
        merged.insert(1, "signal_date", signal_date.date().isoformat())
        for prefix in ("m1_first5", "m1_first15", "m1_first30"):
            if "ctx_amount" in merged.columns:
                merged[f"{prefix}_amount_vs_ctx_amount"] = _safe_div(merged[f"{prefix}_amount"], merged["ctx_amount"])
            if "ctx_float_market_cap" in merged.columns:
                merged[f"{prefix}_amount_vs_ctx_float_mcap"] = _safe_div(merged[f"{prefix}_amount"], merged["ctx_float_market_cap"])
        rows.append(merged)
        manifest_rows.append(
            {
                "exec_date": exec_date.date().isoformat(),
                "signal_date": signal_date.date().isoformat(),
                "rows": int(merged.shape[0]),
                "context_matched_rows": int(merged["ctx_amount"].notna().sum()) if "ctx_amount" in merged.columns else None,
                "context_match_rate": _round(merged["ctx_amount"].notna().mean()) if "ctx_amount" in merged.columns else None,
                "source_file": str(item["silver_file"]),
            }
        )
    if not rows:
        raise RuntimeError("No minute feature rows were built.")
    panel = pd.concat(rows, ignore_index=True)
    panel_path = output_root / "cn_minute_feature_panel_v1_2026_available.parquet"
    panel.to_parquet(panel_path, index=False)
    _write_csv(output_root / "cn_minute_feature_panel_v1_manifest.csv", manifest_rows)
    feature_contract = []
    for column in panel.columns:
        if column.startswith("label_"):
            role = "evaluation_label_not_selector_input"
            earliest = "future_after_execution"
        elif column.startswith("m1_first5"):
            role = "minute_native_feature"
            earliest = "09:35"
        elif column.startswith("m1_first15"):
            role = "minute_native_feature"
            earliest = "09:45"
        elif column.startswith("m1_first30"):
            role = "minute_native_feature"
            earliest = "10:00"
        elif column.startswith("m1_"):
            role = "minute_native_feature_or_day_summary"
            earliest = "depends_on_field; day summary is label/diagnostic"
        elif column.startswith("ctx_"):
            role = "lagged_daily_context_feature"
            earliest = "available_from_signal_date_prior_to_exec_date"
        else:
            role = "key"
            earliest = "n/a"
        feature_contract.append({"field_name": column, "role": role, "earliest_valid_use": earliest})
    _write_csv(output_root / "cn_minute_feature_panel_v1_contract.csv", feature_contract)
    summary = {
        "decision": "PASS_MINUTE_FEATURE_PANEL_V1_BUILT",
        "panel_path": str(panel_path),
        "rows": int(panel.shape[0]),
        "columns": int(panel.shape[1]),
        "exec_date_start": str(panel["exec_date"].min()),
        "exec_date_end": str(panel["exec_date"].max()),
        "unique_symbols": int(panel["code"].nunique()),
        "days": int(panel["exec_date"].nunique()),
        "median_context_match_rate": _round(pd.DataFrame(manifest_rows)["context_match_rate"].median()),
        "label_columns": [col for col in panel.columns if col.startswith("label_")],
        "minute_feature_columns": [col for col in panel.columns if col.startswith("m1_") and not col.startswith("m1_day")][:80],
        "context_columns": [col for col in panel.columns if col.startswith("ctx_")][:80],
        "outputs": {
            "panel": str(panel_path),
            "manifest": str(output_root / "cn_minute_feature_panel_v1_manifest.csv"),
            "contract": str(output_root / "cn_minute_feature_panel_v1_contract.csv"),
            "json": str(output_root / "cn_minute_feature_panel_v1_report.json"),
            "markdown": str(output_root / "CN_MINUTE_FEATURE_PANEL_V1_REPORT_2026-06-01.md"),
        },
    }
    write_json_artifact(output_root / "cn_minute_feature_panel_v1_report.json", summary)
    lines = [
        "# CN Minute Feature Panel V1 - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"rows: `{summary['rows']}`",
        f"columns: `{summary['columns']}`",
        f"coverage: `{summary['exec_date_start']}` to `{summary['exec_date_end']}`",
        f"unique_symbols: `{summary['unique_symbols']}`",
        f"median_context_match_rate: `{summary['median_context_match_rate']}`",
        "",
        "## Boundary",
        "",
        "- `m1_first5/*15/*30` fields are minute-native features with explicit earliest signal times.",
        "- `ctx_*` fields are lagged daily/enrichment context from the previous trading day.",
        "- `label_*` fields are future execution/evaluation labels and are forbidden as selector inputs.",
    ]
    (output_root / "CN_MINUTE_FEATURE_PANEL_V1_REPORT_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_MINUTE_FEATURE_PANEL_V1_DECISION_2026-06-01.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minute-root", type=Path, default=DEFAULT_MINUTE_ROOT)
    parser.add_argument("--daily-panel-path", type=Path, default=DEFAULT_DAILY_PANEL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", default="2026-01-05")
    parser.add_argument("--end-date", default="2026-04-10")
    parser.add_argument("--limit-days", type=int, default=0)
    args = parser.parse_args()
    summary = run(
        minute_root=args.minute_root,
        daily_panel_path=args.daily_panel_path,
        output_root=args.output_root,
        start_date=args.start_date,
        end_date=args.end_date,
        limit_days=args.limit_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
