# -*- coding: utf-8 -*-
"""
Extract selected GPJYVALUE series from TDX tdxgp package.

Each stock file record is 13 bytes:
    uint8 type_id, uint32 date(YYYYMMDD), float value1, float value2
"""

from __future__ import annotations

import argparse
import json
import struct
import zipfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "scripts" / "data"
DEFAULT_TDXGP = Path(r"G:\tdxgp (1).zip")
DEFAULT_START_DATE = "2025-08-06"
RECORD = struct.Struct("<BIff")

GPJY_META = {
    1: ("shareholder_count", "count", "GPJYVALUE(1): shareholder count"),
    2: ("lhb_total", "10k_cny", "GPJYVALUE(2): dragon-tiger total buy/sell"),
    3: ("margin_balance", "mixed", "GPJYVALUE(3): margin balance / short balance"),
    4: ("block_trade", "mixed", "GPJYVALUE(4): block trade avg px / amount"),
    5: ("holder_change", "mixed", "GPJYVALUE(5): insider trade avg px / shares"),
    6: ("northbound_holding", "share", "GPJYVALUE(6): northbound holding shares"),
    7: ("northbound_turnover", "10k_cny", "GPJYVALUE(7): northbound net buy"),
    8: ("lhb_inst_sell", "mixed", "GPJYVALUE(8): dragon-tiger institutional sell"),
    9: ("lhb_inst_buy", "mixed", "GPJYVALUE(9): dragon-tiger institutional buy"),
    10: ("investor_relations", "mixed", "GPJYVALUE(10): investor-relations events"),
    11: ("margin_buy_repay", "10k_cny", "GPJYVALUE(11): margin buy / repay"),
    12: ("short_sell_repay", "share", "GPJYVALUE(12): short sell / short repay"),
    13: ("margin_net", "mixed", "GPJYVALUE(13): net margin / net short"),
    15: ("limit_status", "mixed", "GPJYVALUE(15): limit-up/down status"),
    16: ("total_market_value", "10k_cny", "GPJYVALUE(16): total market value"),
    17: ("lhb_broker_branch", "10k_cny", "GPJYVALUE(17): dragon-tiger broker branch"),
    18: ("lhb_connect", "10k_cny", "GPJYVALUE(18): dragon-tiger stock connect"),
}


def symbol_from_name(name: str) -> str | None:
    stem = Path(name).stem.lower()
    if stem.startswith("gpsh") and len(stem) >= 10:
        return "sh" + stem[4:10]
    if stem.startswith("gpsz") and len(stem) >= 10:
        return "sz" + stem[4:10]
    if stem.startswith("gpbj") and len(stem) >= 10:
        return "bj" + stem[4:10]
    return None


def parse_type_list(text: str) -> set[int]:
    out: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return out


def extract_events(tdxgp: Path, start_date: str, type_ids: set[int]) -> pd.DataFrame:
    if not tdxgp.exists():
        raise FileNotFoundError(f"tdxgp zip not found: {tdxgp}")

    start_i = int(str(pd.Timestamp(start_date).date()).replace("-", ""))
    rows: list[tuple[object, ...]] = []
    with zipfile.ZipFile(tdxgp) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".dat"):
                continue
            symbol = symbol_from_name(name)
            if symbol is None:
                continue
            market = symbol[:2]
            code = symbol[2:]
            data = zf.read(name)
            for offset in range(0, len(data) - RECORD.size + 1, RECORD.size):
                type_id, date_i, value1, value2 = RECORD.unpack_from(data, offset)
                if type_id not in type_ids or date_i < start_i:
                    continue
                field, unit, description = GPJY_META.get(type_id, (f"gpjy_{type_id}", "", f"GPJYVALUE({type_id})"))
                rows.append((date_i, symbol, code, market, type_id, field, value1, value2, unit, description))

    cols = ["date", "symbol", "code6", "market", "type_id", "field", "value1", "value2", "unit", "description"]
    events = pd.DataFrame(rows, columns=cols)
    if events.empty:
        return events
    events["date"] = pd.to_datetime(events["date"].astype(str), format="%Y%m%d", errors="coerce")
    events = events.loc[events["date"].notna()].sort_values(["symbol", "type_id", "date"]).reset_index(drop=True)
    return events


