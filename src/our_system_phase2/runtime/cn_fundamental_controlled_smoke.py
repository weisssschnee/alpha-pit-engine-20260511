from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


DEFAULT_AGG_ROOT = Path(
    "G:/Project_V7_Rotation/data/cn_public_enrichment/"
    "cn_fundamental_akshare_batch_v1_20260531/aggregated_v1"
)
DEFAULT_OUTPUT_DIR = Path("reports/cn_fundamental_controlled_smoke_20260531")
DEFAULT_REGISTRY = Path("runtime/field_registry/cn_fundamental_field_registry_v1_20260531.json")

DATASET_POLICIES: dict[str, dict[str, Any]] = {
    "balance_sheet_report_em": {
        "kind": "financial_statement",
        "entity_key": "source_code6",
        "period_date": "REPORT_DATE",
        "notice_date": "NOTICE_DATE",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "profit_sheet_report_em": {
        "kind": "financial_statement",
        "entity_key": "source_code6",
        "period_date": "REPORT_DATE",
        "notice_date": "NOTICE_DATE",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "cash_flow_sheet_report_em": {
        "kind": "financial_statement",
        "entity_key": "source_code6",
        "period_date": "REPORT_DATE",
        "notice_date": "NOTICE_DATE",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "financial_analysis_indicator_sina": {
        "kind": "financial_ratio",
        "entity_key": "source_code6",
        "period_date": "日期",
        "notice_date": None,
        "use_status": "diagnostic_until_announcement_date_join",
    },
    "share_change_cninfo": {
        "kind": "share_structure",
        "entity_key": "source_code6",
        "period_date": "变动日期",
        "notice_date": "公告日期",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "dividend_cninfo": {
        "kind": "dividend_event",
        "entity_key": "source_code6",
        "period_date": "报告时间",
        "notice_date": "实施方案公告日期",
        "use_status": "hold_due_announcement_date_anomaly_check",
    },
    "main_stock_holder_sina": {
        "kind": "holder_structure",
        "entity_key": "source_code6",
        "period_date": "截至日期",
        "notice_date": "公告日期",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "circulate_stock_holder_sina": {
        "kind": "holder_structure",
        "entity_key": "source_code6",
        "period_date": "截止日期",
        "notice_date": "公告日期",
        "use_status": "pit_ready_with_notice_date_lag",
    },
    "zygc_em": {
        "kind": "business_composition",
        "entity_key": "source_code6",
        "period_date": "报告日期",
        "notice_date": None,
        "use_status": "diagnostic_until_announcement_date_join",
    },
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parquet_path(root: Path, dataset: str) -> Path:
    return root / dataset / f"{dataset}.parquet"


def _date_stats(frame: pd.DataFrame, column: str | None) -> dict[str, Any]:
    if not column or column not in frame.columns:
        return {"column": column, "present": False}
    values = pd.to_datetime(frame[column], errors="coerce")
    valid = values.dropna()
    anomaly = valid.lt(pd.Timestamp("1990-01-01")).sum()
    return {
        "column": column,
        "present": True,
        "valid_ratio": round(float(values.notna().mean()), 6),
        "min": str(valid.min().date()) if not valid.empty else None,
        "max": str(valid.max().date()) if not valid.empty else None,
        "pre_1990_count": int(anomaly),
    }


def _numeric_columns(frame: pd.DataFrame, columns: list[str], sample_size: int = 2000) -> list[str]:
    sample = frame.head(sample_size)
    out: list[str] = []
    for column in columns:
        if column.startswith("_") or column.lower() in {"source_em", "source_code6"}:
            continue
        values = pd.to_numeric(sample[column], errors="coerce")
        if values.notna().mean() >= 0.50:
            out.append(column)
    return out


def _field_rows(dataset: str, columns: list[str], numeric: set[str], policy: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    time_cols = {str(policy.get("period_date") or ""), str(policy.get("notice_date") or "")}
    for column in columns:
        rows.append(
            {
                "dataset": dataset,
                "field_name": column,
                "field_role": "entity_key" if column == policy.get("entity_key") else ("time_key" if column in time_cols else ("numeric_candidate" if column in numeric else "metadata")),
                "kind": policy.get("kind"),
                "use_status": policy.get("use_status"),
                "pit_policy": (
                    "use notice/announcement date, then next trading day availability"
                    if policy.get("notice_date")
                    else "no reliable announcement date; diagnostic or conservative lag only"
                ),
            }
        )
    return rows


def build_smoke(*, agg_root: Path, output_dir: Path, registry_path: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for dataset, policy in DATASET_POLICIES.items():
        path = _parquet_path(agg_root, dataset)
        if not path.exists():
            dataset_rows.append({"dataset": dataset, "status": "missing", "path": str(path)})
            status_counts["missing"] += 1
            continue
        pf = pq.ParquetFile(path)
        columns = list(pf.schema_arrow.names)
        head = pd.read_parquet(path).head(5000)
        full_key = policy["entity_key"] if policy["entity_key"] in head.columns else None
        symbols = int(head[full_key].astype(str).nunique()) if full_key else None
        numeric = set(_numeric_columns(head, columns))
        period_stats = _date_stats(head, policy.get("period_date"))
        notice_stats = _date_stats(head, policy.get("notice_date"))
        use_status = str(policy.get("use_status"))
        blocking: list[str] = []
        if policy.get("notice_date") and not notice_stats.get("present"):
            blocking.append("missing_notice_date")
        if notice_stats.get("pre_1990_count", 0):
            blocking.append("notice_date_pre_1990_anomaly")
        if "diagnostic" in use_status:
            blocking.append("no_reliable_announcement_date")
        if "hold" in use_status:
            blocking.append("requires_date_anomaly_resolution")
        dataset_rows.append(
            {
                "dataset": dataset,
                "status": "ok",
                "path": str(path),
                "kind": policy.get("kind"),
                "rows": int(pf.metadata.num_rows),
                "columns": int(len(columns)),
                "sample_symbols": symbols,
                "numeric_candidate_columns": int(len(numeric)),
                "period_date_column": policy.get("period_date"),
                "notice_date_column": policy.get("notice_date"),
                "period_valid_ratio": period_stats.get("valid_ratio"),
                "period_min": period_stats.get("min"),
                "period_max": period_stats.get("max"),
                "notice_valid_ratio": notice_stats.get("valid_ratio"),
                "notice_min": notice_stats.get("min"),
                "notice_max": notice_stats.get("max"),
                "notice_pre_1990_count_sample": notice_stats.get("pre_1990_count"),
                "use_status": use_status,
                "blocking_issues": "|".join(blocking),
            }
        )
        status_counts[use_status] += 1
        field_rows.extend(_field_rows(dataset, columns, numeric, policy))

    errors_path = agg_root / "error_manifest.csv"
    error_summary: dict[str, int] = {}
    if errors_path.exists():
        errors = pd.read_csv(errors_path)
        if "dataset" in errors.columns:
            error_summary = {str(key): int(value) for key, value in errors.groupby("dataset").size().sort_index().items()}

    payload = {
        "registry_id": "cn_fundamental_field_registry_v1_20260531",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_CN_FUNDAMENTAL_CONTROLLED_SMOKE_WITH_PIT_HOLDS",
        "agg_root": str(agg_root),
        "dataset_count": len(dataset_rows),
        "status_counts": dict(sorted(status_counts.items())),
        "error_summary": error_summary,
        "global_policy": {
            "financial_statement_use": "NOTICE_DATE <= signal_date_previous_session; available next trading day",
            "report_date_warning": "REPORT_DATE/日期/报告日期 is period date, not signal availability date",
            "dividend_warning": "1970 announcement dates block promotion until repaired",
            "holder_warning": "holder tables are usable only by announcement date and aggregate-level features",
            "scope": "top200 high-amount controlled smoke; not full-universe PIT proof",
        },
        "datasets": dataset_rows,
        "fields": field_rows,
    }
    _write_json(registry_path, payload)
    _write_json(output_dir / "cn_fundamental_controlled_smoke.json", payload)
    _write_csv(output_dir / "cn_fundamental_dataset_contract.csv", dataset_rows)
    _write_csv(output_dir / "cn_fundamental_field_contract.csv", field_rows)
    _write_markdown(output_dir / "CN_FUNDAMENTAL_CONTROLLED_SMOKE_2026-05-31.md", payload)
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# CN Fundamental Controlled Smoke",
        "",
        f"decision: `{payload['decision']}`",
        "",
        "## Dataset Status",
        "",
    ]
    for key, value in payload["status_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Key Policy", ""])
    for key, value in payload["global_policy"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Outputs", ""])
    lines.append("- cn_fundamental_controlled_smoke.json")
    lines.append("- cn_fundamental_dataset_contract.csv")
    lines.append("- cn_fundamental_field_contract.csv")
    lines.append(f"- registry: {DEFAULT_REGISTRY}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agg-root", type=Path, default=DEFAULT_AGG_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--registry-path", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()
    payload = build_smoke(agg_root=args.agg_root, output_dir=args.output_dir, registry_path=args.registry_path)
    print(json.dumps({"decision": payload["decision"], "status_counts": payload["status_counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
