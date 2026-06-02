"""Final QA for the CN minute feature panel v2.

This is a read-only checker. It validates the code-date panel contract without
loading the full wide panel into memory at once.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_PANEL_ROOT = Path("runtime/minute_feature_panels/cn_minute_feature_panel_v2_20260602_full")
DEFAULT_REPORT_ROOT = Path("reports/cn_minute_feature_panel_v2_20260602_final_qa")
KEY_COLUMNS = ["exec_date", "signal_date", "code"]
REQUIRED_PREFIXES = ["m1_first5_", "m1_first15_", "m1_first30_", "ctx_", "label_"]
FORBIDDEN_SELECTOR_PREFIXES = ["label_"]
FORBIDDEN_SELECTOR_COLUMNS = {"m1_day_close", "m1_day_high", "m1_day_low", "m1_amount_day", "m1_vol_day", "m1_bars_day"}


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


def _parquet_files(panel_root: Path) -> list[Path]:
    return sorted(path for path in panel_root.rglob("*.parquet") if path.is_file())


def _schema_role(column: str) -> str:
    if column in KEY_COLUMNS:
        return "key"
    if column.startswith("label_"):
        return "evaluation_label_not_selector_input"
    if column in FORBIDDEN_SELECTOR_COLUMNS:
        return "day_summary_not_selector_input"
    if column.startswith("m1_first5_"):
        return "minute_native_after_0935"
    if column.startswith("m1_first15_"):
        return "minute_native_after_0945"
    if column.startswith("m1_first30_"):
        return "minute_native_after_1000"
    if column.startswith("m1_"):
        return "minute_native_or_day_summary_review"
    if column.startswith("ctx_"):
        return "lagged_daily_context_prior_signal_date"
    return "unknown_review_required"


def _safe_min(series: pd.Series) -> str | None:
    if series.empty:
        return None
    value = series.min()
    return None if pd.isna(value) else str(value)


def _safe_max(series: pd.Series) -> str | None:
    if series.empty:
        return None
    value = series.max()
    return None if pd.isna(value) else str(value)


def run(*, panel_root: Path, report_root: Path, sample_context_cols: int) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    files = _parquet_files(panel_root)
    file_rows: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    seen_schema: set[str] = set()
    total_rows = 0
    duplicate_key_rows = 0
    ctx_checked_rows = 0
    ctx_any_match_rows = 0
    key_null_rows = 0
    year_rows: dict[str, int] = {}
    error_rows: list[dict[str, Any]] = []

    for path in files:
        rel = path.relative_to(panel_root).as_posix()
        try:
            pf = pq.ParquetFile(path)
            columns = pf.schema_arrow.names
            rows = int(pf.metadata.num_rows)
            total_rows += rows
            year = rel.split("/")[0].replace("year=", "") if "/" in rel else "unknown"
            year_rows[year] = year_rows.get(year, 0) + rows

            missing_keys = [column for column in KEY_COLUMNS if column not in columns]
            if missing_keys:
                error_rows.append({"path": rel, "error": "missing_key_columns", "detail": "|".join(missing_keys)})
                continue

            for column in columns:
                if column not in seen_schema:
                    seen_schema.add(column)
                    schema_rows.append(
                        {
                            "field_name": column,
                            "role": _schema_role(column),
                            "selector_allowed": "false"
                            if column.startswith(tuple(FORBIDDEN_SELECTOR_PREFIXES)) or column in FORBIDDEN_SELECTOR_COLUMNS
                            else "true",
                        }
                    )

            key_frame = pd.read_parquet(path, columns=KEY_COLUMNS)
            duplicate_key_rows += int(key_frame.duplicated(KEY_COLUMNS).sum())
            key_null_rows += int(key_frame[KEY_COLUMNS].isna().any(axis=1).sum())
            exec_min = _safe_min(key_frame["exec_date"])
            exec_max = _safe_max(key_frame["exec_date"])
            symbols = int(key_frame["code"].nunique())

            ctx_columns = [column for column in columns if column.startswith("ctx_")][:sample_context_cols]
            ctx_rate = None
            if ctx_columns:
                ctx_frame = pd.read_parquet(path, columns=ctx_columns)
                any_ctx = ctx_frame.notna().any(axis=1)
                ctx_checked_rows += int(any_ctx.shape[0])
                ctx_any_match_rows += int(any_ctx.sum())
                ctx_rate = float(any_ctx.mean())

            file_rows.append(
                {
                    "path": rel,
                    "rows": rows,
                    "columns": len(columns),
                    "exec_date_min": exec_min,
                    "exec_date_max": exec_max,
                    "symbols": symbols,
                    "ctx_sample_any_match_rate": ctx_rate,
                }
            )
        except Exception as exc:  # noqa: BLE001
            error_rows.append({"path": rel, "error": type(exc).__name__, "detail": str(exc)[:300]})

    prefix_coverage = {
        prefix: any(row["field_name"].startswith(prefix) for row in schema_rows)
        for prefix in REQUIRED_PREFIXES
    }
    unknown_fields = [row for row in schema_rows if row["role"] == "unknown_review_required"]
    forbidden_selector_fields = [
        row["field_name"]
        for row in schema_rows
        if row["field_name"].startswith(tuple(FORBIDDEN_SELECTOR_PREFIXES)) or row["field_name"] in FORBIDDEN_SELECTOR_COLUMNS
    ]
    ctx_match_rate = (ctx_any_match_rows / ctx_checked_rows) if ctx_checked_rows else None
    decision = "PASS_MINUTE_FEATURE_PANEL_V2_FINAL_QA"
    fail_reasons: list[str] = []
    if not files:
        fail_reasons.append("no_parquet_files")
    if error_rows:
        fail_reasons.append("file_read_or_schema_errors")
    if duplicate_key_rows:
        fail_reasons.append("duplicate_exec_date_code_keys")
    if key_null_rows:
        fail_reasons.append("null_key_rows")
    for prefix, present in prefix_coverage.items():
        if not present:
            fail_reasons.append(f"missing_required_prefix:{prefix}")
    if fail_reasons:
        decision = "REVIEW_MINUTE_FEATURE_PANEL_V2_FINAL_QA"

    summary = {
        "decision": decision,
        "panel_root": str(panel_root),
        "parquet_files": len(files),
        "total_rows": int(total_rows),
        "year_rows": year_rows,
        "schema_columns": len(schema_rows),
        "duplicate_key_rows": int(duplicate_key_rows),
        "key_null_rows": int(key_null_rows),
        "context_sample_any_match_rate": ctx_match_rate,
        "required_prefix_coverage": prefix_coverage,
        "forbidden_selector_field_count": len(forbidden_selector_fields),
        "unknown_field_count": len(unknown_fields),
        "error_count": len(error_rows),
        "fail_reasons": fail_reasons,
        "boundary": {
            "ctx_fields": "prior signal_date only",
            "m1_first5": "available after 09:35",
            "m1_first15": "available after 09:45",
            "m1_first30": "available after 10:00",
            "label_fields": "evaluation only, forbidden for selector input",
        },
    }
    write_json_artifact(report_root / "cn_minute_feature_panel_v2_final_qa.json", summary)
    _write_csv(report_root / "file_manifest.csv", file_rows)
    _write_csv(report_root / "field_contract_qa.csv", schema_rows)
    _write_csv(report_root / "error_manifest.csv", error_rows)
    lines = [
        "# CN Minute Feature Panel V2 Final QA - 2026-06-02",
        "",
        f"decision: `{decision}`",
        f"parquet_files: `{len(files)}`",
        f"total_rows: `{total_rows}`",
        f"duplicate_key_rows: `{duplicate_key_rows}`",
        f"key_null_rows: `{key_null_rows}`",
        f"context_sample_any_match_rate: `{ctx_match_rate}`",
        f"unknown_field_count: `{len(unknown_fields)}`",
        "",
        "## Boundary",
        "",
        "- `ctx_*` fields are prior-trading-day context only.",
        "- `m1_first5/15/30_*` fields are intraday observable after the stated cutoff.",
        "- `label_*` and full-day summaries are evaluation-only, not selector input.",
    ]
    (report_root / "CN_MINUTE_FEATURE_PANEL_V2_FINAL_QA_2026-06-02.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-root", type=Path, default=DEFAULT_PANEL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--sample-context-cols", type=int, default=24)
    args = parser.parse_args()
    summary = run(panel_root=args.panel_root, report_root=args.report_root, sample_context_cols=args.sample_context_cols)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["decision"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
