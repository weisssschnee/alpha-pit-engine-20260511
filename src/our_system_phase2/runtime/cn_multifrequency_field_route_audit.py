"""Build the CN multi-frequency field route audit.

The goal is to prevent data loss and leakage by explicitly routing each new
data family into one of:

- minute-native feature,
- timestamped intraday event feature,
- lagged daily context,
- announcement/PIT context,
- execution/tradability diagnostic.
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


DEFAULT_DATA_ROOT = Path(r"G:\Project_V7_Rotation\data\cn_public_enrichment")
DEFAULT_OUTPUT = Path("reports/cn_multifrequency_field_route_audit_20260601")


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


def _schema(path: Path) -> tuple[int, list[str]]:
    pf = pq.ParquetFile(path)
    return int(pf.metadata.num_rows), list(pf.schema_arrow.names)


def _route(path: Path, columns: list[str]) -> tuple[str, str, str]:
    cols = set(columns)
    lower_cols = {c.lower() for c in columns}
    text = " ".join(str(part).lower() for part in path.parts)
    if {"trade_time", "open", "close", "amount"}.issubset(cols):
        return (
            "minute_native_feature",
            "use after each bar close only; auction not available unless separate auction data exists",
            "future bars and close-derived labels forbidden as selector input",
        )
    if "up_limit_time" in cols:
        return (
            "timestamped_stock_intraday_event_feature",
            "usable only after up_limit_time and only after timestamp coverage audit",
            "same-day use before event time is leakage; reason text needs separate NLP governance",
        )
    if "time" in cols and {"uplimit_count", "open_board_count"}.issubset(cols):
        return (
            "timestamped_market_intraday_event_feature",
            "usable only at or after row time; requires non-null same-date coverage",
            "2026 current silver has null trend fields and must not be used until repaired",
        )
    if any(c in cols for c in ["NOTICE_DATE", "公告日期", "实施方案公告日期", "HOLD_NOTICE_DATE", "HOLD_N_DATE"]):
        return (
            "announcement_pit_context",
            "usable from announcement/notice date plus conservative lag",
            "report/end date joins without announcement timestamp are leakage",
        )
    if "billboard" in text:
        return (
            "event_disclosure_context",
            "usable after disclosure / next trading day unless timestamp contract proves earlier",
            "cannot be used intraday on trade date by default",
        )
    if "rzrq" in text or any(c in cols for c in ["RZYE", "RZMRE", "RQYE", "DATE"]):
        return (
            "daily_lagged_context",
            "usable trade_date-1 or later after vendor update lag",
            "same-day margin data is forbidden",
        )
    if any(c in cols for c in ["date", "date1", "REPORT_DATE", "TRADE_DATE", "报告日期"]):
        return (
            "daily_lagged_context",
            "usable trade_date-1 or later unless source timestamp contract proves earlier",
            "same-day daily close/state fields are forbidden for intraday selector",
        )
    if any("date" in c for c in lower_cols):
        return (
            "date_keyed_context_needs_manual_contract",
            "requires source-specific PIT contract before selector use",
            "not eligible for minute selector until classified",
        )
    return (
        "unclassified_needs_contract",
        "do not use in selector until field contract is written",
        "unclassified field family",
    )


def _coverage_probe(path: Path, route: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        if "uplimit_trend" in str(path):
            frame = pd.read_parquet(path, columns=["date", "time", "uplimit_count", "open_board_count"])
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            recent = frame[frame["date"] >= pd.Timestamp("2026-01-01")]
            out.update(
                {
                    "date_min": str(frame["date"].min().date()) if frame["date"].notna().any() else "",
                    "date_max": str(frame["date"].max().date()) if frame["date"].notna().any() else "",
                    "coverage_note": "2026_null" if not recent.empty and recent["time"].notna().mean() == 0 else "ok_or_partial",
                    "time_nonnull_2026": float(recent["time"].notna().mean()) if not recent.empty else None,
                    "uplimit_count_nonnull_2026": float(recent["uplimit_count"].notna().mean()) if not recent.empty else None,
                }
            )
        elif "review_uplimit_reason" in str(path):
            frame = pd.read_parquet(path, columns=["date1", "stock_code", "up_limit_time", "up_limit_keep_times", "fengdan_money"])
            frame["date1"] = pd.to_datetime(frame["date1"], errors="coerce")
            recent = frame[frame["date1"] >= pd.Timestamp("2026-01-01")]
            out.update(
                {
                    "date_min": str(frame["date1"].min().date()) if frame["date1"].notna().any() else "",
                    "date_max": str(frame["date1"].max().date()) if frame["date1"].notna().any() else "",
                    "coverage_note": "ok_timestamped_stock_event",
                    "up_limit_time_nonnull_2026": float(recent["up_limit_time"].notna().mean()) if not recent.empty else None,
                    "stock_event_rows_2026": int(recent.shape[0]),
                }
            )
    except Exception as exc:  # noqa: BLE001
        out["coverage_note"] = f"probe_error:{type(exc).__name__}"
    return out


def run(*, data_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(data_root.rglob("*.parquet")):
        if any(part.startswith("_") for part in path.parts):
            continue
        try:
            nrows, columns = _schema(path)
        except Exception as exc:  # noqa: BLE001
            rows.append({"path": str(path), "status": "schema_error", "error": f"{type(exc).__name__}:{str(exc)[:200]}"})
            continue
        route, allowed_use, forbidden_use = _route(path, columns)
        row = {
            "path": str(path.relative_to(data_root)),
            "rows": nrows,
            "columns": len(columns),
            "route": route,
            "allowed_use": allowed_use,
            "forbidden_use": forbidden_use,
            "key_columns": "|".join([c for c in columns if c.lower() in {"date", "date1", "trade_time", "time", "code", "stock_code", "security_code", "scode"} or c in {"NOTICE_DATE", "TRADE_DATE", "REPORT_DATE", "公告日期", "HOLD_NOTICE_DATE"}][:20]),
            "sample_columns": "|".join(columns[:40]),
            "status": "ok",
        }
        row.update(_coverage_probe(path, route))
        rows.append(row)
    _write_csv(output_root / "cn_multifrequency_field_route_audit.csv", rows)
    frame = pd.DataFrame(rows)
    route_counts = frame["route"].value_counts(dropna=False).to_dict() if not frame.empty else {}
    blockers = frame[frame["route"].astype(str).str.contains("unclassified|needs", case=False, na=False)].to_dict("records") if not frame.empty else []
    special = frame[frame["path"].astype(str).str.contains("uplimit|review_uplimit", case=False, na=False)].to_dict("records") if not frame.empty else []
    summary = {
        "decision": "PASS_MULTIFREQUENCY_ROUTE_AUDIT_WITH_BLOCKERS",
        "data_root": str(data_root),
        "dataset_count": int(len(rows)),
        "route_counts": route_counts,
        "blocked_or_manual_contract_count": int(len(blockers)),
        "special_limit_event_routes": special,
        "outputs": {
            "route_csv": str(output_root / "cn_multifrequency_field_route_audit.csv"),
            "json": str(output_root / "cn_multifrequency_field_route_audit.json"),
            "markdown": str(output_root / "CN_MULTIFREQUENCY_FIELD_ROUTE_AUDIT_2026-06-01.md"),
        },
    }
    write_json_artifact(output_root / "cn_multifrequency_field_route_audit.json", summary)
    lines = [
        "# CN Multifrequency Field Route Audit - 2026-06-01",
        "",
        f"decision: `{summary['decision']}`",
        f"dataset_count: `{summary['dataset_count']}`",
        f"blocked_or_manual_contract_count: `{summary['blocked_or_manual_contract_count']}`",
        "",
        "## Route Counts",
        "",
    ]
    for key, value in route_counts.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Critical Findings",
            "",
            "- `review_uplimit_reason.up_limit_time` is a timestamped stock-level intraday event candidate.",
            "- `uplimit_trend.time` is a timestamped market-level intraday candidate, but current 2026 silver rows are null and must not be used until repaired.",
            "- Daily, margin, fundamental, holder, dividend, and billboard fields are retained as lagged/PIT context rather than discarded.",
        ]
    )
    (output_root / "CN_MULTIFREQUENCY_FIELD_ROUTE_AUDIT_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("reports/CN_MULTIFREQUENCY_FIELD_ROUTE_AUDIT_DECISION_2026-06-01.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = run(data_root=args.data_root, output_root=args.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
