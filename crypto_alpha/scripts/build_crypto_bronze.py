from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("G:/AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
FUTURES_MANIFEST = ROOT / "manifests" / "phase1_core12_202401_202604_manifest_combined.csv"
FUNDING_MANIFEST = ROOT / "manifests" / "fundingRate_core12_202401_current_manifest.csv"
BRONZE_ROOT = ROOT / "curated" / "bronze" / "alphafactory_crypto_v0"
REPORT_DIR = WORKSPACE / "reports"

CORE12 = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "LTCUSDT",
    "BCHUSDT",
    "SUIUSDT",
]

KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def candidate_paths(row: dict[str, str]) -> list[Path]:
    out: list[Path] = []
    for value in [row.get("local_path", ""), row.get("error", "")]:
        for part in str(value).split(";"):
            part = part.strip()
            if part.lower().endswith(".zip"):
                out.append(Path(part))
    seen: set[str] = set()
    uniq: list[Path] = []
    for path in out:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            uniq.append(path)
    return uniq


def resolve_valid_zip(row: dict[str, str]) -> tuple[Path | None, str | None]:
    for path in candidate_paths(row):
        if path.exists() and zipfile.is_zipfile(path):
            return path, None
    paths = [str(path) for path in candidate_paths(row)]
    return None, "no_valid_zip:" + "|".join(paths[:4])


def normalize_epoch_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    max_abs = numeric.abs().max()
    if pd.isna(max_abs):
        return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
    if max_abs > 10**15:
        return pd.to_datetime(numeric, unit="ns", utc=True, errors="coerce")
    if max_abs > 10**13:
        return pd.to_datetime(numeric, unit="us", utc=True, errors="coerce")
    return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")


def read_kline_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]
        if not names:
            raise ValueError("zip_has_no_files")
        with zf.open(names[0]) as f:
            df = pd.read_csv(f, header=None, names=KLINE_COLUMNS)
    if len(df.columns) != 12:
        raise ValueError(f"unexpected_column_count:{len(df.columns)}")
    return df


def build_futures_klines(intervals: set[str], max_files: int | None = None) -> dict[str, Any]:
    rows = read_csv(FUTURES_MANIFEST)
    selected = [
        row
        for row in rows
        if row.get("data_type") == "klines"
        and row.get("interval") in intervals
        and row.get("symbol") in CORE12
    ]
    selected.sort(key=lambda row: (row.get("symbol", ""), row.get("interval", ""), row.get("date_range", "")))
    if max_files is not None:
        selected = selected[:max_files]

    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in selected:
        groups.setdefault((row["symbol"], row["interval"]), []).append(row)

    stats: dict[str, Any] = {"groups": {}, "file_errors": []}
    for (symbol, interval), group_rows in groups.items():
        frames: list[pd.DataFrame] = []
        source_files: list[str] = []
        for row in group_rows:
            path, err = resolve_valid_zip(row)
            if err or path is None:
                stats["file_errors"].append(
                    {
                        "dataset": "futures_um_klines",
                        "symbol": symbol,
                        "interval": interval,
                        "date_range": row.get("date_range", ""),
                        "error": err,
                    }
                )
                continue
            try:
                frame = read_kline_zip(path)
            except Exception as exc:  # noqa: BLE001
                stats["file_errors"].append(
                    {
                        "dataset": "futures_um_klines",
                        "symbol": symbol,
                        "interval": interval,
                        "date_range": row.get("date_range", ""),
                        "path": str(path),
                        "error": f"{type(exc).__name__}:{exc}",
                    }
                )
                continue
            frame["symbol"] = symbol
            frame["interval"] = interval
            frame["source_date_range"] = row.get("date_range", "")
            frames.append(frame)
            source_files.append(str(path))

        key = f"{symbol}_{interval}"
        if not frames:
            stats["groups"][key] = {"rows": 0, "files": 0, "output": None, "status": "empty"}
            continue

        df = pd.concat(frames, ignore_index=True)
        for col in [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
        ]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["number_of_trades"] = pd.to_numeric(df["number_of_trades"], errors="coerce").astype("Int64")
        df["open_time_raw"] = pd.to_numeric(df["open_time"], errors="coerce").astype("Int64")
        df["close_time_raw"] = pd.to_numeric(df["close_time"], errors="coerce").astype("Int64")
        df["open_time"] = normalize_epoch_series(df["open_time_raw"])
        df["close_time"] = normalize_epoch_series(df["close_time_raw"])
        df = df.dropna(subset=["open_time", "close_time", "close"]).drop_duplicates(["symbol", "interval", "open_time"])
        df = df.sort_values(["symbol", "interval", "open_time"]).reset_index(drop=True)

        out_dir = BRONZE_ROOT / "binance_futures_um" / "klines" / f"interval={interval}" / f"symbol={symbol}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "part.parquet"
        df.to_parquet(out_path, index=False)
        stats["groups"][key] = {
            "rows": int(len(df)),
            "files": len(source_files),
            "output": str(out_path),
            "output_sha256": sha256_file(out_path),
            "min_open_time": df["open_time"].min().isoformat() if len(df) else None,
            "max_open_time": df["open_time"].max().isoformat() if len(df) else None,
            "status": "ok",
        }
    return stats


