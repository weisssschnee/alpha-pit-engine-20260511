"""Read-only QA for the CN non-1min PIT context panel v1."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pandas as pd

from our_system_phase2.services.artifact_schema import write_json_artifact


DEFAULT_PANEL_ROOT = Path("runtime/nonminute_context_panels/cn_nonminute_pit_context_panel_v1_20260602")
DEFAULT_REPORT_ROOT = Path("reports/cn_nonminute_pit_context_panel_v1_20260602_qa")


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


def _panel_files(panel_root: Path) -> list[Path]:
    if panel_root.is_dir():
        return sorted(panel_root.rglob("*.parquet"))
    return [panel_root] if panel_root.exists() else []


def _family_columns(columns: list[str]) -> dict[str, list[str]]:
    return {
        "rzrq_daily": [col for col in columns if col.startswith("ctx_rzrq_")],
        "fundamental_balance": [col for col in columns if col.startswith("ctx_fund_bs_")],
        "fundamental_profit": [col for col in columns if col.startswith("ctx_fund_ps_")],
        "fundamental_cashflow": [col for col in columns if col.startswith("ctx_fund_cf_")],
        "holder_count": [col for col in columns if col.startswith("ctx_holder_")],
        "billboard_diagnostic": [col for col in columns if col.startswith("ctx_billboard_")],
        "market_updown": [col for col in columns if col.startswith("ctx_mkt_updown_")],
    }


def run(*, panel_root: Path, report_root: Path) -> dict[str, Any]:
    report_root.mkdir(parents=True, exist_ok=True)
    files = _panel_files(panel_root)
    if not files:
        raise FileNotFoundError(f"no parquet files found under {panel_root}")

    year_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    pit_rows: list[dict[str, Any]] = []
    all_columns: set[str] = set()
    total_rows = 0
    duplicate_total = 0
    key_null_total = 0
    pit_violation_total = 0
    forbidden_selector_prefix_hits = 0
    for path in files:
        frame = pd.read_parquet(path)
        all_columns.update(frame.columns)
        total_rows += int(frame.shape[0])
        year = int(frame["year"].dropna().iloc[0]) if "year" in frame.columns and frame["year"].notna().any() else None
        dup = int(frame.duplicated(["date", "code"]).sum()) if {"date", "code"}.issubset(frame.columns) else int(frame.shape[0])
        duplicate_total += dup
        key_null = int(frame[["date", "code"]].isna().any(axis=1).sum()) if {"date", "code"}.issubset(frame.columns) else int(frame.shape[0])
        key_null_total += key_null

        date = pd.to_datetime(frame["date"], errors="coerce") if "date" in frame.columns else pd.Series(pd.NaT, index=frame.index)
        meta_cols = [col for col in frame.columns if col.startswith("meta_") and col.endswith("_available_date")]
        file_pit_bad = 0
        for col in meta_cols:
            meta_date = pd.to_datetime(frame[col], errors="coerce")
            bad = int((meta_date > date).sum())
            pit_violation_total += bad
            file_pit_bad += bad
            pit_rows.append({"year": year, "file": str(path), "meta_column": col, "nonnull": int(meta_date.notna().sum()), "bad_gt_date": bad})

        families = _family_columns(list(frame.columns))
        for family, cols in families.items():
            if not cols:
                coverage_rows.append({"year": year, "family": family, "columns": 0, "mean_nonnull_rate": 0.0, "max_nonnull_rate": 0.0})
            else:
                rates = frame[cols].notna().mean()
                coverage_rows.append(
                    {
                        "year": year,
                        "family": family,
                        "columns": len(cols),
                        "mean_nonnull_rate": float(rates.mean()),
                        "max_nonnull_rate": float(rates.max()),
                    }
                )
        forbidden_selector_prefix_hits += len([col for col in frame.columns if col.startswith("label_")])
        year_rows.append(
            {
                "year": year,
                "file": str(path),
                "rows": int(frame.shape[0]),
                "columns": int(frame.shape[1]),
                "duplicate_key_rows": dup,
                "key_null_rows": key_null,
                "pit_bad_meta_rows": file_pit_bad,
            }
        )

    _write_csv(report_root / "year_qa.csv", year_rows)
    _write_csv(report_root / "coverage_by_family_year.csv", coverage_rows)
    _write_csv(report_root / "pit_metadata_qa.csv", pit_rows)

    decision = "PASS_NONMINUTE_PIT_CONTEXT_PANEL_V1_QA"
    blocking: list[str] = []
    if duplicate_total:
        blocking.append("duplicate date-code keys")
    if key_null_total:
        blocking.append("null date/code keys")
    if pit_violation_total:
        blocking.append("metadata available_date later than panel date")
    if forbidden_selector_prefix_hits:
        blocking.append("label_ columns present")
    if blocking:
        decision = "FAIL_NONMINUTE_PIT_CONTEXT_PANEL_V1_QA"

    summary = {
        "decision": decision,
        "panel_root": str(panel_root),
        "report_root": str(report_root),
        "files": len(files),
        "total_rows": total_rows,
        "columns": len(all_columns),
        "duplicate_key_rows": duplicate_total,
        "key_null_rows": key_null_total,
        "pit_available_date_gt_panel_date_rows": pit_violation_total,
        "forbidden_label_prefix_columns": forbidden_selector_prefix_hits,
        "blocking": blocking,
        "outputs": {
            "year_qa": str(report_root / "year_qa.csv"),
            "coverage": str(report_root / "coverage_by_family_year.csv"),
            "pit_metadata_qa": str(report_root / "pit_metadata_qa.csv"),
            "json": str(report_root / "cn_nonminute_pit_context_panel_v1_qa.json"),
            "markdown": str(report_root / "CN_NONMINUTE_PIT_CONTEXT_PANEL_V1_QA_2026-06-02.md"),
        },
    }
    write_json_artifact(report_root / "cn_nonminute_pit_context_panel_v1_qa.json", summary)
    lines = [
        "# CN Non-1min PIT Context Panel v1 QA - 2026-06-02",
        "",
        f"decision: `{decision}`",
        f"total_rows: `{total_rows}`",
        f"columns: `{len(all_columns)}`",
        f"duplicate_key_rows: `{duplicate_total}`",
        f"key_null_rows: `{key_null_total}`",
        f"pit_available_date_gt_panel_date_rows: `{pit_violation_total}`",
        f"forbidden_label_prefix_columns: `{forbidden_selector_prefix_hits}`",
        "",
        "## Files",
        "",
    ]
    for row in year_rows:
        lines.append(f"- `{row['year']}` rows `{row['rows']}`, columns `{row['columns']}`, duplicate keys `{row['duplicate_key_rows']}`")
    if blocking:
        lines.extend(["", "## Blocking", ""])
        for item in blocking:
            lines.append(f"- {item}")
    (report_root / "CN_NONMINUTE_PIT_CONTEXT_PANEL_V1_QA_2026-06-02.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel-root", type=Path, default=DEFAULT_PANEL_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    args = parser.parse_args()
    summary = run(panel_root=args.panel_root, report_root=args.report_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(summary["decision"]).startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
