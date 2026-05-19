from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(r"G:\AlphaFactory_CryptoData")
WORKSPACE = ROOT / "alphafactory_crypto"
REPORTS = WORKSPACE / "reports"

MANIFESTS = {
    "futures_vision": ROOT / "manifests" / "phase1_core12_202401_202604_manifest_combined.csv",
    "spot_vision": ROOT / "manifests" / "spot_core6_202401_202604_manifest.csv",
    "funding_rate": ROOT / "manifests" / "fundingRate_core12_202401_current_manifest.csv",
    "positioning_recent": ROOT / "manifests" / "positioning_core12_recent29d_5m_manifest.csv",
}

CORE12 = {
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
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def detect_ts_unit(value: str) -> str:
    try:
        number = abs(int(float(value)))
    except Exception:
        return "non_numeric"
    if number >= 10**15:
        return "microseconds_or_nanoseconds"
    if number >= 10**12:
        return "milliseconds"
    if number >= 10**9:
        return "seconds"
    return "unknown"


def first_data_row_from_zip(path: Path) -> tuple[list[str] | None, int | None, str | None]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.endswith("/")]
            if not names:
                return None, None, "empty_zip"
            row_count = 0
            first_row: list[str] | None = None
            with archive.open(names[0]) as handle:
                for raw in handle:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    parts = line.split(",")
                    if parts and not parts[0].lstrip("-").isdigit():
                        continue
                    row_count += 1
                    if first_row is None:
                        first_row = parts
            return first_row, row_count, None
    except Exception as exc:
        return None, None, f"{type(exc).__name__}:{str(exc)[:240]}"


def sample_csv_header(path: Path) -> tuple[list[str], int, str | None]:
    try:
        count = 0
        header: list[str] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            for i, row in enumerate(reader):
                if i == 0:
                    header = row
                else:
                    count += 1
        return header, count, None
    except Exception as exc:
        return [], 0, f"{type(exc).__name__}:{str(exc)[:240]}"