def augment_slice(input_slice: Path, events: pd.DataFrame) -> pd.DataFrame:
    data = pd.read_parquet(input_slice)
    out = data.copy()
    symbol = out["symbol"].astype(str) if "symbol" in out.columns else out["code"].astype(str)
    if "market" in out.columns:
        has_prefix = symbol.str.match(r"^(sh|sz|bj)\d{6}$", na=False)
        symbol = symbol.where(has_prefix, out["market"].astype(str) + symbol.str[-6:])
    out["symbol"] = symbol
    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    mv = events.loc[events["type_id"].eq(16), ["date", "symbol", "value1"]].rename(columns={"value1": "tdxgp_total_mv_10k_cny"})
    out = out.merge(mv, how="left", on=["date", "symbol"])
    out["tdxgp_total_market_cap"] = out["tdxgp_total_mv_10k_cny"] * 10000.0
    out["tdxgp_total_market_cap_billion"] = out["tdxgp_total_market_cap"] / 1e9
    out["tdxgp_total_market_cap_source"] = out["tdxgp_total_market_cap"].notna().map({True: "tdxgp_gpjvalue_16_total_mv", False: None})

    limit = events.loc[events["type_id"].eq(15), ["date", "symbol", "value1", "value2"]].copy()
    if not limit.empty:
        limit["tdxgp_limit_status"] = pd.to_numeric(limit["value1"], errors="coerce")
        limit = limit[limit["tdxgp_limit_status"].isin([-2.0, -1.0, 0.0, 1.0, 2.0])].copy()
        limit["tdxgp_limit_status_value2"] = pd.to_numeric(limit["value2"], errors="coerce")
        limit["_status_priority"] = limit["tdxgp_limit_status"].abs()
        limit = limit.sort_values(["symbol", "date", "_status_priority"])
        limit = limit.groupby(["symbol", "date"], as_index=False).tail(1)
        limit = limit[["date", "symbol", "tdxgp_limit_status", "tdxgp_limit_status_value2"]]
        out = out.merge(limit, how="left", on=["date", "symbol"])
        out["is_limit_up"] = out["tdxgp_limit_status"].eq(2.0).astype(float)
        out["is_limit_down"] = out["tdxgp_limit_status"].eq(-2.0).astype(float)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tdxgp", type=Path, default=DEFAULT_TDXGP)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--types", default="1,3,6,11,12,13,15,16")
    parser.add_argument("--events-output", type=Path)
    parser.add_argument("--input-slice", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()

    type_ids = parse_type_list(args.types)
    events = extract_events(args.tdxgp, args.start_date, type_ids)
    start_tag = args.start_date.replace("-", "")
    events_output = args.events_output or DATA_DIR / f"tdxgp_gpjvalue_types_{'-'.join(map(str, sorted(type_ids)))}_since_{start_tag}.parquet"
    events_output.parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(events_output, index=False)

    report: dict[str, object] = {
        "tdxgp": str(args.tdxgp),
        "start_date": args.start_date,
        "type_ids": sorted(type_ids),
        "events_output": str(events_output),
        "events_rows": int(len(events)),
        "events_symbols": int(events["symbol"].nunique()) if not events.empty else 0,
        "type_counts": {str(k): int(v) for k, v in events["type_id"].value_counts().sort_index().to_dict().items()} if not events.empty else {},
    }

    if args.input_slice:
        output = args.output or args.input_slice.with_name(f"{args.input_slice.stem}_tdxgp_gpjvalue.parquet")
        augmented = augment_slice(args.input_slice, events)
        output.parent.mkdir(parents=True, exist_ok=True)
        augmented.to_parquet(output, index=False)
        report.update(
            {
                "input_slice": str(args.input_slice),
                "output": str(output),
                "output_rows": int(len(augmented)),
                "tdxgp_total_mv_coverage_rows": float(augmented["tdxgp_total_market_cap"].notna().mean()) if len(augmented) else 0.0,
                "tdxgp_limit_status_non_null_rows": int(augmented["tdxgp_limit_status"].notna().sum())
                if "tdxgp_limit_status" in augmented.columns
                else 0,
                "tdxgp_close_limit_up_rows": int(pd.to_numeric(augmented.get("is_limit_up"), errors="coerce").fillna(0).sum())
                if "is_limit_up" in augmented.columns
                else 0,
                "tdxgp_close_limit_down_rows": int(pd.to_numeric(augmented.get("is_limit_down"), errors="coerce").fillna(0).sum())
                if "is_limit_down" in augmented.columns
                else 0,
            }
        )

    report_output = args.report_output or events_output.with_name(f"{events_output.stem}_report.json")
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