def build_funding_rate() -> dict[str, Any]:
    rows = read_csv(FUNDING_MANIFEST)
    stats: dict[str, Any] = {"groups": {}, "file_errors": []}
    for row in rows:
        symbol = row.get("symbol", "")
        path = Path(row.get("local_path", ""))
        key = symbol
        if symbol not in CORE12:
            continue
        if not path.exists():
            stats["file_errors"].append({"dataset": "fundingRate", "symbol": symbol, "error": "missing_file", "path": str(path)})
            continue
        try:
            df = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            stats["file_errors"].append({"dataset": "fundingRate", "symbol": symbol, "error": f"{type(exc).__name__}:{exc}", "path": str(path)})
            continue
        df["symbol"] = symbol
        df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
        df["markPrice"] = pd.to_numeric(df["markPrice"], errors="coerce")
        df["fundingTime_raw"] = pd.to_numeric(df["fundingTime"], errors="coerce").astype("Int64")
        df["fundingTime"] = normalize_epoch_series(df["fundingTime_raw"])
        df = df.dropna(subset=["fundingTime", "fundingRate"]).drop_duplicates(["symbol", "fundingTime"])
        df = df.sort_values(["symbol", "fundingTime"]).reset_index(drop=True)
        out_dir = BRONZE_ROOT / "binance_futures_um" / "fundingRate" / f"symbol={symbol}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "part.parquet"
        df.to_parquet(out_path, index=False)
        stats["groups"][key] = {
            "rows": int(len(df)),
            "output": str(out_path),
            "output_sha256": sha256_file(out_path),
            "min_funding_time": df["fundingTime"].min().isoformat() if len(df) else None,
            "max_funding_time": df["fundingTime"].max().isoformat() if len(df) else None,
            "status": "ok",
        }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bronze parquet for crypto AlphaFactory v0.")
    parser.add_argument("--intervals", default="1h,5m", help="Comma-separated futures kline intervals.")
    parser.add_argument("--skip-funding", action="store_true", help="Skip fundingRate bronze.")
    parser.add_argument("--max-files", type=int, default=None, help="Limit futures manifest files for smoke testing.")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    intervals = {part.strip() for part in args.intervals.split(",") if part.strip()}
    result: dict[str, Any] = {
        "generated_at": utc_now(),
        "bronze_root": str(BRONZE_ROOT),
        "intervals": sorted(intervals),
        "max_files": args.max_files,
        "futures_klines": build_futures_klines(intervals, args.max_files),
    }
    if not args.skip_funding:
        result["funding_rate"] = build_funding_rate()

    total_errors = len(result["futures_klines"]["file_errors"]) + len(result.get("funding_rate", {}).get("file_errors", []))
    result["decision"] = "PASS_BRONZE_BUILD_WITH_WARNINGS" if total_errors else "PASS_BRONZE_BUILD"

    json_path = REPORT_DIR / "crypto_bronze_build_20260519.json"
    md_path = REPORT_DIR / "CRYPTO_BRONZE_BUILD_20260519.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Crypto Bronze Build",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- decision: `{result['decision']}`",
        f"- bronze_root: `{BRONZE_ROOT}`",
        f"- intervals: `{sorted(intervals)}`",
        f"- max_files: `{args.max_files}`",
        "",
        "## Futures Klines Groups",
        "",
        "| group | rows | files | min open | max open | status |",
        "|---|---:|---:|---|---|---|",
    ]
    for group, stats in sorted(result["futures_klines"]["groups"].items()):
        lines.append(
            f"| `{group}` | {stats.get('rows', 0)} | {stats.get('files', 0)} | "
            f"{stats.get('min_open_time')} | {stats.get('max_open_time')} | {stats.get('status')} |"
        )
    if "funding_rate" in result:
        lines += ["", "## FundingRate Groups", "", "| symbol | rows | min time | max time | status |", "|---|---:|---|---|---|"]
        for symbol, stats in sorted(result["funding_rate"]["groups"].items()):
            lines.append(
                f"| `{symbol}` | {stats.get('rows', 0)} | {stats.get('min_funding_time')} | "
                f"{stats.get('max_funding_time')} | {stats.get('status')} |"
            )
    lines += [
        "",
        "## File Errors",
        "",
    ]
    errors = result["futures_klines"]["file_errors"] + result.get("funding_rate", {}).get("file_errors", [])
    if errors:
        for item in errors[:50]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("BRONZE_JSON=" + str(json_path))
    print("BRONZE_MD=" + str(md_path))
    print("DECISION=" + result["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