def manifest_summary(name: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    exists = 0
    missing = 0
    status = Counter()
    by_symbol = Counter()
    by_type = Counter()
    by_interval = Counter()
    by_range = Counter()
    total_manifest_rows = len(rows)
    total_row_count = 0
    for row in rows:
        local = Path(row.get("local_path", ""))
        exists += int(local.exists())
        missing += int(not local.exists())
        status[row.get("status", "") or "blank"] += 1
        by_symbol[row.get("symbol", "")] += 1
        by_type[row.get("data_type", "")] += 1
        by_interval[row.get("interval", "")] += 1
        by_range[row.get("date_range", "")] += 1
        try:
            total_row_count += int(float(row.get("row_count") or 0))
        except Exception:
            pass
    return {
        "name": name,
        "manifest_rows": total_manifest_rows,
        "local_files_present": exists,
        "local_files_missing": missing,
        "status_counts": dict(status),
        "symbol_count": len([s for s in by_symbol if s]),
        "symbols": sorted(s for s in by_symbol if s),
        "data_type_counts": dict(by_type),
        "interval_counts": dict(by_interval),
        "date_range_count": len(by_range),
        "total_source_row_count": total_row_count,
    }


def sample_vision_rows(rows: list[dict[str, str]], limit: int = 48) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (row.get("symbol", ""), row.get("data_type", ""), row.get("interval", ""), row.get("date_range", ""))
        if key in seen:
            continue
        seen.add(key)
        path = Path(row.get("local_path", ""))
        if not path.exists():
            continue
        first, scanned_rows, error = first_data_row_from_zip(path)
        out.append(
            {
                "symbol": row.get("symbol", ""),
                "data_type": row.get("data_type", ""),
                "interval": row.get("interval", ""),
                "date_range": row.get("date_range", ""),
                "status": row.get("status", ""),
                "local_path": str(path),
                "first_col_count": len(first or []),
                "timestamp_unit": detect_ts_unit(first[0]) if first else None,
                "scanned_rows": scanned_rows,
                "error": error,
            }
        )
        if len(out) >= limit:
            break
    return out


def csv_dataset_checks(rows: list[dict[str, str]], expected_headers: dict[str, set[str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_type_seen: set[tuple[str, str]] = set()
    for row in rows:
        dtype = row.get("data_type", "")
        symbol = row.get("symbol", "")
        key = (dtype, symbol)
        if key in by_type_seen:
            continue
        by_type_seen.add(key)
        path = Path(row.get("local_path", ""))
        if not path.exists():
            continue
        header, row_count, error = sample_csv_header(path)
        expected = expected_headers.get(dtype, set())
        missing = sorted(expected - set(header)) if expected else []
        out.append(
            {
                "data_type": dtype,
                "symbol": symbol,
                "local_path": str(path),
                "header": header,
                "row_count_scanned": row_count,
                "missing_expected_columns": missing,
                "error": error,
            }
        )
    return out


def build_report() -> tuple[dict[str, Any], str]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows_by_manifest = {name: read_csv(path) for name, path in MANIFESTS.items()}
    summaries = {name: manifest_summary(name, rows) for name, rows in rows_by_manifest.items()}

    vision_samples = sample_vision_rows(rows_by_manifest["futures_vision"], limit=60) + sample_vision_rows(rows_by_manifest["spot_vision"], limit=24)
    timestamp_units = Counter(sample.get("timestamp_unit") or "unknown" for sample in vision_samples)
    bad_col_count = [
        sample
        for sample in vision_samples
        if not sample.get("error") and sample.get("first_col_count") not in (12, None)
    ]
    sample_errors = [sample for sample in vision_samples if sample.get("error")]

    expected = {
        "fundingRate": {"fundingRate", "fundingTime", "markPrice", "symbol"},
        "openInterestHist": {"sumOpenInterest", "sumOpenInterestValue", "symbol", "timestamp"},
        "globalLongShortAccountRatio": {"longAccount", "longShortRatio", "shortAccount", "symbol", "timestamp"},
        "topLongShortAccountRatio": {"longAccount", "longShortRatio", "shortAccount", "symbol", "timestamp"},
        "topLongShortPositionRatio": {"longAccount", "longShortRatio", "shortAccount", "symbol", "timestamp"},
        "takerlongshortRatio": {"buySellRatio", "buyVol", "sellVol", "symbol", "timestamp"},
    }
    api_checks = csv_dataset_checks(rows_by_manifest["funding_rate"] + rows_by_manifest["positioning_recent"], expected)
    api_missing = [row for row in api_checks if row["missing_expected_columns"] or row.get("error")]

    futures_symbols = set(summaries["futures_vision"]["symbols"])
    funding_symbols = set(summaries["funding_rate"]["symbols"])
    positioning_symbols = set(summaries["positioning_recent"]["symbols"])
    universe_gaps = {
        "futures_missing_core12": sorted(CORE12 - futures_symbols),
        "funding_missing_core12": sorted(CORE12 - funding_symbols),
        "positioning_missing_core12": sorted(CORE12 - positioning_symbols),
    }

    blockers = []
    warnings = []
    if universe_gaps["futures_missing_core12"]:
        blockers.append("futures core12 Binance Vision coverage is incomplete")
    if universe_gaps["funding_missing_core12"]:
        warnings.append("fundingRate core12 coverage is incomplete")
    if summaries["positioning_recent"]["date_range_count"] <= 2:
        warnings.append("positioning appears recent-only; keep diagnostic-only for historical backtest")
    if "microseconds_or_nanoseconds" in timestamp_units:
        warnings.append("some timestamp samples are not milliseconds; bronze parser must normalize by magnitude")
    if bad_col_count:
        blockers.append("some Binance Vision kline samples do not have 12 columns")
    if sample_errors:
        warnings.append("some sampled zip files could not be scanned")
    if api_missing:
        blockers.append("API CSV files have missing expected columns or parse errors")

    decision = "PASS_BOOTSTRAP_PREFLIGHT_WITH_WARNINGS" if not blockers else "BLOCK_BOOTSTRAP_PREFLIGHT"
    result: dict[str, Any] = {
        "decision": decision,
        "generated_at": utc_now(),
        "root": str(ROOT),
        "workspace": str(WORKSPACE),
        "manifest_summaries": summaries,
        "universe_gaps": universe_gaps,
        "vision_sample_count": len(vision_samples),
        "vision_timestamp_unit_counts": dict(timestamp_units),
        "vision_bad_column_samples": bad_col_count[:20],
        "vision_sample_errors": sample_errors[:20],
        "api_csv_check_count": len(api_checks),
        "api_csv_issues": api_missing[:40],
        "blockers": blockers,
        "warnings": warnings,
        "recommended_next_step": "build bronze normalizer for futures/spot/funding; keep positioning diagnostic-only until longer history exists",
    }

    lines = [
        "# Crypto AlphaFactory Bootstrap Preflight",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- decision: `{decision}`",
        f"- root: `{ROOT}`",
        f"- workspace: `{WORKSPACE}`",
        "",
        "## Manifest Summary",
        "",
        "| dataset | manifest rows | files present | files missing | symbols | data types | intervals | source rows |",
        "|---|---:|---:|---:|---:|---|---|---:|",
    ]
    for name, summary in summaries.items():
        lines.append(
            f"| `{name}` | {summary['manifest_rows']} | {summary['local_files_present']} | {summary['local_files_missing']} | "
            f"{summary['symbol_count']} | `{json.dumps(summary['data_type_counts'], sort_keys=True)}` | "
            f"`{json.dumps(summary['interval_counts'], sort_keys=True)}` | {summary['total_source_row_count']} |"
        )
    lines += [
        "",
        "## Timestamp / Schema Checks",
        "",
        f"- vision samples scanned: `{len(vision_samples)}`",
        f"- timestamp units: `{dict(timestamp_units)}`",
        f"- bad 12-column samples: `{len(bad_col_count)}`",
        f"- API CSV issue samples: `{len(api_missing)}`",
        "",
        "## Universe Gaps",
        "",
        f"- futures_missing_core12: `{universe_gaps['futures_missing_core12']}`",
        f"- funding_missing_core12: `{universe_gaps['funding_missing_core12']}`",
        f"- positioning_missing_core12: `{universe_gaps['positioning_missing_core12']}`",
        "",
        "## Warnings",
        "",
    ]
    lines.extend(f"- {item}" for item in warnings) if warnings else lines.append("- none")
    lines += ["", "## Blockers", ""]
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- none")
    lines += [
        "",
        "## Execution Boundary",
        "",
        "- FundingRate can enter long-history backtests only with lagged/asof semantics.",
        "- Positioning recent29d is diagnostic-only for now.",
        "- Binance Vision spot timestamp unit must be normalized during bronze parsing.",
        "- Coarser intervals are overlapping evidence, not independent samples.",
        "",
        "## Next Step",
        "",
        "Build bronze normalization for `futures_um` and `spot` bars plus fundingRate. Start alpha smoke on 1h/5m core12 after bronze row-count and timestamp checks pass.",
    ]
    return result, "\n".join(lines) + "\n"


def main() -> int:
    result, markdown = build_report()
    json_path = REPORTS / "crypto_alphafactory_preflight_20260519.json"
    md_path = REPORTS / "CRYPTO_ALPHAFACTORY_PREFLIGHT_20260519.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    print("PREFLIGHT_JSON=" + str(json_path))
    print("PREFLIGHT_MD=" + str(md_path))
    print("DECISION=" + result["decision"])
    return 0 if not result["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
