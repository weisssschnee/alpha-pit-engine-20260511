# -*- coding: utf-8 -*-
"""
Build a recent A-share OHLCV slice from official TDX daily zip files.

The script downloads/caches the official TDX vipdoc daily archives, parses the
.day binary records, filters to stocks and major indices, and optionally carries
sector labels from the existing validation slice.
"""

from __future__ import annotations

import argparse
import json
import struct
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "scripts" / "data"
DEFAULT_REFERENCE = DATA_DIR / "phase2_stock_validation_slice_2026-04-27.parquet"
DEFAULT_CACHE = DATA_DIR / "tdx_official_vipdoc"
DEFAULT_START_DATE = "2025-08-06"

TDX_DAILY_ARCHIVES = {
    "sh": "https://www.tdx.com.cn/products/data/data/vipdoc/shlday.zip",
    "sz": "https://www.tdx.com.cn/products/data/data/vipdoc/szlday.zip",
    "bj": "https://www.tdx.com.cn/products/data/data/vipdoc/bjlday.zip",
}

RECORD = struct.Struct("<IIIIIfII")


def is_supported_symbol(market: str, code: str) -> bool:
    if market == "sh":
        return code.startswith(("000", "880", "881", "882", "883", "884", "885", "886", "887", "888", "889", "600", "601", "603", "605", "688", "689"))
    if market == "sz":
        return code.startswith(("399", "000", "001", "002", "003", "300", "301"))
    if market == "bj":
        return code.startswith(("4", "8", "9"))
    return False


def instrument_type(market: str, code: str) -> str:
    if market == "sh" and code.startswith(("000", "880", "881", "882", "883", "884", "885", "886", "887", "888", "889")):
        return "index"
    if market == "sz" and code.startswith("399"):
        return "index"
    return "stock"


def download_archive(market: str, cache_dir: Path, force: bool = False) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = TDX_DAILY_ARCHIVES[market]
    target = cache_dir / Path(url).name
    if target.exists() and target.stat().st_size > 0 and not force:
        return target

    tmp = target.with_suffix(target.suffix + ".tmp")
    print(f"downloading {url} -> {target}")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(target)
    return target


def _date_int(date_text: str | None) -> int | None:
    if not date_text:
        return None
    return int(str(pd.Timestamp(date_text).date()).replace("-", ""))


def iter_day_rows(zip_path: Path, market: str, start_i: int, end_i: int | None):
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".day")]
        for name in names:
            filename = Path(name).name.lower()
            if not filename.startswith(market) or len(filename) < 12:
                continue
            code = filename[2:8]
            if not is_supported_symbol(market, code):
                continue
            symbol = f"{market}{code}"
            kind = instrument_type(market, code)
            content = zf.read(name)
            for offset in range(0, len(content) - RECORD.size + 1, RECORD.size):
                date_i, open_i, high_i, low_i, close_i, amount_f, volume_i, _ = RECORD.unpack_from(content, offset)
                if date_i < start_i:
                    continue
                if end_i is not None and date_i > end_i:
                    continue
                yield (
                    date_i,
                    symbol,
                    market,
                    open_i / 100.0,
                    high_i / 100.0,
                    low_i / 100.0,
                    close_i / 100.0,
                    float(amount_f),
                    float(volume_i),
                    kind,
                )


def load_sector_map(reference_path: Path) -> pd.DataFrame:
    if not reference_path.exists():
        return pd.DataFrame(columns=["code", "sector_code", "sector", "sector_source", "sector_confidence"])

    cols = ["date", "code", "sector_code", "sector", "sector_source", "sector_confidence"]
    ref = pd.read_parquet(reference_path, columns=cols)
    ref = ref.sort_values(["code", "date"])
    sector = ref.groupby("code", as_index=False).tail(1)
    return sector[["code", "sector_code", "sector", "sector_source", "sector_confidence"]]


def build_slice(args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, object]]:
    start_i = _date_int(args.start_date)
    end_i = _date_int(args.end_date)
    if start_i is None:
        raise ValueError("--start-date is required")
    markets = ["sh", "sz"] + ([] if args.no_bj else ["bj"])

    rows = []
    archive_sizes: dict[str, int] = {}
    for market in markets:
        archive = download_archive(market, args.cache_dir, force=args.force_download)
        archive_sizes[market] = int(archive.stat().st_size)
        rows.extend(iter_day_rows(archive, market, start_i, end_i))

    columns = [
        "date",
        "code",
        "market",
        "open",
        "high",
        "low",
        "close",
        "amount",
        "volume",
        "instrument_type",
    ]
    data = pd.DataFrame(rows, columns=columns)
    if data.empty:
        raise ValueError("TDX daily archives produced no rows for the requested window")

    data["date"] = pd.to_datetime(data["date"].astype(str), format="%Y%m%d", errors="coerce")
    data = data.loc[data["date"].notna()].copy()
    data = data.sort_values(["code", "date"]).reset_index(drop=True)
    data["volume"] = data["volume"].round().astype("int64")
    data["susp"] = False
    data["daily_ret"] = data.groupby("code", sort=False)["close"].pct_change()
    prev_close = data.groupby("code", sort=False)["close"].shift(1)
    data["overnight"] = data["open"] / prev_close - 1.0
    data["rt_change_pct"] = data["daily_ret"] * 100.0
    data["is_limit_up"] = pd.NA
    data["is_limit_down"] = pd.NA

    sector = load_sector_map(args.reference_slice)
    if not sector.empty:
        data = data.merge(sector, how="left", on="code")
    else:
        data["sector_code"] = pd.NA
        data["sector"] = pd.NA
        data["sector_source"] = pd.NA
        data["sector_confidence"] = pd.NA

    ordered = [
        "date",
        "code",
        "market",
        "open",
        "high",
        "low",
        "close",
        "amount",
        "volume",
        "susp",
        "is_limit_up",
        "is_limit_down",
        "rt_change_pct",
        "daily_ret",
        "overnight",
        "sector_code",
        "sector",
        "sector_source",
        "sector_confidence",
        "instrument_type",
    ]
    data = data[ordered]

    report = {
        "start_date": args.start_date,
        "end_date_arg": args.end_date,
        "rows": int(len(data)),
        "symbols": int(data["code"].nunique()),
        "date_min": str(data["date"].min()),
        "date_max": str(data["date"].max()),
        "markets": {str(k): int(v) for k, v in data["market"].value_counts().to_dict().items()},
        "instrument_type_counts": {
            str(k): int(v) for k, v in data["instrument_type"].value_counts(dropna=False).to_dict().items()
        },
        "sector_coverage_rows": float(data["sector"].notna().mean()),
        "archive_sizes": archive_sizes,
        "source_urls": TDX_DAILY_ARCHIVES,
    }
    return data, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--reference-slice", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--no-bj", action="store_true")
    args = parser.parse_args()

    data, report = build_slice(args)
    start_tag = args.start_date.replace("-", "")
    end_tag = str(data["date"].max().date()).replace("-", "")
    output = args.output or DATA_DIR / f"phase2_stock_tdx_official_{start_tag}_to_{end_tag}.parquet"
    report_output = args.report_output or output.with_name(f"{output.stem}_report.json")

    output.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(output, index=False)
    report["output"] = str(output)
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
