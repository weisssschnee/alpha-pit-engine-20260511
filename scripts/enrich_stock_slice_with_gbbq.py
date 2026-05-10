# -*- coding: utf-8 -*-
"""
Enrich a stock OHLCV slice with point-in-time share capital from TDX gbbq.

The TDX gbbq file is a compact capital-change event store. This script keeps
the output recent by exporting only events from the requested start date onward,
plus one pre-start seed record per stock for correct as-of joins.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "scripts" / "data" / "phase2_stock_validation_slice_2026-04-27.parquet"
DEFAULT_GBBQ = Path(r"G:\tdxmock\T0002\hq_cache\gbbq")
DEFAULT_START_DATE = "2020-01-01"


def _import_gbbq_reader():
    try:
        from pytdx.reader import GbbqReader  # type: ignore

        return GbbqReader
    except Exception:
        fallback = Path(r"G:\PythonProject\.venv\Lib\site-packages")
        if fallback.exists():
            sys.path.append(str(fallback))
        from pytdx.reader import GbbqReader  # type: ignore

        return GbbqReader


def _market_prefix(market: object) -> str | None:
    try:
        m = int(market)
    except Exception:
        return None
    if m == 0:
        return "sz"
    if m == 1:
        return "sh"
    if m == 2:
        return "bj"
    return None


def _instrument_type(symbol: object) -> str:
    s = str(symbol)
    if len(s) < 8:
        return "unknown"
    prefix = s[:2]
    code = s[2:]
    if prefix == "sh":
        if code.startswith(("000", "880", "881", "882", "883", "884", "885", "886", "887", "888", "889")):
            return "index"
        if code.startswith(("5", "1")):
            return "fund_or_bond"
        if code.startswith("6"):
            return "stock"
    if prefix == "sz":
        if code.startswith("399"):
            return "index"
        if code.startswith(("15", "16", "18")):
            return "fund_or_bond"
        if code.startswith(("00", "30")):
            return "stock"
    if prefix == "bj":
        if code.startswith(("4", "8", "9")):
            return "stock"
    return "unknown"


def load_gbbq_events(gbbq_path: Path, start_date: str) -> pd.DataFrame:
    if not gbbq_path.exists():
        raise FileNotFoundError(f"gbbq file not found: {gbbq_path}")

    GbbqReader = _import_gbbq_reader()
    raw = GbbqReader().get_df(str(gbbq_path))
    if raw.empty:
        raise ValueError(f"gbbq reader returned no rows: {gbbq_path}")

    events = raw.loc[raw["category"] == 5].copy()
    if events.empty:
        raise ValueError("gbbq has no category=5 share-capital events")

    events["market_prefix"] = events["market"].map(_market_prefix)
    events = events.loc[events["market_prefix"].notna()].copy()
    events["bare_code"] = events["code"].astype(str).str.zfill(6)
    events["symbol"] = events["market_prefix"] + events["bare_code"]
    events["event_date"] = pd.to_datetime(
        events["datetime"].astype(str), format="%Y%m%d", errors="coerce"
    ).astype("datetime64[ns]")
    events = events.loc[events["event_date"].notna()].copy()

    events = events.rename(
        columns={
            "hongli_panqianliutong": "before_float_share_10k",
            "peigujia_qianzongguben": "before_total_share_10k",
            "songgu_qianzongguben": "after_float_share_10k",
            "peigu_houzongguben": "after_total_share_10k",
        }
    )
    numeric_cols = [
        "before_float_share_10k",
        "before_total_share_10k",
        "after_float_share_10k",
        "after_total_share_10k",
    ]
    for col in numeric_cols:
        events[col] = pd.to_numeric(events[col], errors="coerce")

    events = events.sort_values(["symbol", "event_date"])
    start_ts = pd.Timestamp(start_date)

    pre_seed = (
        events.loc[events["event_date"] < start_ts]
        .groupby("symbol", as_index=False, sort=False)
        .tail(1)
        .assign(is_pre_start_seed=True)
    )
    pre_seed["source_event_date"] = pre_seed["event_date"]
    pre_seed["event_date"] = start_ts
    recent = events.loc[events["event_date"] >= start_ts].copy()
    recent["is_pre_start_seed"] = False
    recent["source_event_date"] = recent["event_date"]

    keep_cols = [
        "symbol",
        "market_prefix",
        "bare_code",
        "event_date",
        "source_event_date",
        "is_pre_start_seed",
        "before_float_share_10k",
        "before_total_share_10k",
        "after_float_share_10k",
        "after_total_share_10k",
    ]
    scoped = pd.concat([pre_seed[keep_cols], recent[keep_cols]], ignore_index=True)
    scoped = scoped.sort_values(["symbol", "event_date"]).reset_index(drop=True)

    scoped["float_share"] = scoped["after_float_share_10k"] * 10000.0
    scoped["total_share"] = scoped["after_total_share_10k"] * 10000.0
    scoped["float_share_source"] = "tdx_gbbq_category5_after_float"
    scoped["total_share_source"] = "tdx_gbbq_category5_after_total"
    return scoped


def enrich_slice(input_path: Path, events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    if not input_path.exists():
        raise FileNotFoundError(f"input slice not found: {input_path}")

    data = pd.read_parquet(input_path)
    required = {"date", "code", "close"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"input slice is missing required columns: {missing}")

    out = data.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").astype("datetime64[ns]")
    out["symbol"] = out["code"].astype(str)
    if "market" in out.columns:
        code_has_prefix = out["symbol"].str.match(r"^(sh|sz|bj)\d{6}$", na=False)
        out.loc[~code_has_prefix, "symbol"] = out.loc[~code_has_prefix, "market"].astype(str) + out.loc[
            ~code_has_prefix, "symbol"
        ].str[-6:]

    event_cols = [
        "symbol",
        "event_date",
        "source_event_date",
        "float_share",
        "total_share",
        "after_float_share_10k",
        "after_total_share_10k",
        "float_share_source",
        "total_share_source",
    ]
    events_for_join = events[event_cols].rename(
        columns={"event_date": "capital_event_date", "source_event_date": "capital_source_event_date"}
    )

    pieces: list[pd.DataFrame] = []
    for symbol, group in out.sort_values(["symbol", "date"]).groupby("symbol", sort=False):
        ev = events_for_join.loc[events_for_join["symbol"] == symbol].sort_values("capital_event_date")
        if ev.empty:
            g = group.copy()
            for col in events_for_join.columns:
                if col != "symbol":
                    g[col] = np.nan
            pieces.append(g)
            continue
        joined = pd.merge_asof(
            group.sort_values("date"),
            ev,
            left_on="date",
            right_on="capital_event_date",
            by="symbol",
            direction="backward",
            allow_exact_matches=True,
        )
        pieces.append(joined)

    enriched = pd.concat(pieces, ignore_index=True)
    enriched["instrument_type"] = enriched["symbol"].map(_instrument_type)
    enriched["is_capital_applicable"] = enriched["instrument_type"].eq("stock")
    enriched["market_cap"] = pd.to_numeric(enriched["close"], errors="coerce") * enriched["total_share"]
    enriched["float_market_cap"] = pd.to_numeric(enriched["close"], errors="coerce") * enriched["float_share"]
    enriched["market_cap_billion"] = enriched["market_cap"] / 1e9
    enriched["float_market_cap_billion"] = enriched["float_market_cap"] / 1e9
    enriched["gbbq_has_capital"] = enriched["total_share"].notna() & enriched["float_share"].notna()

    enriched["capital_event_date"] = pd.to_datetime(enriched["capital_event_date"], errors="coerce")
    enriched["capital_source_event_date"] = pd.to_datetime(enriched["capital_source_event_date"], errors="coerce")
    coverage = float(enriched["gbbq_has_capital"].mean()) if len(enriched) else 0.0
    applicable = enriched["is_capital_applicable"]
    applicable_coverage = (
        float(enriched.loc[applicable, "gbbq_has_capital"].mean()) if bool(applicable.any()) else 0.0
    )
    report = {
        "input": str(input_path),
        "rows": int(len(enriched)),
        "symbols": int(enriched["symbol"].nunique()),
        "date_min": str(enriched["date"].min()),
        "date_max": str(enriched["date"].max()),
        "coverage_rows": coverage,
        "coverage_capital_applicable_rows": applicable_coverage,
        "missing_rows": int((~enriched["gbbq_has_capital"]).sum()),
        "missing_symbols": int(
            enriched.loc[~enriched["gbbq_has_capital"], "symbol"].dropna().nunique()
        ),
        "capital_applicable_rows": int(applicable.sum()),
        "capital_applicable_symbols": int(enriched.loc[applicable, "symbol"].nunique()),
        "missing_capital_applicable_rows": int((applicable & ~enriched["gbbq_has_capital"]).sum()),
        "missing_capital_applicable_symbols": int(
            enriched.loc[applicable & ~enriched["gbbq_has_capital"], "symbol"].dropna().nunique()
        ),
        "instrument_type_counts": {
            str(k): int(v) for k, v in enriched["instrument_type"].value_counts(dropna=False).to_dict().items()
        },
        "capital_event_min": str(enriched["capital_event_date"].min()),
        "capital_event_max": str(enriched["capital_event_date"].max()),
    }
    return enriched, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--gbbq", type=Path, default=DEFAULT_GBBQ)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--events-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()

    start_tag = args.start_date.replace("-", "")
    output = args.output or args.input.with_name(f"{args.input.stem}_gbbq_cap_enriched_{start_tag}.parquet")
    events_output = args.events_output or args.input.with_name(f"tdx_gbbq_capital_events_since_{start_tag}.parquet")
    report_output = args.report_output or args.input.with_name(f"{output.stem}_report.json")

    events = load_gbbq_events(args.gbbq, args.start_date)
    enriched, report = enrich_slice(args.input, events)

    output.parent.mkdir(parents=True, exist_ok=True)
    events_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    events.to_parquet(events_output, index=False)
    enriched.to_parquet(output, index=False)
    report.update(
        {
            "gbbq": str(args.gbbq),
            "start_date": args.start_date,
            "events_output": str(events_output),
            "events_rows": int(len(events)),
            "events_symbols": int(events["symbol"].nunique()),
            "events_pre_start_seeds": int(events["is_pre_start_seed"].sum()),
            "output": str(output),
        }
    )
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
