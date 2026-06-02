"""Audit 1-minute data alignment with lagged daily/enrichment features.

This script is intentionally read-only. It separates:

- minute-native fields that can support intraday features,
- lagged daily/enrichment context that can be used before a minute trade date,
- future intraday labels/execution diagnostics that must not enter selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_MINUTE_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531"
)
DEFAULT_DAILY_PANEL = Path(
    "runtime/datasets/phase2_stock_tdx_official_20250806_to_20260508_cn_event_fundamental_augmented_v2_20260531.parquet"
)
DEFAULT_OUTPUT = Path("reports/cn_minute_feature_alignment_audit_20260601")


def _round(value: Any, digits: int = 6) -> float | None:
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _field_group(column: str) -> str:
    lower = column.lower()
    if lower in {"date", "code", "name", "industry"}:
        return "identity"
    if lower.startswith("fund_"):
        return "fundamental_context_lagged"
    if "limit" in lower:
        return "daily_limit_event_context_lagged"
    if any(token in lower for token in ["amount", "volume", "turnover", "float", "market_cap", "cap_"]):
        return "daily_flow_liquidity_capacity_context_lagged"
    if any(token in lower for token in ["open", "high", "low", "close", "return", "pct", "ma", "amplitude"]):
        return "daily_price_state_context_lagged"
    if any(token in lower for token in ["susp", "st", "delist", "list_date"]):
        return "tradability_context_lagged"
    return "other_daily_context_lagged"


def _manifest_rows(path: Path, start: str, end: str) -> list[dict[str, Any]]:
    rows = _read_csv(path)
    out: list[dict[str, Any]] = []
    for row in rows:
        date = str(row.get("date") or "")
        if start <= date <= end and Path(str(row.get("silver_file") or "")).exists():
            out.append(row)
    out.sort(key=lambda row: str(row.get("date") or ""))
    return out


def _minute_schema(path: Path) -> dict[str, Any]:
    frame = pd.read_parquet(path)
    return {
        "columns": list(frame.columns),
        "rows": int(frame.shape[0]),
        "unique_codes": int(frame["code"].astype(str).nunique()) if "code" in frame.columns else 0,
        "time_min": str(pd.to_datetime(frame["trade_time"], errors="coerce").min()) if "trade_time" in frame.columns else None,
        "time_max": str(pd.to_datetime(frame["trade_time"], errors="coerce").max()) if "trade_time" in frame.columns else None,
    }


def _minute_early_feature_sample(path: Path) -> list[dict[str, Any]]:
    cols = ["code", "trade_time", "open", "close", "vol", "amount", "pre_close"]
    frame = pd.read_parquet(path, columns=cols)
    frame["code"] = frame["code"].astype(str).str.strip().str.upper()
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    rows: list[dict[str, Any]] = []
    for code, group in frame.groupby("code", sort=False):
        if len(rows) >= 500:
            break
        group = group.sort_values("trade_time")
        first5 = group.head(5)
        first30 = group.head(30)

        def _vwap(part: pd.DataFrame) -> float | None:
            vol = pd.to_numeric(part["vol"], errors="coerce").fillna(0.0)
            close = pd.to_numeric(part["close"], errors="coerce")
            if float(vol.sum()) <= 0:
                return None
            return float((close * vol).sum() / vol.sum())

        open_price = float(group.iloc[0]["open"])
        pre_close = float(group.iloc[0]["pre_close"])
        vwap5 = _vwap(first5)
        vwap30 = _vwap(first30)
        rows.append(
            {
                "code": code,
                "open_gap_vs_preclose": _round(open_price / pre_close - 1.0 if pre_close > 0 else None, 8),
                "first5_vwap_return_vs_open": _round(vwap5 / open_price - 1.0 if vwap5 and open_price > 0 else None, 8),
                "first30_vwap_return_vs_open": _round(vwap30 / open_price - 1.0 if vwap30 and open_price > 0 else None, 8),
                "amount5": _round(pd.to_numeric(first5["amount"], errors="coerce").fillna(0.0).sum()),
                "amount30": _round(pd.to_numeric(first30["amount"], errors="coerce").fillna(0.0).sum()),
            }
        )
    return rows


def _coverage_by_group(daily: pd.DataFrame, signal_dates: set[pd.Timestamp], minute_codes_by_date: dict[pd.Timestamp, set[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped_columns: dict[str, list[str]] = {}
    for column in daily.columns:
        if column in {"date", "code", "_code_norm"}:
            continue
        grouped_columns.setdefault(_field_group(column), []).append(column)

    daily_by_date = {pd.Timestamp(date).normalize(): group for date, group in daily.groupby(pd.to_datetime(daily["date"]).dt.normalize(), sort=False)}
    for signal_date in sorted(signal_dates):
        day = daily_by_date.get(signal_date)
        if day is None:
            continue
        # The execution date is the next manifest date whose signal date maps here.
        relevant_exec_dates = [exec_date for exec_date in minute_codes_by_date if exec_date > signal_date]
        if not relevant_exec_dates:
            continue
        minute_codes = minute_codes_by_date[min(relevant_exec_dates)]
        subset = day[day["_code_norm"].isin(minute_codes)]
        for group_name, columns in grouped_columns.items():
            if not columns or subset.empty:
                continue
            nonnull = subset[columns].notna().mean().mean()
            rows.append(
                {
                    "signal_date": signal_date.date().isoformat(),
                    "field_group": group_name,
                    "field_count": len(columns),
                    "matched_symbols": int(subset.shape[0]),
                    "mean_field_coverage": _round(nonnull),
                    "sample_fields": "|".join(columns[:20]),
                }
            )
    return rows


def run(
    *,
    minute_root: Path,
    daily_panel_path: Path,
    output_root: Path,
    start_date: str,
    end_date: str,
    sample_days: int,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = minute_root / "stock_1min_2026_manifest.csv"
    manifest = _manifest_rows(manifest_path, start_date.replace("-", ""), end_date.replace("-", ""))
    if sample_days > 0:
        manifest = manifest[:sample_days]
    if not manifest:
        raise FileNotFoundError(f"No minute partitions found in {manifest_path}")

    daily = pd.read_parquet(daily_panel_path)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily["_code_norm"] = daily["code"].map(_normalize_cn_code)
    trade_dates = sorted(pd.to_datetime(daily["date"], errors="coerce").dropna().unique())
    prior_by_date = {pd.Timestamp(trade_dates[i]).normalize(): pd.Timestamp(trade_dates[i - 1]).normalize() for i in range(1, len(trade_dates))}

    schema = _minute_schema(Path(str(manifest[0]["silver_file"])))
    minute_codes_by_date: dict[pd.Timestamp, set[str]] = {}
    overlap_rows: list[dict[str, Any]] = []
    signal_dates: set[pd.Timestamp] = set()
    for row in manifest:
        exec_date = pd.Timestamp(str(row["date"])).normalize()
        signal_date = prior_by_date.get(exec_date)
        if signal_date is None:
            continue
        signal_dates.add(signal_date)
        sample = pd.read_parquet(str(row["silver_file"]), columns=["code"])
        minute_codes = set(sample["code"].astype(str).str.strip().str.upper().dropna().unique())
        minute_codes_by_date[exec_date] = minute_codes
        same_day = daily[daily["date"] == exec_date]
        prior_day = daily[daily["date"] == signal_date]
        same_codes = set(same_day["_code_norm"].dropna().astype(str))
        prior_codes = set(prior_day["_code_norm"].dropna().astype(str))
        overlap_rows.append(
            {
                "exec_date": exec_date.date().isoformat(),
                "signal_date": signal_date.date().isoformat(),
                "minute_symbols": len(minute_codes),
                "daily_same_day_symbols": len(same_codes),
                "daily_prior_signal_symbols": len(prior_codes),
                "same_day_overlap": len(minute_codes & same_codes),
                "same_day_overlap_rate": _round(len(minute_codes & same_codes) / len(minute_codes) if minute_codes else None),
                "prior_signal_overlap": len(minute_codes & prior_codes),
                "prior_signal_overlap_rate": _round(len(minute_codes & prior_codes) / len(minute_codes) if minute_codes else None),
                "minute_only_symbols_prior": len(minute_codes - prior_codes),
                "daily_only_symbols_prior": len(prior_codes - minute_codes),
            }
        )

    field_routes: list[dict[str, Any]] = []
    for column in daily.columns:
        if column == "_code_norm":
            continue
        group = _field_group(column)
        field_routes.append(
            {
                "field_name": column,
                "source_frequency": "daily_or_enrichment",
                "route": "lagged_context_feature",
                "field_group": group,
                "allowed_minute_use": "trade_date_minus_1_or_earlier_context_only",
                "forbidden_use": "same_day_intraday_selection_without_timestamp_contract",
            }
        )
    for column in schema["columns"]:
        role = "minute_native_feature"
        allowed = "observable_after_bar_close_for_intraday_signal"
        if column in {"close", "high", "low"}:
            allowed = "observable_after_current_bar_close; future bars are labels only"
        field_routes.append(
            {
                "field_name": column,
                "source_frequency": "1min",
                "route": role,
                "field_group": "minute_ohlcv_amount",
                "allowed_minute_use": allowed,
                "forbidden_use": "future_bar_use_before_bar_timestamp",
            }
        )
    derived_routes = [
        {
            "feature_name": "open_gap_vs_preclose",
            "source": "1min open + pre_close",
            "earliest_signal_time": "09:30 bar close",
            "economic_role": "overnight repricing / auction imbalance proxy",
            "allowed": "intraday signal after first bar; daily T+1 context if lagged",
        },
        {
            "feature_name": "first5_vwap_return_vs_open",
            "source": "first five 1min bars",
            "earliest_signal_time": "09:35",
            "economic_role": "early chase/exhaustion and immediate flow pressure",
            "allowed": "trade after 09:35 only",
        },
        {
            "feature_name": "first30_amount_vs_prior_daily_amount",
            "source": "first30 minute amount + prior daily amount",
            "earliest_signal_time": "10:00",
            "economic_role": "early abnormal participation relative to prior liquidity",
            "allowed": "trade after 10:00 only",
        },
        {
            "feature_name": "vwap5_to_close_return",
            "source": "future close after 09:35 execution",
            "earliest_signal_time": "label_only",
            "economic_role": "execution calibration / forward label",
            "allowed": "evaluation only; never selector input",
        },
    ]
    coverage_rows = _coverage_by_group(daily, signal_dates, minute_codes_by_date)
    early_sample = _minute_early_feature_sample(Path(str(manifest[0]["silver_file"])))

    _write_csv(output_root / "minute_daily_overlap_by_date.csv", overlap_rows)
    _write_csv(output_root / "field_route_contract.csv", field_routes)
    _write_csv(output_root / "lagged_context_coverage_by_group.csv", coverage_rows)
    _write_csv(output_root / "minute_early_feature_sample.csv", early_sample)
    _write_csv(output_root / "minute_derived_feature_contract.csv", derived_routes)

    overlap_frame = pd.DataFrame(overlap_rows)
    coverage_frame = pd.DataFrame(coverage_rows)
    summary = {
        "decision": "PASS_MINUTE_DAILY_ALIGNMENT_AUDIT",
        "minute_root": str(minute_root),
        "daily_panel_path": str(daily_panel_path),
        "minute_schema": schema,
        "audited_minute_days": int(len(overlap_rows)),
        "minute_date_start": overlap_rows[0]["exec_date"] if overlap_rows else None,
        "minute_date_end": overlap_rows[-1]["exec_date"] if overlap_rows else None,
        "median_prior_signal_overlap_rate": _round(overlap_frame["prior_signal_overlap_rate"].median()) if not overlap_frame.empty else None,
        "min_prior_signal_overlap_rate": _round(overlap_frame["prior_signal_overlap_rate"].min()) if not overlap_frame.empty else None,
        "daily_columns": int(len(daily.columns) - 1),
        "daily_field_groups": coverage_frame.groupby("field_group")["field_count"].max().to_dict() if not coverage_frame.empty else {},
        "outputs": {
            "overlap_csv": str(output_root / "minute_daily_overlap_by_date.csv"),
            "field_route_contract_csv": str(output_root / "field_route_contract.csv"),
            "coverage_csv": str(output_root / "lagged_context_coverage_by_group.csv"),
            "minute_derived_contract_csv": str(output_root / "minute_derived_feature_contract.csv"),
            "early_feature_sample_csv": str(output_root / "minute_early_feature_sample.csv"),
            "json": str(output_root / "cn_minute_feature_alignment_audit.json"),
            "markdown": str(output_root / "CN_MINUTE_FEATURE_ALIGNMENT_AUDIT_2026-06-01.md"),
        },
    }
    write_json_artifact(output_root / "cn_minute_feature_alignment_audit.json", summary)

    lines = [
        "# CN Minute Feature Alignment Audit - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"audited_minute_days: `{summary['audited_minute_days']}`",
        f"minute_coverage_audited: `{summary['minute_date_start']}` to `{summary['minute_date_end']}`",
        f"minute_columns: `{', '.join(schema['columns'])}`",
        f"median_prior_signal_overlap_rate: `{summary['median_prior_signal_overlap_rate']}`",
        f"min_prior_signal_overlap_rate: `{summary['min_prior_signal_overlap_rate']}`",
        "",
        "## Interpretation",
        "",
        "- 1min native fields are not the same object as daily/enrichment fields.",
        "- Daily/fundamental/event fields are allowed only as lagged context for a minute trade date unless a timestamp contract proves intraday availability.",
        "- Future intraday bars and close-derived returns are execution labels/diagnostics, not selector features.",
        "- The next valid 1min feature step is to build minute-native early-session features and join lagged daily context by normalized code and prior trading day.",
        "",
        "## Outputs",
        "",
    ]
    for key, value in summary["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    (output_root / "CN_MINUTE_FEATURE_ALIGNMENT_AUDIT_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_MINUTE_FEATURE_ALIGNMENT_AUDIT_DECISION_2026-06-01.md").write_text(
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
    parser.add_argument("--sample-days", type=int, default=0, help="0 means all matching 2026 minute dates.")
    args = parser.parse_args()
    summary = run(
        minute_root=args.minute_root,
        daily_panel_path=args.daily_panel_path,
        output_root=args.output_root,
        start_date=args.start_date,
        end_date=args.end_date,
        sample_days=args.sample_days,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
