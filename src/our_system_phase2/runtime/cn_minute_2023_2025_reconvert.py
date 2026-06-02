"""Reconvert 2023-2025 CN stock 1min zip archives into symbol parquet v2.

The previous converter produced parquet files with only partition columns in
some environments because its Chinese header mapping was corrupted. This
converter does not depend on Chinese header literals. It maps the known source
CSV layout by position:

time, code, name, open, close, high, low, volume, amount, pct_chg, amplitude.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_SOURCE_ROOT = Path(r"G:\BaiduNetdiskDownload")
DEFAULT_OUTPUT_ROOT = Path(
    r"G:\Project_V7_Rotation\data\cn_public_enrichment\cn_local_minute_daily_silver_v1_20260531\stock_1min_2023_2025_symbol_parquet_v2"
)
DEFAULT_REPORT_ROOT = Path("reports/cn_minute_2023_2025_reconvert_20260601")

POSITIONAL_COLUMNS = [
    "trade_time",
    "code_raw",
    "name",
    "open",
    "close",
    "high",
    "low",
    "vol",
    "amount",
    "pct_chg",
    "amplitude_pct",
]
KEEP_COLUMNS = [
    "code",
    "trade_time",
    "date",
    "name",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
    "pct_chg",
    "amplitude_pct",
    "code_raw",
    "year",
]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "vol", "amount", "pct_chg", "amplitude_pct"]


def _norm_member(name: str) -> tuple[str | None, int | None]:
    match = re.match(r"^(sz|sh|bj)(\d{6})_(\d{4})\.csv$", Path(name).name.lower())
    if not match:
        return None, None
    exchange, code, year = match.groups()
    suffix = {"sz": "SZ", "sh": "SH", "bj": "BJ"}[exchange]
    return f"{code}.{suffix}", int(year)


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    last_exc: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise RuntimeError(f"failed_read_csv:{type(last_exc).__name__}:{str(last_exc)[:200]}")


def _normalize_source_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(col).strip().replace("\ufeff", "") for col in frame.columns]
    if len(frame.columns) >= 12 and str(frame.columns[0]).lower().startswith("unnamed"):
        frame = frame.iloc[:, 1:12].copy()
    elif len(frame.columns) >= 11:
        frame = frame.iloc[:, :11].copy()
    else:
        raise ValueError(f"source_has_too_few_columns:{len(frame.columns)}")
    frame.columns = POSITIONAL_COLUMNS
    return frame


def _write_manifest(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _convert_member(zf: zipfile.ZipFile, member: str, out_root: Path, *, overwrite: bool) -> dict[str, Any]:
    code, year = _norm_member(member)
    if not code or not year:
        return {"source_member": member, "status": "skip_unrecognized_name"}

    out_path = out_root / f"year={year}" / f"code={code}" / "part.parquet"
    if out_path.exists() and not overwrite:
        return {"year": year, "code": code, "source_member": member, "status": "exists", "path": str(out_path)}

    with zf.open(member) as handle:
        raw = handle.read()
    frame = _normalize_source_columns(_read_csv_bytes(raw))
    frame["code"] = code
    frame["year"] = year
    frame["trade_time"] = pd.to_datetime(frame["trade_time"], errors="coerce")
    frame["date"] = frame["trade_time"].dt.strftime("%Y%m%d")
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[KEEP_COLUMNS]

    if frame["trade_time"].isna().all():
        return {"year": year, "code": code, "source_member": member, "status": "error_all_trade_time_null"}
    if frame[["open", "high", "low", "close", "amount"]].isna().all(axis=None):
        return {"year": year, "code": code, "source_member": member, "status": "error_all_price_amount_null"}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    duplicate_count = int(frame.duplicated(["code", "trade_time"]).sum())
    return {
        "year": year,
        "code": code,
        "source_member": member,
        "status": "ok",
        "rows": int(frame.shape[0]),
        "columns": "|".join(frame.columns),
        "date_min": str(frame["date"].min()),
        "date_max": str(frame["date"].max()),
        "time_min": str(frame["trade_time"].dt.strftime("%H:%M:%S").min()),
        "time_max": str(frame["trade_time"].dt.strftime("%H:%M:%S").max()),
        "duplicate_code_time": duplicate_count,
        "path": str(out_path),
        "bytes": int(out_path.stat().st_size),
    }


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def run(
    *,
    source_root: Path,
    output_root: Path,
    report_root: Path,
    years: list[int],
    limit_members_per_year: int,
    overwrite: bool,
    progress_every: int,
    member_shard_index: int,
    member_shard_count: int,
) -> dict[str, Any]:
    if member_shard_count < 1:
        raise ValueError("member_shard_count must be >= 1")
    if member_shard_index < 0 or member_shard_index >= member_shard_count:
        raise ValueError("member_shard_index must satisfy 0 <= index < count")
    report_root.mkdir(parents=True, exist_ok=True)
    if overwrite and output_root.exists():
        resolved = output_root.resolve()
        required = "stock_1min_2023_2025_symbol_parquet_v2"
        if required not in str(resolved):
            raise RuntimeError(f"refusing_to_delete_unexpected_output_root:{resolved}")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest_path = report_root / "stock_1min_2023_2025_reconvert_manifest.csv"
    progress_path = report_root / "progress.jsonl"
    rows: list[dict[str, Any]] = []
    started = time.time()
    converted = 0

    for year in years:
        archive = source_root / f"{year}_1min.zip"
        if not archive.exists():
            rows.append({"year": year, "status": "missing_archive", "archive": str(archive)})
            continue
        with zipfile.ZipFile(archive) as zf:
            members = sorted([name for name in zf.namelist() if name.lower().endswith(".csv")])
            original_year_total = len(members)
            if member_shard_count > 1:
                members = [
                    member
                    for member_index, member in enumerate(members)
                    if member_index % member_shard_count == member_shard_index
                ]
            if limit_members_per_year > 0:
                members = members[:limit_members_per_year]
            year_total = len(members)
            for index, member in enumerate(members, start=1):
                try:
                    row = _convert_member(zf, member, output_root, overwrite=overwrite)
                except Exception as exc:  # noqa: BLE001
                    code, parsed_year = _norm_member(member)
                    row = {
                        "year": parsed_year or year,
                        "code": code,
                        "source_member": member,
                        "status": "error_exception",
                        "error": f"{type(exc).__name__}:{str(exc)[:240]}",
                    }
                rows.append(row)
                converted += 1
                if progress_every > 0 and (converted % progress_every == 0 or index == year_total):
                    event = {
                        "event": "progress",
                        "year": year,
                        "year_index": index,
                        "year_total": year_total,
                        "original_year_total": original_year_total,
                        "member_shard_index": member_shard_index,
                        "member_shard_count": member_shard_count,
                        "converted_total": converted,
                        "elapsed_sec": round(time.time() - started, 3),
                        "status_counts": _status_counts(rows),
                    }
                    with progress_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                    _write_manifest(rows, manifest_path)

    _write_manifest(rows, manifest_path)
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    success_rows = [row for row in rows if row.get("status") in {"ok", "exists", "skip_unrecognized_name"}]
    if limit_members_per_year > 0:
        decision = "PASS_RECONVERT_CANARY" if rows and len(success_rows) == len(rows) else "FAIL_RECONVERT_CANARY_NO_OK_ROWS"
    else:
        decision = "PASS_RECONVERT_FULL" if rows and len(success_rows) == len(rows) else "REVIEW_RECONVERT_FULL_WITH_ERRORS"
    summary = {
        "decision": decision,
        "source_root": str(source_root),
        "output_root": str(output_root),
        "years": years,
        "limit_members_per_year": limit_members_per_year,
        "member_shard_index": member_shard_index,
        "member_shard_count": member_shard_count,
        "records": len(rows),
        "ok_records": len(ok_rows),
        "success_records": len(success_rows),
        "status_counts": _status_counts(rows),
        "rows_total": int(sum(int(row.get("rows") or 0) for row in ok_rows)),
        "elapsed_sec": round(time.time() - started, 3),
        "manifest": str(manifest_path),
        "progress": str(progress_path),
        "sample_ok": ok_rows[:5],
    }
    write_json_artifact(report_root / "stock_1min_2023_2025_reconvert_report.json", summary)
    lines = [
        "# CN 1min 2023-2025 Reconvert Report - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"records: `{summary['records']}`",
        f"ok_records: `{summary['ok_records']}`",
        f"success_records: `{summary['success_records']}`",
        f"rows_total: `{summary['rows_total']}`",
        f"member_shard: `{member_shard_index}/{member_shard_count}`",
        f"output_root: `{summary['output_root']}`",
        "",
        "## Boundary",
        "",
        "- This rebuilds invalid 2023-2025 symbol parquet files that previously contained only code/year.",
        "- Source zips start at 09:30 bars; no 09:25-09:30 auction detail is present in these archives.",
        "- The converter maps columns by source position, not by localized header text.",
    ]
    (report_root / "CN_1MIN_2023_2025_RECONVERT_REPORT_2026-06-01.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--limit-members-per-year", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument("--member-shard-index", type=int, default=0)
    parser.add_argument("--member-shard-count", type=int, default=1)
    args = parser.parse_args()
    years = [int(item.strip()) for item in args.years.split(",") if item.strip()]
    summary = run(
        source_root=args.source_root,
        output_root=args.output_root,
        report_root=args.report_root,
        years=years,
        limit_members_per_year=args.limit_members_per_year,
        overwrite=bool(args.overwrite),
        progress_every=args.progress_every,
        member_shard_index=args.member_shard_index,
        member_shard_count=args.member_shard_count,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
